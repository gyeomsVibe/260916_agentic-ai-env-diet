"""SQLite DDL v1 and transaction contracts for U10 tests only."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import PurePath
from typing import Any


class MigrationError(RuntimeError):
    pass


DDL_V1 = r"""
CREATE TABLE IF NOT EXISTS schema_migrations (
  version INTEGER PRIMARY KEY, checksum TEXT NOT NULL UNIQUE,
  applied_at TEXT NOT NULL, app_version TEXT NOT NULL
);
CREATE TABLE capabilities (
  actor TEXT PRIMARY KEY, schema_version INTEGER NOT NULL, cli_version TEXT NOT NULL,
  help_hash TEXT NOT NULL CHECK(length(help_hash)=64 AND help_hash NOT GLOB '*[^0-9A-Fa-f]*'), features_json TEXT NOT NULL,
  storage_kind TEXT NOT NULL CHECK(storage_kind IN ('LOCAL','NETWORK','SYNC','REMOVABLE','UNKNOWN')),
  probed_at TEXT NOT NULL, expires_at TEXT NOT NULL
);
CREATE TABLE plans (
  task_id TEXT PRIMARY KEY, card_revision INTEGER NOT NULL CHECK(card_revision>=0),
  status TEXT NOT NULL, depends_json TEXT NOT NULL, acceptance_hash TEXT NOT NULL CHECK(length(acceptance_hash)=64 AND acceptance_hash NOT GLOB '*[^0-9A-Fa-f]*'),
  source_kind TEXT NOT NULL DEFAULT 'PLAN_CARD' CHECK(source_kind='PLAN_CARD')
);
CREATE TABLE attempts (
  attempt_id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES plans(task_id),
  parent_task_id TEXT, call_depth INTEGER NOT NULL DEFAULT 0 CHECK(call_depth>=0),
  max_hops INTEGER NOT NULL CHECK(max_hops>=0 AND call_depth<=max_hops),
  state TEXT NOT NULL CHECK(state IN ('PENDING','RUNNING','VERIFYING','SUCCEEDED','FAILED','NEEDS_RECONCILIATION')),
  idempotency_key TEXT NOT NULL UNIQUE
);
CREATE TABLE resources (
  resource_id TEXT PRIMARY KEY, kind TEXT NOT NULL CHECK(kind IN ('PATH','PORT','DB','CACHE','ARTIFACT','ENV','EXTERNAL')),
  canonical_value TEXT NOT NULL, next_fencing_token INTEGER NOT NULL DEFAULT 0 CHECK(next_fencing_token>=0),
  UNIQUE(kind, canonical_value)
);
CREATE TABLE leases (
  lease_id TEXT PRIMARY KEY, attempt_id TEXT NOT NULL REFERENCES attempts(attempt_id),
  resource_id TEXT NOT NULL REFERENCES resources(resource_id), owner TEXT NOT NULL,
  fencing_token INTEGER NOT NULL CHECK(fencing_token>0), expires_at TEXT NOT NULL,
  state TEXT NOT NULL CHECK(state IN ('ACTIVE','RELEASED','EXPIRED','REVOKED'))
);
CREATE UNIQUE INDEX one_active_lease_per_resource ON leases(resource_id) WHERE state='ACTIVE';
CREATE UNIQUE INDEX unique_resource_fence ON leases(resource_id, fencing_token);
CREATE TABLE deliveries (
  delivery_id TEXT PRIMARY KEY, direction TEXT NOT NULL CHECK(direction IN ('INBOX','OUTBOX')),
  dedupe_key TEXT NOT NULL UNIQUE, payload_ref TEXT NOT NULL, state TEXT NOT NULL CHECK(state IN ('PENDING','CLAIMED','ACKED','DEAD')),
  available_at TEXT NOT NULL, claimed_by TEXT, result_hash TEXT, acked_at TEXT
);
CREATE TABLE events (
  event_id INTEGER PRIMARY KEY AUTOINCREMENT, aggregate_id TEXT NOT NULL, kind TEXT NOT NULL,
  payload_hash TEXT NOT NULL CHECK(length(payload_hash)=64 AND payload_hash NOT GLOB '*[^0-9A-Fa-f]*'), created_at TEXT NOT NULL
);
CREATE TRIGGER events_no_update BEFORE UPDATE ON events BEGIN SELECT RAISE(ABORT, 'events are append-only'); END;
CREATE TRIGGER events_no_delete BEFORE DELETE ON events BEGIN SELECT RAISE(ABORT, 'events are append-only'); END;
CREATE TABLE artifacts (
  artifact_id TEXT PRIMARY KEY, attempt_id TEXT NOT NULL REFERENCES attempts(attempt_id),
  relative_path TEXT NOT NULL CHECK(relative_path<>'' AND substr(relative_path,1,1)<>'/' AND instr(relative_path,':')=0 AND instr('/'||replace(relative_path,'\\','/')||'/','/../')=0),
  size INTEGER NOT NULL CHECK(size>=0), sha256 TEXT NOT NULL CHECK(length(sha256)=64 AND sha256 NOT GLOB '*[^0-9A-Fa-f]*'), media_type TEXT NOT NULL
);
CREATE TABLE checkpoints (
  checkpoint_id TEXT PRIMARY KEY, attempt_id TEXT NOT NULL REFERENCES attempts(attempt_id),
  resource_id TEXT NOT NULL REFERENCES resources(resource_id), base_manifest_hash TEXT NOT NULL CHECK(length(base_manifest_hash)=64 AND base_manifest_hash NOT GLOB '*[^0-9A-Fa-f]*'),
  artifact_set_hash TEXT NOT NULL CHECK(length(artifact_set_hash)=64 AND artifact_set_hash NOT GLOB '*[^0-9A-Fa-f]*'), fence INTEGER NOT NULL CHECK(fence>0)
);
CREATE TABLE receipts (
  receipt_id TEXT PRIMARY KEY, attempt_id TEXT NOT NULL REFERENCES attempts(attempt_id),
  resource_id TEXT NOT NULL REFERENCES resources(resource_id), fencing_token INTEGER NOT NULL CHECK(fencing_token>0),
  acceptance_hash TEXT NOT NULL CHECK(length(acceptance_hash)=64 AND acceptance_hash NOT GLOB '*[^0-9A-Fa-f]*'), checks_ref TEXT NOT NULL,
  verdict TEXT NOT NULL CHECK(verdict IN ('PASS','FAIL')), signer TEXT NOT NULL
);
CREATE TABLE effects (
  effect_id TEXT PRIMARY KEY, attempt_id TEXT NOT NULL REFERENCES attempts(attempt_id),
  resource_id TEXT NOT NULL REFERENCES resources(resource_id), fencing_token INTEGER NOT NULL CHECK(fencing_token>0),
  kind TEXT NOT NULL, idempotency_key TEXT UNIQUE, provider_ref TEXT,
  state TEXT NOT NULL CHECK(state IN ('INTENDED','CONFIRMED','UNKNOWN','RECONCILED','FAILED')),
  retryable INTEGER NOT NULL CHECK(retryable IN (0,1)),
  CHECK(state<>'UNKNOWN' OR retryable=0)
);
CREATE TABLE budgets (
  scope_id TEXT NOT NULL, provider TEXT NOT NULL, turns INTEGER NOT NULL DEFAULT 0 CHECK(turns>=0),
  tokens INTEGER CHECK(tokens IS NULL OR tokens>=0), elapsed_ms INTEGER NOT NULL DEFAULT 0 CHECK(elapsed_ms>=0),
  quota_state TEXT NOT NULL CHECK(quota_state IN ('AVAILABLE','EXHAUSTED','UNKNOWN')), PRIMARY KEY(scope_id,provider)
);
CREATE TABLE circuits (
  provider TEXT NOT NULL, failure_class TEXT NOT NULL, state TEXT NOT NULL CHECK(state IN ('CLOSED','OPEN','HALF_OPEN')),
  opened_at TEXT, retry_after TEXT, PRIMARY KEY(provider,failure_class)
);
CREATE TABLE conversations (
  task_id TEXT NOT NULL REFERENCES plans(task_id), tool TEXT NOT NULL, conversation_id TEXT NOT NULL,
  last_confirmed_turn INTEGER NOT NULL DEFAULT 0 CHECK(last_confirmed_turn>=0), PRIMARY KEY(task_id,tool)
);
"""

DDL_V2 = r"""
CREATE TABLE execution_budget_usage (
  scope_id TEXT NOT NULL, provider TEXT NOT NULL,
  attempts INTEGER NOT NULL CHECK(attempts>=0),
  elapsed_ms INTEGER NOT NULL CHECK(elapsed_ms>=0),
  turns INTEGER NOT NULL CHECK(turns>=0),
  tokens INTEGER NOT NULL CHECK(tokens>=0),
  tool_calls INTEGER NOT NULL CHECK(tool_calls>=0),
  PRIMARY KEY(scope_id, provider)
);
CREATE TABLE execution_stage_events (
  stage_event_id INTEGER PRIMARY KEY AUTOINCREMENT,
  delivery_id TEXT NOT NULL REFERENCES deliveries(delivery_id),
  attempt_id TEXT NOT NULL REFERENCES attempts(attempt_id),
  stage TEXT NOT NULL CHECK(stage IN ('SUBMITTED','CLAIMED','WORKER_FINISHED','ACKED','REPLAYED','FAILED','NEEDS_RECONCILIATION')),
  state TEXT NOT NULL,
  monotonic_ns INTEGER NOT NULL CHECK(monotonic_ns>=0),
  created_at TEXT NOT NULL
);
CREATE INDEX execution_stage_delivery_order ON execution_stage_events(delivery_id, stage_event_id);
"""


@dataclass(frozen=True)
class Migration:
    version: int
    sql: str
    checksum: str


def _checksum(sql: str) -> str:
    return hashlib.sha256(sql.encode("utf-8")).hexdigest()


MIGRATIONS = (
    Migration(1, DDL_V1, _checksum(DDL_V1)),
    Migration(2, DDL_V2, _checksum(DDL_V2)),
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def apply_migrations(connection: sqlite3.Connection, *, app_version: str = "0.1.0") -> None:
    """Apply checksum-pinned forward migrations. Re-application is idempotent."""
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, checksum TEXT NOT NULL UNIQUE, applied_at TEXT NOT NULL, app_version TEXT NOT NULL)"
    )
    applied = dict(connection.execute("SELECT version, checksum FROM schema_migrations"))
    known_versions = {migration.version for migration in MIGRATIONS}
    if set(applied) - known_versions:
        raise MigrationError("database schema is newer than this app")
    for migration in MIGRATIONS:
        if migration.version in applied:
            if applied[migration.version] != migration.checksum:
                raise MigrationError(f"migration checksum mismatch for v{migration.version}")
            continue
        if applied and migration.version <= max(applied):
            raise MigrationError("down or out-of-order migration refused")
        try:
            connection.executescript("BEGIN IMMEDIATE;\n" + migration.sql)
            connection.execute(
                "INSERT INTO schema_migrations(version,checksum,applied_at,app_version) VALUES(?,?,?,?)",
                (migration.version, migration.checksum, _now(), app_version),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise


def _event(connection: sqlite3.Connection, aggregate_id: str, kind: str, payload: dict[str, Any]) -> None:
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    connection.execute(
        "INSERT INTO events(aggregate_id,kind,payload_hash,created_at) VALUES(?,?,?,?)",
        (aggregate_id, kind, digest, _now()),
    )


def _assert_current_fence(connection: sqlite3.Connection, attempt_id: str, resource_id: str, token: int) -> None:
    row = connection.execute(
        "SELECT 1 FROM leases WHERE attempt_id=? AND resource_id=? AND fencing_token=? AND state='ACTIVE'",
        (attempt_id, resource_id, token),
    ).fetchone()
    newest = connection.execute("SELECT next_fencing_token FROM resources WHERE resource_id=?", (resource_id,)).fetchone()
    if row is None or newest is None or newest[0] != token:
        raise ValueError("STALE_FENCE")


def claim_lease(connection: sqlite3.Connection, *, lease_id: str, attempt_id: str, resource_id: str, owner: str, expires_at: str) -> int:
    with connection:
        connection.execute("UPDATE resources SET next_fencing_token=next_fencing_token+1 WHERE resource_id=?", (resource_id,))
        token_row = connection.execute("SELECT next_fencing_token FROM resources WHERE resource_id=?", (resource_id,)).fetchone()
        if token_row is None:
            raise ValueError("unknown resource")
        connection.execute(
            "INSERT INTO leases(lease_id,attempt_id,resource_id,owner,fencing_token,expires_at,state) VALUES(?,?,?,?,?,?,'ACTIVE')",
            (lease_id, attempt_id, resource_id, owner, token_row[0], expires_at),
        )
        _event(connection, lease_id, "LEASE_CLAIMED", {"resource_id": resource_id, "fence": token_row[0]})
    return int(token_row[0])


def create_checkpoint(connection: sqlite3.Connection, *, checkpoint_id: str, attempt_id: str, resource_id: str, fence: int, base_manifest_hash: str, artifact_set_hash: str) -> None:
    with connection:
        _assert_current_fence(connection, attempt_id, resource_id, fence)
        connection.execute("INSERT INTO checkpoints VALUES(?,?,?,?,?,?)", (checkpoint_id, attempt_id, resource_id, base_manifest_hash, artifact_set_hash, fence))
        _event(connection, checkpoint_id, "CHECKPOINT_CREATED", {"fence": fence})


def create_receipt(connection: sqlite3.Connection, *, receipt_id: str, attempt_id: str, resource_id: str, fencing_token: int, acceptance_hash: str, checks_ref: str, verdict: str, signer: str) -> None:
    with connection:
        _assert_current_fence(connection, attempt_id, resource_id, fencing_token)
        connection.execute("INSERT INTO receipts VALUES(?,?,?,?,?,?,?,?)", (receipt_id, attempt_id, resource_id, fencing_token, acceptance_hash, checks_ref, verdict, signer))
        _event(connection, receipt_id, "RECEIPT_RECORDED", {"verdict": verdict, "fence": fencing_token})


def create_effect(connection: sqlite3.Connection, *, effect_id: str, attempt_id: str, resource_id: str, fencing_token: int, kind: str, idempotency_key: str | None, provider_ref: str | None, state: str, retryable: bool) -> None:
    with connection:
        _assert_current_fence(connection, attempt_id, resource_id, fencing_token)
        connection.execute("INSERT INTO effects VALUES(?,?,?,?,?,?,?,?,?)", (effect_id, attempt_id, resource_id, fencing_token, kind, idempotency_key, provider_ref, state, int(retryable)))
        _event(connection, effect_id, "EFFECT_RECORDED", {"state": state, "fence": fencing_token})


def ack_delivery(connection: sqlite3.Connection, *, delivery_id: str, result_hash: str) -> None:
    with connection:
        row = connection.execute("SELECT state,result_hash FROM deliveries WHERE delivery_id=?", (delivery_id,)).fetchone()
        if row is None:
            raise ValueError("unknown delivery")
        if row[0] == "ACKED":
            if row[1] != result_hash:
                raise ValueError("ACK_RESULT_CONFLICT")
            return
        if row[0] != "CLAIMED":
            raise ValueError("DELIVERY_NOT_PROCESSED")
        _event(connection, delivery_id, "DELIVERY_PROCESSED", {"result_hash": result_hash})
        connection.execute("UPDATE deliveries SET state='ACKED',result_hash=?,acked_at=? WHERE delivery_id=?", (result_hash, _now(), delivery_id))


def mark_attempt_succeeded(connection: sqlite3.Connection, *, attempt_id: str, acceptance_hash: str) -> None:
    receipt = connection.execute(
        "SELECT 1 FROM receipts WHERE attempt_id=? AND acceptance_hash=? AND verdict='PASS'",
        (attempt_id, acceptance_hash),
    ).fetchone()
    unresolved_effect = connection.execute(
        "SELECT 1 FROM effects WHERE attempt_id=? AND state IN ('INTENDED','UNKNOWN','FAILED')",
        (attempt_id,),
    ).fetchone()
    if receipt is None:
        raise ValueError("PASS_RECEIPT_REQUIRED")
    if unresolved_effect is not None:
        raise ValueError("EFFECT_RECONCILIATION_REQUIRED")
    with connection:
        connection.execute("UPDATE attempts SET state='SUCCEEDED' WHERE attempt_id=?", (attempt_id,))
        _event(connection, attempt_id, "ATTEMPT_SUCCEEDED", {"acceptance_hash": acceptance_hash})


def validate_promotion_candidate(connection: sqlite3.Connection, *, attempt_id: str, resource_id: str, fencing_token: int, acceptance_hash: str) -> None:
    """Fail closed unless the current fence, PASS receipt, and effects permit promotion."""
    _assert_current_fence(connection, attempt_id, resource_id, fencing_token)
    receipt = connection.execute(
        "SELECT 1 FROM receipts WHERE attempt_id=? AND resource_id=? AND fencing_token=? AND acceptance_hash=? AND verdict='PASS'",
        (attempt_id, resource_id, fencing_token, acceptance_hash),
    ).fetchone()
    if receipt is None:
        raise ValueError("PASS_RECEIPT_REQUIRED")
    unresolved = connection.execute(
        "SELECT 1 FROM effects WHERE attempt_id=? AND state IN ('INTENDED','UNKNOWN','FAILED')",
        (attempt_id,),
    ).fetchone()
    if unresolved is not None:
        raise ValueError("EFFECT_RECONCILIATION_REQUIRED")


def validate_artifact_reference(relative_path: str, sha256: str) -> bool:
    normalized = relative_path.replace("\\", "/")
    path = PurePath(normalized)
    return bool(relative_path) and not path.is_absolute() and ":" not in relative_path and ".." not in path.parts and len(sha256) == 64
