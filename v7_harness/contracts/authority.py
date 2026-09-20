"""Pure Authority Matrix validation; never writes PLAN or task cards."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AuthorityDecision:
    allowed: bool
    code: str
    reason: str


def validate_authority(
    *,
    plan_revision: int,
    projected_revision: int,
    plan_acceptance_hash: str,
    projected_acceptance_hash: str,
    requested_operation: str,
) -> AuthorityDecision:
    if requested_operation in {"DB_WRITE_PLAN", "DB_RENDER_PLAN", "DB_OVERWRITE_CARD"}:
        return AuthorityDecision(False, "AUTHORITY_CONFLICT", "execution projection cannot write plan authority")
    if projected_revision != plan_revision:
        return AuthorityDecision(False, "AUTHORITY_CONFLICT", "card revision differs from DB projection")
    if projected_acceptance_hash != plan_acceptance_hash:
        return AuthorityDecision(False, "AUTHORITY_CONFLICT", "acceptance hash differs from DB projection")
    return AuthorityDecision(True, "COMPATIBLE", "projection matches plan authority")

