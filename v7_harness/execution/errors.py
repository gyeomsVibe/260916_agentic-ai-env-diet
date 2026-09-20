"""Execution error taxonomy for U12 durable execution."""

from __future__ import annotations


class ExecutionError(RuntimeError):
    """Base error for durable execution failures."""

    def __init__(self, message: str, *, retryable: bool = False, error_class: str = "UNKNOWN") -> None:
        super().__init__(message)
        self.message = message
        self.retryable = retryable
        self.error_class = error_class


class QueueSaturationError(ExecutionError):
    """Raised on bounded queue saturation for fast retryable failure."""

    def __init__(self, message: str = "QUEUE_SATURATED") -> None:
        super().__init__(message, retryable=True, error_class="QUEUE_SATURATED")


class StaleFenceError(ExecutionError):
    """Raised when an operation uses an expired or stale fencing token."""

    def __init__(self, message: str = "STALE_FENCE", *, retryable: bool = False, error_class: str = "STALE_FENCE") -> None:
        super().__init__(message, retryable=retryable, error_class=error_class)


class CircuitOpenError(ExecutionError):
    """Raised when circuit breaker is OPEN or HALF_OPEN rejects non-canary work."""

    def __init__(self, message: str = "CIRCUIT_OPEN", *, retryable: bool = False) -> None:
        super().__init__(message, retryable=retryable, error_class="CIRCUIT_OPEN")


class QuotaFailClosedError(ExecutionError):
    """Raised when quota is UNKNOWN or EXHAUSTED (fail closed)."""

    def __init__(self, message: str = "QUOTA_FAIL_CLOSED") -> None:
        super().__init__(message, retryable=False, error_class="QUOTA_FAIL_CLOSED")


class DuplicateDeliveryError(ExecutionError):
    """Raised when a conflicting delivery or attempt is rejected."""

    def __init__(self, message: str = "DUPLICATE_DELIVERY") -> None:
        super().__init__(message, retryable=False, error_class="DUPLICATE_DELIVERY")


class DrainInProgressError(ExecutionError):
    """Raised when execution engine is draining and cannot accept new work."""

    def __init__(self, message: str = "DRAIN_IN_PROGRESS") -> None:
        super().__init__(message, retryable=True, error_class="DRAIN_IN_PROGRESS")


class WorkerExecutionError(ExecutionError):
    """Raised when worker execution crashes, times out, or produces invalid output."""

    def __init__(self, message: str, *, retryable: bool = False, error_class: str = "WORKER_ERROR") -> None:
        super().__init__(message, retryable=retryable, error_class=error_class)


class LateResultError(WorkerExecutionError, StaleFenceError):
    """Raised when a late or stale worker result arrives and is reconciled."""

    def __init__(
        self,
        message: str = "LATE_RESULT_NEEDS_RECONCILIATION",
        *,
        retryable: bool = False,
        error_class: str = "LATE_RESULT_NEEDS_RECONCILIATION",
    ) -> None:
        ExecutionError.__init__(self, message, retryable=retryable, error_class=error_class)


