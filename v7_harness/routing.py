"""U39: the worker route as a state machine — deterministic → Ollama once → Antigravity once → coordinator verdict.

The user's rule (2026-09-25): do not keep nursing an Ollama failure. Re-prompting a stateless 7B model after a
semantic failure rarely helps and every coaching round costs the coordinator paid tokens; coaching pays only when
q > C_coach / C_remote (docs/41 §2). A format-only failure is retried once by the harness at no coordinator cost,
inside the same local budget. A remote failure goes to task splitting, never back to the local model.
"""

from __future__ import annotations

from typing import Any

# docs/41 §5: P08's verified PASS used 10,031 local tokens; about 20% headroom.
LOCAL_BUDGET_TOKENS = 12_000
# The existing safety ceiling for one remote attempt, not an optimized value.
REMOTE_CAP_TOKENS = 120_000

FAILURES = ("FORMAT_ONLY", "SEMANTIC", "UNSUPPORTED", "SCOPE", "TOOL_LIMIT", "JUDGMENT_REQUIRED", "ENVIRONMENT")

# The output was the wrong shape, not the wrong answer: a mechanical retry can fix it.
_FORMAT_MARKERS = ("no file block", "EDIT_SEARCH_NOT_FOUND", "EDIT_SEARCH_AMBIGUOUS", "NO_BLOCKS", "not valid JSON",
                   "SCHEMA")
# The worker could not run the task at all within its limits.
_TOOL_LIMIT_MARKERS = ("PROMPT_TOO_LARGE", "TIMEOUT")
# Not the worker's fault: fix the machine, do not escalate to a paid worker.
_ENVIRONMENT_CLASSES = ("ACCEPT_INFRA", "ACCEPT_NOT_RUN", "SOURCE_DIVERGED", "BROKER_ALREADY_RUNNING", "DB_UNAVAILABLE",
                        "COST_EXCEEDED", "COST_UNKNOWN")


def classify_failure(summary: dict[str, Any]) -> str | None:
    """None for PASS; otherwise one of FAILURES, from the pilot summary alone (no model call)."""
    verdict = summary.get("verdict_hint")
    if verdict == "PASS":
        return None
    error_class = str(summary.get("error_class") or "")
    detail = str(summary.get("error_detail") or summary.get("message") or "")
    if error_class in _ENVIRONMENT_CLASSES:
        return "ENVIRONMENT"
    # A BLOCKED run is not the worker's fault unless the worker itself failed (the cascade rule since U17).
    if verdict == "BLOCKED" and error_class not in ("PROVIDER_ERROR", "EXECUTION_ERROR", "TIMEOUT"):
        return "ENVIRONMENT"
    if error_class == "SCOPE_VIOLATION":
        return "SCOPE"
    if any(marker in detail or marker in error_class for marker in _TOOL_LIMIT_MARKERS):
        return "TOOL_LIMIT"
    if any(marker in detail for marker in _FORMAT_MARKERS):
        return "FORMAT_ONLY"
    if "unreachable" in detail or error_class in ("PROVIDER_ERROR", "EXECUTION_ERROR"):
        return "UNSUPPORTED"
    # A failed acceptance, an unrequested deletion or a syntax error: the content was wrong.
    return "SEMANTIC"


def local_tokens(summary: dict[str, Any]) -> int:
    usage = summary.get("agy_usage") or {}
    return sum(int(usage.get(key) or 0) for key in ("input_tokens", "output_tokens")
               if isinstance(usage.get(key), int) and not isinstance(usage.get(key), bool))


def next_route(stage: str, failure: str | None, *, local_attempts: int, local_tokens: int) -> str:
    """Where the work goes next: done | local_retry | remote | split | stop."""
    if failure is None:
        return "done"
    if failure == "ENVIRONMENT":
        return "stop"
    if stage == "local":
        if failure == "FORMAT_ONLY" and local_attempts < 2 and local_tokens < LOCAL_BUDGET_TOKENS:
            return "local_retry"
        return "remote"
    if stage == "local_retry":
        return "remote"
    if stage == "remote":
        return "split"
    raise ValueError(f"unknown stage: {stage}")
