"""
Comprehensive tests for v9 schema_contract module (U10).
Covers:
1. All 15 required SQLite tables creation & column definitions
2. Forward migration, checksum verification, idempotency, and rollback rejection
3. Versioned JSON schemas (command, envelope, result, capability) validation
4. Authority Matrix pure validator
5. Capability and app compatibility evaluations
6. Invariants:
   - Append-only events (update/delete blocked)
   - Unique active lease per resource constraint
   - Stale fencing token rejection
   - UNKNOWN effect retry prohibition
   - Delivery deduplication
   - Receipt verification for success
"""

import sqlite3
import unittest

from v7_harness.schema_contract import (
    AuthorityConflictError,
    AuthorityLevel,
    AuthorityMatrixValidator,
    DDL_V1,
    DownMigrationDisallowedError,
    MigrationChecksumMismatchError,
    MigrationManager,
    StaleFencingTokenError,
    UnknownEffectRetryDisallowedError,
    assert_effect_retry_allowed,
    assert_valid_fence,
    compute_script_checksum,
    deliver_with_deduplication,
    evaluate_compatibility,
    record_event_append_only,
    validate_capability_v1,
    validate_command_v1,
    validate_envelope_v1,
    validate_result_v1,
    verify_receipt_for_success,
)


class TestAuthorityMatrix(unittest.TestCase):
    def test_priority_hierarchy(self):
        # Platform/User can override anything
        self.assertTrue(AuthorityMatrixValidator.can_override(AuthorityLevel.PLATFORM_USER, AuthorityLevel.PROJECT_RULES))
        self.assertTrue(AuthorityMatrixValidator.can_override(AuthorityLevel.PLATFORM_USER, AuthorityLevel.RUNTIME_LEDGER))

        # Runtime ledger (level 5) cannot override Plan/Card (level 4)
        self.assertFalse(AuthorityMatrixValidator.can_override(AuthorityLevel.RUNTIME_LEDGER, AuthorityLevel.PLAN_CARD))

        # External unverified (level 7) cannot override Runtime ledger (level 5)
        self.assertFalse(AuthorityMatrixValidator.can_override(AuthorityLevel.EXTERNAL_UNVERIFIED, AuthorityLevel.RUNTIME_LEDGER))

    def test_assert_can_override_raises(self):
        with self.assertRaises(AuthorityConflictError):
            AuthorityMatrixValidator.assert_can_override(
                AuthorityLevel.RUNTIME_LEDGER,
                AuthorityLevel.ORCHESTRATION_DESIGN,
                context="DB trying to rewrite docs/01"
            )


class TestVersionedSchemas(unittest.TestCase):
    def test_command_v1_validation(self):
        valid_cmd = {
            "version": "1.0.0",
            "command_id": "cmd-001",
            "task_id": "U10",
            "idempotency_key": "idemp-001",
            "action": "delegate",
            "payload": {"prompt": "Run contract tests"},
            "timestamp": "2026-09-17T03:00:00Z"
        }
        ok, errors = validate_command_v1(valid_cmd)
        self.assertTrue(ok, errors)

        # Invalid action
        invalid_cmd = dict(valid_cmd, action="unsupported_action")
        ok, errors = validate_command_v1(invalid_cmd)
        self.assertFalse(ok)
        self.assertTrue(any("Invalid action" in e for e in errors))

    def test_envelope_v1_validation(self):
        valid_env = {
            "version": "1.0.0",
            "envelope_id": "env-001",
            "task_id": "U10",
            "attempt_id": "att-001",
            "fencing_token": 1,
            "call_depth": 0,
            "max_hops": 2,
            "mode": "managed",
            "caller": "codex",
            "callee": "antigravity",
            "budget": {
                "max_elapsed_ms": 600000,
                "max_tokens": 4000,
                "max_turns": 10
            },
            "payload": {}
        }
        ok, errors = validate_envelope_v1(valid_env)
        self.assertTrue(ok, errors)

        # Invalid mode
        invalid_env = dict(valid_env, mode="forbidden_mode")
        ok, errors = validate_envelope_v1(invalid_env)
        self.assertFalse(ok)

        # Stale/invalid fencing token
        invalid_token = dict(valid_env, fencing_token=0)
        ok, errors = validate_envelope_v1(invalid_token)
        self.assertFalse(ok)

    def test_result_v1_validation(self):
        valid_res = {
            "version": "1.0.0",
            "task_id": "U10",
            "attempt_id": "att-001",
            "fencing_token": 1,
            "state": "succeeded",
            "result_ref": "artifact:result-sha256",
            "changed_files": ["v7_harness/schema_contract.py"],
            "checks": [{"cmd": "python -m unittest", "exit": 0}],
            "risks": [],
            "spec_change_requests": [],
            "next": "Review by Codex",
            "usage": {"input_tokens": 100, "output_tokens": 200},
            "evidence_path": ".coord/receipts/U10.json"
        }
        ok, errors = validate_result_v1(valid_res)
        self.assertTrue(ok, errors)

        # Invalid state
        invalid_res = dict(valid_res, state="unknown_state")
        ok, errors = validate_result_v1(invalid_res)
        self.assertFalse(ok)

    def test_capability_v1_validation(self):
        valid_cap = {
            "version": "1.0.0",
            "actor": "antigravity",
            "cli_version": "1.2.4",
            "help_hash": "a1b2c3d4",
            "features": ["json_schema", "sandbox", "print_mode"],
            "probed_at": "2026-09-17T00:00:00Z",
            "expires_at": "2026-09-17T12:00:00Z"
        }
        ok, errors = validate_capability_v1(valid_cap)
        self.assertTrue(ok, errors)


class TestCapabilityEvaluator(unittest.TestCase):
    def test_compatibility_success(self):
        cap = {
            "version": "1.0.0",
            "actor": "antigravity",
            "cli_version": "1.2.4",
            "help_hash": "hash123",
            "features": ["sandbox", "json_output"],
            "probed_at": "2026-09-17T00:00:00Z",
            "expires_at": "2026-09-17T12:00:00Z"
        }
        ok, reasons = evaluate_compatibility(
            app_version="1.0.0",
            required_features=["sandbox"],
            capability_record=cap,
            current_iso_time="2026-09-17T03:00:00Z"
        )
        self.assertTrue(ok, reasons)

    def test_compatibility_expired(self):
        cap = {
            "version": "1.0.0",
            "actor": "codex",
            "cli_version": "0.154.0",
            "help_hash": "hash123",
            "features": ["exec"],
            "probed_at": "2026-09-16T00:00:00Z",
            "expires_at": "2026-09-16T12:00:00Z"
        }
        ok, reasons = evaluate_compatibility(
            app_version="1.0.0",
            required_features=["exec"],
            capability_record=cap,
            current_iso_time="2026-09-17T03:00:00Z"
        )
        self.assertFalse(ok)
        self.assertTrue(any("expired" in r for r in reasons))

    def test_compatibility_missing_feature(self):
        cap = {
            "version": "1.0.0",
            "actor": "codex",
            "cli_version": "0.154.0",
            "help_hash": "hash123",
            "features": ["exec"],
            "probed_at": "2026-09-17T00:00:00Z",
            "expires_at": "2026-09-17T12:00:00Z"
        }
        ok, reasons = evaluate_compatibility(
            app_version="1.0.0",
            required_features=["named_pipe_auth"],
            capability_record=cap,
            current_iso_time="2026-09-17T03:00:00Z"
        )
        self.assertFalse(ok)
        self.assertTrue(any("Missing required feature" in r for r in reasons))


class TestDatabaseContractAndInvariants(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.execute("PRAGMA foreign_keys = ON;")

    def tearDown(self):
        self.conn.close()

    def test_migration_and_fifteen_tables(self):
        applied = MigrationManager.apply_migration(
            self.conn,
            version=1,
            ddl_script=DDL_V1,
            app_version="0.9.0",
            applied_at="2026-09-17T03:00:00Z"
        )
        self.assertTrue(applied)

        missing = MigrationManager.verify_all_tables_exist(self.conn)
        self.assertEqual(missing, [], f"Missing required tables: {missing}")

        # Idempotency check: re-applying same script returns False without error
        reapplied = MigrationManager.apply_migration(
            self.conn,
            version=1,
            ddl_script=DDL_V1,
            app_version="0.9.0"
        )
        self.assertFalse(reapplied)

    def test_migration_checksum_mismatch(self):
        MigrationManager.apply_migration(
            self.conn,
            version=1,
            ddl_script=DDL_V1,
            app_version="0.9.0"
        )
        # Different DDL for same version must fail
        with self.assertRaises(MigrationChecksumMismatchError):
            MigrationManager.apply_migration(
                self.conn,
                version=1,
                ddl_script="-- modified script",
                app_version="0.9.0"
            )

    def test_down_migration_disallowed(self):
        MigrationManager.apply_migration(
            self.conn,
            version=2,
            ddl_script="CREATE TABLE test_v2 (id INT);",
            app_version="0.9.0"
        )
        with self.assertRaises(DownMigrationDisallowedError):
            MigrationManager.apply_migration(
                self.conn,
                version=1,
                ddl_script=DDL_V1,
                app_version="0.9.0"
            )

    def test_events_append_only_trigger(self):
        MigrationManager.apply_migration(self.conn, 1, DDL_V1, "0.9.0")
        event_id = record_event_append_only(
            self.conn,
            aggregate_id="task-U10",
            kind="STARTED",
            payload={"step": "init"}
        )
        self.assertGreater(event_id, 0)

        # UPDATE must be blocked by trigger
        with self.assertRaises(sqlite3.DatabaseError):
            self.conn.execute("UPDATE events SET kind = 'MUTATED' WHERE event_id = ?;", (event_id,))

        # DELETE must be blocked by trigger
        with self.assertRaises(sqlite3.DatabaseError):
            self.conn.execute("DELETE FROM events WHERE event_id = ?;", (event_id,))

    def test_one_active_lease_per_resource(self):
        MigrationManager.apply_migration(self.conn, 1, DDL_V1, "0.9.0")

        # Setup dependencies: plan, attempt, resource
        self.conn.execute(
            "INSERT INTO plans (task_id, status, acceptance_hash) VALUES ('U10', 'ACTIVE', 'hash1');"
        )
        self.conn.execute(
            "INSERT INTO attempts (attempt_id, task_id, state, idempotency_key) VALUES ('att-1', 'U10', 'RUNNING', 'idk-1');"
        )
        self.conn.execute(
            "INSERT INTO attempts (attempt_id, task_id, state, idempotency_key) VALUES ('att-2', 'U10', 'RUNNING', 'idk-2');"
        )
        self.conn.execute(
            "INSERT INTO resources (resource_id, kind, canonical_value) VALUES ('res-1', 'path', 'src/api');"
        )

        # First active lease succeeds
        self.conn.execute(
            "INSERT INTO leases (lease_id, attempt_id, resource_id, owner, fencing_token, expires_at, state) "
            "VALUES ('l-1', 'att-1', 'res-1', 'worker-1', 1, '2026-09-17T04:00:00Z', 'ACTIVE');"
        )
        self.conn.commit()

        # Second ACTIVE lease on same resource fails unique index constraint
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "INSERT INTO leases (lease_id, attempt_id, resource_id, owner, fencing_token, expires_at, state) "
                "VALUES ('l-2', 'att-2', 'res-1', 'worker-2', 2, '2026-09-17T04:00:00Z', 'ACTIVE');"
            )

    def test_stale_fencing_token_check(self):
        MigrationManager.apply_migration(self.conn, 1, DDL_V1, "0.9.0")
        self.conn.execute(
            "INSERT INTO plans (task_id, status, acceptance_hash) VALUES ('U10', 'ACTIVE', 'hash1');"
        )
        self.conn.execute(
            "INSERT INTO attempts (attempt_id, task_id, state, idempotency_key) VALUES ('att-1', 'U10', 'RUNNING', 'idk-1');"
        )
        self.conn.execute(
            "INSERT INTO resources (resource_id, kind, canonical_value) VALUES ('res-1', 'path', 'src/api');"
        )
        self.conn.execute(
            "INSERT INTO leases (lease_id, attempt_id, resource_id, owner, fencing_token, expires_at, state) "
            "VALUES ('l-1', 'att-1', 'res-1', 'worker-1', 5, '2026-09-17T04:00:00Z', 'ACTIVE');"
        )
        self.conn.commit()

        # Proposed fence 4 or 5 is stale (current max is 5)
        with self.assertRaises(StaleFencingTokenError):
            assert_valid_fence(self.conn, "res-1", 5)

        with self.assertRaises(StaleFencingTokenError):
            assert_valid_fence(self.conn, "res-1", 4)

        # Proposed fence 6 is strictly higher, so valid
        assert_valid_fence(self.conn, "res-1", 6)

    def test_unknown_effect_retry_prohibited(self):
        # Retry allowed for normal states
        assert_effect_retry_allowed("FAILED")
        assert_effect_retry_allowed("PENDING")

        # Retry prohibited for UNKNOWN and NEEDS_RECONCILIATION
        with self.assertRaises(UnknownEffectRetryDisallowedError):
            assert_effect_retry_allowed("UNKNOWN")

        with self.assertRaises(UnknownEffectRetryDisallowedError):
            assert_effect_retry_allowed("NEEDS_RECONCILIATION")

    def test_delivery_deduplication(self):
        MigrationManager.apply_migration(self.conn, 1, DDL_V1, "0.9.0")
        first = deliver_with_deduplication(
            self.conn,
            delivery_id="del-1",
            direction="inbox",
            dedupe_key="msg-dedupe-key-123",
            payload_ref="artifact/1"
        )
        self.assertTrue(first)

        # Duplicate submission with same dedupe_key returns False (deduplicated)
        duplicate = deliver_with_deduplication(
            self.conn,
            delivery_id="del-2",
            direction="inbox",
            dedupe_key="msg-dedupe-key-123",
            payload_ref="artifact/1"
        )
        self.assertFalse(duplicate)

    def test_verify_receipt_for_success(self):
        MigrationManager.apply_migration(self.conn, 1, DDL_V1, "0.9.0")
        self.conn.execute(
            "INSERT INTO plans (task_id, status, acceptance_hash) VALUES ('U10', 'ACTIVE', 'acc-hash-xyz');"
        )
        self.conn.execute(
            "INSERT INTO attempts (attempt_id, task_id, state, idempotency_key) VALUES ('att-1', 'U10', 'RUNNING', 'idk-1');"
        )
        self.conn.execute(
            "INSERT INTO receipts (receipt_id, attempt_id, acceptance_hash, verdict, signer) "
            "VALUES ('rec-1', 'att-1', 'acc-hash-xyz', 'PASS', 'verifier');"
        )
        self.conn.commit()

        # Matches PASS and expected hash
        self.assertTrue(verify_receipt_for_success(self.conn, "att-1", "acc-hash-xyz"))

        # Fails if hash mismatch
        self.assertFalse(verify_receipt_for_success(self.conn, "att-1", "acc-hash-different"))


if __name__ == "__main__":
    unittest.main()
