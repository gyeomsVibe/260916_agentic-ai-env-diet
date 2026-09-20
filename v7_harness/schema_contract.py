"""
Capability, schema contract, and DB invariants module for v9 architecture.
Standard library only, zero external dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, IntEnum
import hashlib
import json
import sqlite3
from typing import Any, Optional


# =====================================================================
# Authority Matrix
# =====================================================================

class AuthorityLevel(IntEnum):
    """
    Authority hierarchy defined in docs/13 Section 4.
    Lower numerical value indicates higher authority priority.
    """
    PLATFORM_USER = 1         # Platform policies & latest user prompt
    PROJECT_RULES = 2         # AGENTS.override.md / AGENTS.md
    ORCHESTRATION_DESIGN = 3  # docs/01_unified-agent-orchestration-design.md
    PLAN_CARD = 4             # .coord/PLAN.md and task cards
    RUNTIME_LEDGER = 5        # SQLite event ledger & execution projections
    DERIVED_MANIFEST = 6      # Generated manifest / consensus
    EXTERNAL_UNVERIFIED = 7   # Model output, GitHub issues, Reddit


class AuthorityConflictError(Exception):
    """Raised when lower authority attempts to override higher authority."""
    pass


class AuthorityMatrixValidator:
    """Pure validator for Authority Matrix invariants."""

    @staticmethod
    def can_override(actor: AuthorityLevel, target: AuthorityLevel) -> bool:
        """Actor can override target if actor has equal or higher authority (actor <= target)."""
        return int(actor) <= int(target)

    @classmethod
    def assert_can_override(cls, actor: AuthorityLevel, target: AuthorityLevel, context: str = "") -> None:
        if not cls.can_override(actor, target):
            msg = (
                f"Authority violation in '{context}': Actor {actor.name} (level {int(actor)}) "
                f"cannot override or dictate {target.name} (level {int(target)})."
            )
            raise AuthorityConflictError(msg)


# =====================================================================
# Exceptions for Contract & Invariants
# =====================================================================

class ContractError(Exception):
    """Base exception for schema contract errors."""
    pass


class MigrationError(ContractError):
    """Base exception for database migrations."""
    pass


class MigrationChecksumMismatchError(MigrationError):
    """Raised when migration script hash does not match applied migration hash."""
    pass


class DownMigrationDisallowedError(MigrationError):
    """Raised when down-migration or non-forward migration is attempted."""
    pass


class StaleFencingTokenError(ContractError):
    """Raised when a stale fencing token is used for checkpoint, receipt, or effect."""
    pass


class UnknownEffectRetryDisallowedError(ContractError):
    """Raised when automated retry is attempted on UNKNOWN/NEEDS_RECONCILIATION effect."""
    pass


class IncompatibleCapabilityError(ContractError):
    """Raised when an actor's capabilities do not satisfy the required contract."""
    pass


# =====================================================================
# Versioned JSON Schemas & Pure Validators
# =====================================================================

COMMAND_SCHEMA_V1 = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "CoordinationCommandV1",
    "type": "object",
    "required": ["version", "command_id", "task_id", "idempotency_key", "action", "payload", "timestamp"],
    "properties": {
        "version": {"type": "string", "enum": ["1.0.0"]},
        "command_id": {"type": "string"},
        "task_id": {"type": "string"},
        "idempotency_key": {"type": "string"},
        "action": {"type": "string", "enum": ["diagnose", "plan", "delegate", "ask-codex", "render", "verify"]},
        "payload": {"type": "object"},
        "timestamp": {"type": "string"}
    }
}

ENVELOPE_SCHEMA_V1 = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "ExecutionEnvelopeV1",
    "type": "object",
    "required": [
        "version", "envelope_id", "task_id", "attempt_id", "fencing_token",
        "call_depth", "max_hops", "mode", "caller", "callee", "budget", "payload"
    ],
    "properties": {
        "version": {"type": "string", "enum": ["1.0.0"]},
        "envelope_id": {"type": "string"},
        "task_id": {"type": "string"},
        "attempt_id": {"type": "string"},
        "fencing_token": {"type": "integer", "minimum": 1},
        "call_depth": {"type": "integer", "minimum": 0},
        "max_hops": {"type": "integer", "minimum": 1},
        "mode": {"type": "string", "enum": ["managed", "standalone", "imported"]},
        "caller": {"type": "string"},
        "callee": {"type": "string"},
        "budget": {
            "type": "object",
            "required": ["max_elapsed_ms", "max_tokens", "max_turns"],
            "properties": {
                "max_elapsed_ms": {"type": "integer", "minimum": 1},
                "max_tokens": {"type": "integer", "minimum": 1},
                "max_turns": {"type": "integer", "minimum": 1}
            }
        },
        "payload": {"type": "object"}
    }
}

RESULT_SCHEMA_V1 = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "ExecutionResultV1",
    "type": "object",
    "required": [
        "version", "task_id", "attempt_id", "fencing_token", "state", "result_ref",
        "changed_files", "checks", "risks", "spec_change_requests", "next",
        "usage", "evidence_path"
    ],
    "properties": {
        "version": {"type": "string", "enum": ["1.0.0"]},
        "task_id": {"type": "string"},
        "attempt_id": {"type": "string"},
        "fencing_token": {"type": "integer", "minimum": 1},
        "state": {"type": "string", "enum": ["succeeded", "failed", "timeout", "wait", "blocked"]},
        "result_ref": {"type": "string"},
        "changed_files": {"type": "array", "items": {"type": "string"}},
        "checks": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["cmd", "exit"],
                "properties": {
                    "cmd": {"type": "string"},
                    "exit": {"type": "integer"}
                }
            }
        },
        "risks": {"type": "array", "items": {"type": "string"}},
        "spec_change_requests": {"type": "array", "items": {"type": "string"}},
        "next": {"type": "string"},
        "usage": {
            "type": "object",
            "required": ["input_tokens", "output_tokens"],
            "properties": {
                "input_tokens": {"type": "integer", "minimum": 0},
                "output_tokens": {"type": "integer", "minimum": 0}
            }
        },
        "evidence_path": {"type": "string"}
    }
}

CAPABILITY_SCHEMA_V1 = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "ActorCapabilityV1",
    "type": "object",
    "required": ["version", "actor", "cli_version", "help_hash", "features", "probed_at", "expires_at"],
    "properties": {
        "version": {"type": "string", "enum": ["1.0.0"]},
        "actor": {"type": "string", "enum": ["codex", "antigravity"]},
        "cli_version": {"type": "string"},
        "help_hash": {"type": "string"},
        "features": {"type": "array", "items": {"type": "string"}},
        "probed_at": {"type": "string"},
        "expires_at": {"type": "string"}
    }
}


def _validate_primitive(val: Any, expected_type: str) -> bool:
    if expected_type == "string":
        return isinstance(val, str)
    if expected_type == "integer":
        return isinstance(val, int) and not isinstance(val, bool)
    if expected_type == "object":
        return isinstance(val, dict)
    if expected_type == "array":
        return isinstance(val, list)
    return True


def validate_command_v1(data: dict) -> tuple[bool, list[str]]:
    """Validate data against COMMAND_SCHEMA_V1 without external dependencies."""
    errors = []
    if not isinstance(data, dict):
        return False, ["Input must be a JSON object"]

    for req in COMMAND_SCHEMA_V1["required"]:
        if req not in data:
            errors.append(f"Missing required field: '{req}'")

    if data.get("version") != "1.0.0":
        errors.append("Field 'version' must be '1.0.0'")

    if "action" in data and data["action"] not in COMMAND_SCHEMA_V1["properties"]["action"]["enum"]:
        errors.append(f"Invalid action '{data['action']}'")

    for field_name in ["command_id", "task_id", "idempotency_key", "timestamp"]:
        if field_name in data and not isinstance(data[field_name], str):
            errors.append(f"Field '{field_name}' must be a string")

    if "payload" in data and not isinstance(data["payload"], dict):
        errors.append("Field 'payload' must be an object")

    return (len(errors) == 0, errors)


def validate_envelope_v1(data: dict) -> tuple[bool, list[str]]:
    """Validate data against ENVELOPE_SCHEMA_V1."""
    errors = []
    if not isinstance(data, dict):
        return False, ["Input must be a JSON object"]

    for req in ENVELOPE_SCHEMA_V1["required"]:
        if req not in data:
            errors.append(f"Missing required field: '{req}'")

    if data.get("version") != "1.0.0":
        errors.append("Field 'version' must be '1.0.0'")

    if "mode" in data and data["mode"] not in ["managed", "standalone", "imported"]:
        errors.append(f"Invalid mode: '{data['mode']}'")

    if "fencing_token" in data and (not isinstance(data["fencing_token"], int) or data["fencing_token"] < 1):
        errors.append("Field 'fencing_token' must be an integer >= 1")

    if "call_depth" in data and (not isinstance(data["call_depth"], int) or data["call_depth"] < 0):
        errors.append("Field 'call_depth' must be an integer >= 0")

    if "max_hops" in data and (not isinstance(data["max_hops"], int) or data["max_hops"] < 1):
        errors.append("Field 'max_hops' must be an integer >= 1")

    if "budget" in data:
        budget = data["budget"]
        if not isinstance(budget, dict):
            errors.append("Field 'budget' must be an object")
        else:
            for b_req in ["max_elapsed_ms", "max_tokens", "max_turns"]:
                if b_req not in budget or not isinstance(budget[b_req], int) or budget[b_req] < 1:
                    errors.append(f"budget.{b_req} must be an integer >= 1")

    return (len(errors) == 0, errors)


def validate_result_v1(data: dict) -> tuple[bool, list[str]]:
    """Validate data against RESULT_SCHEMA_V1."""
    errors = []
    if not isinstance(data, dict):
        return False, ["Input must be a JSON object"]

    for req in RESULT_SCHEMA_V1["required"]:
        if req not in data:
            errors.append(f"Missing required field: '{req}'")

    if data.get("version") != "1.0.0":
        errors.append("Field 'version' must be '1.0.0'")

    if "state" in data and data["state"] not in ["succeeded", "failed", "timeout", "wait", "blocked"]:
        errors.append(f"Invalid state: '{data['state']}'")

    if "fencing_token" in data and (not isinstance(data["fencing_token"], int) or data["fencing_token"] < 1):
        errors.append("Field 'fencing_token' must be an integer >= 1")

    if "changed_files" in data and not isinstance(data["changed_files"], list):
        errors.append("Field 'changed_files' must be a list of strings")

    if "checks" in data:
        if not isinstance(data["checks"], list):
            errors.append("Field 'checks' must be a list of check objects")
        else:
            for i, c in enumerate(data["checks"]):
                if not isinstance(c, dict) or "cmd" not in c or "exit" not in c or not isinstance(c["exit"], int):
                    errors.append(f"Check at index {i} must have 'cmd' string and 'exit' integer")

    if "usage" in data:
        usage = data["usage"]
        if not isinstance(usage, dict):
            errors.append("Field 'usage' must be an object")
        else:
            for u_req in ["input_tokens", "output_tokens"]:
                if u_req not in usage or not isinstance(usage[u_req], int) or usage[u_req] < 0:
                    errors.append(f"usage.{u_req} must be an integer >= 0")

    return (len(errors) == 0, errors)


def validate_capability_v1(data: dict) -> tuple[bool, list[str]]:
    """Validate data against CAPABILITY_SCHEMA_V1."""
    errors = []
    if not isinstance(data, dict):
        return False, ["Input must be a JSON object"]

    for req in CAPABILITY_SCHEMA_V1["required"]:
        if req not in data:
            errors.append(f"Missing required field: '{req}'")

    if data.get("version") != "1.0.0":
        errors.append("Field 'version' must be '1.0.0'")

    if "actor" in data and data["actor"] not in ["codex", "antigravity"]:
        errors.append(f"Invalid actor: '{data['actor']}'")

    if "features" in data and not isinstance(data["features"], list):
        errors.append("Field 'features' must be a list of feature strings")

    return (len(errors) == 0, errors)


# =====================================================================
# Capability & App Compatibility Evaluator
# =====================================================================

def evaluate_compatibility(
    app_version: str,
    required_features: list[str],
    capability_record: dict | None,
    current_iso_time: str | None = None
) -> tuple[bool, list[str]]:
    """
    Evaluates whether an actor's capability satisfies requirements.
    Invariants:
    - If capability is missing or unprobed -> fail closed
    - If capability is expired -> fail closed
    - If any required feature is missing -> fail closed
    """
    reasons = []
    if not capability_record:
        return False, ["No capability record present for actor"]

    is_valid, val_errors = validate_capability_v1(capability_record)
    if not is_valid:
        return False, [f"Capability record schema invalid: {', '.join(val_errors)}"]

    expires_at = capability_record.get("expires_at", "")
    now_str = current_iso_time or datetime.now(timezone.utc).isoformat()
    if expires_at and expires_at <= now_str:
        reasons.append(f"Capability record expired at {expires_at} (current time {now_str})")

    available_features = set(capability_record.get("features", []))
    for req in required_features:
        if req not in available_features:
            reasons.append(f"Missing required feature: '{req}'")

    return (len(reasons) == 0, reasons)


# =====================================================================
# SQLite DDL v1 (15 Essential Tables & Invariants)
# =====================================================================

DDL_V1 = """
-- Schema migration tracking
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    checksum TEXT NOT NULL,
    applied_at TEXT NOT NULL,
    app_version TEXT NOT NULL
);

-- Actor capabilities
CREATE TABLE IF NOT EXISTS capabilities (
    actor TEXT PRIMARY KEY,
    cli_version TEXT NOT NULL,
    help_hash TEXT NOT NULL,
    features_json TEXT NOT NULL DEFAULT '[]',
    probed_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

-- Plan projections
CREATE TABLE IF NOT EXISTS plans (
    task_id TEXT PRIMARY KEY,
    card_revision INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL CHECK (status IN ('BACKLOG', 'READY', 'ACTIVE', 'REVIEW', 'DONE', 'BLOCKED')),
    depends_json TEXT NOT NULL DEFAULT '[]',
    acceptance_hash TEXT NOT NULL
);

-- Attempts and call depth
CREATE TABLE IF NOT EXISTS attempts (
    attempt_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES plans(task_id),
    parent_task_id TEXT,
    call_depth INTEGER NOT NULL DEFAULT 0 CHECK (call_depth >= 0),
    max_hops INTEGER NOT NULL DEFAULT 2 CHECK (max_hops >= 1),
    state TEXT NOT NULL CHECK (state IN ('PENDING', 'RUNNING', 'SUCCEEDED', 'FAILED', 'ORPHANED', 'CANCELLED')),
    idempotency_key TEXT NOT NULL UNIQUE
);

-- Resources
CREATE TABLE IF NOT EXISTS resources (
    resource_id TEXT PRIMARY KEY,
    kind TEXT NOT NULL CHECK (kind IN ('path', 'port', 'database', 'cache', 'artifact', 'environment', 'external')),
    canonical_value TEXT NOT NULL UNIQUE
);

-- Leases & Fencing
CREATE TABLE IF NOT EXISTS leases (
    lease_id TEXT PRIMARY KEY,
    attempt_id TEXT NOT NULL REFERENCES attempts(attempt_id),
    resource_id TEXT NOT NULL REFERENCES resources(resource_id),
    owner TEXT NOT NULL,
    fencing_token INTEGER NOT NULL CHECK (fencing_token > 0),
    expires_at TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('ACTIVE', 'EXPIRED', 'RELEASED', 'REVOKED')),
    UNIQUE(resource_id, fencing_token)
);

CREATE UNIQUE INDEX IF NOT EXISTS one_active_lease_per_resource
ON leases(resource_id) WHERE state = 'ACTIVE';

-- Durable Deliveries (inbox/outbox at-least-once)
CREATE TABLE IF NOT EXISTS deliveries (
    delivery_id TEXT PRIMARY KEY,
    direction TEXT NOT NULL CHECK (direction IN ('inbox', 'outbox')),
    dedupe_key TEXT NOT NULL UNIQUE,
    payload_ref TEXT,
    state TEXT NOT NULL CHECK (state IN ('pending', 'claimed', 'delivered', 'acked', 'dead_letter')),
    available_at TEXT NOT NULL,
    claimed_by TEXT
);
CREATE INDEX IF NOT EXISTS deliveries_poll_idx ON deliveries(direction, state, available_at);

-- Append-Only Events
CREATE TABLE IF NOT EXISTS events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    aggregate_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TRIGGER IF NOT EXISTS events_append_only_update
BEFORE UPDATE ON events
BEGIN
    SELECT RAISE(ABORT, 'events are append-only: updates disallowed');
END;

CREATE TRIGGER IF NOT EXISTS events_append_only_delete
BEFORE DELETE ON events
BEGIN
    SELECT RAISE(ABORT, 'events are append-only: deletions disallowed');
END;

-- Artifacts
CREATE TABLE IF NOT EXISTS artifacts (
    artifact_id TEXT PRIMARY KEY,
    attempt_id TEXT NOT NULL REFERENCES attempts(attempt_id),
    relative_path TEXT NOT NULL,
    size INTEGER NOT NULL CHECK (size >= 0),
    sha256 TEXT NOT NULL,
    media_type TEXT NOT NULL
);

-- Checkpoints
CREATE TABLE IF NOT EXISTS checkpoints (
    checkpoint_id TEXT PRIMARY KEY,
    attempt_id TEXT NOT NULL REFERENCES attempts(attempt_id),
    base_manifest_hash TEXT NOT NULL,
    artifact_set_hash TEXT NOT NULL,
    fence INTEGER NOT NULL CHECK (fence > 0)
);

-- Proof Receipts
CREATE TABLE IF NOT EXISTS receipts (
    receipt_id TEXT PRIMARY KEY,
    attempt_id TEXT NOT NULL REFERENCES attempts(attempt_id),
    acceptance_hash TEXT NOT NULL,
    checks_ref TEXT,
    verdict TEXT NOT NULL CHECK (verdict IN ('PASS', 'FAIL', 'UNKNOWN')),
    signer TEXT NOT NULL
);

-- External Effects & Reconciliation
CREATE TABLE IF NOT EXISTS effects (
    effect_id TEXT PRIMARY KEY,
    attempt_id TEXT NOT NULL REFERENCES attempts(attempt_id),
    kind TEXT NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE,
    provider_ref TEXT,
    state TEXT NOT NULL CHECK (state IN ('PENDING', 'COMMITTED', 'UNKNOWN', 'RECONCILED', 'FAILED'))
);

-- Budgets
CREATE TABLE IF NOT EXISTS budgets (
    scope_id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    turns INTEGER NOT NULL DEFAULT 0 CHECK (turns >= 0),
    tokens INTEGER NOT NULL DEFAULT 0 CHECK (tokens >= 0),
    elapsed_ms INTEGER NOT NULL DEFAULT 0 CHECK (elapsed_ms >= 0),
    quota_state TEXT NOT NULL CHECK (quota_state IN ('AVAILABLE', 'EXHAUSTED', 'UNKNOWN'))
);

-- Circuit Breakers
CREATE TABLE IF NOT EXISTS circuits (
    provider TEXT PRIMARY KEY,
    failure_class TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('CLOSED', 'OPEN', 'HALF_OPEN')),
    opened_at TEXT,
    retry_after TEXT
);

-- Conversations continuity
CREATE TABLE IF NOT EXISTS conversations (
    task_id TEXT PRIMARY KEY REFERENCES plans(task_id),
    tool TEXT NOT NULL CHECK (tool IN ('codex', 'antigravity')),
    conversation_id TEXT NOT NULL,
    last_confirmed_turn INTEGER NOT NULL DEFAULT 0 CHECK (last_confirmed_turn >= 0)
);
"""


def compute_script_checksum(sql_script: str) -> str:
    """Compute SHA-256 hex digest of a SQL migration script."""
    return hashlib.sha256(sql_script.strip().encode("utf-8")).hexdigest()


# =====================================================================
# Migration Manager
# =====================================================================

class MigrationManager:
    """Manages forward-only, checksum-verified, idempotent migrations."""

    REQUIRED_TABLES_V1 = [
        "schema_migrations", "capabilities", "plans", "attempts", "resources",
        "leases", "deliveries", "events", "artifacts", "checkpoints",
        "receipts", "effects", "budgets", "circuits", "conversations"
    ]

    @staticmethod
    def apply_migration(
        conn: sqlite3.Connection,
        version: int,
        ddl_script: str,
        app_version: str,
        applied_at: str | None = None
    ) -> bool:
        """
        Applies a database migration.
        Invariants:
        1. Forward-only: version must be >= 1.
        2. Idempotent: re-running with same version and same checksum succeeds without error.
        3. Checksum verification: mismatch on same version raises MigrationChecksumMismatchError.
        4. Down-migration disallowed: cannot apply version < latest applied version.
        """
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")

        # Ensure schema_migrations table exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                checksum TEXT NOT NULL,
                applied_at TEXT NOT NULL,
                app_version TEXT NOT NULL
            );
        """)
        conn.commit()

        checksum = compute_script_checksum(ddl_script)
        timestamp = applied_at or datetime.now(timezone.utc).isoformat()

        # Check existing migrations
        cursor.execute("SELECT version, checksum FROM schema_migrations ORDER BY version ASC;")
        applied = cursor.fetchall()
        applied_versions = {row[0]: row[1] for row in applied}

        if version in applied_versions:
            if applied_versions[version] != checksum:
                raise MigrationChecksumMismatchError(
                    f"Migration v{version} checksum mismatch! Applied: {applied_versions[version]}, Candidate: {checksum}"
                )
            # Idempotent re-run
            return False

        max_applied = max(applied_versions.keys()) if applied_versions else 0
        if version < max_applied:
            raise DownMigrationDisallowedError(
                f"Cannot apply migration v{version}: forward-only migrations required (latest is v{max_applied})."
            )

        # Apply script in a single transaction
        try:
            cursor.executescript(ddl_script)
            cursor.execute(
                "INSERT INTO schema_migrations (version, checksum, applied_at, app_version) VALUES (?, ?, ?, ?);",
                (version, checksum, timestamp, app_version)
            )
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise MigrationError(f"Failed to apply migration v{version}: {e}") from e

    @classmethod
    def verify_all_tables_exist(cls, conn: sqlite3.Connection) -> list[str]:
        """Returns list of missing required tables."""
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        existing_tables = {row[0] for row in cursor.fetchall()}
        return [tbl for tbl in cls.REQUIRED_TABLES_V1 if tbl not in existing_tables]


# =====================================================================
# Database Invariants Enforcement Helpers
# =====================================================================

def assert_valid_fence(conn: sqlite3.Connection, resource_id: str, proposed_fence: int) -> None:
    """
    Checks fencing token monotony for a resource.
    If proposed_fence <= current active or max fence, rejects as stale.
    """
    cursor = conn.cursor()
    cursor.execute(
        "SELECT MAX(fencing_token) FROM leases WHERE resource_id = ?;",
        (resource_id,)
    )
    row = cursor.fetchone()
    current_max = row[0] if (row and row[0] is not None) else 0

    if proposed_fence <= current_max:
        raise StaleFencingTokenError(
            f"Stale fencing token {proposed_fence} for resource '{resource_id}'. "
            f"Current highest token is {current_max}."
        )


def assert_effect_retry_allowed(effect_state: str) -> None:
    """
    Enforces invariant: automated retries are strictly disallowed when effect state is
    UNKNOWN or NEEDS_RECONCILIATION.
    """
    if effect_state in ("UNKNOWN", "NEEDS_RECONCILIATION"):
        raise UnknownEffectRetryDisallowedError(
            f"Automated retry forbidden for external effect in '{effect_state}' state. "
            "Manual reconciliation required."
        )


def record_event_append_only(
    conn: sqlite3.Connection,
    aggregate_id: str,
    kind: str,
    payload: dict,
    created_at: str | None = None
) -> int:
    """
    Appends an event to the events table.
    Ensures append-only semantics.
    """
    payload_str = json.dumps(payload, sort_keys=True)
    payload_hash = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()
    ts = created_at or datetime.now(timezone.utc).isoformat()

    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO events (aggregate_id, kind, payload_hash, created_at) VALUES (?, ?, ?, ?);",
        (aggregate_id, kind, payload_hash, ts)
    )
    conn.commit()
    return cursor.lastrowid


def deliver_with_deduplication(
    conn: sqlite3.Connection,
    delivery_id: str,
    direction: str,
    dedupe_key: str,
    payload_ref: str | None = None,
    available_at: str | None = None
) -> bool:
    """
    Attempts to insert a delivery with deduplication on dedupe_key.
    Returns True if newly inserted, False if already delivered (idempotent duplicate).
    """
    ts = available_at or datetime.now(timezone.utc).isoformat()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO deliveries (delivery_id, direction, dedupe_key, payload_ref, state, available_at) "
            "VALUES (?, ?, ?, ?, 'pending', ?);",
            (delivery_id, direction, dedupe_key, payload_ref, ts)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        conn.rollback()
        return False


def verify_receipt_for_success(
    conn: sqlite3.Connection,
    attempt_id: str,
    expected_acceptance_hash: str
) -> bool:
    """
    Verifies that an attempt has a valid PASS proof receipt with matching acceptance hash.
    SUCCEEDED requires this invariant to hold.
    """
    cursor = conn.cursor()
    cursor.execute(
        "SELECT verdict, acceptance_hash FROM receipts WHERE attempt_id = ?;",
        (attempt_id,)
    )
    rows = cursor.fetchall()
    for verdict, acc_hash in rows:
        if verdict == "PASS" and acc_hash == expected_acceptance_hash:
            return True
    return False
