"""
Context lease validation module for v7 harness.

Context lease enforces:
- authority: APPROVED-DESIGN, FACT, INFERENCE, CLAIM, UNKNOWN, EXPIRED, UNVERIFIED
- scope: path/task patterns allowed for this context
- created_at: ISO-8601 timestamp
- expires_at: ISO-8601 timestamp (fail-closed when expired)
- supersedes: identifiers of older documents/leases invalidated by this lease
- tier: Tier 0 (always), Tier 1 (task), Tier 2 (as needed), Archive (default excluded)
"""

from __future__ import annotations

import fnmatch
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

VALID_AUTHORITIES = {
    "APPROVED-DESIGN",
    "FACT",
    "INFERENCE",
    "CLAIM",
    "UNKNOWN",
    "EXPIRED",
    "UNVERIFIED",
}

ACCEPTABLE_ACTIVE_AUTHORITIES = {
    "APPROVED-DESIGN",
    "FACT",
    "INFERENCE",
}

VALID_TIERS = {
    "Tier 0",
    "Tier 1",
    "Tier 2",
    "Archive",
}


def parse_iso_timestamp(ts_str: str) -> datetime:
    """Parse ISO-8601 timestamp, ensuring timezone-aware comparison."""
    dt = datetime.fromisoformat(ts_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


@dataclass
class ContextLease:
    lease_id: str
    document_path: str
    authority: str
    scope: list[str]
    created_at: str
    expires_at: Optional[str] = None
    supersedes: list[str] = field(default_factory=list)
    tier: str = "Tier 1"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ContextLease:
        return cls(
            lease_id=data["lease_id"],
            document_path=data["document_path"],
            authority=data["authority"],
            scope=list(data.get("scope", ["*"])),
            created_at=data["created_at"],
            expires_at=data.get("expires_at"),
            supersedes=list(data.get("supersedes", [])),
            tier=data.get("tier", "Tier 1"),
        )


@dataclass
class LeaseValidationResult:
    lease_id: str
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class ContextLeaseValidator:
    """Validates context leases against authority, expiry, scope, and supersession."""

    def __init__(self, allowed_authorities: Optional[set[str]] = None):
        self.allowed_authorities = allowed_authorities or ACCEPTABLE_ACTIVE_AUTHORITIES

    def validate_lease(
        self,
        lease: ContextLease,
        reference_time: Optional[datetime] = None,
        target_scope: Optional[str] = None,
    ) -> LeaseValidationResult:
        errors: list[str] = []
        warnings: list[str] = []

        if not lease.lease_id or not isinstance(lease.lease_id, str):
            errors.append("Missing or invalid lease_id")
        if not lease.document_path or not isinstance(lease.document_path, str):
            errors.append("Missing or invalid document_path")

        # Authority checks
        if lease.authority not in VALID_AUTHORITIES:
            errors.append(f"Unrecognized authority: '{lease.authority}'")
        elif lease.authority not in self.allowed_authorities:
            errors.append(
                f"Authority '{lease.authority}' is not acceptable for active execution (allowed: {sorted(self.allowed_authorities)})"
            )

        # Tier checks
        if lease.tier not in VALID_TIERS:
            errors.append(f"Invalid tier: '{lease.tier}'")
        elif lease.tier == "Archive":
            warnings.append("Context is marked as Archive and should not be loaded by default")

        # Created_at check
        try:
            created_dt = parse_iso_timestamp(lease.created_at)
        except (ValueError, TypeError) as exc:
            errors.append(f"Invalid created_at timestamp: {exc}")
            created_dt = None

        # Expiration check
        ref_dt = reference_time or datetime.now(timezone.utc)
        if ref_dt.tzinfo is None:
            ref_dt = ref_dt.replace(tzinfo=timezone.utc)

        if lease.expires_at:
            try:
                expires_dt = parse_iso_timestamp(lease.expires_at)
                if created_dt and expires_dt <= created_dt:
                    errors.append("expires_at must be strictly later than created_at")
                if ref_dt > expires_dt:
                    errors.append(
                        f"Lease expired at {lease.expires_at} (reference time: {ref_dt.isoformat()})"
                    )
            except (ValueError, TypeError) as exc:
                errors.append(f"Invalid expires_at timestamp: {exc}")

        # Scope check
        if target_scope is not None:
            matches_scope = any(
                fnmatch.fnmatch(target_scope, pattern) or fnmatch.fnmatch(pattern, target_scope)
                for pattern in lease.scope
            )
            if not matches_scope:
                errors.append(
                    f"Target scope '{target_scope}' does not match lease scope patterns {lease.scope}"
                )

        return LeaseValidationResult(
            lease_id=lease.lease_id,
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    def validate_lease_set(
        self,
        leases: list[ContextLease],
        reference_time: Optional[datetime] = None,
        target_scope: Optional[str] = None,
    ) -> tuple[dict[str, LeaseValidationResult], set[str]]:
        """
        Validates multiple leases and resolves superseding relationships.
        Returns a mapping of lease_id -> LeaseValidationResult, and the set of valid lease_ids.
        """
        results: dict[str, LeaseValidationResult] = {}
        lease_map = {l.lease_id: l for l in leases}

        # First pass: individual validation
        for lease in leases:
            results[lease.lease_id] = self.validate_lease(
                lease, reference_time=reference_time, target_scope=target_scope
            )

        # Second pass: superseding resolution
        # Collect all IDs/paths that are superseded by ANY lease
        superseded_ids: set[str] = set()
        for lease in leases:
            for sup in lease.supersedes:
                superseded_ids.add(sup)
                # also match by document path
                for other_id, other_lease in lease_map.items():
                    if other_lease.document_path == sup or other_id == sup:
                        superseded_ids.add(other_id)

        for lease_id in superseded_ids:
            if lease_id in results:
                results[lease_id].valid = False
                results[lease_id].errors.append(
                    f"Lease '{lease_id}' is superseded by a newer context lease"
                )

        valid_lease_ids = {lid for lid, res in results.items() if res.valid}
        return results, valid_lease_ids
