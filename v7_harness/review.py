"""U38: an independent, read-only review of a pilot bundle by Claude Code (`pilot review`). docs/40 §2-2.

The review is evidence for the judge, never a verdict. On one OS account every actor name can be forged (B83), so
a reviewer's PASS cannot stand in for Codex's or the user's approval; it is written with "advisory": true. A reviewer
never reviews its own worker's bundle, and it runs under the same budget gate as a paid worker (B85).
"""

from __future__ import annotations

import difflib
import json
import re
import subprocess
import time
from pathlib import Path
from typing import Any

REVIEWERS = ("claude",)
SCHEMA_HINT = ('{"verdict": "PASS" or "REWORK", "counterexamples": ["..."], '
               '"evidence_lines": ["path:line quote", "..."]}')
MAX_DIFF_CHARS = 60_000


class ReviewRefused(Exception):
    pass


def bundle_diff(source: Path, staging: Path, changed: list[str]) -> str:
    parts = []
    for rel in changed:
        before = (source / rel).read_text(encoding="utf-8", errors="replace").splitlines(True) if (source / rel).is_file() else []
        after = (staging / rel).read_text(encoding="utf-8", errors="replace").splitlines(True) if (staging / rel).is_file() else []
        parts.extend(difflib.unified_diff(before, after, f"a/{rel}", f"b/{rel}"))
    return "".join(parts)


def review_prompt(task_id: str, manual_text: str, diff: str) -> str:
    return (f"[{task_id}] Review this change against its contract. Read files in the current directory if needed.\n\n"
            f"## Contract\n{manual_text}\n\n## Diff\n```diff\n{diff[:MAX_DIFF_CHARS]}\n```\n\n"
            f"Reply with exactly one JSON object: {SCHEMA_HINT}")


def parse_verdict(text: str) -> dict[str, Any] | None:
    match = re.search(r"\{.*\}", text or "", re.S)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict) or data.get("verdict") not in ("PASS", "REWORK"):
        return None
    return {"verdict": data["verdict"],
            "counterexamples": [str(x)[:500] for x in data.get("counterexamples") or []][:20],
            "evidence_lines": [str(x)[:300] for x in data.get("evidence_lines") or []][:40]}


def run_review(*, task_id: str, work_dir: Path, source: Path, manual_text: str, reviewer: str, budget: int,
               model: str | None = None, timeout_s: int = 600, runner: Any = subprocess.run) -> dict[str, Any]:
    from .adapters.claude_worker import DEFAULT_MODEL, review_command, usage_from, worker_env
    from .pilot import evaluate_cost_gate

    if reviewer not in REVIEWERS:
        raise ReviewRefused(f"UNKNOWN_REVIEWER:{reviewer}")
    if budget <= 0:
        raise ReviewRefused("REVIEW_WITHOUT_BUDGET: pass --budget > 0 (a review is a paid call)")
    runs = Path(work_dir) / "runs" / task_id
    try:
        summary = json.loads((runs / "summary.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReviewRefused(f"NO_PILOT_SUMMARY:{runs / 'summary.json'} ({type(exc).__name__})") from exc
    try:
        author = (runs / "worker").read_text(encoding="utf-8").strip()
    except OSError:
        author = ""
    if not author:
        # Fail closed: without the author the rule "never review your own worker's bundle" cannot be checked.
        raise ReviewRefused(f"AUTHOR_UNKNOWN: {runs / 'worker'} is missing (bundle built before U38?)")
    if author == reviewer:
        raise ReviewRefused(f"REVIEWER_IS_AUTHOR:{reviewer} wrote this bundle")
    staging = Path(summary.get("agy_workspace") or "")
    changed = [str(x) for x in summary.get("changed_files") or []]
    if not changed or not staging.is_dir():
        raise ReviewRefused("NOTHING_TO_REVIEW: no changed files or no staged copy")

    prompt = review_prompt(task_id, manual_text, bundle_diff(Path(source), staging, changed))
    started = time.monotonic()
    usage: dict[str, int] = {}
    error = ""
    verdict = None
    try:
        done = runner(review_command(prompt, model or DEFAULT_MODEL), cwd=str(staging), env=worker_env(),
                      capture_output=True, timeout=timeout_s)
        result = json.loads(done.stdout.decode("utf-8", errors="replace"))
        if isinstance(result, dict):
            usage = usage_from(result)
            verdict = parse_verdict(str(result.get("result") or ""))
            if verdict is None:
                error = "REVIEW_UNPARSED: the reviewer did not return the JSON verdict"
        else:
            error = "REVIEW_NOT_JSON_OBJECT"
    except subprocess.TimeoutExpired:
        error = f"REVIEW_TIMEOUT:{timeout_s}s"
    except (OSError, ValueError) as exc:
        error = f"REVIEW_FAILED:{type(exc).__name__}: {exc}"[:300]
    cost_gate = evaluate_cost_gate(usage, budget)
    record = {
        "task_id": task_id, "reviewer": reviewer, "author_worker": author, "bundle_id": summary.get("bundle_id"),
        # Evidence for the judge, not a verdict (B83): the judge still approves or rejects the bundle.
        "advisory": True,
        "verdict": verdict["verdict"] if verdict and cost_gate == "WITHIN" else "UNUSABLE",
        "counterexamples": (verdict or {}).get("counterexamples", []),
        "evidence_lines": (verdict or {}).get("evidence_lines", []),
        "cost_gate": cost_gate, "usage": usage, "elapsed_s": int(time.monotonic() - started), "error": error,
    }
    out = runs / f"review_{reviewer}.json"
    out.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    record["review_path"] = str(out)
    _record_usage(Path(source), task_id, reviewer, model or DEFAULT_MODEL, usage, record, out)
    return record


def _record_usage(source: Path, task_id: str, reviewer: str, model: str, usage: dict[str, int], record: dict,
                  receipt: Path) -> None:
    """A review is a paid call; it goes in the ledger as kind "review" (RSI windows read kind "pilot" only)."""
    if not ((source / ".git").is_dir() or (source / ".coord" / "PLAN.md").is_file()):
        return
    from .coord.usage_ledger import record_usage

    entry = {
        "schema": "uaos-usage-v2", "work_id": f"{task_id}-review-{reviewer}", "actor": reviewer, "model": model,
        "kind": "review", "collection_mode": "automatic",
        "input_tokens": usage.get("input_tokens"), "output_tokens": usage.get("output_tokens"),
        "wall_time_s": None, "outcome": record["verdict"], "receipt": str(receipt), "independent_verifier": None,
        "rsi_eligible": False, "exclusion_reason": "ADVISORY_REVIEW", "worker": reviewer, "cost_gate": record["cost_gate"],
    }
    for extra in ("cache_creation_input_tokens", "cache_read_input_tokens", "cost_microusd"):
        if extra in usage:
            entry[extra] = usage[extra]
    try:
        record_usage(source, entry)
    except Exception as exc:  # noqa: BLE001 - the review file is the receipt; the ledger is best effort
        record["usage_ledger_error"] = f"{type(exc).__name__}: {exc}"[:200]
