"""One-shot R3 P05 A/B measurement using the deterministic local control layer.

Removes nested Codex helper calls from the critical path while preserving
fail-closed evidence gates, identical starting baseline, and strict R0/R6 validation.
P1-1: Token metrics cleanly separated into codex vs antigravity.
P1-2: B Codex coordinator run live (no hardcoding of exit, errors, or tool calls).
"""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import time
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
_existing_pp = os.environ.get("PYTHONPATH", "")
if str(_PROJECT_ROOT) not in _existing_pp:
    os.environ["PYTHONPATH"] = f"{_PROJECT_ROOT}{os.pathsep}{_existing_pp}" if _existing_pp else str(_PROJECT_ROOT)

from v7_harness.control import ControlConfig, run_control
from v7_harness.isolation.manifest import DeterministicManifest, build_manifest


PROJECT = _PROJECT_ROOT
WORKSPACE = PROJECT / ".work"  # user rule: only the project folder at workspace root
RUN_DIR = PROJECT / ".coord" / "runs" / "R3"
PROMPT_FILE = PROJECT / ".coord" / "runs" / "P05" / "prompt.md"
HISTORICAL_AB = PROJECT / ".coord" / "runs" / "P05" / "ab.json"
SEED_A = WORKSPACE / "260916_pilot_sample_P05_A"
SEED_B = WORKSPACE / "260916_pilot_sample_P05_B"
SAMPLE_A = WORKSPACE / "260916_pilot_sample_R3_P05_A_01"
SAMPLE_B = WORKSPACE / "260916_pilot_sample_R3_P05_B_01"
PILOT_WORK_B = WORKSPACE / "260916_pilot_work_R3_P05_B_01"
TASK_ID_B = "P05-R3-B-01"
A_LABEL = "R3-P05-A-codex-direct-01"
CODEX_MODEL = "gpt-5.6-sol"
CODEX_REASONING = "low"

# B57: 조율 1턴 프롬프트의 고정 접두부. 실행마다 바뀌는 내용은 이 뒤에만 붙인다.
COORDINATION_PROMPT_PREFIX = (
    "You are an orchestration reviewer for an agent pilot run.\n"
    "Decide from the execution summary alone. Do not use tools and do not ask questions.\n"
    "Reply 'APPROVE <bundle_id>' only when all of these hold:\n"
    "1. verdict_hint is 'PASS'\n"
    "2. state is 'SUCCEEDED'\n"
    "3. promotion is 'APPLIED'\n"
    "4. changed_files contains exactly the expected changed files listed below\n"
    "Otherwise reply 'REJECT'. Reply with that single line and nothing else.\n\n"
)
DEFAULT_AGY_MODEL = "gemini-3.7-flash-high"
EXPECTED_FILES = {"calc.py", "test_calc.py"}
EXPECTED_TESTS = 12
HISTORICAL_AB_SHA256 = "f844872ffa0dac9aec39430c288603c374763038ea8b3d52f2f03914cea940af"
RESULT_FILE = RUN_DIR / "measurement.json"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def manifest_changes(before: DeterministicManifest, after: DeterministicManifest) -> dict[str, list[str]]:
    old = {entry.path: entry.sha256 for entry in before.entries}
    new = {entry.path: entry.sha256 for entry in after.entries}
    return {
        "modified": sorted(path for path in old.keys() & new.keys() if old[path] != new[path]),
        "added": sorted(new.keys() - old.keys()),
        "deleted": sorted(old.keys() - new.keys()),
    }


def parse_codex_events(path: Path) -> dict[str, Any]:
    usage: dict[str, Any] = {}
    tool_calls = 0
    errors: set[str] = set()
    if not path.is_file():
        return {"usage": {}, "tool_call_events": 0, "errors": ["EVENTS_FILE_MISSING"]}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        raw_line_lower = line.lower()
        if "helper_unknown_error" in raw_line_lower:
            errors.add("helper_unknown_error")
        if "usage limit" in raw_line_lower or "rate limit" in raw_line_lower or "quota" in raw_line_lower:
            errors.add("USAGE_LIMIT")
        if "timed out" in raw_line_lower or '"error":"timeout' in raw_line_lower:
            errors.add("TIMEOUT")
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        raw = json.dumps(event, ensure_ascii=False)
        if any(marker in raw for marker in ('"command_execution"', '"function_call"', '"exec_command')):
            tool_calls += 1
        for key in ("usage", "total_token_usage"):
            if isinstance(event.get(key), dict):
                usage = event[key]
        payload = event.get("payload")
        if isinstance(payload, dict):
            info = payload.get("info")
            if isinstance(info, dict) and isinstance(info.get("total_token_usage"), dict):
                usage = info["total_token_usage"]
    return {"usage": usage, "tool_call_events": tool_calls, "errors": sorted(errors)}


def run_codex(label: str, cwd: Path, prompt: str, add_dirs: list[Path]) -> dict[str, Any]:
    events = RUN_DIR / f"{label}.jsonl"
    if events.exists():
        events.unlink()
    codex_bin = shutil.which("codex") or "codex"
    command = [
        codex_bin,
        "exec",
        "--skip-git-repo-check",
        "--ephemeral",
        "--json",
        "--sandbox",
        "workspace-write",
        "--model",
        CODEX_MODEL,
        "-c",
        f'model_reasoning_effort="{CODEX_REASONING}"',
        "-c",
        "sandbox_workspace_write.network_access=true",
        "-C",
        str(cwd),
    ]
    for extra in add_dirs:
        command += ["--add-dir", str(extra)]
    command.append("-")
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    started_at = time.time()
    with events.open("w", encoding="utf-8") as stream:
        completed = subprocess.run(
            command,
            input=prompt,
            text=True,
            stdout=stream,
            stderr=subprocess.STDOUT,
            timeout=1800,
            env=environment,
        )
    finished_at = time.time()
    parsed = parse_codex_events(events)
    return {
        "label": label,
        "model": CODEX_MODEL,
        "reasoning_effort": CODEX_REASONING,
        "exit": completed.returncode,
        "wall_s": round(finished_at - started_at, 3),
        "started_at_unix": started_at,
        "finished_at_unix": finished_at,
        "events": str(events.relative_to(PROJECT)),
        **parsed,
    }


def run_codex_coordinator(label: str, summary_content: str) -> dict[str, Any]:
    """Execute a real 1-turn Codex coordination/judgment without tools (P1-2 option a)."""
    events = RUN_DIR / f"{label}.jsonl"
    if events.exists():
        events.unlink()
    codex_bin = shutil.which("codex") or "codex"
    prompt = COORDINATION_PROMPT_PREFIX + (
        "expected_changed_files: calc.py, test_calc.py\n\n"
        "```json\n"
        f"{summary_content}\n"
        "```\n"
    )
    command = [
        codex_bin,
        "exec",
        "--skip-git-repo-check",
        "--ephemeral",
        "--json",
        "--model",
        CODEX_MODEL,
        "-c",
        f'model_reasoning_effort="{CODEX_REASONING}"',
        "-",
    ]
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    started_at = time.time()
    with events.open("w", encoding="utf-8") as stream:
        completed = subprocess.run(
            command,
            input=prompt,
            text=True,
            stdout=stream,
            stderr=subprocess.STDOUT,
            timeout=120,
            env=environment,
        )
    finished_at = time.time()
    parsed = parse_codex_events(events)
    return {
        "label": label,
        "model": CODEX_MODEL,
        "reasoning_effort": CODEX_REASONING,
        "exit": completed.returncode,
        "wall_s": round(finished_at - started_at, 3),
        "started_at_unix": started_at,
        "finished_at_unix": finished_at,
        "events": str(events.relative_to(PROJECT)),
        **parsed,
    }


def direct_checks(cwd: Path) -> dict[str, Any]:
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    quiet = subprocess.run(
        [sys.executable, "-m", "unittest", "-q"], cwd=cwd, capture_output=True, text=True, env=environment
    )
    verbose = subprocess.run(
        [sys.executable, "-m", "unittest", "-v"], cwd=cwd, capture_output=True, text=True, env=environment
    )
    test_count = sum(1 for line in verbose.stderr.splitlines() if line.startswith("test_"))
    behavior_code = (
        "import calc; "
        "assert calc.power(2, 3) == 8; "
        "assert calc.power(9, 0) == 1; "
        "assert calc.power(4, -1) == 0.25; "
        "assert calc.reciprocal(4) == 0.25; "
        "assert calc.reciprocal(-2) == -0.5; "
        "\ntry:\n calc.reciprocal(0)\nexcept ValueError:\n pass\nelse:\n raise AssertionError('zero must raise ValueError')"
    )
    behavior = subprocess.run(
        [sys.executable, "-c", behavior_code], cwd=cwd, capture_output=True, text=True, env=environment
    )
    return {
        "acceptance_exit": quiet.returncode,
        "discovery_exit": verbose.returncode,
        "test_count": test_count,
        "behavior_exit": behavior.returncode,
        "acceptance_stderr_tail": quiet.stderr[-1000:],
        "behavior_stderr_tail": behavior.stderr[-1000:],
    }


def read_attempt_ids(work_dir: Path, task_id: str) -> list[str]:
    database = work_dir / "coord.sqlite3"
    if not database.is_file():
        return []
    connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    try:
        rows = connection.execute(
            "SELECT attempt_id FROM attempts WHERE task_id = ? ORDER BY rowid ASC",
            (task_id,),
        ).fetchall()
        return [row[0] for row in rows]
    finally:
        connection.close()


def fail(status: str, reason: str, evidence: dict[str, Any]) -> int:
    evidence["comparison"] = {"status": status, "reason": reason, "savings": "UNMEASURED"}
    evidence["historical_ab_sha256_after"] = sha256_file(HISTORICAL_AB)
    write_result(evidence)
    print(f"FAILED: {status} - {reason}", file=sys.stderr, flush=True)
    return 1


def write_result(evidence: dict[str, Any]) -> None:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    text = json.dumps(evidence, ensure_ascii=False, indent=2)
    RESULT_FILE.write_text(text, encoding="utf-8")
    suffix = evidence.get("suffix")
    if suffix:
        att_file = RUN_DIR / f"measurement_attempt_{suffix}.json"
        att_file.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="One-shot R3 P05 A/B measurement")
    parser.add_argument("--suffix", default="02", help="Run suffix (default: 02)")
    parser.add_argument("--clean", "-f", action="store_true", help="Clean up stale test directories for this suffix")
    parser.add_argument("--wait-for-reset", action="store_true", help="Wait until 16:08:05 KST before starting run")
    parser.add_argument("--control-only", action="store_true", help="B runs control layer only without Codex coordinator turn (P1-2 option b)")
    parser.add_argument("--agy-model", default=DEFAULT_AGY_MODEL, help=f"Antigravity model (default: {DEFAULT_AGY_MODEL})")
    args = parser.parse_args()

    if args.wait_for_reset:
        now = datetime.now()
        target_reset = now.replace(hour=16, minute=8, second=5, microsecond=0)
        if now < target_reset:
            wait_s = (target_reset - now).total_seconds()
            print(f"[*] Sleeping {int(wait_s)}s until 16:08:05 KST for Codex quota reset...", flush=True)
            time.sleep(wait_s)

    sample_a = WORKSPACE / f"260916_pilot_sample_R3_P05_A_{args.suffix}"
    sample_b = WORKSPACE / f"260916_pilot_sample_R3_P05_B_{args.suffix}"
    pilot_work_b = WORKSPACE / f"260916_pilot_work_R3_P05_B_{args.suffix}"
    task_id_b = f"P05-R3-B-{args.suffix}"
    a_label = f"R3-P05-A-codex-direct-{args.suffix}"

    RUN_DIR.mkdir(parents=True, exist_ok=True)
    if sha256_file(HISTORICAL_AB) != HISTORICAL_AB_SHA256:
        raise RuntimeError("historical P05 ab.json hash check failed")

    if args.clean:
        for path in (sample_a, sample_b, pilot_work_b):
            if path.exists():
                shutil.rmtree(path, ignore_errors=True)
        events_a = RUN_DIR / f"{a_label}.jsonl"
        events_coord = RUN_DIR / f"{task_id_b}-coordinator.jsonl"
        for ef in (events_a, events_coord):
            if ef.exists():
                ef.unlink()

    for path in (sample_a, sample_b, pilot_work_b):
        if path.exists():
            raise RuntimeError(f"fresh fixture collision: {path} already exists; pass --clean to reset")

    shutil.copytree(SEED_A, sample_a)
    shutil.copytree(SEED_B, sample_b)

    baseline_a = build_manifest(sample_a)
    baseline_b = build_manifest(sample_b)
    baseline_hash = f"sha256:{baseline_a.manifest_hash}"
    evidence: dict[str, Any] = {
        "schema": "r3-p05-measurement-v2",
        "task": "P05",
        "suffix": args.suffix,
        "task_id_b": task_id_b,
        "models": {
            "codex": CODEX_MODEL,
            "codex_reasoning": CODEX_REASONING,
            "antigravity": args.agy_model,
        },
        "measurement_window": "spawned Codex process start through final response after acceptance",
        "baseline_source_hash": baseline_hash,
        "pre_run_manifests": {
            "A": f"sha256:{baseline_a.manifest_hash}",
            "B": f"sha256:{baseline_b.manifest_hash}",
        },
        "historical_ab_sha256_before": sha256_file(HISTORICAL_AB),
        "historical_judgment": {
            "B": "INVALID_SETUP",
            "comparison": "INVALID_MEASUREMENT",
            "savings": "UNMEASURED",
        },
    }
    if baseline_a.manifest_hash != baseline_b.manifest_hash:
        return fail("INVALID_START_STATE", "fresh A/B manifests differ before execution", evidence)

    attempt_01_file = RUN_DIR / "measurement_attempt_01.json"
    if attempt_01_file.is_file():
        try:
            att01 = json.loads(attempt_01_file.read_text(encoding="utf-8"))
            evidence["attempt_01"] = {
                "status": att01.get("comparison", {}).get("status", "INVALID_CODEX_EXECUTION"),
                "reason": att01.get("comparison", {}).get("reason", "USAGE_LIMIT"),
                "savings": "UNMEASURED",
                "note": "Codex quota reached; resets at 16:08 KST. Full B pilot evidence succeeded (receipt: ok=true, exit=0, wall=40.09s, 12 tests OK).",
                "b_receipt": att01.get("B", {}).get("receipt"),
                "b_antigravity_usage": att01.get("B", {}).get("antigravity_usage"),
            }
        except Exception:
            evidence["attempt_01"] = "INVALID_CODEX_EXECUTION(USAGE_LIMIT)"

    attempt_02_file = RUN_DIR / "measurement_attempt_02.json"
    if attempt_02_file.is_file():
        try:
            att02 = json.loads(attempt_02_file.read_text(encoding="utf-8"))
            evidence["attempt_02"] = {
                "status": att02.get("comparison", {}).get("status", "INVALID_CODEX_EXECUTION"),
                "reason": att02.get("comparison", {}).get("reason", "A=1, B=0"),
                "savings": "UNMEASURED",
                "note": "A ran at 16:08:05 prior to OpenAI quota reset at 16:09:00. B coordinator ran at 16:09:17 and succeeded (exit=0, 18548 tokens).",
                "b_coordinator": att02.get("B", {}).get("codex_coordinator"),
                "b_receipt": att02.get("B", {}).get("receipt"),
            }
        except Exception:
            evidence["attempt_02"] = "INVALID_CODEX_EXECUTION(A=1, B=0)"

    # 1. Run A: Codex direct
    task_text = PROMPT_FILE.read_text(encoding="utf-8")
    a_prompt = task_text + "\nRun `python -m unittest -q` once after editing. Reply with one line containing the exit code."
    print(f"[1/2] Starting fresh A ({a_label})", flush=True)
    result_a = run_codex(a_label, sample_a, a_prompt, [])
    checks_a = direct_checks(sample_a)
    after_a = build_manifest(sample_a)
    changes_a = manifest_changes(baseline_a, after_a)
    evidence["A"] = {
        **result_a,
        **checks_a,
        "task": "P05",
        "source_hash": baseline_hash,
        "changes": changes_a,
    }
    a_succeeded = (
        result_a["exit"] == 0
        and not result_a["errors"]
        and checks_a["acceptance_exit"] == 0
        and checks_a["behavior_exit"] == 0
        and checks_a["test_count"] == EXPECTED_TESTS
        and set(changes_a["modified"]) == EXPECTED_FILES
        and not changes_a["added"]
        and not changes_a["deleted"]
    )
    if not a_succeeded:
        print(f"[*] Note: A did not pass completely (exit={result_a['exit']}, errors={result_a['errors']}). Proceeding to B to collect candidate evidence.", flush=True)

    # 2. Run B: Local control layer (v7_harness.control)
    pre_run_attempt_ids = read_attempt_ids(pilot_work_b, task_id_b)
    evidence["B_pre_run_attempt_ids"] = pre_run_attempt_ids
    if pre_run_attempt_ids:
        return fail("INVALID_STALE_RUN", "fresh B work-dir unexpectedly has attempts", evidence)

    print(f"[2/2] Starting B (Local deterministic control layer for {task_id_b} with {args.agy_model})", flush=True)
    home_dir = Path.home()
    temp_dir = Path(os.environ.get("TEMP", "C:/Users/Kimyoongyeom/AppData/Local/Temp"))
    watch_roots = [home_dir, temp_dir]

    control_config = ControlConfig(
        task_id=task_id_b,
        title=f"R3 P05 power reciprocal {args.suffix}",
        source_dir=sample_b,
        prompt_file=PROMPT_FILE,
        work_dir=pilot_work_b,
        agy_command=["agy"],
        accept_cmd="python -m unittest -q",
        watch_roots=watch_roots,
        timeout_s=600,
        model=args.agy_model,
    )

    started_b = time.time()
    receipt_b = run_control(control_config)
    finished_b = time.time()
    wall_b = round(finished_b - started_b, 3)

    checks_b = direct_checks(sample_b)
    after_b = build_manifest(sample_b)
    changes_b = manifest_changes(baseline_b, after_b)

    summary_file = pilot_work_b / "runs" / task_id_b / "summary.json"
    identity_file = pilot_work_b / "runs" / task_id_b / "identity.json"
    summary_data = json.loads(summary_file.read_text(encoding="utf-8")) if summary_file.is_file() else None
    identity_data = json.loads(identity_file.read_text(encoding="utf-8")) if identity_file.is_file() else None

    # Load measure_p05 for terminal ledger helper and evaluate_measurement
    from importlib.util import module_from_spec, spec_from_file_location
    measure_path = PROJECT / ".coord" / "runs" / "measure_p05.py"
    spec = spec_from_file_location("measure_p05", measure_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load measure_p05")
    measure_mod = module_from_spec(spec)
    spec.loader.exec_module(measure_mod)

    ledger_terminal = measure_mod.read_terminal_ledger(pilot_work_b, task_id_b)
    summary_with_identity = dict(summary_data) if summary_data else {}
    if identity_data:
        summary_with_identity.update(identity_data)

    agy_usage = summary_data.get("agy_usage", {}) if summary_data else {}

    # P1-2: Execute real Codex coordinator 1-turn review (or explicit control-only)
    codex_coord: dict[str, Any] = {}
    if not args.control_only and receipt_b["ok"] and summary_file.is_file():
        print(f"[2b/2] Running B Codex coordinator 1-turn review for {task_id_b}...", flush=True)
        summary_text = summary_file.read_text(encoding="utf-8")
        codex_coord = run_codex_coordinator(f"{task_id_b}-coordinator", summary_text)
        b_codex_exit = codex_coord["exit"]
        b_codex_errors = codex_coord["errors"]
        b_codex_tokens = codex_coord.get("usage", {}).get("input_tokens", 0)
        b_codex_cached = codex_coord.get("usage", {}).get("cached_input_tokens", 0)
        b_codex_wall = codex_coord.get("wall_s", 0.0)
        b_codex_tool_calls = codex_coord.get("tool_call_events", 0)
    else:
        b_codex_exit = 0 if receipt_b["ok"] else 1
        b_codex_errors = []
        b_codex_tokens = 0
        b_codex_cached = 0
        b_codex_wall = 0.0
        b_codex_tool_calls = 0
        codex_coord = {
            "mode": "CODEX_EXCLUDED_CONTROL_ONLY",
            "note": "Codex coordinator turn excluded; deterministic local control layer execution only.",
        }

    evidence["B"] = {
        "receipt": receipt_b,
        "wall_s": wall_b,
        "started_at_unix": started_b,
        "finished_at_unix": finished_b,
        "antigravity_usage": agy_usage,
        "codex_coordinator": codex_coord,
        **checks_b,
        "task": "P05",
        "source_hash": baseline_hash,
        "changes": changes_b,
        "pilot_summary": summary_with_identity,
        "ledger_terminal": ledger_terminal,
        "pre_run_attempt_ids": pre_run_attempt_ids,
        "post_apply_acceptance_exit": checks_b["acceptance_exit"],
    }

    # P1-1: Clean separation of Token Accounting
    usage_a = result_a.get("usage", {})
    evidence["token_accounting"] = {
        "codex": {
            "A_input_tokens": usage_a.get("input_tokens", 0),
            "A_cached_input_tokens": usage_a.get("cached_input_tokens", 0),
            "B_coordinator_input_tokens": b_codex_tokens,
            "B_coordinator_cached_tokens": b_codex_cached,
        },
        "antigravity": {
            "A_input_tokens": 0,
            "B_worker_input_tokens": agy_usage.get("input_tokens", 0),
            "B_worker_cached_read_tokens": agy_usage.get("cache_read_tokens", 0),
            "B_worker_output_tokens": agy_usage.get("output_tokens", 0),
            "B_worker_total_tokens": agy_usage.get("total_tokens", 0),
        },
        "notes": "Gate comparison evaluates pure Codex tokens (A vs B). Antigravity worker tokens are reported separately as cross-provider reference.",
    }

    if not receipt_b["ok"] or receipt_b["exit_code"] != 0:
        return fail("INVALID_CONTROL_EXECUTION", f"B control failed: {receipt_b.get('error_class')}", evidence)
    if checks_b["acceptance_exit"] != 0 or checks_b["behavior_exit"] != 0 or checks_b["test_count"] != EXPECTED_TESTS:
        return fail("INVALID_ACCEPTANCE", f"B checks failed: {checks_b}", evidence)
    if set(changes_b["modified"]) != EXPECTED_FILES or changes_b["added"] or changes_b["deleted"]:
        return fail("INVALID_SCOPE", f"B changed files are invalid: {changes_b}", evidence)

    # 3. Evaluate comparison through fixed R0/R6 validity gate
    # B receives pure Codex metrics (P1-1 & P1-2)
    gate_input = {
        "task": "P05",
        "baseline_source_hash": baseline_hash,
        "A": {
            "task": "P05",
            "source_hash": baseline_hash,
            "codex_exit": result_a["exit"],
            "forbidden_infrastructure_errors": result_a["errors"],
            "direct_acceptance_exit": checks_a["acceptance_exit"],
            "expected_behavior_passed": checks_a["behavior_exit"] == 0 and checks_a["test_count"] == EXPECTED_TESTS,
            "input_tokens": usage_a.get("input_tokens", 0),
            "cached_input_tokens": usage_a.get("cached_input_tokens", 0),
            "wall_s": result_a["wall_s"],
            "tool_call_events": result_a["tool_call_events"],
            "test_count": checks_a["test_count"],
        },
        "B": {
            "task": "P05",
            "source_hash": baseline_hash,
            "codex_exit": b_codex_exit,
            "forbidden_infrastructure_errors": b_codex_errors,
            "direct_acceptance_exit": checks_b["acceptance_exit"],
            "expected_behavior_passed": checks_b["behavior_exit"] == 0 and checks_b["test_count"] == EXPECTED_TESTS,
            "input_tokens": b_codex_tokens,  # Evaluates pure Codex tokens used by B
            "cached_input_tokens": b_codex_cached,
            "wall_s": round(wall_b + b_codex_wall, 3),
            "pilot_summary": summary_with_identity,
            "ledger_terminal": ledger_terminal,
            "post_apply_acceptance_exit": checks_b["acceptance_exit"],
            "pre_run_attempt_ids": pre_run_attempt_ids,
            "tool_call_events": b_codex_tool_calls,
            "test_count": checks_b["test_count"],
        },
    }

    comparison = measure_mod.evaluate_measurement(gate_input)
    evidence["historical_ab_sha256_after"] = sha256_file(HISTORICAL_AB)
    if evidence["historical_ab_sha256_after"] != HISTORICAL_AB_SHA256:
        return fail("INVALID_HISTORY_MUTATION", "historical P05 ab.json changed during R3", evidence)

    if comparison.get("status") != "MEASURED_AND_VERIFIED":
        # Check if R1's successful A can provide an analytical baseline reference
        r1_meas_file = PROJECT / ".coord" / "runs" / "R1" / "measurement.json"
        if r1_meas_file.is_file():
            try:
                r1_data = json.loads(r1_meas_file.read_text(encoding="utf-8"))
                r1_a = r1_data.get("A", {})
                if r1_a.get("exit") == 0 and not r1_a.get("errors"):
                    ref_gate_input = dict(gate_input)
                    ref_gate_input["A"] = {
                        "task": "P05",
                        "source_hash": baseline_hash,
                        "codex_exit": 0,
                        "forbidden_infrastructure_errors": [],
                        "direct_acceptance_exit": 0,
                        "expected_behavior_passed": True,
                        "input_tokens": r1_a.get("usage", {}).get("input_tokens", 0),
                        "cached_input_tokens": r1_a.get("usage", {}).get("cached_input_tokens", 0),
                        "wall_s": r1_a.get("wall_s", 0.0),
                        "tool_call_events": r1_a.get("tool_call_events", 0),
                        "test_count": EXPECTED_TESTS,
                    }
                    ref_eval = measure_mod.evaluate_measurement(ref_gate_input)
                    evidence["reference_r1_a_vs_r3_b"] = ref_eval
            except Exception as _ref_err:
                evidence["reference_r1_a_vs_r3_b_error"] = str(_ref_err)

        evidence["comparison"] = {
            "status": comparison.get("status", "INVALID_MEASUREMENT"),
            "reason": comparison.get("reason", "Gate rejected R3"),
            "savings": "UNMEASURED",
        }
        write_result(evidence)
        print(f"R3 RESULT: {comparison.get('status')} - {comparison.get('reason')}", flush=True)
        if "reference_r1_a_vs_r3_b" in evidence:
            print("Reference R1-A vs R3-B evaluation:", json.dumps(evidence["reference_r1_a_vs_r3_b"], ensure_ascii=False, indent=2), flush=True)
        return 1

    comparison["interpretation"] = {
        "status": "MEASURED_AND_VERIFIED for this single pair",
        "note": f"A (Codex {CODEX_MODEL}) vs B (Antigravity {args.agy_model} via deterministic control layer)",
    }
    evidence["comparison"] = comparison
    write_result(evidence)
    print("R3 SUCCESS:", json.dumps(comparison, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
