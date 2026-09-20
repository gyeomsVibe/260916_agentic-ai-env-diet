"""Minimal deterministic local control layer for v7 harness.

Removes nested Codex helper calls from the critical path and provides
fail-closed validation of pilot execution, independent ledger identity,
approval replay, and post-apply acceptance.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import shlex
import sqlite3
import subprocess
import sys
import time
import gc
import warnings
from typing import Any, Callable, Sequence

from v7_harness.isolation.manifest import build_manifest


@dataclass
class ControlConfig:
    task_id: str
    title: str
    source_dir: Path
    prompt_file: Path
    work_dir: Path
    agy_command: list[str]
    accept_cmd: str
    watch_roots: list[Path]
    timeout_s: int | float = 30
    model: str | None = None


def _make_receipt(
    *,
    ok: bool,
    exit_code: int,
    error_class: str | None,
    task_id: str,
    run_id: str | None = None,
    source_hash: str | None = None,
    bundle_id: str | None = None,
    promotion: str | None = None,
    post_acceptance_exit: int | None = None,
    pilot_invocations: int = 0,
    approval_invocations: int = 0,
    error_detail: str | None = None,
) -> dict[str, Any]:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ResourceWarning)
        gc.collect()
    receipt: dict[str, Any] = {
        "ok": ok,
        "exit_code": exit_code,
        "error_class": error_class,
        "task_id": task_id,
        "run_id": run_id,
        "source_hash": source_hash,
        "bundle_id": bundle_id,
        "promotion": promotion,
        "post_acceptance_exit": post_acceptance_exit,
        "pilot_invocations": pilot_invocations,
        "approval_invocations": approval_invocations,
    }
    if error_detail is not None:
        receipt["error_detail"] = error_detail
    return receipt


def run_control(
    config: ControlConfig,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, Any]:
    sub_env = os.environ.copy()
    project_root = str(Path(__file__).resolve().parent.parent)
    existing_pp = sub_env.get("PYTHONPATH", "")
    if project_root not in existing_pp:
        sub_env["PYTHONPATH"] = f"{project_root}{os.pathsep}{existing_pp}" if existing_pp else project_root

    def _invoke(argv: list[str]) -> subprocess.CompletedProcess[str]:
        kwargs: dict[str, Any] = {
            "cwd": str(source_dir),
            "capture_output": True,
            "text": True,
            "timeout": config.timeout_s,
        }
        if runner is subprocess.run:
            kwargs["env"] = sub_env
        return runner(argv, **kwargs)

    # 1. Preflight freshness and validation
    work_dir = Path(config.work_dir)
    if work_dir.exists():
        return _make_receipt(
            ok=False,
            exit_code=1,
            error_class="WORK_DIR_NOT_FRESH",
            task_id=config.task_id,
            error_detail=f"Work directory already exists: {work_dir}",
        )

    source_dir = Path(config.source_dir)
    if not config.task_id or not source_dir.is_dir() or not Path(config.prompt_file).is_file():
        return _make_receipt(
            ok=False,
            exit_code=1,
            error_class="INVALID_INPUTS",
            task_id=config.task_id,
            error_detail="Invalid task_id, source_dir, or prompt_file",
        )

    start_boundary = time.time()
    source_manifest = build_manifest(source_dir)
    source_hash = f"sha256:{source_manifest.manifest_hash}"

    # 2. Build pilot run command
    pilot_argv = [
        sys.executable,
        "-m",
        "v7_harness.cli",
        "pilot",
        "run",
        "--task",
        config.task_id,
        "--source",
        str(source_dir),
        "--prompt-file",
        str(config.prompt_file),
        "--title",
        config.title,
        "--work-dir",
        str(work_dir),
    ]
    if config.accept_cmd:
        pilot_argv.extend(["--accept-cmd", config.accept_cmd])
    for w in config.watch_roots:
        pilot_argv.extend(["--watch-root", str(w)])
    if config.agy_command:
        pilot_argv.append("--agy-command")
        pilot_argv.extend(config.agy_command)
    if config.timeout_s:
        pilot_argv.extend(["--print-timeout", str(int(config.timeout_s))])
    if config.model:
        pilot_argv.extend(["--model", config.model])

    pilot_invocations = 0
    approval_invocations = 0

    # 3. Spawn pilot run
    try:
        pilot_invocations += 1
        proc = _invoke(pilot_argv)
    except FileNotFoundError:
        return _make_receipt(
            ok=False,
            exit_code=1,
            error_class="PILOT_NOT_STARTED",
            task_id=config.task_id,
            source_hash=source_hash,
            pilot_invocations=pilot_invocations,
        )
    except subprocess.TimeoutExpired:
        return _make_receipt(
            ok=False,
            exit_code=124,
            error_class="PILOT_TIMEOUT",
            task_id=config.task_id,
            source_hash=source_hash,
            pilot_invocations=pilot_invocations,
        )
    except Exception as exc:
        return _make_receipt(
            ok=False,
            exit_code=1,
            error_class="PILOT_NOT_STARTED",
            task_id=config.task_id,
            source_hash=source_hash,
            pilot_invocations=pilot_invocations,
            error_detail=str(exc),
        )

    combined_output = (proc.stdout or "") + "\n" + (proc.stderr or "")
    if "helper_unknown_error" in combined_output or "helper_failure" in combined_output.lower():
        return _make_receipt(
            ok=False,
            exit_code=1,
            error_class="HELPER_FAILURE",
            task_id=config.task_id,
            source_hash=source_hash,
            pilot_invocations=pilot_invocations,
        )

    if proc.returncode != 0:
        return _make_receipt(
            ok=False,
            exit_code=proc.returncode,
            error_class="PILOT_FAILED",
            task_id=config.task_id,
            source_hash=source_hash,
            pilot_invocations=pilot_invocations,
            error_detail=((proc.stderr or "") + "\n" + (proc.stdout or ""))[-1000:],
        )

    # 4. Read summary.json exactly once
    summary_path = work_dir / "runs" / config.task_id / "summary.json"
    if not summary_path.is_file():
        return _make_receipt(
            ok=False,
            exit_code=1,
            error_class="SUMMARY_MISSING",
            task_id=config.task_id,
            source_hash=source_hash,
            pilot_invocations=pilot_invocations,
        )

    try:
        summary_raw = summary_path.read_text(encoding="utf-8")
        summary = json.loads(summary_raw)
    except Exception:
        return _make_receipt(
            ok=False,
            exit_code=1,
            error_class="SUMMARY_INVALID",
            task_id=config.task_id,
            source_hash=source_hash,
            pilot_invocations=pilot_invocations,
        )

    if not isinstance(summary, dict):
        return _make_receipt(
            ok=False,
            exit_code=1,
            error_class="SUMMARY_INVALID",
            task_id=config.task_id,
            source_hash=source_hash,
            pilot_invocations=pilot_invocations,
        )

    # Validate all required summary fields before proceeding
    if (
        summary.get("state") != "SUCCEEDED"
        or summary.get("verdict_hint") != "PASS"
        or summary.get("promotion") != "DRY_RUN_PASSED"
        or summary.get("acceptance_exit") != 0
    ):
        return _make_receipt(
            ok=False,
            exit_code=1,
            error_class="SUMMARY_INVALID",
            task_id=config.task_id,
            source_hash=source_hash,
            pilot_invocations=pilot_invocations,
        )

    if summary.get("effect_state") == "UNKNOWN":
        return _make_receipt(
            ok=False,
            exit_code=1,
            error_class="UNKNOWN_EFFECT",
            task_id=config.task_id,
            source_hash=source_hash,
            pilot_invocations=pilot_invocations,
        )

    changed_files = summary.get("changed_files")
    if not isinstance(changed_files, list) or not changed_files:
        return _make_receipt(
            ok=False,
            exit_code=1,
            error_class="SUMMARY_INVALID",
            task_id=config.task_id,
            source_hash=source_hash,
            pilot_invocations=pilot_invocations,
        )
    for p in changed_files:
        if not isinstance(p, str) or not p:
            return _make_receipt(
                ok=False,
                exit_code=1,
                error_class="SUMMARY_INVALID",
                task_id=config.task_id,
                source_hash=source_hash,
                pilot_invocations=pilot_invocations,
            )
        path_obj = Path(p)
        if path_obj.is_absolute() or ".." in path_obj.parts or path_obj.drive:
            return _make_receipt(
                ok=False,
                exit_code=1,
                error_class="SUMMARY_INVALID",
                task_id=config.task_id,
                source_hash=source_hash,
                pilot_invocations=pilot_invocations,
            )
    if len(changed_files) != len(set(changed_files)):
        return _make_receipt(
            ok=False,
            exit_code=1,
            error_class="SUMMARY_INVALID",
            task_id=config.task_id,
            source_hash=source_hash,
            pilot_invocations=pilot_invocations,
        )

    bundle_id = summary.get("bundle_id")
    if not bundle_id or not isinstance(bundle_id, str) or len(bundle_id) != 64:
        return _make_receipt(
            ok=False,
            exit_code=1,
            error_class="SUMMARY_INVALID",
            task_id=config.task_id,
            source_hash=source_hash,
            pilot_invocations=pilot_invocations,
        )

    # 5. Read identity.json and SQLite ledger independently
    identity_path = work_dir / "runs" / config.task_id / "identity.json"
    if not identity_path.is_file():
        return _make_receipt(
            ok=False,
            exit_code=1,
            error_class="IDENTITY_MISSING",
            task_id=config.task_id,
            source_hash=source_hash,
            bundle_id=bundle_id,
            pilot_invocations=pilot_invocations,
        )

    try:
        identity = json.loads(identity_path.read_text(encoding="utf-8"))
    except Exception:
        return _make_receipt(
            ok=False,
            exit_code=1,
            error_class="IDENTITY_INVALID",
            task_id=config.task_id,
            source_hash=source_hash,
            bundle_id=bundle_id,
            pilot_invocations=pilot_invocations,
        )

    if identity.get("task_id") != config.task_id:
        return _make_receipt(
            ok=False,
            exit_code=1,
            error_class="TASK_ID_MISMATCH",
            task_id=config.task_id,
            source_hash=source_hash,
            bundle_id=bundle_id,
            pilot_invocations=pilot_invocations,
        )

    run_id = identity.get("run_id")
    if identity.get("source_hash") != source_hash:
        return _make_receipt(
            ok=False,
            exit_code=1,
            error_class="SOURCE_ID_MISMATCH",
            task_id=config.task_id,
            run_id=run_id,
            source_hash=source_hash,
            bundle_id=bundle_id,
            pilot_invocations=pilot_invocations,
        )

    if identity.get("bundle_id") != bundle_id:
        return _make_receipt(
            ok=False,
            exit_code=1,
            error_class="BUNDLE_ID_MISMATCH",
            task_id=config.task_id,
            run_id=run_id,
            source_hash=source_hash,
            bundle_id=bundle_id,
            pilot_invocations=pilot_invocations,
        )

    db_path = work_dir / "coord.sqlite3"
    if not db_path.is_file():
        return _make_receipt(
            ok=False,
            exit_code=1,
            error_class="STALE_LEDGER",
            task_id=config.task_id,
            run_id=run_id,
            source_hash=source_hash,
            bundle_id=bundle_id,
            pilot_invocations=pilot_invocations,
        )

    if db_path.stat().st_mtime < start_boundary - 2.0:
        return _make_receipt(
            ok=False,
            exit_code=1,
            error_class="STALE_LEDGER",
            task_id=config.task_id,
            run_id=run_id,
            source_hash=source_hash,
            bundle_id=bundle_id,
            pilot_invocations=pilot_invocations,
        )

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        cursor = conn.cursor()
        attempt_rows = cursor.execute(
            "SELECT attempt_id, state FROM attempts WHERE task_id = ?",
            (config.task_id,),
        ).fetchall()
        if len(attempt_rows) != 1:
            return _make_receipt(
                ok=False,
                exit_code=1,
                error_class="STALE_LEDGER",
                task_id=config.task_id,
                run_id=run_id,
                source_hash=source_hash,
                bundle_id=bundle_id,
                pilot_invocations=pilot_invocations,
            )

        ledger_run_id, ledger_state = attempt_rows[0]
        if ledger_run_id != run_id:
            return _make_receipt(
                ok=False,
                exit_code=1,
                error_class="RUN_ID_MISMATCH",
                task_id=config.task_id,
                run_id=run_id,
                source_hash=source_hash,
                bundle_id=bundle_id,
                pilot_invocations=pilot_invocations,
            )

        if ledger_state != "SUCCEEDED":
            return _make_receipt(
                ok=False,
                exit_code=1,
                error_class="STALE_LEDGER",
                task_id=config.task_id,
                run_id=run_id,
                source_hash=source_hash,
                bundle_id=bundle_id,
                pilot_invocations=pilot_invocations,
            )

        chk_row = cursor.execute(
            "SELECT base_manifest_hash, artifact_set_hash FROM checkpoints WHERE attempt_id = ?",
            (run_id,),
        ).fetchone()
        if not chk_row:
            return _make_receipt(
                ok=False,
                exit_code=1,
                error_class="STALE_LEDGER",
                task_id=config.task_id,
                run_id=run_id,
                source_hash=source_hash,
                bundle_id=bundle_id,
                pilot_invocations=pilot_invocations,
            )

        base_hash, artifact_hash = chk_row
        if base_hash != source_manifest.manifest_hash:
            return _make_receipt(
                ok=False,
                exit_code=1,
                error_class="SOURCE_ID_MISMATCH",
                task_id=config.task_id,
                run_id=run_id,
                source_hash=source_hash,
                bundle_id=bundle_id,
                pilot_invocations=pilot_invocations,
            )

        if artifact_hash != bundle_id:
            return _make_receipt(
                ok=False,
                exit_code=1,
                error_class="BUNDLE_ID_MISMATCH",
                task_id=config.task_id,
                run_id=run_id,
                source_hash=source_hash,
                bundle_id=bundle_id,
                pilot_invocations=pilot_invocations,
            )
    except Exception as exc:
        return _make_receipt(
            ok=False,
            exit_code=1,
            error_class="STALE_LEDGER",
            task_id=config.task_id,
            run_id=run_id,
            source_hash=source_hash,
            bundle_id=bundle_id,
            pilot_invocations=pilot_invocations,
            error_detail=str(exc),
        )
    finally:
        conn.close()

    # 6. Approval replay
    approval_argv = list(pilot_argv) + ["--approve", bundle_id]
    try:
        approval_invocations += 1
        appr_proc = _invoke(approval_argv)
    except Exception as exc:
        return _make_receipt(
            ok=False,
            exit_code=1,
            error_class="APPROVAL_FAILED",
            task_id=config.task_id,
            run_id=run_id,
            source_hash=source_hash,
            bundle_id=bundle_id,
            pilot_invocations=pilot_invocations,
            approval_invocations=approval_invocations,
            error_detail=str(exc),
        )

    appr_combined = (appr_proc.stdout or "") + "\n" + (appr_proc.stderr or "")
    if "helper_unknown_error" in appr_combined or "helper_failure" in appr_combined.lower():
        return _make_receipt(
            ok=False,
            exit_code=1,
            error_class="HELPER_FAILURE",
            task_id=config.task_id,
            run_id=run_id,
            source_hash=source_hash,
            bundle_id=bundle_id,
            pilot_invocations=pilot_invocations,
            approval_invocations=approval_invocations,
        )

    if appr_proc.returncode != 0:
        return _make_receipt(
            ok=False,
            exit_code=appr_proc.returncode,
            error_class="APPROVAL_FAILED",
            task_id=config.task_id,
            run_id=run_id,
            source_hash=source_hash,
            bundle_id=bundle_id,
            pilot_invocations=pilot_invocations,
            approval_invocations=approval_invocations,
        )

    try:
        appr_data = json.loads(appr_proc.stdout)
    except Exception:
        return _make_receipt(
            ok=False,
            exit_code=1,
            error_class="APPROVAL_INVALID",
            task_id=config.task_id,
            run_id=run_id,
            source_hash=source_hash,
            bundle_id=bundle_id,
            pilot_invocations=pilot_invocations,
            approval_invocations=approval_invocations,
        )

    if (
        appr_data.get("promotion") == "APPROVAL_MISMATCH"
        or appr_data.get("bundle_id") != bundle_id
        or appr_data.get("state") != "SUCCEEDED"
        or appr_data.get("verdict_hint") != "PASS"
        or appr_data.get("effect_state") == "UNKNOWN"
    ):
        return _make_receipt(
            ok=False,
            exit_code=1,
            error_class="APPROVAL_MISMATCH",
            task_id=config.task_id,
            run_id=run_id,
            source_hash=source_hash,
            bundle_id=bundle_id,
            pilot_invocations=pilot_invocations,
            approval_invocations=approval_invocations,
        )

    if appr_data.get("promotion") != "APPLIED":
        return _make_receipt(
            ok=False,
            exit_code=1,
            error_class="PASS_WITHOUT_APPLIED",
            task_id=config.task_id,
            run_id=run_id,
            source_hash=source_hash,
            bundle_id=bundle_id,
            pilot_invocations=pilot_invocations,
            approval_invocations=approval_invocations,
        )

    post_manifest = build_manifest(source_dir)
    pre_map = {e.path: e for e in source_manifest.entries}
    post_map = {e.path: e for e in post_manifest.entries}

    observed_changed_paths = set()
    for p, e in post_map.items():
        if p not in pre_map or pre_map[p] != e:
            observed_changed_paths.add(p)
    for p in pre_map:
        if p not in post_map:
            observed_changed_paths.add(p)

    if not observed_changed_paths:
        return _make_receipt(
            ok=False,
            exit_code=1,
            error_class="APPLY_NOT_OBSERVED",
            task_id=config.task_id,
            run_id=run_id,
            source_hash=source_hash,
            bundle_id=bundle_id,
            pilot_invocations=pilot_invocations,
            approval_invocations=approval_invocations,
        )

    declared_changed_paths = set(changed_files)
    if observed_changed_paths != declared_changed_paths:
        return _make_receipt(
            ok=False,
            exit_code=1,
            error_class="APPLY_MISMATCH",
            task_id=config.task_id,
            run_id=run_id,
            source_hash=source_hash,
            bundle_id=bundle_id,
            pilot_invocations=pilot_invocations,
            approval_invocations=approval_invocations,
        )

    # 7. Independent post-apply acceptance against source_dir
    accept_tokens = [t.strip('"') for t in shlex.split(config.accept_cmd, posix=False)]
    try:
        post_proc = _invoke(accept_tokens)
    except Exception as exc:
        return _make_receipt(
            ok=False,
            exit_code=1,
            error_class="POST_APPLY_ACCEPTANCE_FAILED",
            task_id=config.task_id,
            run_id=run_id,
            source_hash=source_hash,
            bundle_id=bundle_id,
            promotion="APPLIED",
            post_acceptance_exit=1,
            pilot_invocations=pilot_invocations,
            approval_invocations=approval_invocations,
            error_detail=str(exc),
        )

    if post_proc.returncode != 0:
        return _make_receipt(
            ok=False,
            exit_code=post_proc.returncode,
            error_class="POST_APPLY_ACCEPTANCE_FAILED",
            task_id=config.task_id,
            run_id=run_id,
            source_hash=source_hash,
            bundle_id=bundle_id,
            promotion="APPLIED",
            post_acceptance_exit=post_proc.returncode,
            pilot_invocations=pilot_invocations,
            approval_invocations=approval_invocations,
        )

    return _make_receipt(
        ok=True,
        exit_code=0,
        error_class=None,
        task_id=config.task_id,
        run_id=run_id,
        source_hash=source_hash,
        bundle_id=bundle_id,
        promotion="APPLIED",
        post_acceptance_exit=0,
        pilot_invocations=pilot_invocations,
        approval_invocations=approval_invocations,
    )
