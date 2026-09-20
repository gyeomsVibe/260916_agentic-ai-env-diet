"""One-shot R1 P05 A/B measurement with fresh identities and fail-closed evidence gates."""

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
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from v7_harness.isolation.manifest import DeterministicManifest, build_manifest


PROJECT = _PROJECT_ROOT
WORKSPACE = PROJECT / ".work"  # user rule: only the project folder at workspace root
RUN_DIR = PROJECT / ".coord" / "runs" / "R1"
PROMPT_FILE = PROJECT / ".coord" / "runs" / "P05" / "prompt.md"
HISTORICAL_AB = PROJECT / ".coord" / "runs" / "P05" / "ab.json"
SEED_A = WORKSPACE / "260916_pilot_sample_P05_A"
SEED_B = WORKSPACE / "260916_pilot_sample_P05_B"
SAMPLE_A = WORKSPACE / "260916_pilot_sample_R1_P05_A_20260919_01"
SAMPLE_B = WORKSPACE / "260916_pilot_sample_R1_P05_B_20260919_01"
PILOT_WORK = WORKSPACE / "260916_pilot_work_R1_P05_B_20260919_01"
TASK_ID = "P05-R1-B-20260919-01"
A_LABEL = "R1-P05-A-codex-direct-20260919-01"
CODEX_MODEL = "gpt-5.6-sol"
CODEX_REASONING = "low"
AGY_MODEL = "gemini-3.7-flash-high"
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
        lower = raw.lower()
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
        raise RuntimeError(f"measurement pollution: event file already exists: {events}")
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
    with events.open("x", encoding="utf-8") as stream:
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
            "SELECT attempt_id FROM attempts WHERE task_id=? OR task_id LIKE ? ORDER BY rowid",
            (task_id, f"{task_id}-%"),
        ).fetchall()
        return [row[0] for row in rows if row and row[0]]
    finally:
        connection.close()


def read_terminal_ledger(work_dir: Path, task_id: str) -> dict[str, Any] | None:
    database = work_dir / "coord.sqlite3"
    if not database.is_file():
        return None
    connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    try:
        row = connection.execute(
            "SELECT attempt_id, state, idempotency_key FROM attempts WHERE task_id=? ORDER BY rowid DESC LIMIT 1",
            (task_id,),
        ).fetchone()
        if not row:
            return None
        attempt_id, attempt_state, idempotency_key = row
        checkpoint = connection.execute(
            "SELECT base_manifest_hash, artifact_set_hash FROM checkpoints WHERE attempt_id=? ORDER BY rowid DESC LIMIT 1",
            (attempt_id,),
        ).fetchone()
        lease = connection.execute(
            "SELECT state FROM leases WHERE attempt_id=? ORDER BY rowid DESC LIMIT 1", (attempt_id,)
        ).fetchone()
        delivery = connection.execute(
            "SELECT state FROM deliveries WHERE dedupe_key=? ORDER BY rowid DESC LIMIT 1", (idempotency_key,)
        ).fetchone()
        return {
            "task_id": task_id,
            "run_id": attempt_id,
            "source_hash": f"sha256:{checkpoint[0]}" if checkpoint else None,
            "bundle_id": checkpoint[1] if checkpoint else None,
            "attempt_state": attempt_state,
            "delivery_state": delivery[0] if delivery else "UNKNOWN",
            "lease_state": lease[0] if lease else "UNKNOWN",
        }
    finally:
        connection.close()


def write_result(data: dict[str, Any]) -> None:
    temporary = RESULT_FILE.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(RESULT_FILE)


def fail(status: str, reason: str, evidence: dict[str, Any]) -> int:
    evidence["comparison"] = {"status": status, "reason": reason, "savings": "UNMEASURED"}
    write_result(evidence)
    print(json.dumps(evidence["comparison"], ensure_ascii=False, indent=2), flush=True)
    return 2


def main() -> int:
    if RESULT_FILE.exists():
        raise RuntimeError(f"measurement pollution: result already exists: {RESULT_FILE}")
    for path in (SAMPLE_A, SAMPLE_B, PILOT_WORK):
        if path.exists():
            raise RuntimeError(f"measurement pollution: fresh path already exists: {path}")
    if sha256_file(HISTORICAL_AB) != HISTORICAL_AB_SHA256:
        raise RuntimeError("historical P05 ab.json hash changed before R1")

    seed_a_manifest = build_manifest(SEED_A)
    seed_b_manifest = build_manifest(SEED_B)
    if seed_a_manifest.manifest_hash != seed_b_manifest.manifest_hash:
        raise RuntimeError("preserved P05 seeds no longer have identical manifests")
    if {entry.path for entry in seed_a_manifest.entries} != EXPECTED_FILES:
        raise RuntimeError("preserved seed file set is not the fixed two-file P05 baseline")

    SAMPLE_A.mkdir()
    SAMPLE_B.mkdir()
    for name in sorted(EXPECTED_FILES):
        shutil.copy2(SEED_A / name, SAMPLE_A / name)
        shutil.copy2(SEED_A / name, SAMPLE_B / name)
    baseline_a = build_manifest(SAMPLE_A)
    baseline_b = build_manifest(SAMPLE_B)
    baseline_hash = f"sha256:{baseline_a.manifest_hash}"
    evidence: dict[str, Any] = {
        "schema": "r1-p05-measurement-v1",
        "task": "P05",
        "task_id_b": TASK_ID,
        "models": {"codex": CODEX_MODEL, "codex_reasoning": CODEX_REASONING, "antigravity": AGY_MODEL},
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

    task_text = PROMPT_FILE.read_text(encoding="utf-8")
    a_prompt = task_text + "\nRun `python -m unittest -q` once after editing. Reply with one line containing the exit code."
    print("[1/2] Starting fresh A (Codex direct)", flush=True)
    result_a = run_codex(A_LABEL, SAMPLE_A, a_prompt, [])
    checks_a = direct_checks(SAMPLE_A)
    after_a = build_manifest(SAMPLE_A)
    changes_a = manifest_changes(baseline_a, after_a)
    evidence["A"] = {
        **result_a,
        **checks_a,
        "task": "P05",
        "source_hash": baseline_hash,
        "changes": changes_a,
    }
    if result_a["exit"] != 0 or result_a["errors"]:
        return fail("INVALID_CODEX_EXECUTION", f"A failed: exit={result_a['exit']} errors={result_a['errors']}", evidence)
    if checks_a["acceptance_exit"] != 0 or checks_a["behavior_exit"] != 0 or checks_a["test_count"] != EXPECTED_TESTS:
        return fail("INVALID_ACCEPTANCE", f"A checks failed: {checks_a}", evidence)
    if set(changes_a["modified"]) != EXPECTED_FILES or changes_a["added"] or changes_a["deleted"]:
        return fail("INVALID_SCOPE", f"A changed files are invalid: {changes_a}", evidence)

    pre_run_attempt_ids = read_attempt_ids(PILOT_WORK, TASK_ID)
    evidence["B_pre_run_attempt_ids"] = pre_run_attempt_ids
    if pre_run_attempt_ids:
        return fail("INVALID_STALE_RUN", "fresh B work-dir unexpectedly has attempts", evidence)

    pilot_command = (
        f'python -m v7_harness.cli pilot run --task {TASK_ID} --source "{SAMPLE_B}" '
        f'--prompt-file "{PROMPT_FILE}" --title "R1 P05 power reciprocal" '
        f'--accept-cmd "python -m unittest -q" --work-dir "{PILOT_WORK}" --model {AGY_MODEL}'
    )
    summary_path = PILOT_WORK / "runs" / TASK_ID / "summary.json"
    b_prompt = (
        f"[{TASK_ID}] Use the project SQLite pilot only. Run this command exactly once and wait for completion; do not poll:\n"
        f"{pilot_command}\n"
        f"Read {summary_path} exactly once. Approve only if verdict_hint is PASS and changed_files is exactly "
        "calc.py and test_calc.py; approve by replaying the identical command once with `--approve <bundle_id>`. "
        "That approval replay must not execute the worker again. Otherwise do not approve. Do not use Antigravity Bridge, "
        "do not weaken HOME/TEMP watches, and do not inspect unrelated files. Reply with one line: verdict, promotion, bundle."
    )
    print("[2/2] Starting fresh B (Codex one-turn SQLite pilot)", flush=True)
    result_b = run_codex(
        f"{TASK_ID}-controller",
        PROJECT,
        b_prompt,
        [SAMPLE_B, PILOT_WORK, Path.home().resolve()],
    )
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.is_file() else None
    identity_path = PILOT_WORK / "runs" / TASK_ID / "identity.json"
    identity = json.loads(identity_path.read_text(encoding="utf-8")) if identity_path.is_file() else None
    if summary is not None and identity is not None:
        summary_with_identity = {**summary, **identity}
    else:
        summary_with_identity = summary or identity
    ledger = read_terminal_ledger(PILOT_WORK, TASK_ID)
    checks_b = direct_checks(SAMPLE_B)
    after_b = build_manifest(SAMPLE_B)
    changes_b = manifest_changes(baseline_b, after_b)
    evidence["B"] = {
        **result_b,
        **checks_b,
        "task": "P05",
        "source_hash": baseline_hash,
        "changes": changes_b,
        "pre_run_attempt_ids": pre_run_attempt_ids,
        "pilot_summary": summary_with_identity,
        "ledger_terminal": ledger,
        "post_apply_acceptance_exit": checks_b["acceptance_exit"],
    }

    if result_b["exit"] != 0 or result_b["errors"]:
        return fail("INVALID_CODEX_EXECUTION", f"B controller failed: exit={result_b['exit']} errors={result_b['errors']}", evidence)
    if checks_b["acceptance_exit"] != 0 or checks_b["behavior_exit"] != 0 or checks_b["test_count"] != EXPECTED_TESTS:
        return fail("INVALID_ACCEPTANCE", f"B checks failed: {checks_b}", evidence)
    if set(changes_b["modified"]) != EXPECTED_FILES or changes_b["added"] or changes_b["deleted"]:
        return fail("INVALID_SCOPE", f"B changed files are invalid: {changes_b}", evidence)

    from importlib.util import module_from_spec, spec_from_file_location

    measure_path = PROJECT / ".coord" / "runs" / "measure_p05.py"
    spec = spec_from_file_location("r1_measure_gate", measure_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load fixed R0 evaluator")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    usage_a = result_a.get("usage", {})
    usage_b = result_b.get("usage", {})
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
            "codex_exit": result_b["exit"],
            "forbidden_infrastructure_errors": result_b["errors"],
            "direct_acceptance_exit": checks_b["acceptance_exit"],
            "expected_behavior_passed": checks_b["behavior_exit"] == 0 and checks_b["test_count"] == EXPECTED_TESTS,
            "input_tokens": usage_b.get("input_tokens", 0),
            "cached_input_tokens": usage_b.get("cached_input_tokens", 0),
            "wall_s": result_b["wall_s"],
            "pilot_summary": summary_with_identity,
            "ledger_terminal": ledger,
            "post_apply_acceptance_exit": checks_b["acceptance_exit"],
            "pre_run_attempt_ids": pre_run_attempt_ids,
            "tool_call_events": result_b["tool_call_events"],
            "test_count": checks_b["test_count"],
        },
    }
    comparison = module.evaluate_measurement(gate_input)
    if comparison.get("status") != "MEASURED_AND_VERIFIED":
        return fail(comparison.get("status", "INVALID_MEASUREMENT"), comparison.get("reason", "R0 gate rejected R1"), evidence)

    comparison["interpretation"] = {
        "codex_metrics": "MEASURED_AND_VERIFIED for this single pair",
        "cross_provider_total_cost": "UNMEASURED",
        "reason": "Antigravity and Codex tokens have no fixed common price/cost basis; order and cache asymmetry remain.",
    }
    evidence["comparison"] = comparison
    evidence["historical_ab_sha256_after"] = sha256_file(HISTORICAL_AB)
    if evidence["historical_ab_sha256_after"] != HISTORICAL_AB_SHA256:
        return fail("INVALID_HISTORY_MUTATION", "historical P05 ab.json changed during R1", evidence)
    write_result(evidence)
    print(json.dumps(comparison, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
