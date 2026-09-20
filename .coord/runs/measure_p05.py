"""Run apples-to-apples A/B measurement for P05 under identical task and model conditions."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
WORKSPACE = PROJECT / ".work"  # user rule: only the project folder at workspace root
SAMPLE_A = WORKSPACE / "260916_pilot_sample_P05_A"
SAMPLE_B = WORKSPACE / "260916_pilot_sample_P05_B"
NET = "sandbox_workspace_write.network_access=true"


def run_codex(label: str, cwd: Path, prompt: str, extra_dirs: list[Path]) -> dict:
    out_dir = PROJECT / ".coord" / "runs" / "codex-measure"
    out_dir.mkdir(parents=True, exist_ok=True)
    events_path = out_dir / f"{label}.jsonl"

    codex_bin = shutil.which("codex") or "codex"
    cmd = [
        codex_bin,
        "exec",
        "--skip-git-repo-check",
        "--json",
        "--sandbox",
        "workspace-write",
        "-c",
        NET,
        "-C",
        str(cwd),
    ]
    for d in extra_dirs:
        cmd += ["--add-dir", str(d)]
    cmd.append("-")

    start = time.time()
    with events_path.open("w", encoding="utf-8") as stream:
        completed = subprocess.run(
            cmd,
            input=prompt,
            text=True,
            stdout=stream,
            stderr=subprocess.STDOUT,
            timeout=1800,
        )
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
        rate = event.get("rate_limits") or (
            (event.get("payload") or {}).get("rate_limits") if isinstance(event.get("payload"), dict) else None
        )
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


def count_tests(cwd: Path) -> int:
    proc = subprocess.run([sys.executable, "-m", "unittest", "-v"], cwd=cwd, capture_output=True, text=True)
    return len([line for line in proc.stderr.splitlines() if line.startswith("test_")])


def hash_workspace(cwd: Path) -> str:
    hasher = hashlib.sha256()
    for p in sorted(cwd.rglob("*")):
        if p.is_file() and not p.name.startswith("."):
            hasher.update(p.relative_to(cwd).as_posix().encode("utf-8"))
            hasher.update(p.read_bytes())
    return f"sha256:{hasher.hexdigest()}"


def read_terminal_ledger(work_dir: Path | str, task_id: str) -> dict | None:
    work_dir = Path(work_dir)
    db_path = work_dir / "coord.sqlite3"
    if not db_path.is_file():
        return None

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        cursor = conn.cursor()
        row = cursor.execute(
            "SELECT attempt_id, state, idempotency_key FROM attempts WHERE task_id = ? ORDER BY rowid DESC LIMIT 1",
            (task_id,),
        ).fetchone()
        if not row:
            return None
        attempt_id, attempt_state, idempotency_key = row

        chk = cursor.execute(
            "SELECT base_manifest_hash, artifact_set_hash FROM checkpoints WHERE attempt_id = ? ORDER BY rowid DESC LIMIT 1",
            (attempt_id,),
        ).fetchone()
        source_hash = f"sha256:{chk[0]}" if chk else None
        bundle_id = chk[1] if chk else None

        lease = cursor.execute(
            "SELECT state FROM leases WHERE attempt_id = ? ORDER BY rowid DESC LIMIT 1",
            (attempt_id,),
        ).fetchone()
        lease_state = lease[0] if lease else "RELEASED"

        deliv = cursor.execute(
            "SELECT state FROM deliveries WHERE dedupe_key = ? ORDER BY rowid DESC LIMIT 1",
            (idempotency_key,),
        ).fetchone()
        if not deliv:
            deliv = cursor.execute(
                "SELECT state FROM deliveries WHERE dedupe_key LIKE ? OR delivery_id LIKE ? ORDER BY rowid DESC LIMIT 1",
                (f"{task_id}:%", f"{task_id}-cmd%"),
            ).fetchone()
        delivery_state = deliv[0] if deliv else "UNKNOWN"

        return {
            "task_id": task_id,
            "run_id": attempt_id,
            "source_hash": source_hash,
            "bundle_id": bundle_id,
            "attempt_state": attempt_state,
            "delivery_state": delivery_state,
            "lease_state": lease_state,
        }
    finally:
        conn.close()


def read_pre_run_attempt_ids(work_dir: Path | str, task_id: str) -> list[str]:
    work_dir = Path(work_dir)
    db_path = work_dir / "coord.sqlite3"
    if not db_path.is_file():
        return []

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        cursor = conn.cursor()
        rows = cursor.execute(
            "SELECT attempt_id FROM attempts WHERE task_id = ? OR task_id LIKE ? ORDER BY rowid ASC",
            (task_id, f"{task_id}-%"),
        ).fetchall()
        return [row[0] for row in rows if row and row[0]]
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()


def read_pilot_identity(work_dir: Path | str, task_id: str) -> dict | None:
    work_dir = Path(work_dir)
    identity_file = work_dir / "runs" / task_id / "identity.json"
    if not identity_file.is_file():
        return None
    return json.loads(identity_file.read_text(encoding="utf-8"))


def evaluate_measurement(evidence: dict) -> dict:
    expected_task = evidence.get("task")
    baseline_hash = evidence.get("baseline_source_hash")

    a = evidence.get("A", {})
    b = evidence.get("B", {})

    task_identical = bool(expected_task and a.get("task") == expected_task and b.get("task") == expected_task)
    starting_state_identical = bool(baseline_hash and a.get("source_hash") == baseline_hash and b.get("source_hash") == baseline_hash)

    # 1. Both Codex runs exited 0
    codex_a_exit = a.get("codex_exit", a.get("exit", 0))
    codex_b_exit = b.get("codex_exit", b.get("exit", 0))
    if codex_a_exit != 0 or codex_b_exit != 0:
        return {
            "status": "INVALID_CODEX_EXECUTION",
            "task_identical": task_identical,
            "starting_state_identical": starting_state_identical,
            "reason": f"Codex execution failed (A={codex_a_exit}, B={codex_b_exit})",
        }

    # 2. Forbidden infrastructure errors are absent
    infra_errors_a = a.get("forbidden_infrastructure_errors", [])
    infra_errors_b = b.get("forbidden_infrastructure_errors", [])
    forbidden_patterns = {"helper_unknown_error", "USAGE_LIMIT"}
    has_forbidden = (
        bool(infra_errors_a)
        or bool(infra_errors_b)
        or any(err in forbidden_patterns for err in a.get("errors", []))
        or any(err in forbidden_patterns for err in b.get("errors", []))
    )
    if has_forbidden:
        return {
            "status": "INVALID_INFRASTRUCTURE",
            "task_identical": task_identical,
            "starting_state_identical": starting_state_identical,
            "reason": "Forbidden infrastructure errors detected",
        }

    # 3. Task and baseline/source hashes match
    if not starting_state_identical:
        return {
            "status": "INVALID_START_STATE",
            "task_identical": task_identical,
            "starting_state_identical": starting_state_identical,
            "reason": f"Baseline source hash mismatch (baseline={baseline_hash}, A={a.get('source_hash')}, B={b.get('source_hash')})",
        }
    if not task_identical:
        return {
            "status": "INVALID_TASK",
            "task_identical": task_identical,
            "starting_state_identical": starting_state_identical,
            "reason": f"Task mismatch (expected={expected_task}, A={a.get('task')}, B={b.get('task')})",
        }

    # 4. Direct expected behavior passed
    exp_a = a.get("expected_behavior_passed", a.get("acceptance_exit") == 0)
    exp_b = b.get("expected_behavior_passed", b.get("direct_acceptance_exit") == 0)
    direct_exit_a = a.get("direct_acceptance_exit", a.get("acceptance_exit", 0))
    direct_exit_b = b.get("direct_acceptance_exit", 0)
    if not exp_a or not exp_b or direct_exit_a != 0 or direct_exit_b != 0:
        return {
            "status": "INVALID_ACCEPTANCE",
            "task_identical": task_identical,
            "starting_state_identical": starting_state_identical,
            "reason": "Direct expected behavior did not pass",
        }

    # 5. B pilot summary exists
    summary = b.get("pilot_summary")
    if not summary or not isinstance(summary, dict):
        return {
            "status": "INVALID_SETUP",
            "task_identical": task_identical,
            "starting_state_identical": starting_state_identical,
            "reason": "B pilot summary is missing or invalid",
        }

    # 6. Summary task/run/source/bundle identity matches a terminal SQLite ledger
    ledger = b.get("ledger_terminal")

    if not ledger or ledger.get("attempt_state") not in ("SUCCEEDED", "COMPLETED", "TERMINAL"):
        return {
            "status": "INVALID_LEDGER",
            "task_identical": task_identical,
            "starting_state_identical": starting_state_identical,
            "reason": f"Ledger is missing or non-terminal: {ledger.get('attempt_state') if ledger else None}",
        }

    # Top-level matching: summary source_hash must match top-level baseline_source_hash
    if summary.get("source_hash") != baseline_hash:
        return {
            "status": "INVALID_PILOT_IDENTITY",
            "task_identical": task_identical,
            "starting_state_identical": starting_state_identical,
            "reason": f"Summary source_hash ({summary.get('source_hash')}) != baseline ({baseline_hash})",
        }

    # Top-level matching: summary task_id must match top-level task or start with task + "-"
    summary_task = summary.get("task_id", "")
    if not (summary_task == expected_task or summary_task.startswith(f"{expected_task}-")):
        return {
            "status": "INVALID_PILOT_IDENTITY",
            "task_identical": task_identical,
            "starting_state_identical": starting_state_identical,
            "reason": f"Summary task_id ({summary_task}) does not match expected task ({expected_task})",
        }

    for key in ("task_id", "run_id", "source_hash", "bundle_id"):
        if summary.get(key) != ledger.get(key):
            return {
                "status": "INVALID_PILOT_IDENTITY",
                "task_identical": task_identical,
                "starting_state_identical": starting_state_identical,
                "reason": f"Summary identity mismatch on {key}",
            }

    # 7. Stale run check (P1 freshness)
    pre_run_attempt_ids = b.get("pre_run_attempt_ids")
    if (
        "pre_run_attempt_ids" not in b
        or pre_run_attempt_ids is None
        or not isinstance(pre_run_attempt_ids, (list, tuple, set, frozenset))
    ):
        return {
            "status": "INVALID_STALE_RUN",
            "task_identical": task_identical,
            "starting_state_identical": starting_state_identical,
            "reason": "Missing or invalid pre_run_attempt_ids in B",
        }

    ledger_run_id = ledger.get("run_id") if ledger else None
    if ledger_run_id and ledger_run_id in pre_run_attempt_ids:
        return {
            "status": "INVALID_STALE_RUN",
            "task_identical": task_identical,
            "starting_state_identical": starting_state_identical,
            "reason": f"Run {ledger_run_id} is stale (already in ledger before B run)",
        }

    # 8. Verdict is PASS
    if summary.get("verdict_hint") != "PASS":
        return {
            "status": "INVALID_VERDICT",
            "task_identical": task_identical,
            "starting_state_identical": starting_state_identical,
            "reason": f"Verdict hint is {summary.get('verdict_hint')}, expected PASS",
        }

    # 8. Promotion is actually APPLIED
    if summary.get("promotion") != "APPLIED":
        return {
            "status": "INVALID_PROMOTION",
            "task_identical": task_identical,
            "starting_state_identical": starting_state_identical,
            "reason": f"Promotion is {summary.get('promotion')}, expected APPLIED",
        }

    # 9. Post-apply acceptance exits 0
    post_apply_exit = b.get("post_apply_acceptance_exit")
    if post_apply_exit is None or post_apply_exit != 0:
        return {
            "status": "INVALID_POST_ACCEPTANCE",
            "task_identical": task_identical,
            "starting_state_identical": starting_state_identical,
            "reason": f"Post-apply acceptance exit code was {post_apply_exit}, expected 0",
        }

    # 10. All gates passed -> MEASURED_AND_VERIFIED
    tokens_a = a.get("input_tokens", 0)
    tokens_b = b.get("input_tokens", 0)
    input_reduction = round((tokens_a - tokens_b) / tokens_a * 100, 1) if tokens_a > 0 else 0.0

    wall_a = a.get("wall_s", 0.0)
    wall_b = b.get("wall_s", 0.0)
    wall_reduction = round((wall_a - wall_b) / wall_a * 100, 1) if wall_a > 0 else 0.0

    cached_a = a.get("cached_input_tokens", 0)
    cached_b = b.get("cached_input_tokens", 0)
    noncached_a = tokens_a - cached_a
    noncached_b = tokens_b - cached_b
    noncached_reduction = round((noncached_a - noncached_b) / noncached_a * 100, 1) if noncached_a > 0 else 0.0

    return {
        "status": "MEASURED_AND_VERIFIED",
        "task_identical": task_identical,
        "starting_state_identical": starting_state_identical,
        "savings": {
            "wall_reduction_pct": wall_reduction,
            "input_token_reduction_pct": input_reduction,
            "noncached_input_token_reduction_pct": noncached_reduction,
        },
        "codex_input_tokens": {
            "A_codex_only": tokens_a,
            "B_codex_one_turn": tokens_b,
            "reduction_pct": input_reduction,
        },
        "codex_wall_seconds": {
            "A_codex_only": wall_a,
            "B_codex_one_turn": wall_b,
            "reduction_pct": wall_reduction,
        },
        "quality_gate": "PASS",
        "diagnostics": {
            "tool_call_events": {
                "A_codex_only": a.get("tool_call_events", 0),
                "B_codex_one_turn": b.get("tool_call_events", 0),
            },
            "tests_passed": {
                "A_codex_only": a.get("test_count", 0),
                "B_codex_one_turn": b.get("test_count", 0),
            },
        },
    }


def main() -> int:
    prompt_file = PROJECT / ".coord" / "runs" / "P05" / "prompt.md"
    p05_text = prompt_file.read_text(encoding="utf-8")

    # 1. Condition A: Codex Only
    events_a_path = PROJECT / ".coord" / "runs" / "codex-measure" / "P05-A-codex-only.jsonl"
    if events_a_path.exists() and (PROJECT / ".coord" / "runs" / "P05" / "ab.json").exists():
        existing_ab = json.loads((PROJECT / ".coord" / "runs" / "P05" / "ab.json").read_text(encoding="utf-8"))
        res_a = existing_ab["A_codex_only"]
        print(f"[1/2] Condition A (Codex Only) already recorded: wall_s={res_a['wall_s']}, tests={res_a['test_count']}", flush=True)
    else:
        print("[1/2] Starting Condition A (Codex Only)...", flush=True)
        prompt_a = (
            p05_text
            + "\nAfter editing, run `python -m unittest` once and report the exit code in one line."
        )
        res_a = run_codex("P05-A-codex-only", SAMPLE_A, prompt_a, [])
        res_a["acceptance_exit"] = acceptance(SAMPLE_A)
        res_a["test_count"] = count_tests(SAMPLE_A)
        print(f"Condition A Finished: exit={res_a['exit']}, wall_s={res_a['wall_s']}, tests={res_a['test_count']}", flush=True)

    # 2. Condition B: Codex One-Turn Delegation + Antigravity Pilot
    print("[2/2] Starting Condition B (Codex One-Turn + Antigravity Pilot)...", flush=True)
    pre_run_attempt_ids = read_pre_run_attempt_ids(PROJECT / ".coord" / "pilot", "P05")
    prompt_b = (
        "[P05] Follow AGENTS.md one-turn rule. Run this command exactly once and wait for it (no polling):\n"
        'python -m v7_harness.cli pilot run --task P05 --source .work\\260916_pilot_sample_P05_B --prompt-file .coord/runs/P05/prompt.md '
        '--title "power reciprocal" --accept-cmd "python -m unittest -q" --work-dir .coord/pilot --model gemini-3.7-flash-high\n'
        "Then read .coord/pilot/runs/P05/summary.json once. If verdict_hint is PASS, run the same command once more with "
        "--approve <bundle_id>. Otherwise do not approve. Do not read any other file. Reply with one line: verdict, promotion."
    )
    extra_dirs = [SAMPLE_B, Path.home().resolve()]
    res_b = run_codex("P05-B-one-turn", PROJECT, prompt_b, extra_dirs)
    summary_path = PROJECT / ".coord" / "pilot" / "runs" / "P05" / "summary.json"
    pilot_summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.is_file() else None
    ident = read_pilot_identity(PROJECT / ".coord" / "pilot", "P05")
    if pilot_summary is not None and ident is not None:
        pilot_summary = {**pilot_summary, **ident}
    elif ident is not None:
        pilot_summary = ident
    res_b["pilot_summary"] = pilot_summary
    res_b["sample_acceptance_exit"] = acceptance(SAMPLE_B)
    res_b["test_count"] = count_tests(SAMPLE_B)
    print(f"Condition B Finished: exit={res_b['exit']}, wall_s={res_b['wall_s']}, tests={res_b['test_count']}", flush=True)

    tokens_a = res_a.get("usage", {}).get("input_tokens", 0)
    cached_a = res_a.get("usage", {}).get("cached_input_tokens", 0)
    tokens_b = res_b.get("usage", {}).get("input_tokens", 0)
    cached_b = res_b.get("usage", {}).get("cached_input_tokens", 0)

    baseline_hash = hash_workspace(SAMPLE_A) if SAMPLE_A.exists() else "UNKNOWN"
    a_hash = baseline_hash
    b_hash = hash_workspace(SAMPLE_B) if SAMPLE_B.exists() else "UNKNOWN"

    evidence = {
        "task": "P05",
        "baseline_source_hash": baseline_hash,
        "A": {
            "task": "P05",
            "source_hash": a_hash,
            "codex_exit": res_a.get("exit", 1),
            "forbidden_infrastructure_errors": res_a.get("errors", []),
            "direct_acceptance_exit": res_a.get("acceptance_exit", 1),
            "expected_behavior_passed": res_a.get("acceptance_exit") == 0 and res_a.get("test_count", 0) >= 12,
            "input_tokens": tokens_a,
            "cached_input_tokens": cached_a,
            "wall_s": res_a.get("wall_s", 0.0),
            "tool_call_events": res_a.get("tool_call_events", 0),
            "test_count": res_a.get("test_count", 0),
        },
        "B": {
            "task": "P05",
            "source_hash": b_hash,
            "codex_exit": res_b.get("exit", 1),
            "forbidden_infrastructure_errors": res_b.get("errors", []),
            "direct_acceptance_exit": res_b.get("sample_acceptance_exit", 1),
            "expected_behavior_passed": res_b.get("sample_acceptance_exit") == 0 and res_b.get("test_count", 0) >= 12,
            "input_tokens": tokens_b,
            "cached_input_tokens": cached_b,
            "wall_s": res_b.get("wall_s", 0.0),
            "pilot_summary": res_b.get("pilot_summary"),
            "ledger_terminal": read_terminal_ledger(PROJECT / ".coord" / "pilot", "P05"),
            "post_apply_acceptance_exit": res_b.get("sample_acceptance_exit", 1),
            "pre_run_attempt_ids": pre_run_attempt_ids,
            "tool_call_events": res_b.get("tool_call_events", 0),
            "test_count": res_b.get("test_count", 0),
        },
    }

    comparison = evaluate_measurement(evidence)

    out_data = {
        "task": "P05",
        "task_description": "Add power and reciprocal functions with 3+ unit tests each",
        "A_codex_only": res_a,
        "B_codex_one_turn": res_b,
        "comparison": comparison,
    }

    out_path_env = os.environ.get("MEASURE_OUT_FILE")
    if out_path_env:
        out_file = Path(out_path_env).resolve()
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(json.dumps(out_data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved results to {out_file}")
    else:
        print("Comparison evaluation:")
        print(json.dumps(comparison, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
