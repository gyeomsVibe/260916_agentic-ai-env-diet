"""Shared input validation for adapters (M1 P1 fixes)."""

from __future__ import annotations

import math
import re
from typing import Any, Callable

IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f\x85\u2028\u2029]")
PARTIAL_TIMEOUT_PATTERN = re.compile(r"time[d]?[\s_-]*out")


def normalize_enum(value: str, allowed: frozenset[str], field: str, error: Callable[[str], Exception]) -> str:
    normalized = str(value).strip().casefold()
    if normalized not in allowed:
        raise error(f"{field} must be one of {sorted(allowed)}: {value!r}")
    return normalized


def require_identifier(value: str, field: str, error: Callable[[str], Exception]) -> str:
    if not isinstance(value, str) or not IDENTIFIER_PATTERN.fullmatch(value):
        raise error(f"{field} is not a safe identifier: {value!r}")
    return value


def require_no_control_characters(value: str, field: str, error: Callable[[str], Exception]) -> str:
    if not isinstance(value, str) or CONTROL_CHARACTERS.search(value):
        raise error(f"{field} must not contain control characters: {value!r}")
    return value


def is_partial_timeout(stderr_text: str) -> bool:
    lowered = stderr_text.casefold()
    return "partial" in lowered and PARTIAL_TIMEOUT_PATTERN.search(lowered) is not None


def validate_usage(raw: Any) -> dict[str, int] | None:
    """Return usage as finite non-negative ints; None if any value is invalid."""
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        return None
    usage: dict[str, int] = {}
    for key, value in raw.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        if isinstance(value, float) and (not math.isfinite(value) or not value.is_integer()):
            return None
        if value < 0:
            return None
        usage[str(key)] = int(value)
    return usage
