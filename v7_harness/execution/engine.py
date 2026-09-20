"""Durable execution engine coordinating delivery lifecycle, leases, circuits, and mock launcher."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from typing import Any, Callable

from v7_harness.broker.core import BrokerCore
from v7_harness.contracts.database import (
    ack_delivery as _db_ack_delivery,
    mark_attempt_succeeded as _db_mark_attempt_succeeded,
)
from v7_harness.contracts.execution import WorkerDecision
from v7_harness.execution.circuit import CircuitBreakerManager, RetryBudget, check_quota, reserve_retry_budget
from v7_harness.execution.dispatcher import BoundedDispatcher
from v7_harness.execution.errors import (
    CircuitOpenError,
    DrainInProgressError,
    DuplicateDeliveryError,
    ExecutionError,
    LateResultError,
    QuotaFailClosedError,
    StaleFenceError,
    WorkerExecutionError,
)
from v7_harness.execution.launcher import MockSubprocessLauncher
from v7_harness.execution.lease import (
    assert_fence,
    claim_lease,
    ensure_resource,
    record_effect,
    record_receipt,
    renew_lease_conditional,
)


def _event(connection: sqlite3.Connection, aggregate_id: str, kind: str, payload: dict[str, Any]) -> None:
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    connection.execute(
        "INSERT INTO events(aggregate_id,kind,payload_hash,created_at) VALUES(?,?,?,datetime('now'))",
        (aggregate_id, kind, digest),
    )


def _stage_event(
    connection: sqlite3.Connection,
    *,
    delivery_id: str,
    attempt_id: str,
    stage: str,
    state: str,
    monotonic_ns: int,
) -> None:
    """Store timing/state evidence only; never prompt, output, or payload text."""
    connection.execute(
        "INSERT INTO execution_stage_events(delivery_id,attempt_id,stage,state,monotonic_ns,created_at) "
        "VALUES(?,?,?,?,?,datetime('now'))",
        (delivery_id, attempt_id, stage, state, monotonic_ns),
    )


def ensure_plan(
    connection: sqlite3.Connection,
    *,
    task_id: str,
    card_revision: int = 1,
    acceptance_hash: str = "a" * 64,
) -> None:
    connection.execute(
        "INSERT OR IGNORE INTO plans(task_id, card_revision, status, depends_json, acceptance_hash, source_kind) "
        "VALUES(?, ?, 'ACTIVE', '[]', ?, 'PLAN_CARD')",
        (task_id, card_revision, acceptance_hash),
    )


def ensure_attempt(
    connection: sqlite3.Connection,
    *,
    attempt_id: str,
    task_id: str,
    idempotency_key: str,
    max_hops: int = 2,
) -> None:
    ensure_plan(connection, task_id=task_id)
    connection.execute(
        "INSERT OR IGNORE INTO attempts(attempt_id, task_id, parent_task_id, call_depth, max_hops, state, idempotency_key) "
        "VALUES(?, ?, NULL, 0, ?, 'RUNNING', ?)",
        (attempt_id, task_id, max_hops, idempotency_key),
    )


class DurableExecutionEngine:
    """Orchestrate durable at-least-once delivery lifecycle and fail-closed gates."""

    def __init__(
        self,
        target: BrokerCore | BoundedDispatcher,
        *,
        circuit_manager: CircuitBreakerManager | None = None,
        launcher: MockSubprocessLauncher | None = None,
        default_lease_duration: float = 30.0,
        retry_budget: RetryBudget | None = None,
    ) -> None:
        if isinstance(target, BoundedDispatcher):
            self._dispatcher: BoundedDispatcher | None = target
            self._core: BrokerCore | None = None
        else:
            self._dispatcher = None
            self._core = target
        self.circuit_manager = circuit_manager or CircuitBreakerManager()
        self.launcher = launcher or MockSubprocessLauncher()
        self.default_lease_duration = default_lease_duration
        self.retry_budget = retry_budget or RetryBudget()
        self._draining = False

    def drain(self, timeout: float = 5.0) -> None:
        self._draining = True
        if self._dispatcher is not None:
            self._dispatcher.drain(timeout=timeout)

    def _execute_in_db(self, fn: Callable[[sqlite3.Connection], Any]) -> Any:
        if self._dispatcher is not None:
            return self._dispatcher.submit_and_wait(lambda core: fn(core.connection))
        if self._core is not None:
            return fn(self._core.connection)
        raise ExecutionError("NO_DATABASE_TARGET")

    def execute(
        self,
        command: dict[str, Any],
        *,
        mode: str = "success",
        is_canary: bool = False,
        timeout_sec: float | None = None,
        on_wait_hook: Callable[[], None] | None = None,
        effect_callback: Callable[[], None] | None = None,
        effect_failure_mode: str = "unknown",
        after_commit_hook: Callable[[], None] | None = None,
        heartbeat_duration: float | None = None,
        heartbeat_interval_sec: float = 0.25,
        worker_capability: str | None = None,
    ) -> dict[str, Any]:
        """Run execution lifecycle: Phase 1 (claim) -> Phase 2 (worker outside tx) -> Phase 3 (commit)."""
        if self._draining:
            raise DrainInProgressError("DRAIN_IN_PROGRESS")

        delivery_id = command["command_id"]
        task_id = command.get("task_id", "U12")
        attempt_id = command.get("attempt_id", f"att-{delivery_id}")
        resource_id = command.get("resource_id", f"res-{task_id}")
        owner = command.get("owner", "worker-1")
        provider = command.get("provider", "mock-provider")
        failure_class = command.get("failure_class", "WORKER_CRASH")
        scope_id = command.get("scope_id", "default-scope")
        acceptance_hash = command.get("acceptance_hash", "a" * 64)
        idempotency_key = command["idempotency_key"]
        submitted_ns = time.monotonic_ns()
        if effect_failure_mode not in {"unknown", "not_applied"}:
            raise ValueError("INVALID_EFFECT_FAILURE_MODE")

        if worker_capability is None:
            worker_capability = command.get("worker_capability", "unknown")
        if worker_capability not in {"read_only", "effectful", "unknown"}:
            raise ValueError("INVALID_WORKER_CAPABILITY")

        # Phase 1: Claim delivery & lease inside short DB transaction
        def phase1(connection: sqlite3.Connection) -> dict[str, Any]:
            with connection:
                # 1. Replay check: already committed and acked?
                row = connection.execute(
                    "SELECT state, result_hash FROM deliveries WHERE delivery_id=?",
                    (delivery_id,),
                ).fetchone()
                if row is not None and row[0] == "ACKED":
                    _stage_event(
                        connection,
                        delivery_id=delivery_id,
                        attempt_id=attempt_id,
                        stage="REPLAYED",
                        state="ACKED",
                        monotonic_ns=time.monotonic_ns(),
                    )
                    return {
                        "replayed": True,
                        "delivery_id": delivery_id,
                        "state": "ACKED",
                        "result_hash": row[1],
                    }

                # 2. Check if attempt is in NEEDS_RECONCILIATION (fail-closed, no auto-retry)
                att_row = connection.execute(
                    "SELECT state FROM attempts WHERE attempt_id=?", (attempt_id,)
                ).fetchone()
                if att_row is not None and att_row[0] == "NEEDS_RECONCILIATION":
                    raise DuplicateDeliveryError("CANNOT_RETRY_NEEDS_RECONCILIATION: effect outcome unknown")
                unresolved = connection.execute(
                    "SELECT 1 FROM effects WHERE attempt_id=? AND state IN ('INTENDED','UNKNOWN')", (attempt_id,)
                ).fetchone()
                if unresolved is not None:
                    raise DuplicateDeliveryError("CANNOT_RETRY_UNRESOLVED_EFFECT")
                if att_row is not None and att_row[0] == "FAILED":
                    connection.execute(
                        "UPDATE attempts SET state='RUNNING' WHERE attempt_id=? AND state='FAILED'", (attempt_id,)
                    )

                if row is not None:
                    dedupe = connection.execute(
                        "SELECT dedupe_key FROM deliveries WHERE delivery_id=?", (delivery_id,)
                    ).fetchone()[0]
                    if dedupe != idempotency_key:
                        raise DuplicateDeliveryError("DELIVERY_ID_CONFLICT")

                # 3. Duplicate active claim check
                if row is not None and row[0] == "CLAIMED":
                    # Check if active lease on this resource is still valid
                    active_lease = connection.execute(
                        "SELECT lease_id, expires_at FROM leases WHERE resource_id=? AND state='ACTIVE'",
                        (resource_id,),
                    ).fetchone()
                    if active_lease is not None:
                        is_expired = connection.execute(
                            "SELECT datetime(?) <= datetime('now')", (active_lease[1],)
                        ).fetchone()[0]
                        if not is_expired:
                            raise DuplicateDeliveryError("DELIVERY_ALREADY_CLAIMED")

                # 4. Setup tables
                ensure_plan(connection, task_id=task_id, acceptance_hash=acceptance_hash)
                ensure_attempt(connection, attempt_id=attempt_id, task_id=task_id, idempotency_key=idempotency_key)
                ensure_resource(connection, resource_id=resource_id)

                # 5. Quota check: fail-closed if UNKNOWN or EXHAUSTED
                check_quota(connection, scope_id=scope_id, provider=provider)

                # 6. Circuit breaker check: enforce canary in HALF_OPEN
                self.circuit_manager.check_circuit(
                    connection, provider=provider, failure_class=failure_class, is_canary=is_canary
                )
                reserve_retry_budget(
                    connection,
                    scope_id=scope_id,
                    provider=provider,
                    budget=self.retry_budget,
                    elapsed_ms=int(command.get("elapsed_ms", 0)),
                    turns=int(command.get("turns", 1)),
                    tokens=int(command.get("tokens", 0)),
                    tool_calls=int(command.get("tool_calls", 1)),
                )

                # 7. Claim lease and bump fence
                # Get next fence token to form unique lease_id
                next_tok_row = connection.execute("SELECT next_fencing_token + 1 FROM resources WHERE resource_id=?", (resource_id,)).fetchone()
                next_tok = next_tok_row[0] if next_tok_row else 1
                lease_id = f"lease-{delivery_id}-{next_tok}"
                fence = claim_lease(
                    connection,
                    lease_id=lease_id,
                    attempt_id=attempt_id,
                    resource_id=resource_id,
                    owner=owner,
                    duration_sec=self.default_lease_duration,
                )

                # 7. Insert or update delivery to CLAIMED
                if row is None:
                    connection.execute(
                        "INSERT INTO deliveries(delivery_id, direction, dedupe_key, payload_ref, state, available_at, claimed_by) "
                        "VALUES(?, 'INBOX', ?, ?, 'CLAIMED', datetime('now'), ?)",
                        (delivery_id, idempotency_key, command.get("payload_ref", "payload:ref"), owner),
                    )
                else:
                    changed = connection.execute(
                        "UPDATE deliveries SET state='CLAIMED', claimed_by=? WHERE delivery_id=? AND state IN ('PENDING','CLAIMED')",
                        (owner, delivery_id),
                    ).rowcount
                    if changed != 1:
                        raise DuplicateDeliveryError("INVALID_DELIVERY_TRANSITION")

                _event(connection, delivery_id, "DELIVERY_CLAIMED", {"fence": fence, "attempt_id": attempt_id})
                _stage_event(
                    connection,
                    delivery_id=delivery_id,
                    attempt_id=attempt_id,
                    stage="SUBMITTED",
                    state="PENDING",
                    monotonic_ns=submitted_ns,
                )
                _stage_event(
                    connection,
                    delivery_id=delivery_id,
                    attempt_id=attempt_id,
                    stage="CLAIMED",
                    state="CLAIMED",
                    monotonic_ns=time.monotonic_ns(),
                )
                return {"replayed": False, "fence": fence}

        p1_result = self._execute_in_db(phase1)
        if p1_result["replayed"]:
            # Commit-before-response replay: return committed result without effect execution!
            return {
                "ok": True,
                "replayed": True,
                "delivery_id": delivery_id,
                "state": "ACKED",
                "result_hash": p1_result["result_hash"],
            }

        fence = p1_result["fence"]

        heartbeat_failed = [False]

        def heartbeat() -> bool:
            def _renew(connection: sqlite3.Connection) -> bool:
                with connection:
                    return renew_lease_conditional(
                        connection,
                        owner=owner,
                        attempt_id=attempt_id,
                        resource_id=resource_id,
                        fence=fence,
                        duration_sec=heartbeat_duration or self.default_lease_duration,
                    )

            try:
                ok = bool(self._execute_in_db(_renew))
            except Exception:
                ok = False
            if not ok:
                heartbeat_failed[0] = True
            return ok

        # Phase 2: Worker execution OUTSIDE any SQLite transaction
        # DB connection is completely idle / transaction closed!
        try:
            decision = self.launcher.launch(
                attempt_id=attempt_id,
                acceptance_hash=acceptance_hash,
                command_id=delivery_id,
                mode=mode,
                timeout_sec=timeout_sec,
                on_wait_hook=on_wait_hook,
                worker_capability=worker_capability,
                heartbeat=heartbeat,
                heartbeat_interval_sec=heartbeat_interval_sec,
            )
        except StaleFenceError:
            heartbeat_failed[0] = True
            decision = WorkerDecision(
                successful=False,
                result_status="NEEDS_RECONCILIATION",
                effect_state="UNKNOWN",
                retryable=False,
                error_class="LATE_RESULT_NEEDS_RECONCILIATION",
            )
        except Exception:
            raise

        effect_prepared = False
        if decision.successful and not heartbeat_failed[0] and effect_callback is not None:
            def prepare_effect(connection: sqlite3.Connection) -> None:
                with connection:
                    assert_fence(connection, attempt_id=attempt_id, resource_id=resource_id, token=fence)
                    effect_id = f"eff-{delivery_id}"
                    existing_effect = connection.execute(
                        "SELECT state,idempotency_key FROM effects WHERE effect_id=?", (effect_id,)
                    ).fetchone()
                    if existing_effect is None:
                        connection.execute(
                            "INSERT INTO effects VALUES(?,?,?,?,?,?,?,?,?)",
                            (effect_id, attempt_id, resource_id, fence, "EXTERNAL_MUTATION", idempotency_key, None, "INTENDED", 0),
                        )
                    elif existing_effect == ("FAILED", idempotency_key):
                        connection.execute(
                            "UPDATE effects SET fencing_token=?,state='INTENDED',provider_ref=NULL,retryable=0 "
                            "WHERE effect_id=? AND state='FAILED'",
                            (fence, effect_id),
                        )
                    else:
                        raise DuplicateDeliveryError("CANNOT_RETRY_UNRESOLVED_EFFECT")

            try:
                self._execute_in_db(prepare_effect)
                effect_prepared = True
            except StaleFenceError:
                heartbeat_failed[0] = True

            if effect_prepared:
                try:
                    effect_callback()
                except BaseException:
                    if effect_failure_mode == "not_applied":
                        decision = WorkerDecision(False, "ERROR", "NONE", True, "EFFECT_NOT_APPLIED")
                    else:
                        decision = WorkerDecision(False, "NEEDS_RECONCILIATION", "UNKNOWN", False, "SIDE_EFFECT_UNKNOWN")

        result_hash = hashlib.sha256(f"result:{delivery_id}:{attempt_id}".encode("utf-8")).hexdigest()
        finished_ns = time.monotonic_ns()

        def reconcile_late_result(connection: sqlite3.Connection) -> None:
            with connection:
                _stage_event(
                    connection,
                    delivery_id=delivery_id,
                    attempt_id=attempt_id,
                    stage="WORKER_FINISHED",
                    state=decision.result_status,
                    monotonic_ns=finished_ns,
                )
                effect_id = f"eff-{delivery_id}"
                existing_effect = connection.execute(
                    "SELECT 1 FROM effects WHERE effect_id=?", (effect_id,)
                ).fetchone()
                if existing_effect is not None:
                    connection.execute(
                        "UPDATE effects SET state='UNKNOWN', provider_ref='provider:unknown', retryable=0 WHERE effect_id=?",
                        (effect_id,),
                    )
                else:
                    connection.execute(
                        "INSERT INTO effects VALUES(?,?,?,?,?,?,?,?,?)",
                        (effect_id, attempt_id, resource_id, fence, "EXTERNAL_MUTATION", idempotency_key, "provider:unknown", "UNKNOWN", 0),
                    )
                connection.execute(
                    "UPDATE attempts SET state='NEEDS_RECONCILIATION' WHERE attempt_id=?",
                    (attempt_id,),
                )
                lease_id = f"lease-{delivery_id}-{fence}"
                connection.execute(
                    "UPDATE leases SET state='EXPIRED' WHERE lease_id=?",
                    (lease_id,),
                )
                _event(connection, delivery_id, "DELIVERY_LATE_RECONCILE", {"fence": fence, "attempt_id": attempt_id})
                _stage_event(
                    connection,
                    delivery_id=delivery_id,
                    attempt_id=attempt_id,
                    stage="NEEDS_RECONCILIATION",
                    state="NEEDS_RECONCILIATION",
                    monotonic_ns=time.monotonic_ns(),
                )
                self.circuit_manager.record_failure(connection, provider=provider, failure_class=failure_class)

        if heartbeat_failed[0]:
            self._execute_in_db(reconcile_late_result)
            raise LateResultError("LATE_RESULT_NEEDS_RECONCILIATION")

        # Phase 3: Validate fence & commit result in short DB transaction
        def phase3(connection: sqlite3.Connection) -> dict[str, Any]:
            with connection:
                # Stale fence validation: fail closed if fence was bumped during worker execution
                try:
                    assert_fence(connection, attempt_id=attempt_id, resource_id=resource_id, token=fence)
                except StaleFenceError:
                    return {"stale": True}

                _stage_event(
                    connection,
                    delivery_id=delivery_id,
                    attempt_id=attempt_id,
                    stage="WORKER_FINISHED",
                    state=decision.result_status,
                    monotonic_ns=finished_ns,
                )

                if decision.successful:
                    receipt_id = f"rcpt-{delivery_id}"
                    effect_id = f"eff-{delivery_id}"
                    connection.execute(
                        "INSERT INTO receipts VALUES(?,?,?,?,?,?,?,?)",
                        (receipt_id, attempt_id, resource_id, fence, acceptance_hash, "checks:pass", "PASS", "signer:u12"),
                    )
                    if effect_prepared:
                        if connection.execute(
                            "UPDATE effects SET state='CONFIRMED',provider_ref='provider:ok' "
                            "WHERE effect_id=? AND state='INTENDED' AND fencing_token=?",
                            (effect_id, fence),
                        ).rowcount != 1:
                            raise ExecutionError("INVALID_EFFECT_TRANSITION")
                    else:
                        connection.execute(
                            "INSERT INTO effects VALUES(?,?,?,?,?,?,?,?,?)",
                            (effect_id, attempt_id, resource_id, fence, "STATE_MUTATION", idempotency_key, "provider:ok", "CONFIRMED", 0),
                        )
                    if connection.execute(
                        "UPDATE attempts SET state='SUCCEEDED' WHERE attempt_id=? AND state='RUNNING'", (attempt_id,)
                    ).rowcount != 1:
                        raise ExecutionError("INVALID_ATTEMPT_TRANSITION")
                    if connection.execute(
                        "UPDATE deliveries SET state='ACKED',result_hash=?,acked_at=datetime('now') "
                        "WHERE delivery_id=? AND state='CLAIMED'",
                        (result_hash, delivery_id),
                    ).rowcount != 1:
                        raise ExecutionError("INVALID_DELIVERY_TRANSITION")
                    _event(connection, delivery_id, "DELIVERY_PROCESSED", {"result_hash": result_hash})
                    _stage_event(
                        connection,
                        delivery_id=delivery_id,
                        attempt_id=attempt_id,
                        stage="ACKED",
                        state="ACKED",
                        monotonic_ns=time.monotonic_ns(),
                    )
                    self.circuit_manager.record_success(
                        connection, provider=provider, failure_class=failure_class, was_canary=is_canary
                    )
                    return {"ok": True, "replayed": False, "delivery_id": delivery_id, "state": "ACKED", "result_hash": result_hash}

                # Worker failed: NO false ACK, NO false SUCCEEDED!
                lease_id = f"lease-{delivery_id}-{fence}"

                if decision.effect_state == "UNKNOWN":
                    # Unknown effect outcome: record with state='UNKNOWN', retryable=0
                    effect_id = f"eff-{delivery_id}"
                    if effect_prepared:
                        if connection.execute(
                            "UPDATE effects SET state='UNKNOWN',provider_ref='provider:unknown',retryable=0 "
                            "WHERE effect_id=? AND state='INTENDED' AND fencing_token=?",
                            (effect_id, fence),
                        ).rowcount != 1:
                            raise ExecutionError("INVALID_EFFECT_TRANSITION")
                    else:
                        connection.execute(
                            "INSERT INTO effects VALUES(?,?,?,?,?,?,?,?,?)",
                            (effect_id, attempt_id, resource_id, fence, "EXTERNAL_MUTATION", idempotency_key, "provider:unknown", "UNKNOWN", 0),
                        )
                    connection.execute(
                        "UPDATE leases SET state='EXPIRED' WHERE lease_id=?",
                        (lease_id,),
                    )
                    connection.execute(
                        "UPDATE attempts SET state='NEEDS_RECONCILIATION' WHERE attempt_id=?",
                        (attempt_id,),
                    )
                    self.circuit_manager.record_failure(connection, provider=provider, failure_class=failure_class)
                    _stage_event(
                        connection,
                        delivery_id=delivery_id,
                        attempt_id=attempt_id,
                        stage="NEEDS_RECONCILIATION",
                        state="NEEDS_RECONCILIATION",
                        monotonic_ns=time.monotonic_ns(),
                    )
                    err_cls = decision.error_class if decision.error_class != "UNKNOWN" else "SIDE_EFFECT_UNKNOWN"
                    return {"error": "UNKNOWN_EFFECT_NEEDS_RECONCILIATION", "retryable": False, "error_class": err_cls}

                # Regular failure / crash / timeout / validation error
                connection.execute(
                    "UPDATE leases SET state='REVOKED' WHERE lease_id=?",
                    (lease_id,),
                )
                connection.execute("UPDATE attempts SET state='FAILED' WHERE attempt_id=?", (attempt_id,))
                if effect_prepared:
                    connection.execute(
                        "UPDATE effects SET state='FAILED',provider_ref='provider:not-applied',retryable=0 "
                        "WHERE effect_id=? AND state='INTENDED' AND fencing_token=?",
                        (f"eff-{delivery_id}", fence),
                    )
                self.circuit_manager.record_failure(connection, provider=provider, failure_class=failure_class)
                _stage_event(
                    connection,
                    delivery_id=delivery_id,
                    attempt_id=attempt_id,
                    stage="FAILED",
                    state="FAILED",
                    monotonic_ns=time.monotonic_ns(),
                )
                return {"error": f"WORKER_FAILED: {decision.result_status}", "retryable": decision.retryable, "error_class": decision.error_class}

        outcome = self._execute_in_db(phase3)
        if outcome.get("stale"):
            self._execute_in_db(reconcile_late_result)
            raise LateResultError("LATE_RESULT_NEEDS_RECONCILIATION")

        if "error" in outcome:
            raise WorkerExecutionError(outcome["error"], retryable=outcome["retryable"], error_class=outcome["error_class"])
        if after_commit_hook is not None:
            after_commit_hook()
        return outcome
