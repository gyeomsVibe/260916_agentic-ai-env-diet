"""Measure Codex-side cost for P03 A (Codex only) and P04 B (Codex + pilot run, one-turn rule).

Runs two fresh, non-interactive `codex exec --json` sessions after the Codex usage reset and records:
wall time, tool calls, input/output tokens, 5h-window used_percent before/after (from session rate_limits),
and acceptance results. Writes .coord/runs/P03/ab.json (A part) and .coord/runs/P04/ab.json.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
WORKSPACE = PROJECT / ".work"  # user rule: only the project folder at workspace root
SAMPLE = WORKSPACE / "260916_pilot_sample"
SAMPLE_A = WORKSPACE / "260916_pilot_sample_A"
NET = 'sandbox_workspace_write.network_access=true'


def run_codex(label: str, cwd: Path, prompt: str, extra_dirs: list[Path]) -> dict:
    out_dir = PROJECT / ".coord" / "runs" / "codex-measure"
    out_dir.mkdir(parents=True, exist_ok=True)
    events_path = out_dir / f"{label}.jsonl"
    cmd = [shutil.which("codex") or "codex", "exec", "--skip-git-repo-check", "--json", "--sandbox", "workspace-write", "-c", NET, "-C", str(cwd)]
    for d in extra_dirs:
        cmd += ["--add-dir", str(d)]
    cmd.append("-")  # prompt via stdin: codex.CMD (cmd.exe) mangles multi-line/quoted argv
    start = time.time()
    with events_path.open("w", encoding="utf-8") as stream:
        completed = subprocess.run(cmd, input=prompt.encode("utf-8"), stdout=stream, stderr=subprocess.STDOUT, timeout=3600)
    wall = round(time.time() - start, 1)
    tool_calls = 0
    usage: dict = {}
    percents: list[float] = []
    errors: list[str] = []
    for line in events_path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        text = json.dumps(event)
        if '"command_execution"' in text or '"function_call"' in text or '"exec_command' in text:
            tool_calls += 1
        for key in ("usage", "total_token_usage"):
            if isinstance(event.get(key), dict):
                usage = event[key]
        info = (event.get("payload") or {}).get("info") if isinstance(event.get("payload"), dict) else None
        if isinstance(info, dict) and isinstance(info.get("total_token_usage"), dict):
            usage = info["total_token_usage"]
        rate = event.get("rate_limits") or ((event.get("payload") or {}).get("rate_limits") if isinstance(event.get("payload"), dict) else None)
        if isinstance(rate, dict) and isinstance(rate.get("primary"), dict) and "used_percent" in rate["primary"]:
            percents.append(rate["primary"]["used_percent"])
        if "usage limit" in text.lower():
            errors.append("USAGE_LIMIT")
    return {
        "label": label,
        "exit": completed.returncode,
        "wall_s": wall,
        "tool_call_events": tool_calls,
        "usage": usage,
        "codex_5h_used_percent_first": percents[0] if percents else None,
        "codex_5h_used_percent_last": percents[-1] if percents else None,
        "errors": sorted(set(errors)),
        "events": str(events_path.relative_to(PROJECT)),
    }


def acceptance(cwd: Path) -> int:
    return subprocess.run([sys.executable, "-m", "unittest", "-q"], cwd=cwd, capture_output=True).returncode


def main() -> int:
    p03 = (PROJECT / ".coord" / "runs" / "P03" / "prompt.md").read_text(encoding="utf-8")
    a = run_codex("P03-A-codex-only", SAMPLE_A, p03 + "\nAfter editing, run `python -m unittest` once and report the exit code in one line.", [])
    a["acceptance_exit"] = acceptance(SAMPLE_A)
    ab_path = PROJECT / ".coord" / "runs" / "P03" / "ab.json"
    ab = json.loads(ab_path.read_text(encoding="utf-8"))
    ab["A_codex_only"] = a
    ab_path.write_text(json.dumps(ab, ensure_ascii=False, indent=2), encoding="utf-8")
    if "USAGE_LIMIT" in a["errors"]:
        return 3

    b_prompt = (
        "[P04] Follow AGENTS.md one-turn rule. Run this command exactly once and wait for it (no polling):\n"
        'python -m v7_harness.cli pilot run --task P04 --source ..\\260916_pilot_sample --prompt-file .coord/runs/P04/prompt.md '
        '--title "variance stdev" --accept-cmd "python -m unittest -q" --work-dir .coord/pilot --agy-command python .coord/runs/P03/agy_model.py\n'
        "Then read .coord/pilot/runs/P04/summary.json once. If verdict_hint is PASS, run the same command once more with "
        "--approve <bundle_id>. Otherwise do not approve. Do not read any other file. Reply with one line: verdict, promotion."
    )
    b = run_codex("P04-B-one-turn", PROJECT, b_prompt, [SAMPLE])
    summary_path = PROJECT / ".coord" / "pilot" / "runs" / "P04" / "summary.json"
    b["pilot_summary"] = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.is_file() else None
    b["sample_acceptance_exit"] = acceptance(SAMPLE)
    out = {
        "task": "P04",
        "B_codex_one_turn": b,
        "baseline_P01_B": {"tool_calls": 147, "input_tokens": 16614049, "codex_5h_pct_delta": 8},
        "notes": "measured values only",
    }
    p04 = PROJECT / ".coord" / "runs" / "P04" / "ab.json"
    p04.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"A": {k: a[k] for k in ("exit", "wall_s", "tool_call_events", "usage", "acceptance_exit")},
                      "B": {k: b[k] for k in ("exit", "wall_s", "tool_call_events", "usage", "sample_acceptance_exit")}}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
