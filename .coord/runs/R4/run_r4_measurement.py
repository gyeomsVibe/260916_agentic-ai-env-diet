"""R4 Live A/B measurement driver for P06 (stats) and P07 (inventory).

Generalizes the R3 measurement harness across medium-sized tasks:
- A: Codex direct (gpt-5.6-sol, low reasoning)
- B: Deterministic control layer (gemini-3.7-flash-high) + 1-turn Codex coordinator review
- Quality Gates: Unit tests + hidden acceptance script (independent behavior verification)
- Preflight quota probe (B56 / Memo 41): Probes Codex usage limit before heavy runs
- Work-dir isolation: Strictly inside .work/
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import re
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
WORKSPACE = PROJECT / ".work"
RUN_DIR = PROJECT / ".coord" / "runs" / "R4"
SEED = WORKSPACE / "260916_pilot_sample_P05_A"

CODEX_MODEL = "gpt-5.6-sol"
CODEX_REASONING = "low"

# B57: 조율 1턴 프롬프트의 고정 접두부. 과제·실행마다 바뀌는 내용은 이 뒤에만 붙인다.
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
FALLBACK_AGY_MODEL = "gemini-3.1-pro-high"

TASK_REGISTRY: dict[str, dict[str, Any]] = {
    "P06": {
        "title": "stats 7 functions",
        "prompt_file": RUN_DIR / "P06_prompt.md",
        "accept_script": RUN_DIR / "P06_accept.py",
        "expected_marker": "P06_ACCEPT_OK",
        "min_tests": 24,  # 6 existing + 18 stats
        "expected_added": {"stats.py", "test_stats.py"},
        "expected_modified": set(),
        "expected_deleted": set(),
    },
    "P07": {
        "title": "Inventory class and CSV",
        "prompt_file": RUN_DIR / "P07_prompt.md",
        "accept_script": RUN_DIR / "P07_accept.py",
        "expected_marker": "P07_ACCEPT_OK",
        "min_tests": 26,  # 6 existing + 20 inventory
        "expected_added": {"inventory.py", "test_inventory.py"},
        "expected_modified": set(),
        "expected_deleted": set(),
    },
}


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


def run_preflight_probe() -> dict[str, Any]:
    """Runs a 1-token preflight probe to verify Codex quota before starting heavy runs."""
    codex_bin = shutil.which("codex") or "codex"
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
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    for attempt in range(1, 4):
        print(f"[*] Running Codex preflight quota probe (attempt {attempt}/3)...", flush=True)
        started_at = time.time()
        proc = subprocess.run(
            command,
            input="Reply with the single word OK.",
            text=True,
            capture_output=True,
            env=env,
            timeout=120,
        )
        finished_at = time.time()

        usage: dict[str, Any] = {}
        errors: set[str] = set()
        reset_time_str = None
        for line in proc.stdout.splitlines():
            line_lower = line.lower()
            if "usage limit" in line_lower or "quota" in line_lower:
                errors.add("USAGE_LIMIT")
                match = re.search(r"try again at\s+([0-9]{1,2}:[0-9]{2}\s*(?:AM|PM)?)", line, re.IGNORECASE)
                if match:
                    reset_time_str = match.group(1)
            try:
                ev = json.loads(line)
                for key in ("usage", "total_token_usage"):
                    if isinstance(ev.get(key), dict):
                        usage = ev[key]
            except Exception:
                pass

        if proc.returncode == 0 and not errors:
            print(f"[+] Codex preflight quota probe PASSED ({round(finished_at - started_at, 2)}s, {usage.get('input_tokens', 0)} tokens)", flush=True)
            return {
                "status": "PASS",
                "attempt": attempt,
                "wall_s": round(finished_at - started_at, 3),
                "usage": usage,
                "errors": [],
            }

        print(f"[-] Codex preflight probe failed: errors={sorted(errors)}, reset_time='{reset_time_str}'", flush=True)
        if attempt < 3:
            wait_s = 120
            if reset_time_str:
                try:
                    now = datetime.now()
                    fmt = "%I:%M %p" if ("AM" in reset_time_str.upper() or "PM" in reset_time_str.upper()) else "%H:%M"
                    t_struct = datetime.strptime(reset_time_str.strip(), fmt)
                    target = now.replace(hour=t_struct.hour, minute=t_struct.minute, second=0, microsecond=0)
                    if target < now:
                        target += timedelta(days=1)
                    wait_s = max(15, int((target - now).total_seconds()) + 120)
                except Exception as ex:
                    print(f"[*] Could not parse reset time '{reset_time_str}': {ex}", flush=True)
            print(f"[*] Waiting {wait_s}s before next preflight probe...", flush=True)
            time.sleep(wait_s)

    return {
        "status": "USAGE_LIMIT_EXHAUSTED",
        "attempt": 3,
        "wall_s": round(finished_at - started_at, 3),
        "usage": usage,
        "errors": sorted(errors),
    }


def run_codex(label: str, cwd: Path, prompt: str) -> dict[str, Any]:
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
        "-",
    ]
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    started_at = time.time()
    with events.open("w", encoding="utf-8") as stream:
        completed = subprocess.run(
            command,
            input=prompt,
            text=True,
            stdout=stream,
            stderr=subprocess.STDOUT,
            timeout=1800,
            env=env,
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


def run_codex_coordinator(label: str, summary_content: str, expected_added: set[str]) -> dict[str, Any]:
    """Execute a real 1-turn Codex coordination/judgment without tools."""
    events = RUN_DIR / f"{label}.jsonl"
    if events.exists():
        events.unlink()
    codex_bin = shutil.which("codex") or "codex"
    expected_files_str = ", ".join(sorted(expected_added))
    # B57: 캐시 적중은 프롬프트 접두부가 바이트 단위로 같을 때만 안정적이다. 고정 계약을 앞에,
    # 과제마다 달라지는 summary·기대 파일 목록을 뒤에 둔다.
    prompt = COORDINATION_PROMPT_PREFIX + (
        f"expected_changed_files: {expected_files_str}\n\n"
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
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    started_at = time.time()
    with events.open("w", encoding="utf-8") as stream:
        completed = subprocess.run(
            command,
            input=prompt,
            text=True,
            stdout=stream,
            stderr=subprocess.STDOUT,
            timeout=120,
            env=env,
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


def count_tests(sample_dir: Path) -> int:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        [sys.executable, "-m", "unittest", "-v"],
        cwd=sample_dir,
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    return len([line for line in proc.stderr.splitlines() if line.startswith("test_")])


def run_unit_tests(sample_dir: Path) -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        [sys.executable, "-m", "unittest", "-q"],
        cwd=sample_dir,
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    test_count = count_tests(sample_dir)
    return {
        "acceptance_exit": proc.returncode,
        "test_count": test_count,
        "stderr_tail": proc.stderr[-1000:],
    }


def run_hidden_acceptance(sample_dir: Path, accept_script: Path, expected_marker: str) -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        [sys.executable, str(accept_script)],
        cwd=sample_dir,
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    passed = (proc.returncode == 0) and (expected_marker in proc.stdout)
    return {
        "accept_script_exit": proc.returncode,
        "accept_script_passed": passed,
        "accept_script_stdout": proc.stdout[-1000:],
        "accept_script_stderr": proc.stderr[-1000:],
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


def read_terminal_ledger(work_dir: Path, task_id: str) -> dict[str, Any] | None:
    database = work_dir / "coord.sqlite3"
    if not database.is_file():
        return None
    connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    try:
        cursor = connection.cursor()
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
        connection.close()


def run_single_task(task_key: str, suffix: str, clean: bool, agy_model: str) -> dict[str, Any]:
    task_cfg = TASK_REGISTRY[task_key]
    title = task_cfg["title"]
    prompt_file = task_cfg["prompt_file"]
    accept_script = task_cfg["accept_script"]
    expected_marker = task_cfg["expected_marker"]
    min_tests = task_cfg["min_tests"]
    expected_added = task_cfg["expected_added"]

    sample_a = WORKSPACE / f"260916_pilot_sample_R4_{task_key}_A_{suffix}"
    sample_b = WORKSPACE / f"260916_pilot_sample_R4_{task_key}_B_{suffix}"
    pilot_work_b = WORKSPACE / f"260916_pilot_work_R4_{task_key}_B_{suffix}"
    task_id_b = f"{task_key}-R4-B-{suffix}"
    a_label = f"R4-{task_key}-A-codex-direct-{suffix}"
    b_coord_label = f"{task_id_b}-coordinator"

    RUN_DIR.mkdir(parents=True, exist_ok=True)
    result_file = RUN_DIR / f"measurement_{task_key}.json"
    attempt_result_file = RUN_DIR / f"measurement_{task_key}_attempt_{suffix}.json"

    print(f"\n{'='*70}\n[R4] Starting {task_key} ({title}) [suffix={suffix}]\n{'='*70}", flush=True)

    if clean:
        for path in (sample_a, sample_b, pilot_work_b):
            if path.exists():
                shutil.rmtree(path, ignore_errors=True)
        for ef in (RUN_DIR / f"{a_label}.jsonl", RUN_DIR / f"{b_coord_label}.jsonl"):
            if ef.exists():
                ef.unlink()

    for path in (sample_a, sample_b, pilot_work_b):
        if path.exists():
            raise RuntimeError(f"Fixture collision: {path} already exists; pass --clean to reset")

    shutil.copytree(SEED, sample_a)
    shutil.copytree(SEED, sample_b)

    baseline_a = build_manifest(sample_a)
    baseline_b = build_manifest(sample_b)
    baseline_hash = f"sha256:{baseline_a.manifest_hash}"

    evidence: dict[str, Any] = {
        "schema": "r4-measurement-v1",
        "task": task_key,
        "title": title,
        "suffix": suffix,
        "task_id_b": task_id_b,
        "models": {
            "codex": CODEX_MODEL,
            "codex_reasoning": CODEX_REASONING,
            "antigravity": agy_model,
        },
        "baseline_source_hash": baseline_hash,
        "pre_run_manifests": {
            "A": f"sha256:{baseline_a.manifest_hash}",
            "B": f"sha256:{baseline_b.manifest_hash}",
        },
    }

    # 0. Preflight quota probe
    preflight = run_preflight_probe()
    evidence["preflight"] = preflight
    if preflight["status"] != "PASS":
        evidence["comparison"] = {
            "status": "INVALID_CODEX_EXECUTION",
            "reason": f"Preflight quota probe failed: {preflight.get('errors')}",
            "savings": "UNMEASURED",
        }
        text = json.dumps(evidence, ensure_ascii=False, indent=2)
        result_file.write_text(text, encoding="utf-8")
        attempt_result_file.write_text(text, encoding="utf-8")
        return evidence

    # 1. Run A: Codex direct
    task_text = prompt_file.read_text(encoding="utf-8")
    a_prompt = task_text + "\nRun `python -m unittest -q` once after editing. Reply with one line containing the exit code."
    print(f"[1/2] Starting fresh A ({a_label})...", flush=True)
    result_a = run_codex(a_label, sample_a, a_prompt)
    checks_a = run_unit_tests(sample_a)
    hidden_a = run_hidden_acceptance(sample_a, accept_script, expected_marker)
    after_a = build_manifest(sample_a)
    changes_a = manifest_changes(baseline_a, after_a)

    evidence["A"] = {
        **result_a,
        **checks_a,
        **hidden_a,
        "task": task_key,
        "source_hash": baseline_hash,
        "changes": changes_a,
    }
    print(f"[A] Completed in {result_a['wall_s']}s (exit={result_a['exit']}, tests={checks_a['test_count']}, hidden_passed={hidden_a['accept_script_passed']})", flush=True)

    # 2. Run B: Local control layer (v7_harness.control)
    pre_run_attempt_ids = read_attempt_ids(pilot_work_b, task_id_b)
    evidence["B_pre_run_attempt_ids"] = pre_run_attempt_ids
    if pre_run_attempt_ids:
        evidence["comparison"] = {
            "status": "INVALID_STALE_RUN",
            "reason": "fresh B work-dir unexpectedly has attempts",
            "savings": "UNMEASURED",
        }
        text = json.dumps(evidence, ensure_ascii=False, indent=2)
        result_file.write_text(text, encoding="utf-8")
        attempt_result_file.write_text(text, encoding="utf-8")
        return evidence

    print(f"[2/2] Starting B ({task_id_b}) with {agy_model}...", flush=True)
    home_dir = Path.home()
    temp_dir = Path(os.environ.get("TEMP", "C:/Users/Kimyoongyeom/AppData/Local/Temp"))
    watch_roots = [home_dir, temp_dir]

    active_agy_model = agy_model
    control_config = ControlConfig(
        task_id=task_id_b,
        title=f"R4 {task_key} {suffix}",
        source_dir=sample_b,
        prompt_file=prompt_file,
        work_dir=pilot_work_b,
        agy_command=["agy"],
        accept_cmd="python -m unittest -q",
        watch_roots=watch_roots,
        timeout_s=900,
        model=active_agy_model,
    )

    started_b = time.time()
    receipt_b = run_control(control_config)
    finished_b = time.time()
    wall_b = round(finished_b - started_b, 3)

    # Memo 44 rule 4: if NO_CHANGES / REWORK, retry once with gemini-3.1-pro-high
    fallback_used = False
    if not receipt_b.get("ok"):
        print(f"[*] B resulted in non-OK status ({receipt_b.get('error_class')}). Retrying once with {FALLBACK_AGY_MODEL} as per Memo 44...", flush=True)
        fallback_used = True
        active_agy_model = FALLBACK_AGY_MODEL
        # clean sample_b and pilot_work_b
        shutil.rmtree(sample_b, ignore_errors=True)
        shutil.rmtree(pilot_work_b, ignore_errors=True)
        shutil.copytree(SEED, sample_b)
        control_config_fb = ControlConfig(
            task_id=task_id_b,
            title=f"R4 {task_key} {suffix} fb",
            source_dir=sample_b,
            prompt_file=prompt_file,
            work_dir=pilot_work_b,
            agy_command=["agy"],
            accept_cmd="python -m unittest -q",
            watch_roots=watch_roots,
            timeout_s=900,
            model=active_agy_model,
        )
        started_b = time.time()
        receipt_b = run_control(control_config_fb)
        finished_b = time.time()
        wall_b = round(finished_b - started_b, 3)

    checks_b = run_unit_tests(sample_b)
    hidden_b = run_hidden_acceptance(sample_b, accept_script, expected_marker)
    after_b = build_manifest(sample_b)
    changes_b = manifest_changes(baseline_b, after_b)

    summary_file = pilot_work_b / "runs" / task_id_b / "summary.json"
    identity_file = pilot_work_b / "runs" / task_id_b / "identity.json"
    summary_data = json.loads(summary_file.read_text(encoding="utf-8")) if summary_file.is_file() else None
    identity_data = json.loads(identity_file.read_text(encoding="utf-8")) if identity_file.is_file() else None

    ledger_terminal = read_terminal_ledger(pilot_work_b, task_id_b)
    summary_with_identity = dict(summary_data) if summary_data else {}
    if identity_data:
        summary_with_identity.update(identity_data)

    agy_usage = summary_data.get("agy_usage", {}) if summary_data else {}

    # Run B Codex coordinator 1-turn review
    print(f"[2b/2] Running B Codex coordinator 1-turn review for {task_id_b}...", flush=True)
    coord_res = run_codex_coordinator(
        b_coord_label,
        json.dumps(summary_with_identity, ensure_ascii=False, indent=2),
        expected_added,
    )
    print(f"[B Coordinator] Completed in {coord_res['wall_s']}s (exit={coord_res['exit']})", flush=True)

    receipt_dict = dict(receipt_b)
    receipt_dict["fallback_used"] = fallback_used
    receipt_dict["active_model"] = active_agy_model

    evidence["B"] = {
        "receipt": receipt_dict,
        "wall_s": wall_b,
        "antigravity_usage": agy_usage,
        "codex_coordinator": coord_res,
        **checks_b,
        **hidden_b,
        "task": task_key,
        "source_hash": baseline_hash,
        "changes": changes_b,
        "pilot_summary": summary_with_identity,
        "ledger_terminal": ledger_terminal,
        "pre_run_attempt_ids": pre_run_attempt_ids,
        "post_apply_acceptance_exit": checks_b["acceptance_exit"],
    }

    # Token Accounting
    a_usage = result_a.get("usage", {})
    b_usage = coord_res.get("usage", {})
    evidence["token_accounting"] = {
        "codex": {
            "A_input_tokens": a_usage.get("input_tokens", 0),
            "A_cached_input_tokens": a_usage.get("cached_input_tokens", 0),
            "A_noncached_tokens": a_usage.get("input_tokens", 0) - a_usage.get("cached_input_tokens", 0),
            "A_output_tokens": a_usage.get("output_tokens", 0),
            "B_coordinator_input_tokens": b_usage.get("input_tokens", 0),
            "B_coordinator_cached_tokens": b_usage.get("cached_input_tokens", 0),
            "B_coordinator_noncached_tokens": b_usage.get("input_tokens", 0) - b_usage.get("cached_input_tokens", 0),
            "B_coordinator_output_tokens": b_usage.get("output_tokens", 0),
        },
        "antigravity": {
            "A_input_tokens": 0,
            "B_worker_input_tokens": agy_usage.get("input_tokens", 0),
            "B_worker_cached_read_tokens": agy_usage.get("cache_read_tokens", 0),
            "B_worker_output_tokens": agy_usage.get("output_tokens", 0),
            "B_worker_total_tokens": agy_usage.get("total_tokens", 0),
        },
        "notes": "Gate comparison evaluates pure Codex tokens (A vs B). Antigravity worker tokens reported separately.",
    }

    # Quality Gate Verification
    a_ok = (
        result_a["exit"] == 0
        and not result_a["errors"]
        and checks_a["acceptance_exit"] == 0
        and checks_a["test_count"] >= min_tests
        and hidden_a["accept_script_passed"]
        and set(changes_a["added"]) == expected_added
        and not changes_a["modified"]
        and not changes_a["deleted"]
    )
    b_ok = (
        receipt_b.get("ok") is True
        and receipt_b.get("exit_code") == 0
        and receipt_b.get("promotion") == "APPLIED"
        and checks_b["acceptance_exit"] == 0
        and checks_b["test_count"] >= min_tests
        and hidden_b["accept_script_passed"]
        and set(changes_b["added"]) == expected_added
        and not changes_b["modified"]
        and not changes_b["deleted"]
        and coord_res["exit"] == 0
        and not coord_res["errors"]
    )

    if not a_ok or not b_ok:
        reasons = []
        if not a_ok:
            reasons.append(f"A failed quality gate (exit={result_a['exit']}, errors={result_a['errors']}, tests={checks_a['test_count']}/{min_tests}, hidden={hidden_a['accept_script_passed']})")
        if not b_ok:
            reasons.append(f"B failed quality gate (ok={receipt_b.get('ok')}, promo={receipt_b.get('promotion')}, tests={checks_b['test_count']}/{min_tests}, hidden={hidden_b['accept_script_passed']}, coord_exit={coord_res['exit']})")
        evidence["comparison"] = {
            "status": "INVALID_MEASUREMENT",
            "reason": "; ".join(reasons),
            "savings": "UNMEASURED",
        }
        text = json.dumps(evidence, ensure_ascii=False, indent=2)
        result_file.write_text(text, encoding="utf-8")
        attempt_result_file.write_text(text, encoding="utf-8")
        print(f"[-] {task_key} FAILED: {evidence['comparison']['reason']}", flush=True)
        return evidence

    # Calculate Savings
    a_in = a_usage.get("input_tokens", 0)
    a_nc = a_in - a_usage.get("cached_input_tokens", 0)
    a_out = a_usage.get("output_tokens", 0)
    b_in = b_usage.get("input_tokens", 0)
    b_nc = b_in - b_usage.get("cached_input_tokens", 0)
    b_out = b_usage.get("output_tokens", 0)
    b_wall_total = round(wall_b + coord_res["wall_s"], 3)

    in_red = round((a_in - b_in) / a_in * 100, 1) if a_in else 0.0
    nc_red = round((a_nc - b_nc) / a_nc * 100, 1) if a_nc else 0.0
    out_red = round((a_out - b_out) / a_out * 100, 1) if a_out else 0.0
    wall_red = round((result_a["wall_s"] - b_wall_total) / result_a["wall_s"] * 100, 1) if result_a["wall_s"] else 0.0

    evidence["comparison"] = {
        "status": "MEASURED_AND_VERIFIED",
        "task_identical": True,
        "starting_state_identical": True,
        "savings": {
            "wall_reduction_pct": wall_red,
            "input_token_reduction_pct": in_red,
            "noncached_input_token_reduction_pct": nc_red,
            "output_token_reduction_pct": out_red,
        },
        "codex_input_tokens": {
            "A_codex_only": a_in,
            "B_codex_one_turn": b_in,
            "reduction_pct": in_red,
        },
        "codex_wall_seconds": {
            "A_codex_only": result_a["wall_s"],
            "B_codex_one_turn": b_wall_total,
            "reduction_pct": wall_red,
        },
        "quality_gate": "PASS",
        "diagnostics": {
            "tool_call_events": {
                "A_codex_only": result_a["tool_call_events"],
                "B_codex_one_turn": coord_res["tool_call_events"],
            },
            "tests_passed": {
                "A_codex_only": checks_a["test_count"],
                "B_codex_one_turn": checks_b["test_count"],
            },
            "hidden_acceptance": {
                "A": hidden_a["accept_script_passed"],
                "B": hidden_b["accept_script_passed"],
            },
        },
        "interpretation": {
            "status": f"MEASURED_AND_VERIFIED for {task_key}",
            "note": f"A (Codex {CODEX_MODEL}) vs B (Antigravity {active_agy_model} via deterministic control layer)",
        },
    }

    text = json.dumps(evidence, ensure_ascii=False, indent=2)
    result_file.write_text(text, encoding="utf-8")
    attempt_result_file.write_text(text, encoding="utf-8")

    print(f"\n[+] {task_key} SUCCESS: MEASURED_AND_VERIFIED", flush=True)
    print(f"    Codex Input Tokens: {a_in} -> {b_in} (-{in_red}%)", flush=True)
    print(f"    Codex Output Tokens: {a_out} -> {b_out} (-{out_red}%)", flush=True)
    print(f"    Wall-clock Time: {result_a['wall_s']}s -> {b_wall_total}s (-{wall_red}%)", flush=True)
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser(description="One-shot R4 live measurement driver for P06 and P07")
    parser.add_argument("--task", choices=["P06", "P07", "all"], default="all", help="Task to measure (default: all)")
    parser.add_argument("--suffix", default="01", help="Run suffix (default: 01)")
    parser.add_argument("--clean", "-f", action="store_true", help="Clean up stale test directories for this suffix")
    parser.add_argument("--agy-model", default=DEFAULT_AGY_MODEL, help=f"Antigravity model (default: {DEFAULT_AGY_MODEL})")
    args = parser.parse_args()

    tasks_to_run = ["P06", "P07"] if args.task == "all" else [args.task]
    overall_ok = True

    for t in tasks_to_run:
        res = run_single_task(t, args.suffix, args.clean, args.agy_model)
        if res.get("comparison", {}).get("status") != "MEASURED_AND_VERIFIED":
            overall_ok = False

    return 0 if overall_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
