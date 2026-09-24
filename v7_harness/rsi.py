"""Evidence-gated self-improvement (RSI) for UAOS: observe → propose → try → gate → judge → (rollback).

The loop proposes; it never adopts itself. Why it stops short of self-adoption (docs/38):
- Self-improving agents game their evaluators: the Darwin Gödel Machine removed its own hallucination-detection markers,
  METR saw o3 patch a scorer and a timer, STOP disabled its sandbox flag "for efficiency".
- Without external feedback, self-correction does not reliably help (Huang et al., ICLR 2024), and LLM judges prefer
  their own outputs (self-preference bias).
- A poisoned evaluation set keeps contaminating later generations of a self-modifying agent (Roesner & Kohno 2026).
So every candidate is judged on executed evidence read from this project's own ledger (never on numbers the author
types in), by a verifier other than its author, without touching the evaluators or the evidence, and a judge who is
neither the author nor the verifier makes the final call. Adopted policy changes keep the previous value for rollback.

What may evolve: the knobs in `.coord/rsi/policy.json` (only toward stricter values), manual templates, task cards and
docs. Code and evaluators change only through the normal reviewed path (PLAN card → pilot → judge), never through here.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import statistics
import time
from collections import Counter
from pathlib import Path
from typing import Any

POLICY_PATH = Path(".coord") / "rsi" / "policy.json"
DECISIONS_PATH = Path(".coord") / "rsi" / "decisions.jsonl"
LEDGER_PATH = Path(".coord") / "usage" / "runs.jsonl"

DEFAULT_POLICY: dict[str, Any] = {
    # docs/24·docs/30: a local model gets a manual that scores at least 80 for concreteness.
    "local_min_specificity": 80,
    "remote_min_specificity": 60,
    # docs/27·docs/31: analyze after 10 comparable samples; below 3 nothing is concluded.
    "window": 10,
    "min_samples": 3,
    # docs/27 §4: a run that costs more than 3x the previous comparable run fails the cost gate.
    "max_cost_ratio": 3.0,
}
# The documented values are floors (or a ceiling for the cost ratio). A policy may only get stricter: a loop that could
# lower min_samples to 1 or raise the cost ratio to 100 would be grading its own homework.
POLICY_BOUNDS: dict[str, tuple[float, float]] = {
    "local_min_specificity": (80, 100),
    "remote_min_specificity": (60, 100),
    "window": (10, 100),
    "min_samples": (3, 50),
    "max_cost_ratio": (1.0, 3.0),
}

# Things the gate never lets the loop change: the evaluators, the evidence and the loop itself.
EVALUATOR_PATTERNS = (
    "tests/*",
    ".githooks/*",
    ".coord/runs/run_regression.py",
    ".coord/usage/*",
    str(DECISIONS_PATH.as_posix()),
    "v7_harness/rsi.py",
    "v7_harness/manual.py",
    "v7_harness/calculator_gate.py",
    "v7_harness/olla_evidence.py",
    "v7_harness/accept_triage.py",
    "v7_harness/adapters/ollama_worker.py",
    "v7_harness/isolation/*",
)
# Things the loop may change (through the gate and the judge). fnmatch's `*` also crosses `/`.
RSI_TARGET_PATTERNS = (POLICY_PATH.as_posix(), ".coord/tasks/*", "docs/*")

# docs/31 §3: Antigravity may verify someone else's change; the final call is Codex's (Claude while Codex is absent).
VERIFIERS = ("codex", "claude", "antigravity")
JUDGES = ("codex", "claude", "user")

# Deterministic remedies per failure cause. Adding a remedy is a reviewed code change, not something the loop does.
REMEDIES: dict[str, tuple[str, str]] = {
    "UNREQUESTED_DELETION": ("manual_template", "Ask for ===EDIT blocks, quote the SEARCH text, add the tests that import the file to acceptance; if the code is already known use worker: apply"),
    "SYNTAX_ERROR": ("manual_template", "Split the task per file and quote the exact SEARCH text; for dictated code use worker: apply"),
    "SCOPE_VIOLATION": ("manual_template", "Name the exact file in the goal and keep allow to that file"),
    "EDIT_SEARCH_NOT_FOUND": ("manual_template", "Copy the SEARCH lines verbatim from the pinned input into the manual"),
    "EDIT_SEARCH_AMBIGUOUS": ("manual_template", "Extend the SEARCH text until it is unique"),
    "PROMPT_TOO_LARGE": ("manual_template", "Split the input or summarise it first (olla read map); keep one file per manual"),
    "NO_CHANGES": ("manual_template", "State one concrete verb and the exact file; read-only tasks need --allow-no-changes"),
    "PROVIDER_ERROR": ("environment", "Check that the Ollama service and model are up; do not escalate to a paid worker automatically"),
    "EXECUTION_ERROR": ("environment", "Check the worker command and the Ollama service before retrying"),
    "TIMEOUT": ("manual_template", "Split the task or raise timeout_s in the contract; reconcile the run first"),
    "ACCEPT_INFRA": ("environment", "Fix the environment (interpreter, PYTHONPATH, missing tool) before retrying; the worker is not at fault"),
    "ACCEPT_NOT_RUN": ("environment", "Make the acceptance command runnable in the staging directory"),
    "SOURCE_DIVERGED": ("environment", "Keep a single writer during pilot runs (QUIET_LOCK); retry after the other writer finishes"),
}


class RsiRefused(Exception):
    """An adoption or rollback that the rules do not allow."""


# ---------------------------------------------------------------- policy


def policy_violations(values: dict[str, Any]) -> list[str]:
    """Keys that are unknown, not numbers, or outside the bounds (weaker than the documented floors)."""
    problems: list[str] = []
    for key, value in values.items():
        if key not in POLICY_BOUNDS:
            problems.append(f"POLICY_UNKNOWN_KEY:{key}")
            continue
        low, high = POLICY_BOUNDS[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            problems.append(f"POLICY_NOT_A_NUMBER:{key}")
        elif not low <= value <= high:
            problems.append(f"POLICY_OUT_OF_BOUNDS:{key}={value} (allowed {low}..{high}; the floors are the documented values)")
    if isinstance(values.get("min_samples"), (int, float)) and isinstance(values.get("window"), (int, float)):
        if values["min_samples"] > values["window"]:
            problems.append("POLICY_INCONSISTENT:min_samples>window")
    return problems


def load_policy(project: Path) -> dict[str, Any]:
    """The documented defaults, overridden by `.coord/rsi/policy.json` only where the stored value is within bounds."""
    policy = dict(DEFAULT_POLICY)
    path = Path(project) / POLICY_PATH
    try:
        stored = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return policy
    if not isinstance(stored, dict):
        return policy
    for key in DEFAULT_POLICY:
        if key in stored and not policy_violations({key: stored[key]}):
            policy[key] = stored[key]
    if policy["min_samples"] > policy["window"]:
        policy["min_samples"], policy["window"] = DEFAULT_POLICY["min_samples"], DEFAULT_POLICY["window"]
    return policy


# ---------------------------------------------------------------- observe


def load_rows(project: Path) -> list[dict[str, Any]]:
    """Pilot rows of the project's usage ledger, oldest first. Unreadable lines are counted, never silently dropped."""
    path = Path(project) / LEDGER_PATH
    rows: list[dict[str, Any]] = []
    if not path.is_file():
        return rows
    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")
    # A last line without its newline is still being appended by a pilot (the sentinel reads without the ledger
    # lock); it is read on the next cycle instead of being counted as unreadable.
    for line in lines[:-1] if not text.endswith("\n") else lines:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            rows.append({"kind": "pilot", "outcome": "UNREADABLE", "worker": "unknown"})
            continue
        if isinstance(row, dict) and row.get("kind") == "pilot":
            rows.append(row)
    rows.sort(key=_ts)
    return rows


def _ts(row: dict[str, Any]) -> float:
    ts = row.get("ts")
    return float(ts) if isinstance(ts, (int, float)) and not isinstance(ts, bool) else 0.0


def _cause(row: dict[str, Any]) -> str | None:
    if row.get("outcome") == "PASS":
        return None
    error_class = row.get("error_class")
    if error_class and error_class != "NONE":
        return str(error_class)
    detail = str(row.get("error_detail") or "")
    for known in REMEDIES:
        if known in detail:
            return known
    return str(row.get("rework_class") or row.get("outcome") or "UNKNOWN")


def metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(rows)
    outcomes = Counter(str(row.get("outcome")) for row in rows)
    tokens = [
        row["input_tokens"] for row in rows
        if isinstance(row.get("input_tokens"), int) and not isinstance(row.get("input_tokens"), bool)
    ]
    return {
        "n": n,
        "pass_rate": round(outcomes["PASS"] / n, 3) if n else None,
        "rework_rate": round(outcomes["REWORK"] / n, 3) if n else None,
        "blocked_rate": round(outcomes["BLOCKED"] / n, 3) if n else None,
        "median_input_tokens": statistics.median(tokens) if tokens else None,
    }


def analyze(rows: list[dict[str, Any]], policy: dict[str, Any] | None = None) -> dict[str, Any]:
    policy = policy or DEFAULT_POLICY
    window = int(policy["window"])
    by_worker: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_worker.setdefault(str(row.get("worker") or "unknown"), []).append(row)
    workers: dict[str, Any] = {}
    for worker, worker_rows in sorted(by_worker.items()):
        recent = worker_rows[-window:]
        causes = Counter(cause for cause in (_cause(row) for row in recent) if cause)
        info = metrics(recent)
        if info["n"] < int(policy["min_samples"]):
            status = "INSUFFICIENT_SAMPLES"
        elif info["n"] < window:
            status = "PARTIAL_WINDOW"
        else:
            status = "WINDOW_READY"
        workers[worker] = {
            **info,
            "total": len(worker_rows),
            "status": status,
            "causes": causes.most_common(),
            # docs rule: the same cause twice means change the route, not retry longer.
            "recurring": sorted(cause for cause, count in causes.items() if count >= 2),
            "recent_work_ids": [row.get("work_id") for row in recent][-5:],
        }
    total = len(rows)
    return {
        "samples": total,
        "window": window,
        "dictation_share": round(len(by_worker.get("apply", [])) / total, 3) if total else None,
        "workers": workers,
        "note": "Account savings stay UNMEASURED without before/after usage snapshots (docs/27).",
    }


# ---------------------------------------------------------------- propose


def propose(analysis: dict[str, Any], policy: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Deterministic proposals from the analysis. A proposal is a hypothesis for the judge, not a change."""
    policy = policy or DEFAULT_POLICY
    proposals: list[dict[str, Any]] = []
    for worker, info in analysis["workers"].items():
        if info["status"] == "INSUFFICIENT_SAMPLES":
            continue
        for cause, count in info["causes"]:
            target, action = REMEDIES.get(cause, ("review", f"No remedy on file for {cause}; the judge reviews the receipts"))
            proposals.append({
                "worker": worker,
                "cause": cause,
                "count": count,
                "recurring": cause in info["recurring"],
                "target": target,
                "action": action,
                "evidence": info["recent_work_ids"],
            })
        if (
            worker in ("local", "ollama")
            and info["status"] == "WINDOW_READY"
            and info["rework_rate"] is not None
            and info["rework_rate"] > 0.5
        ):
            current = int(policy["local_min_specificity"])
            raised = min(current + 5, int(POLICY_BOUNDS["local_min_specificity"][1]))
            proposals.append({
                "worker": worker,
                "cause": "HIGH_REWORK_RATE",
                "count": info["n"],
                "recurring": True,
                "target": "policy",
                "action": (f"Raise local_min_specificity from {current} to {raised} in {POLICY_PATH.as_posix()}, "
                           "or route this task family to worker: apply / agy"),
                "policy": {"local_min_specificity": raised},
                "evidence": info["recent_work_ids"],
            })
    for proposal in proposals:
        key = f"{proposal['worker']}|{proposal['cause']}|{proposal['target']}"
        proposal["id"] = "rsi_" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]
    proposals.sort(key=lambda p: (not p["recurring"], -p["count"], p["id"]))
    return proposals


def candidate_template(proposal: dict[str, Any], author: str) -> dict[str, Any]:
    """A candidate file to fill after the trial runs. The metrics are computed from the ledger, never typed in."""
    return {
        "id": proposal["id"],
        "author": author,
        "verifier": "<codex|claude|antigravity, not the author>",
        "hypothesis": f"{proposal['action']} (cause {proposal['cause']} on worker {proposal['worker']})",
        "changed_paths": [POLICY_PATH.as_posix()] if proposal.get("policy") else ["<.coord/tasks/... or docs/...>"],
        "policy": proposal.get("policy", {}),
        "before_work_ids": list(proposal.get("evidence") or []),
        "after_work_ids": ["<work_ids of the trial runs, at least min_samples>"],
    }


# ---------------------------------------------------------------- gate


def _matches(path: str, patterns: tuple[str, ...]) -> bool:
    normalized = path.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return any(fnmatch.fnmatch(normalized, pattern) for pattern in patterns)


def gate(candidate: dict[str, Any], policy: dict[str, Any] | None = None) -> dict[str, Any]:
    """Decide from metrics whether a tried change may go to the judge. Use gate_from_ledger for real candidates.

    candidate = {"id", "author", "verifier", "changed_paths": [...], "policy": {optional new knob values},
                 "before": {n, pass_rate, rework_rate, blocked_rate, median_input_tokens}, "after": {same keys}}
    """
    policy = policy or DEFAULT_POLICY
    reasons: list[str] = []
    paths = [str(path) for path in candidate.get("changed_paths") or []]
    if not paths:
        reasons.append("NO_CHANGE_LISTED")
    touched = [path for path in paths if _matches(path, EVALUATOR_PATTERNS)]
    if touched:
        reasons.append("EVALUATOR_TOUCHED:" + ",".join(touched[:5]))
    outside = [path for path in paths if path not in touched and not _matches(path, RSI_TARGET_PATTERNS)]
    if outside:
        reasons.append("OUT_OF_RSI_SCOPE:" + ",".join(outside[:5]) + " (use the reviewed PLAN/pilot path)")
    proposed = candidate.get("policy") or {}
    if not isinstance(proposed, dict):
        reasons.append("POLICY_NOT_AN_OBJECT")
    else:
        reasons.extend(policy_violations({**policy, **proposed}))
        if proposed and POLICY_PATH.as_posix() not in [p.replace("\\", "/").removeprefix("./") for p in paths]:
            reasons.append(f"POLICY_CHANGE_NOT_LISTED:{POLICY_PATH.as_posix()}")

    author = str(candidate.get("author") or "").lower()
    verifier = str(candidate.get("verifier") or "").lower()
    if verifier not in VERIFIERS or verifier == author:
        reasons.append(f"SELF_OR_INVALID_VERIFIER:{verifier or 'none'} (author {author or 'unknown'})")

    before = candidate.get("before") or {}
    after = candidate.get("after") or {}
    minimum = int(policy["min_samples"])
    if (before.get("n") or 0) < minimum or (after.get("n") or 0) < minimum:
        reasons.append(f"INSUFFICIENT_SAMPLES:before={before.get('n', 0)},after={after.get('n', 0)},min={minimum}")
    else:
        # Several metrics at once: optimizing one number while another gets worse is how gaming shows up (Goodhart).
        if (after.get("pass_rate") or 0) < (before.get("pass_rate") or 0):
            reasons.append(f"REGRESSION:pass_rate {before.get('pass_rate')}→{after.get('pass_rate')}")
        for rate in ("rework_rate", "blocked_rate"):
            if (after.get(rate) or 0) > (before.get(rate) or 0):
                reasons.append(f"REGRESSION:{rate} {before.get(rate)}→{after.get(rate)}")
        before_tokens, after_tokens = before.get("median_input_tokens"), after.get("median_input_tokens")
        if before_tokens and after_tokens and after_tokens > float(policy["max_cost_ratio"]) * before_tokens:
            reasons.append(f"COST_REGRESSION:{before_tokens}→{after_tokens}")
        improved = (
            (after.get("pass_rate") or 0) > (before.get("pass_rate") or 0)
            or (after.get("rework_rate") or 0) < (before.get("rework_rate") or 0)
            or (before_tokens and after_tokens and after_tokens < before_tokens)
        )
        if not improved and not any(reason.startswith("REGRESSION") for reason in reasons):
            reasons.append("NO_GAIN")
    return {
        "id": candidate.get("id"),
        "decision": "REJECT" if reasons else "ADOPT_CANDIDATE",
        "reasons": reasons,
        "before": before,
        "after": after,
        "next": ("a judge who is neither the author nor the verifier runs `rsi adopt`; adoption is never automatic"
                 if not reasons else "keep the current policy"),
    }


def gate_from_ledger(project: Path, candidate: dict[str, Any], policy: dict[str, Any] | None = None) -> dict[str, Any]:
    """The gate on executed evidence: before/after metrics are recomputed from the ledger rows named by work_id."""
    policy = policy or load_policy(project)
    reasons: list[str] = []
    if "before" in candidate or "after" in candidate:
        reasons.append("SELF_REPORTED_METRICS: name before_work_ids/after_work_ids; the gate reads the ledger itself")
    before_ids = [str(i) for i in candidate.get("before_work_ids") or []]
    after_ids = [str(i) for i in candidate.get("after_work_ids") or []]
    overlap = sorted(set(before_ids) & set(after_ids))
    if overlap:
        reasons.append("OVERLAPPING_SAMPLES:" + ",".join(overlap[:5]))
    rows = load_rows(project)
    known = {str(row.get("work_id")) for row in rows}
    missing = [work_id for work_id in before_ids + after_ids if work_id not in known]
    if missing:
        reasons.append("EVIDENCE_NOT_IN_LEDGER:" + ",".join(missing[:5]))
    before_rows = [row for row in rows if str(row.get("work_id")) in set(before_ids)]
    after_rows = [row for row in rows if str(row.get("work_id")) in set(after_ids)]
    before_workers = {str(row.get("worker")) for row in before_rows}
    after_workers = {str(row.get("worker")) for row in after_rows}
    if before_rows and after_rows and before_workers != after_workers:
        reasons.append(f"NOT_COMPARABLE:workers {sorted(before_workers)} vs {sorted(after_workers)}")
    measured = {key: value for key, value in candidate.items() if key not in ("before", "after")}
    result = gate({**measured, "before": metrics(before_rows), "after": metrics(after_rows)}, policy)
    result["reasons"] = reasons + result["reasons"]
    result["decision"] = "REJECT" if result["reasons"] else "ADOPT_CANDIDATE"
    if result["reasons"]:
        result["next"] = "keep the current policy"
    return result


# ---------------------------------------------------------------- judge, record, rollback


def read_decisions(project: Path) -> list[dict[str, Any]]:
    path = Path(project) / DECISIONS_PATH
    if not path.is_file():
        return []
    decisions = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            decisions.append(item)
    return decisions


def record_decision(project: Path, decision: dict[str, Any]) -> Path:
    path = Path(project) / DECISIONS_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), **decision}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
    return path


def _write_policy(project: Path, values: dict[str, Any]) -> None:
    path = Path(project) / POLICY_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(values, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def adopt(project: Path, candidate: dict[str, Any], judge: str) -> dict[str, Any]:
    """The judge's call. Re-runs the ledger gate, applies a policy change (keeping the previous value) and records it.

    Manual-template and docs changes are recorded here but land through a normal reviewed commit.
    """
    judge = judge.lower()
    author = str(candidate.get("author") or "").lower()
    verifier = str(candidate.get("verifier") or "").lower()
    if judge not in JUDGES:
        raise RsiRefused(f"JUDGE_NOT_ALLOWED:{judge}")
    if judge != "user" and judge in (author, verifier):
        raise RsiRefused(f"JUDGE_NOT_INDEPENDENT:{judge} is the author or the verifier")
    verdict = gate_from_ledger(project, candidate)
    if verdict["decision"] != "ADOPT_CANDIDATE":
        record_decision(project, {"action": "REJECTED", "id": candidate.get("id"), "judge": judge,
                                  "author": author, "verifier": verifier, "reasons": verdict["reasons"]})
        raise RsiRefused("GATE_REJECTED:" + "; ".join(verdict["reasons"][:3]))
    # docs/31 §4: one change at a time, re-checked over the next window, so an effect can be attributed to it.
    rows_now = len(load_rows(project))
    for pending in open_trials(project, rows_now):
        if not pending["due"]:
            raise RsiRefused(f"ONE_CHANGE_PER_WINDOW:{pending['id']} is on trial until ledger row {pending['recheck_at_rows']}"
                             f" (now {rows_now})")
    previous = load_policy(project)
    proposed = candidate.get("policy") or {}
    if proposed:
        _write_policy(project, {**previous, **proposed})
    record_decision(project, {
        "action": "ADOPTED", "id": candidate.get("id"), "judge": judge, "author": author, "verifier": verifier,
        "changed_paths": candidate.get("changed_paths"), "policy": proposed, "previous_policy": previous,
        "before": verdict["before"], "after": verdict["after"],
        "hypothesis": str(candidate.get("hypothesis") or "")[:300],
        "recheck_at_rows": rows_now + int(previous["window"]),
    })
    return {"adopted": candidate.get("id"), "policy_written": bool(proposed), "policy": load_policy(project),
            "next": "commit .coord/rsi/ with the change; re-measure after the next window and roll back if it regresses"}


def open_trials(project: Path, rows_now: int | None = None) -> list[dict[str, Any]]:
    """Adoptions not rolled back yet, with whether their re-check window is complete."""
    rows_now = len(load_rows(project)) if rows_now is None else rows_now
    decisions = read_decisions(project)
    rolled = {item.get("id") for item in decisions if item.get("action") == "ROLLED_BACK"}
    trials = []
    for item in decisions:
        if item.get("action") == "ADOPTED" and item.get("id") not in rolled:
            recheck = int(item.get("recheck_at_rows") or 0)
            trials.append({"id": item.get("id"), "recheck_at_rows": recheck, "due": rows_now >= recheck,
                           "before": item.get("before")})
    return trials


def rollback(project: Path, judge: str, reason: str) -> dict[str, Any]:
    """Restore the policy from before the most recent adoption that is not yet rolled back."""
    judge = judge.lower()
    if judge not in JUDGES:
        raise RsiRefused(f"JUDGE_NOT_ALLOWED:{judge}")
    decisions = read_decisions(project)
    rolled = {item.get("id") for item in decisions if item.get("action") == "ROLLED_BACK"}
    for item in reversed(decisions):
        if item.get("action") == "ADOPTED" and item.get("id") not in rolled:
            if item.get("policy"):
                _write_policy(project, item.get("previous_policy") or dict(DEFAULT_POLICY))
            record_decision(project, {"action": "ROLLED_BACK", "id": item.get("id"), "judge": judge,
                                      "reason": reason[:300]})
            return {"rolled_back": item.get("id"), "policy": load_policy(project)}
    raise RsiRefused("NOTHING_TO_ROLL_BACK")


# ---------------------------------------------------------------- sentinel hook


def rsi_review_messages(
    project: Path, analysis: dict[str, Any], policy: dict[str, Any] | None = None
) -> list[tuple[str, dict[str, Any]]]:
    """Mailbox messages (not P1), one per worker that completed a new analysis window. The id names the window,
    so the sentinel publishes each window once and never repeats it after it is read."""
    policy = policy or load_policy(project)
    messages = []
    for worker, info in analysis["workers"].items():
        window_count = info["total"] // int(policy["window"])
        if info["status"] != "WINDOW_READY" or window_count == 0:
            continue
        message_id = f"rsi_review_{worker}_{int(policy['window'])}x{window_count}"
        summary = (f"RSI window {window_count} for {worker}: pass {info['pass_rate']}, rework {info['rework_rate']}, "
                   f"recurring {','.join(info['recurring']) or 'none'} — run `rsi propose`")
        messages.append((message_id, {"kind": "RSI_REVIEW", "step": "RSI", "summary": summary[:200], "actor": "sentinel"}))
    return messages
