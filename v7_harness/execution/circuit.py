"""Circuit breaker, retry budgets, and quota fail-closed validation."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from typing import Any

from v7_harness.execution.errors import CircuitOpenError, QuotaFailClosedError


def _event(connection: sqlite3.Connection, aggregate_id: str, kind: str, payload: dict[str, Any]) -> None:
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    connection.execute(
        "INSERT INTO events(aggregate_id,kind,payload_hash,created_at) VALUES(?,?,?,datetime('now'))",
        (aggregate_id, kind, digest),
    )


class CircuitBreakerManager:
    """Track root-cause failures, open circuit on 3rd failure, enforce canary in half-open."""

    def __init__(self, failure_threshold: int = 3, default_cooldown_sec: float = 60.0) -> None:
        self._failure_threshold = failure_threshold
        self._default_cooldown_sec = default_cooldown_sec
        self._failure_counts: dict[tuple[str, str], int] = {}

    def failure_count(self, provider: str, failure_class: str) -> int:
        return self._failure_counts.get((provider, failure_class), 0)

    @staticmethod
    def durable_failure_count(connection: sqlite3.Connection, provider: str, failure_class: str) -> int:
        aggregate = f"{provider}:{failure_class}"
        return int(connection.execute(
            "SELECT count(*) FROM events WHERE aggregate_id=? AND kind='CIRCUIT_FAILURE' "
            "AND event_id > COALESCE((SELECT max(event_id) FROM events WHERE aggregate_id=? AND kind='CIRCUIT_RESET'),0)",
            (aggregate, aggregate),
        ).fetchone()[0])

    def check_circuit(
        self,
        connection: sqlite3.Connection,
        provider: str,
        failure_class: str,
        *,
        is_canary: bool = False,
    ) -> None:
        row = connection.execute(
            "SELECT state, opened_at, retry_after FROM circuits WHERE provider=? AND failure_class=?",
            (provider, failure_class),
        ).fetchone()
        if row is None or row[0] == "CLOSED":
            return

        state, _, retry_after = row
        if state == "OPEN":
            # Check if retry_after has elapsed
            if retry_after is not None:
                elapsed = connection.execute(
                    "SELECT datetime('now') >= datetime(?)", (retry_after,)
                ).fetchone()[0]
                if elapsed:
                    connection.execute(
                        "UPDATE circuits SET state='HALF_OPEN' WHERE provider=? AND failure_class=?",
                        (provider, failure_class),
                    )
                    state = "HALF_OPEN"
                else:
                    raise CircuitOpenError(f"CIRCUIT_OPEN: provider={provider}, failure_class={failure_class} is OPEN")
            else:
                raise CircuitOpenError(f"CIRCUIT_OPEN: provider={provider}, failure_class={failure_class} is OPEN")

        if state == "HALF_OPEN":
            if is_canary:
                # Reserve the only canary slot durably.  OPEN with no retry_after
                # blocks every other caller until this canary records success/failure.
                connection.execute(
                    "UPDATE circuits SET state='OPEN', retry_after=NULL WHERE provider=? AND failure_class=? AND state='HALF_OPEN'",
                    (provider, failure_class),
                )
                return
            raise CircuitOpenError("CANARY_REQUIRED_IN_HALF_OPEN: only canary permitted during HALF_OPEN")

    def record_failure(
        self,
        connection: sqlite3.Connection,
        provider: str,
        failure_class: str,
        *,
        cooldown_sec: float | None = None,
    ) -> None:
        cooldown = cooldown_sec if cooldown_sec is not None else self._default_cooldown_sec
        key = (provider, failure_class)
        _event(connection, f"{provider}:{failure_class}", "CIRCUIT_FAILURE", {"failure_class": failure_class})
        count = self.durable_failure_count(connection, provider, failure_class)
        self._failure_counts[key] = count

        row = connection.execute(
            "SELECT state FROM circuits WHERE provider=? AND failure_class=?",
            (provider, failure_class),
        ).fetchone()
        current_state = row[0] if row else "CLOSED"

        if current_state == "HALF_OPEN" or count >= self._failure_threshold:
            connection.execute(
                "INSERT INTO circuits(provider, failure_class, state, opened_at, retry_after) "
                "VALUES(?, ?, 'OPEN', datetime('now'), datetime('now', '+' || ? || ' seconds')) "
                "ON CONFLICT(provider, failure_class) DO UPDATE SET "
                "state='OPEN', opened_at=datetime('now'), retry_after=datetime('now', '+' || ? || ' seconds')",
                (provider, failure_class, int(cooldown), int(cooldown)),
            )
            _event(
                connection,
                f"{provider}:{failure_class}",
                "CIRCUIT_OPENED",
                {"provider": provider, "failure_class": failure_class, "consecutive_failures": count},
            )

    def record_success(
        self,
        connection: sqlite3.Connection,
        provider: str,
        failure_class: str,
        *,
        was_canary: bool = False,
    ) -> None:
        key = (provider, failure_class)
        self._failure_counts[key] = 0
        _event(
            connection,
            f"{provider}:{failure_class}",
            "CIRCUIT_RESET",
            {"provider": provider, "failure_class": failure_class, "was_canary": was_canary},
        )
        row = connection.execute(
            "SELECT state FROM circuits WHERE provider=? AND failure_class=?",
            (provider, failure_class),
        ).fetchone()
        if row is not None and row[0] != "CLOSED":
            connection.execute(
                "UPDATE circuits SET state='CLOSED', opened_at=NULL, retry_after=NULL WHERE provider=? AND failure_class=?",
                (provider, failure_class),
            )
            _event(
                connection,
                f"{provider}:{failure_class}",
                "CIRCUIT_CLOSED",
                {"provider": provider, "failure_class": failure_class, "was_canary": was_canary},
            )


def check_quota(connection: sqlite3.Connection, *, scope_id: str, provider: str) -> None:
    """Fail closed unless quota is explicitly AVAILABLE."""
    row = connection.execute(
        "SELECT quota_state FROM budgets WHERE scope_id=? AND provider=?",
        (scope_id, provider),
    ).fetchone()
    if row is None:
        raise QuotaFailClosedError(f"QUOTA_UNKNOWN: no budget record for scope={scope_id}, provider={provider}")
    quota_state = row[0]
    if quota_state == "UNKNOWN":
        raise QuotaFailClosedError(f"QUOTA_UNKNOWN: quota state is UNKNOWN for scope={scope_id}, provider={provider}")
    if quota_state == "EXHAUSTED":
        raise QuotaFailClosedError(f"QUOTA_EXHAUSTED: quota exhausted for scope={scope_id}, provider={provider}")
    if quota_state != "AVAILABLE":
        raise QuotaFailClosedError(f"QUOTA_FAIL_CLOSED: unexpected quota state '{quota_state}'")


def set_quota_state(
    connection: sqlite3.Connection,
    *,
    scope_id: str,
    provider: str,
    quota_state: str,
    turns: int = 0,
    tokens: int | None = None,
) -> None:
    connection.execute(
        "INSERT INTO budgets(scope_id, provider, turns, tokens, elapsed_ms, quota_state) "
        "VALUES(?,?,?,?,0,?) "
        "ON CONFLICT(scope_id, provider) DO UPDATE SET quota_state=excluded.quota_state",
        (scope_id, provider, turns, tokens, quota_state),
    )


@dataclass(frozen=True)
class RetryBudget:
    max_attempts: int = 3
    max_elapsed_ms: int = 30_000
    max_turns: int = 3
    max_tokens: int = 8_000
    max_tool_calls: int = 3


def reserve_retry_budget(
    connection: sqlite3.Connection,
    *,
    scope_id: str,
    provider: str,
    budget: RetryBudget,
    elapsed_ms: int = 0,
    turns: int = 1,
    tokens: int = 0,
    tool_calls: int = 1,
) -> None:
    """Atomically reserve bounded retry resources before a worker is launched."""
    row = connection.execute(
        "SELECT attempts,elapsed_ms,turns,tokens,tool_calls FROM execution_budget_usage WHERE scope_id=? AND provider=?",
        (scope_id, provider),
    ).fetchone() or (0, 0, 0, 0, 0)
    proposed = (row[0] + 1, row[1] + elapsed_ms, row[2] + turns, row[3] + tokens, row[4] + tool_calls)
    limits = (budget.max_attempts, budget.max_elapsed_ms, budget.max_turns, budget.max_tokens, budget.max_tool_calls)
    if any(value > limit for value, limit in zip(proposed, limits)):
        raise CircuitOpenError("RETRY_BUDGET_EXHAUSTED")
    connection.execute(
        "INSERT INTO execution_budget_usage VALUES(?,?,?,?,?,?,?) "
        "ON CONFLICT(scope_id,provider) DO UPDATE SET attempts=excluded.attempts,elapsed_ms=excluded.elapsed_ms,"
        "turns=excluded.turns,tokens=excluded.tokens,tool_calls=excluded.tool_calls",
        (scope_id, provider, *proposed),
    )
