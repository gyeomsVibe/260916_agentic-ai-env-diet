from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9_\-\.]{20,}"),
]

REQUIRED_KEYS = (
    "schema",
    "work_id",
    "actor",
    "model",
    "kind",
    "collection_mode",
    "input_tokens",
    "output_tokens",
    "wall_time_s",
    "outcome",
    "receipt",
    "independent_verifier",
    "rsi_eligible",
    "exclusion_reason",
)

NULLABLE_KEYS = {
    "model",
    "input_tokens",
    "output_tokens",
    "wall_time_s",
    "independent_verifier",
    "exclusion_reason",
}

NON_NULLABLE_KEYS = set(REQUIRED_KEYS) - NULLABLE_KEYS

NON_EMPTY_STRING_KEYS = (
    "schema",
    "work_id",
    "actor",
    "kind",
    "collection_mode",
    "outcome",
    "receipt",
)

NULLABLE_STRING_KEYS = (
    "model",
    "independent_verifier",
    "exclusion_reason",
)


class UsageRejected(Exception):
    """Raised when a usage record fails validation or secret check."""
    pass


def _check_secrets(obj: Any) -> None:
    if isinstance(obj, str):
        for pat in SECRET_PATTERNS:
            if pat.search(obj):
                raise UsageRejected("secret detected in usage record")
    elif isinstance(obj, dict):
        for k, v in obj.items():
            _check_secrets(k)
            _check_secrets(v)
    elif isinstance(obj, (list, tuple)):
        for item in obj:
            _check_secrets(item)


def record_usage(
    project_root: Path,
    entry: dict[str, Any],
    lock_timeout_s: float = 10.0,
) -> Path:
    if not isinstance(entry, dict):
        raise UsageRejected("entry must be a dict")

    for k in REQUIRED_KEYS:
        if k not in entry:
            raise UsageRejected(f"missing required key: {k}")
        if k in NON_NULLABLE_KEYS and entry[k] is None:
            raise UsageRejected(f"key cannot be null: {k}")

    # schema validation
    if entry["schema"] != "uaos-usage-v2":
        raise UsageRejected("schema must equal 'uaos-usage-v2'")

    # non-empty string validation
    for k in NON_EMPTY_STRING_KEYS:
        val = entry[k]
        if not isinstance(val, str) or len(val.strip()) == 0:
            raise UsageRejected(f"{k} must be a non-empty string")

    # nullable string validation
    for k in NULLABLE_STRING_KEYS:
        val = entry[k]
        if val is not None and not isinstance(val, str):
            raise UsageRejected(f"{k} must be a string or null")

    # rsi_eligible validation
    if not isinstance(entry["rsi_eligible"], bool):
        raise UsageRejected("rsi_eligible must be bool")

    # token counts validation
    for token_key in ("input_tokens", "output_tokens"):
        val = entry[token_key]
        if val is not None:
            if isinstance(val, bool) or not isinstance(val, int) or val < 0:
                raise UsageRejected(f"{token_key} must be a non-negative integer or null")

    # wall_time_s validation
    wall_time = entry["wall_time_s"]
    if wall_time is not None:
        if isinstance(wall_time, bool) or not isinstance(wall_time, (int, float)) or wall_time < 0:
            raise UsageRejected("wall_time_s must be a non-negative number or null")

    # Secret check on all values/strings
    _check_secrets(entry)

    # Immutability & ts handling
    record = dict(entry)
    if "ts" not in record or record["ts"] is None:
        record["ts"] = time.time()
    elif isinstance(record["ts"], bool) or not isinstance(record["ts"], (int, float)) or record["ts"] < 0:
        raise UsageRejected("ts must be a non-negative number")

    try:
        line = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
    except (TypeError, ValueError) as err:
        raise UsageRejected(f"failed to serialize usage record: {err}") from err

    for pat in SECRET_PATTERNS:
        if pat.search(line):
            raise UsageRejected("secret detected in usage record")

    encoded = line.encode("utf-8")

    project_root = Path(project_root)
    usage_dir = project_root / ".coord" / "usage"
    usage_dir.mkdir(parents=True, exist_ok=True)
    target_file = usage_dir / "runs.jsonl"
    lock_file = usage_dir / "runs.jsonl.lock"

    t_end = time.time() + lock_timeout_s
    fd: int | None = None
    while True:
        try:
            fd = os.open(str(lock_file), os.O_CREAT | os.O_EXCL | os.O_RDWR)
            break
        except (FileExistsError, PermissionError):
            if time.time() >= t_end:
                break
            time.sleep(0.005)

    if fd is None:
        raise UsageRejected("usage ledger lock timeout")

    try:
        with open(target_file, "ab") as f:
            f.write(encoded)
            f.flush()
            os.fsync(f.fileno())
        return target_file
    finally:
        try:
            os.close(fd)
        except OSError:
            pass
        unlink_end = time.time() + 1.0
        while time.time() < unlink_end:
            try:
                os.unlink(str(lock_file))
                break
            except FileNotFoundError:
                break
            except OSError:
                time.sleep(0.002)
