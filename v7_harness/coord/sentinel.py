"""U23 S3: Local Sentinel - Deterministic Health Checks, Triage, and Wake-on-P1 Gatekeeper.

Operates at 0 paid API token cost. Deterministic rules decide actionable state;
local models can summarize/triage but cannot approve, delete, or suppress a required alert.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from .mailbox import Mailbox
from .adapter import sync_stream_to_mailbox


def _is_pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        import ctypes
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        SYNCHRONIZE = 0x00100000
        handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE, False, pid)
        if not handle:
            return False
        exit_code = ctypes.c_ulong()
        if ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            ctypes.windll.kernel32.CloseHandle(handle)
            return exit_code.value == 259
        ctypes.windll.kernel32.CloseHandle(handle)
        return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False


def check_quiet_lock(project_root: Path, max_age_s: float = 3600.0) -> dict[str, Any]:
    lock_file = project_root / ".work" / "QUIET_LOCK"
    if not lock_file.is_file():
        return {"status": "CLEAN", "is_stale": False, "lock_data": None}

    try:
        raw = lock_file.read_text(encoding="utf-8")
        data = json.loads(raw)
    except Exception:
        return {"status": "STALE", "is_stale": True, "reason": "CORRUPTED_LOCK_FILE", "lock_data": None}

    raw_started = data.get("started_at", 0)
    try:
        started_at = float(raw_started)
    except (ValueError, TypeError):
        try:
            from datetime import datetime
            started_at = datetime.fromisoformat(str(raw_started)).timestamp()
        except Exception:
            started_at = 0.0
    pid = int(data.get("pid", 0))
    age = time.time() - started_at

    if age > max_age_s:
        return {"status": "STALE", "is_stale": True, "reason": f"AGE_EXCEEDED ({age:.1f}s > {max_age_s}s)", "lock_data": data}

    if not _is_pid_alive(pid):
        return {"status": "STALE", "is_stale": True, "reason": f"DEAD_PROCESS (pid={pid})", "lock_data": data}

    return {"status": "ACTIVE", "is_stale": False, "lock_data": data}


def check_ledger_reconciliation(pilot_dir: Path) -> list[str]:
    runs_dir = pilot_dir / "runs"
    if not runs_dir.is_dir():
        return []

    needs_reconcile = []
    for item in runs_dir.iterdir():
        if item.is_dir():
            summary_file = item / "summary.json"
            if summary_file.is_file():
                try:
                    data = json.loads(summary_file.read_text(encoding="utf-8"))
                    verdict = data.get("verdict_hint", "")
                    if verdict in ("NEEDS_RECONCILIATION", "UNKNOWN"):
                        needs_reconcile.append(item.name)
                except Exception:
                    needs_reconcile.append(item.name)
    return sorted(needs_reconcile)


def triage_failure(error_log: str, staging: Path | None = None) -> dict[str, Any]:
    from ..accept_triage import _CODE, _INFRA

    for pat in _CODE:
        if pat.search(error_log):
            return {"classification": "CODE", "is_p1": False, "summary": "Code defect detected"}

    for pat in _INFRA:
        if pat.search(error_log):
            return {"classification": "INFRA", "is_p1": True, "summary": "Infrastructure defect detected"}

    return {"classification": "UNKNOWN", "is_p1": False, "summary": "Unclassified failure"}


def generate_briefing(project_root: Path, box: Mailbox | None = None, max_lines: int = 60, max_bytes: int = 6144) -> str:
    lock_info = check_quiet_lock(project_root)
    lines = [
        "# Sentinel Briefing",
        "",
        f"- Status: Lock={lock_info['status']}",
    ]
    if lock_info["is_stale"]:
        lines.append(f"  Warning: Lock is STALE ({lock_info.get('reason')})")

    if box is not None:
        items = box.list_inbox()
        lines.append(f"- Mailbox Inbox: {len(items)} messages pending")

    pilot_dir = project_root / ".coord" / "pilot"
    reconciles = check_ledger_reconciliation(pilot_dir)
    if reconciles:
        lines.append(f"- Unreconciled Tasks: {', '.join(reconciles)}")
    else:
        lines.append("- Unreconciled Tasks: None")

    briefing = "\n".join(lines[:max_lines]) + "\n"
    encoded = briefing.encode("utf-8")
    if len(encoded) > max_bytes:
        briefing = encoded[:max_bytes].decode("utf-8", errors="ignore")
    return briefing


def run_sentinel_cycle(project_root: Path, box: Mailbox, recipient: str = "codex") -> dict[str, Any]:
    import hashlib

    t0 = time.time()
    lock_info = check_quiet_lock(project_root)
    pilot_dir = project_root / ".coord" / "pilot"
    reconcile_tasks = check_ledger_reconciliation(pilot_dir)

    try:
        sync_stream_to_mailbox(project_root, box)
    except Exception:
        pass

    p1_reasons: list[str] = []
    p1_events: list[dict[str, Any]] = []
    if lock_info["is_stale"]:
        reason_code = str(lock_info.get("reason", "STALE")).split(" (", 1)[0]
        p1_reasons.append(f"STALE_LOCK: {reason_code}")
        p1_events.append(
            {
                "kind": "stale_lock",
                "reason": reason_code,
                "lock_data": lock_info.get("lock_data"),
            }
        )
    if reconcile_tasks:
        stable_tasks = sorted(reconcile_tasks)
        p1_reasons.append(f"NEEDS_RECONCILIATION: {','.join(stable_tasks)}")
        p1_events.append({"kind": "needs_reconciliation", "tasks": stable_tasks})

    for msg_id in box.list_inbox():
        claimed = box.claim(msg_id, consumer_id="sentinel_probe")
        if claimed:
            payload = claimed.payload
            box.nack(claimed)
            if not isinstance(payload, dict):
                continue
            expires_at = payload.get("expires_at")
            if (
                isinstance(expires_at, (int, float))
                and not isinstance(expires_at, bool)
                and float(expires_at) <= t0
            ):
                continue
            if payload.get("kind") == "BLOCKED" or payload.get("is_p1"):
                p1_reasons.append(f"BLOCKED_TASK: {payload.get('step')}")
                p1_events.append(
                    {
                        "kind": "mailbox_p1",
                        "message_id": msg_id,
                        "payload": payload,
                    }
                )

    p1_wake_emitted = False
    if p1_events:
        canonical = json.dumps(
            {"recipient": recipient, "events": p1_events},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        event_fingerprint = hashlib.sha256(canonical).hexdigest()
        wake_id = f"wake_{event_fingerprint[:24]}"
        wake_name = f"{wake_id}.json"
        already_recorded = (box.inbox_dir / wake_name).is_file() or (box.ack_dir / wake_name).is_file()
        if not already_recorded:
            box.publish(
                message_id=wake_id,
                payload={
                    "recipient": recipient,
                    "p1_alert": True,
                    "wake_reason": "; ".join(p1_reasons),
                    "event_fingerprint": event_fingerprint,
                    "actor": "sentinel",
                },
            )
            p1_wake_emitted = True

    wall_time_s = time.time() - t0
    return {
        "wall_time_s": wall_time_s,
        "paid_api_calls": 0,
        "p1_wake_emitted": p1_wake_emitted,
        "lock_status": lock_info["status"],
        "reconcile_tasks": reconcile_tasks,
    }
