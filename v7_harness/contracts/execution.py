"""Pure interpretation of worker evidence; exit code and prose are non-authoritative."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WorkerDecision:
    successful: bool
    result_status: str
    effect_state: str
    retryable: bool
    error_class: str


def interpret_worker_result(*, envelope_status: str, exit_code: int, response_claim: str, effect_observed: bool | None, provider_error: str | None) -> WorkerDecision:
    """Treat structured envelope/effect evidence as stronger than exit/prose claims."""
    del exit_code, response_claim
    error_class = "TRANSIENT_CAPACITY" if provider_error and ("503" in provider_error or "capacity" in provider_error.lower()) else ("NONE" if envelope_status == "SUCCEEDED" else "UNKNOWN")
    if envelope_status != "SUCCEEDED":
        effect_state = "CONFIRMED" if effect_observed is True else "NONE" if effect_observed is False else "UNKNOWN"
        return WorkerDecision(False, "NEEDS_RECONCILIATION" if effect_state == "UNKNOWN" else "ERROR", effect_state, False if effect_state == "UNKNOWN" else error_class == "TRANSIENT_CAPACITY", error_class)
    if effect_observed is None:
        return WorkerDecision(False, "NEEDS_RECONCILIATION", "UNKNOWN", False, error_class)
    return WorkerDecision(True, "SUCCEEDED", "CONFIRMED" if effect_observed else "NONE", False, error_class)
