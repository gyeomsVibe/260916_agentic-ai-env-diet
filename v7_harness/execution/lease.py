"""Lease lifecycle, fencing token progression, and stale fence validation."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from typing import Any

from v7_harness.contracts.database import (
    create_checkpoint as _db_create_checkpoint,
    create_effect as _db_create_effect,
    create_receipt as _db_create_receipt,
    validate_promotion_candidate as _db_validate_promotion_candidate,
)
from v7_harness.execution.errors import ExecutionError, StaleFenceError


def _now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def _event(connection: sqlite3.Connection, aggregate_id: str, kind: str, payload: dict[str, Any]) -> None:
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    connection.execute(
        "INSERT INTO events(aggregate_id,kind,payload_hash,created_at) VALUES(?,?,?,datetime('now'))",
        (aggregate_id, kind, digest),
    )


def ensure_resource(
    connection: sqlite3.Connection,
    *,
    resource_id: str,
    kind: str = "PATH",
    canonical_value: str | None = None,
) -> None:
    val = canonical_value or resource_id
    connection.execute(
        "INSERT OR IGNORE INTO resources(resource_id, kind, canonical_value, next_fencing_token) VALUES(?,?,?,0)",
        (resource_id, kind, val),
    )


def sweep_expired_leases(connection: sqlite3.Connection, resource_id: str | None = None) -> int:
    if resource_id:
        cursor = connection.execute(
            "UPDATE leases SET state='EXPIRED' WHERE resource_id=? AND state='ACTIVE' AND datetime(expires_at) <= datetime('now')",
            (resource_id,),
        )
    else:
        cursor = connection.execute(
            "UPDATE leases SET state='EXPIRED' WHERE state='ACTIVE' AND datetime(expires_at) <= datetime('now')"
        )
    return cursor.rowcount


def claim_lease(
    connection: sqlite3.Connection,
    *,
    lease_id: str,
    attempt_id: str,
    resource_id: str,
    owner: str,
    duration_sec: float = 30.0,
) -> int:
    """Acquire exclusive active lease, bumping resource fencing token monotonically."""
    ensure_resource(connection, resource_id=resource_id)
    sweep_expired_leases(connection, resource_id)

    active = connection.execute(
        "SELECT lease_id, owner, fencing_token FROM leases WHERE resource_id=? AND state='ACTIVE'",
        (resource_id,),
    ).fetchone()
    if active is not None:
        raise ExecutionError(f"RESOURCE_BUSY: active lease {active[0]} held by {active[1]}")

    connection.execute("UPDATE resources SET next_fencing_token=next_fencing_token+1 WHERE resource_id=?", (resource_id,))
    token_row = connection.execute("SELECT next_fencing_token FROM resources WHERE resource_id=?", (resource_id,)).fetchone()
    if token_row is None:
        raise ExecutionError("RESOURCE_NOT_FOUND")
    token = int(token_row[0])

    connection.execute(
        "INSERT INTO leases(lease_id,attempt_id,resource_id,owner,fencing_token,expires_at,state) "
        "VALUES(?,?,?,?,?,datetime('now', '+' || ? || ' seconds'),'ACTIVE')",
        (lease_id, attempt_id, resource_id, owner, token, int(duration_sec)),
    )
    _event(connection, lease_id, "LEASE_CLAIMED", {"resource_id": resource_id, "fence": token, "owner": owner})
    return token


def renew_lease(
    connection: sqlite3.Connection,
    *,
    lease_id: str,
    owner: str,
    duration_sec: float = 30.0,
) -> None:
    row = connection.execute(
        "SELECT attempt_id, resource_id, fencing_token, state FROM leases WHERE lease_id=?",
        (lease_id,),
    ).fetchone()
    if row is None or row[3] != "ACTIVE":
        raise StaleFenceError("LEASE_NOT_ACTIVE")
    assert_fence(connection, attempt_id=row[0], resource_id=row[1], token=row[2])
    connection.execute(
        "UPDATE leases SET expires_at=datetime('now', '+' || ? || ' seconds') WHERE lease_id=? AND owner=? AND state='ACTIVE'",
        (int(duration_sec), lease_id, owner),
    )
    _event(connection, lease_id, "LEASE_RENEWED", {"duration_sec": duration_sec})


def revoke_lease(connection: sqlite3.Connection, *, lease_id: str) -> None:
    connection.execute("UPDATE leases SET state='REVOKED' WHERE lease_id=? AND state='ACTIVE'", (lease_id,))
    _event(connection, lease_id, "LEASE_REVOKED", {})


def expire_lease(connection: sqlite3.Connection, *, lease_id: str) -> None:
    connection.execute("UPDATE leases SET state='EXPIRED' WHERE lease_id=? AND state='ACTIVE'", (lease_id,))
    _event(connection, lease_id, "LEASE_EXPIRED", {})


def bump_fence(connection: sqlite3.Connection, *, resource_id: str) -> int:
    ensure_resource(connection, resource_id=resource_id)
    connection.execute("UPDATE resources SET next_fencing_token=next_fencing_token+1 WHERE resource_id=?", (resource_id,))
    token = connection.execute("SELECT next_fencing_token FROM resources WHERE resource_id=?", (resource_id,)).fetchone()[0]
    _event(connection, resource_id, "FENCE_BUMPED", {"fence": token})
    return int(token)


def renew_lease_conditional(
    connection: sqlite3.Connection,
    *,
    owner: str,
    attempt_id: str,
    resource_id: str,
    fence: int,
    duration_sec: float = 30.0,
) -> bool:
    """Conditionally renew lease requiring current owner+attempt+resource+fence."""
    row = connection.execute(
        "SELECT lease_id, expires_at FROM leases WHERE attempt_id=? AND resource_id=? AND owner=? AND fencing_token=? AND state='ACTIVE'",
        (attempt_id, resource_id, owner, fence),
    ).fetchone()
    if row is None:
        return False
    is_expired = connection.execute("SELECT datetime(?) <= datetime('now')", (row[1],)).fetchone()[0]
    if is_expired:
        connection.execute(
            "UPDATE leases SET state='EXPIRED' WHERE attempt_id=? AND resource_id=? AND fencing_token=?",
            (attempt_id, resource_id, fence),
        )
        return False
    token_row = connection.execute("SELECT next_fencing_token FROM resources WHERE resource_id=?", (resource_id,)).fetchone()
    if token_row is None or token_row[0] != fence:
        return False

    lease_id = row[0]
    cursor = connection.execute(
        "UPDATE leases SET expires_at=datetime('now', '+' || ? || ' seconds') WHERE lease_id=? AND owner=? AND state='ACTIVE'",
        (int(duration_sec), lease_id, owner),
    )
    if cursor.rowcount != 1:
        return False
    _event(connection, lease_id, "LEASE_RENEWED", {"duration_sec": duration_sec, "owner": owner, "fence": fence})
    return True


def assert_fence(connection: sqlite3.Connection, *, attempt_id: str, resource_id: str, token: int) -> None:
    """Fail closed if lease is inactive, expired, or fence token has been superseded."""
    row = connection.execute(
        "SELECT expires_at FROM leases WHERE attempt_id=? AND resource_id=? AND fencing_token=? AND state='ACTIVE'",
        (attempt_id, resource_id, token),
    ).fetchone()
    if row is None:
        raise StaleFenceError("STALE_FENCE: lease not active or does not exist")

    expires_at = row[0]
    expired = connection.execute("SELECT datetime(?) <= datetime('now')", (expires_at,)).fetchone()[0]
    if expired:
        # Reject the caller's transaction first, then persist expiry in its own
        # short owner-thread transaction so the subsequent exception cannot
        # roll the EXPIRED transition back.
        if connection.in_transaction:
            connection.rollback()
        connection.execute("BEGIN IMMEDIATE")
        try:
            connection.execute(
                "UPDATE leases SET state='EXPIRED' WHERE attempt_id=? AND resource_id=? AND fencing_token=? AND state='ACTIVE'",
                (attempt_id, resource_id, token),
            )
            _event(connection, f"{attempt_id}:{resource_id}", "LEASE_EXPIRED", {"fence": token})
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        raise StaleFenceError("STALE_FENCE: lease expired")

    newest = connection.execute(
        "SELECT next_fencing_token FROM resources WHERE resource_id=?", (resource_id,)
    ).fetchone()
    if newest is None or newest[0] != token:
        raise StaleFenceError("STALE_FENCE: token superseded")



def record_checkpoint(
    connection: sqlite3.Connection,
    *,
    checkpoint_id: str,
    attempt_id: str,
    resource_id: str,
    fence: int,
    base_manifest_hash: str,
    artifact_set_hash: str,
) -> None:
    assert_fence(connection, attempt_id=attempt_id, resource_id=resource_id, token=fence)
    _db_create_checkpoint(
        connection,
        checkpoint_id=checkpoint_id,
        attempt_id=attempt_id,
        resource_id=resource_id,
        fence=fence,
        base_manifest_hash=base_manifest_hash,
        artifact_set_hash=artifact_set_hash,
    )


def record_receipt(
    connection: sqlite3.Connection,
    *,
    receipt_id: str,
    attempt_id: str,
    resource_id: str,
    fencing_token: int,
    acceptance_hash: str,
    checks_ref: str,
    verdict: str,
    signer: str,
) -> None:
    assert_fence(connection, attempt_id=attempt_id, resource_id=resource_id, token=fencing_token)
    _db_create_receipt(
        connection,
        receipt_id=receipt_id,
        attempt_id=attempt_id,
        resource_id=resource_id,
        fencing_token=fencing_token,
        acceptance_hash=acceptance_hash,
        checks_ref=checks_ref,
        verdict=verdict,
        signer=signer,
    )


def record_effect(
    connection: sqlite3.Connection,
    *,
    effect_id: str,
    attempt_id: str,
    resource_id: str,
    fencing_token: int,
    kind: str,
    idempotency_key: str | None,
    provider_ref: str | None,
    state: str,
    retryable: bool,
) -> None:
    assert_fence(connection, attempt_id=attempt_id, resource_id=resource_id, token=fencing_token)
    _db_create_effect(
        connection,
        effect_id=effect_id,
        attempt_id=attempt_id,
        resource_id=resource_id,
        fencing_token=fencing_token,
        kind=kind,
        idempotency_key=idempotency_key,
        provider_ref=provider_ref,
        state=state,
        retryable=retryable,
    )


def validate_promotion(
    connection: sqlite3.Connection,
    *,
    attempt_id: str,
    resource_id: str,
    fencing_token: int,
    acceptance_hash: str,
) -> None:
    assert_fence(connection, attempt_id=attempt_id, resource_id=resource_id, token=fencing_token)
    _db_validate_promotion_candidate(
        connection,
        attempt_id=attempt_id,
        resource_id=resource_id,
        fencing_token=fencing_token,
        acceptance_hash=acceptance_hash,
    )
