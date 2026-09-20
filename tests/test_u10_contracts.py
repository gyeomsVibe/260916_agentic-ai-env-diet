from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from v7_harness.contracts.authority import validate_authority
from v7_harness.contracts.compatibility import evaluate_compatibility
from v7_harness.contracts.database import (
    MIGRATIONS,
    MigrationError,
    ack_delivery,
    apply_migrations,
    claim_lease,
    create_checkpoint,
    create_effect,
    create_receipt,
    mark_attempt_succeeded,
    validate_promotion_candidate,
    validate_artifact_reference,
)
from v7_harness.contracts.execution import interpret_worker_result
from v7_harness.contracts.schemas import SchemaValidationError, validate_document


H = "a" * 64
REQUIRED_TABLES = {
    "schema_migrations", "capabilities", "plans", "attempts", "resources", "leases",
    "deliveries", "events", "artifacts", "checkpoints", "receipts", "effects", "budgets",
    "circuits", "conversations", "execution_budget_usage", "execution_stage_events",
}


class ContractDatabaseTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "contract.db"
        self.db = sqlite3.connect(self.db_path)
        apply_migrations(self.db)
        self.db.execute("INSERT INTO plans VALUES('U10',1,'ACTIVE','[]',?,'PLAN_CARD')", (H,))
        self.db.execute("INSERT INTO attempts VALUES('a1','U10',NULL,0,1,'RUNNING','idem-a1')")
        self.db.execute("INSERT INTO resources VALUES('r1','PATH','workspace',0)")
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def test_required_tables_and_forward_metadata(self):
        tables = {row[0] for row in self.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertTrue(REQUIRED_TABLES <= tables)
        self.assertEqual(
            self.db.execute("SELECT version,checksum FROM schema_migrations ORDER BY version").fetchall(),
            [(1, MIGRATIONS[0].checksum), (2, MIGRATIONS[1].checksum)],
        )

    def test_migration_is_idempotent_and_checksum_pinned(self):
        apply_migrations(self.db)
        self.assertEqual(self.db.execute("SELECT count(*) FROM schema_migrations").fetchone()[0], 2)
        self.db.execute("UPDATE schema_migrations SET checksum=? WHERE version=1", ("0" * 64,))
        self.db.commit()
        with self.assertRaises(MigrationError):
            apply_migrations(self.db)

    def test_v1_to_v2_upgrade_is_forward_idempotent_and_checksum_pinned(self):
        legacy = sqlite3.connect(Path(self.temp.name) / "legacy-v1.db")
        try:
            legacy.executescript(MIGRATIONS[0].sql)
            legacy.execute(
                "INSERT INTO schema_migrations(version,checksum,applied_at,app_version) VALUES(1,?,'now','legacy')",
                (MIGRATIONS[0].checksum,),
            )
            legacy.commit()
            apply_migrations(legacy)
            self.assertEqual(
                legacy.execute("SELECT version,checksum FROM schema_migrations ORDER BY version").fetchall(),
                [(1, MIGRATIONS[0].checksum), (2, MIGRATIONS[1].checksum)],
            )
            apply_migrations(legacy)
            self.assertEqual(legacy.execute("SELECT count(*) FROM schema_migrations").fetchone()[0], 2)
            legacy.execute("UPDATE schema_migrations SET checksum=? WHERE version=2", ("f" * 64,))
            legacy.commit()
            with self.assertRaises(MigrationError):
                apply_migrations(legacy)
        finally:
            legacy.close()

    def test_newer_schema_is_refused(self):
        self.db.execute(
            "INSERT INTO schema_migrations(version,checksum,applied_at,app_version) VALUES(999,?,'now','future')",
            ("e" * 64,),
        )
        self.db.commit()
        with self.assertRaisesRegex(MigrationError, "newer"):
            apply_migrations(self.db)

    def test_single_active_lease_and_monotonic_fence(self):
        token1 = claim_lease(self.db, lease_id="l1", attempt_id="a1", resource_id="r1", owner="worker", expires_at="later")
        with self.assertRaises(sqlite3.IntegrityError):
            claim_lease(self.db, lease_id="l2", attempt_id="a1", resource_id="r1", owner="worker", expires_at="later")
        self.db.execute("UPDATE leases SET state='RELEASED' WHERE lease_id='l1'")
        self.db.commit()
        token2 = claim_lease(self.db, lease_id="l2", attempt_id="a1", resource_id="r1", owner="worker", expires_at="later")
        self.assertEqual((token1, token2), (1, 2))

    def test_stale_fence_rejects_checkpoint_receipt_and_effect(self):
        old = claim_lease(self.db, lease_id="l1", attempt_id="a1", resource_id="r1", owner="worker", expires_at="later")
        self.db.execute("UPDATE leases SET state='RELEASED'")
        self.db.commit()
        claim_lease(self.db, lease_id="l2", attempt_id="a1", resource_id="r1", owner="worker", expires_at="later")
        with self.assertRaisesRegex(ValueError, "STALE_FENCE"):
            create_checkpoint(self.db, checkpoint_id="c1", attempt_id="a1", resource_id="r1", fence=old, base_manifest_hash=H, artifact_set_hash=H)
        with self.assertRaisesRegex(ValueError, "STALE_FENCE"):
            create_receipt(self.db, receipt_id="p1", attempt_id="a1", resource_id="r1", fencing_token=old, acceptance_hash=H, checks_ref="artifact:checks", verdict="PASS", signer="codex")
        with self.assertRaisesRegex(ValueError, "STALE_FENCE"):
            create_effect(self.db, effect_id="e1", attempt_id="a1", resource_id="r1", fencing_token=old, kind="WRITE", idempotency_key="effect-1", provider_ref=None, state="UNKNOWN", retryable=False)
        with self.assertRaisesRegex(ValueError, "STALE_FENCE"):
            validate_promotion_candidate(self.db, attempt_id="a1", resource_id="r1", fencing_token=old, acceptance_hash=H)

    def test_delivery_dedupe_and_idempotent_ack(self):
        self.db.execute("INSERT INTO deliveries VALUES('d1','OUTBOX','dedupe-1','artifact:payload','CLAIMED','now','worker',NULL,NULL)")
        self.db.commit()
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("INSERT INTO deliveries VALUES('d2','OUTBOX','dedupe-1','artifact:payload','PENDING','now',NULL,NULL,NULL)")
        ack_delivery(self.db, delivery_id="d1", result_hash=H)
        ack_delivery(self.db, delivery_id="d1", result_hash=H)
        with self.assertRaisesRegex(ValueError, "ACK_RESULT_CONFLICT"):
            ack_delivery(self.db, delivery_id="d1", result_hash="b" * 64)
        self.assertEqual(self.db.execute("SELECT state FROM deliveries WHERE delivery_id='d1'").fetchone()[0], "ACKED")
        self.assertEqual(self.db.execute("SELECT count(*) FROM events WHERE aggregate_id='d1'").fetchone()[0], 1)

    def test_delivery_ack_requires_claimed_and_is_atomic_with_event(self):
        for delivery_id, state in (("pending", "PENDING"), ("dead", "DEAD")):
            self.db.execute("INSERT INTO deliveries VALUES(?,?,?,?,?,'now',NULL,NULL,NULL)", (delivery_id, "OUTBOX", f"dedupe-{delivery_id}", "artifact:payload", state))
            with self.assertRaisesRegex(ValueError, "DELIVERY_NOT_PROCESSED"):
                ack_delivery(self.db, delivery_id=delivery_id, result_hash=H)
        self.db.execute("INSERT INTO deliveries VALUES('atomic','OUTBOX','dedupe-atomic','artifact:payload','CLAIMED','now','worker',NULL,NULL)")
        self.db.execute("CREATE TRIGGER reject_atomic_ack BEFORE UPDATE ON deliveries WHEN NEW.delivery_id='atomic' BEGIN SELECT RAISE(ABORT, 'forced ack failure'); END")
        self.db.commit()
        with self.assertRaises(sqlite3.IntegrityError):
            ack_delivery(self.db, delivery_id="atomic", result_hash=H)
        self.assertEqual(self.db.execute("SELECT count(*) FROM events WHERE aggregate_id='atomic'").fetchone()[0], 0)
        self.assertEqual(self.db.execute("SELECT state FROM deliveries WHERE delivery_id='atomic'").fetchone()[0], "CLAIMED")

    def test_unknown_effect_is_not_retryable_and_blocks_success(self):
        fence = claim_lease(self.db, lease_id="l1", attempt_id="a1", resource_id="r1", owner="worker", expires_at="later")
        with self.assertRaises(sqlite3.IntegrityError):
            create_effect(self.db, effect_id="bad", attempt_id="a1", resource_id="r1", fencing_token=fence, kind="WRITE", idempotency_key=None, provider_ref=None, state="UNKNOWN", retryable=True)
        create_effect(self.db, effect_id="e1", attempt_id="a1", resource_id="r1", fencing_token=fence, kind="WRITE", idempotency_key=None, provider_ref=None, state="UNKNOWN", retryable=False)
        create_receipt(self.db, receipt_id="p1", attempt_id="a1", resource_id="r1", fencing_token=fence, acceptance_hash=H, checks_ref="artifact:checks", verdict="PASS", signer="codex")
        with self.assertRaisesRegex(ValueError, "RECONCILIATION"):
            mark_attempt_succeeded(self.db, attempt_id="a1", acceptance_hash=H)

    def test_matching_pass_receipt_required_for_success(self):
        fence = claim_lease(self.db, lease_id="l1", attempt_id="a1", resource_id="r1", owner="worker", expires_at="later")
        with self.assertRaisesRegex(ValueError, "PASS_RECEIPT_REQUIRED"):
            mark_attempt_succeeded(self.db, attempt_id="a1", acceptance_hash=H)
        create_receipt(self.db, receipt_id="p1", attempt_id="a1", resource_id="r1", fencing_token=fence, acceptance_hash=H, checks_ref="artifact:checks", verdict="PASS", signer="codex")
        mark_attempt_succeeded(self.db, attempt_id="a1", acceptance_hash=H)
        self.assertEqual(self.db.execute("SELECT state FROM attempts WHERE attempt_id='a1'").fetchone()[0], "SUCCEEDED")

    def test_intended_and_failed_effects_block_success_and_promotion(self):
        fence = claim_lease(self.db, lease_id="l1", attempt_id="a1", resource_id="r1", owner="worker", expires_at="later")
        create_receipt(self.db, receipt_id="p1", attempt_id="a1", resource_id="r1", fencing_token=fence, acceptance_hash=H, checks_ref="artifact:checks", verdict="PASS", signer="codex")
        create_effect(self.db, effect_id="e1", attempt_id="a1", resource_id="r1", fencing_token=fence, kind="WRITE", idempotency_key="effect-1", provider_ref=None, state="INTENDED", retryable=False)
        with self.assertRaisesRegex(ValueError, "RECONCILIATION"):
            mark_attempt_succeeded(self.db, attempt_id="a1", acceptance_hash=H)
        with self.assertRaisesRegex(ValueError, "RECONCILIATION"):
            validate_promotion_candidate(self.db, attempt_id="a1", resource_id="r1", fencing_token=fence, acceptance_hash=H)
        self.db.execute("UPDATE effects SET state='FAILED' WHERE effect_id='e1'")
        self.db.commit()
        with self.assertRaisesRegex(ValueError, "RECONCILIATION"):
            validate_promotion_candidate(self.db, attempt_id="a1", resource_id="r1", fencing_token=fence, acceptance_hash=H)

    def test_events_are_append_only(self):
        self.db.execute("INSERT INTO events(aggregate_id,kind,payload_hash,created_at) VALUES('x','K',?,'now')", (H,))
        self.db.commit()
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("DELETE FROM events")

    def test_artifact_reference_rejects_absolute_and_traversal(self):
        self.assertTrue(validate_artifact_reference("results/report.json", H))
        self.assertFalse(validate_artifact_reference("../secret", H))
        self.assertFalse(validate_artifact_reference("C:\\secret", H))
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("INSERT INTO artifacts VALUES('bad','a1','results/report.json',1,?,'application/json')", ("g" * 64,))


class PureContractTest(unittest.TestCase):
    def test_authority_conflict(self):
        ok = validate_authority(plan_revision=1, projected_revision=1, plan_acceptance_hash=H, projected_acceptance_hash=H, requested_operation="EXECUTE")
        self.assertTrue(ok.allowed)
        conflict = validate_authority(plan_revision=1, projected_revision=1, plan_acceptance_hash=H, projected_acceptance_hash=H, requested_operation="DB_OVERWRITE_CARD")
        self.assertEqual((conflict.allowed, conflict.code), (False, "AUTHORITY_CONFLICT"))

    def test_compatibility_and_storage_preflight_contract(self):
        ok = evaluate_compatibility(database_schema=1, app_min_schema=1, app_max_schema=1, capability_schema=1, required_features={"sandbox"}, observed_features={"sandbox": True}, storage_kind="LOCAL")
        self.assertTrue(ok.compatible)
        self.assertEqual(evaluate_compatibility(database_schema=1, app_min_schema=1, app_max_schema=1, capability_schema=1, required_features=(), observed_features={}, storage_kind="SYNC").code, "UNSAFE_STORAGE")

    def test_versioned_schemas_and_forbidden_full_output_fields(self):
        command = {"schema_version": 1, "command_id": "c", "task_id": "U10", "card_revision": 1, "acceptance_hash": H, "idempotency_key": "i", "operation": "VERIFY", "payload_ref": "artifact:p"}
        validate_document("command", command)
        with self.assertRaises(SchemaValidationError):
            validate_document("command", {**command, "full_prompt": "secret"})
        result = {"schema_version": 1, "attempt_id": "a1", "status": "NEEDS_RECONCILIATION", "acceptance_hash": H, "effect_state": "UNKNOWN", "retryable": False, "evidence_hash": H, "receipt_ref": "artifact:r"}
        validate_document("result", result)

    def test_schema_numeric_and_hash_constraints_reject_counterexamples(self):
        command = {"schema_version": 1, "command_id": "c", "task_id": "U10", "card_revision": -1, "acceptance_hash": H, "idempotency_key": "i", "operation": "VERIFY", "payload_ref": "artifact:p"}
        with self.assertRaises(SchemaValidationError):
            validate_document("command", command)
        command["card_revision"] = 1
        command["acceptance_hash"] = "g" * 64
        with self.assertRaises(SchemaValidationError):
            validate_document("command", command)
        envelope = {"schema_version": 1, "attempt_id": "a1", "fencing_token": 0, "requested_workspace": "staging", "observed_cwd": "observed", "isolation_mode": "UNVERIFIED", "scope_manifest_hash": H, "status": "ERROR", "error_class": "UNKNOWN", "partial": False, "stderr_hash": H, "receipt_ref": "artifact:r"}
        with self.assertRaises(SchemaValidationError):
            validate_document("envelope", envelope)

    def test_envelope_has_workspace_and_structured_evidence(self):
        envelope = {"schema_version": 1, "attempt_id": "a1", "fencing_token": 1, "requested_workspace": "staging", "observed_cwd": "observed", "isolation_mode": "UNVERIFIED", "scope_manifest_hash": H, "status": "ERROR", "error_class": "TRANSIENT_CAPACITY", "partial": False, "stderr_hash": H, "receipt_ref": "artifact:r"}
        validate_document("envelope", envelope)

    def test_semantic_status_effect_invariants(self):
        result = {"schema_version": 1, "attempt_id": "a1", "status": "NEEDS_RECONCILIATION", "acceptance_hash": H, "effect_state": "UNKNOWN", "retryable": True, "evidence_hash": H, "receipt_ref": "artifact:r"}
        with self.assertRaises(SchemaValidationError):
            validate_document("result", result)
        result.update(status="SUCCEEDED", retryable=False)
        with self.assertRaises(SchemaValidationError):
            validate_document("result", result)
        envelope = {"schema_version": 1, "attempt_id": "a1", "fencing_token": 1, "requested_workspace": "staging", "observed_cwd": "observed", "isolation_mode": "UNVERIFIED", "scope_manifest_hash": H, "status": "SUCCEEDED", "error_class": "TRANSIENT_CAPACITY", "partial": False, "stderr_hash": H, "receipt_ref": "artifact:r"}
        with self.assertRaises(SchemaValidationError):
            validate_document("envelope", envelope)
        envelope.update(status="ERROR", error_class="NONE")
        with self.assertRaises(SchemaValidationError):
            validate_document("envelope", envelope)

    def test_capability_schema_is_versioned(self):
        capability = {"schema_version": 1, "actor": "antigravity", "cli_version": "1.2.4", "help_hash": H, "features": {"sandbox": True}, "storage_kind": "LOCAL", "probed_at": "now", "expires_at": "later"}
        validate_document("capability", capability)

    def test_error_exit_zero_done_claim_is_not_success(self):
        decision = interpret_worker_result(envelope_status="ERROR", exit_code=0, response_claim="DONE", effect_observed=None, provider_error="503 No capacity")
        self.assertFalse(decision.successful)
        self.assertEqual((decision.result_status, decision.effect_state, decision.retryable, decision.error_class), ("NEEDS_RECONCILIATION", "UNKNOWN", False, "TRANSIENT_CAPACITY"))


if __name__ == "__main__":
    unittest.main()
