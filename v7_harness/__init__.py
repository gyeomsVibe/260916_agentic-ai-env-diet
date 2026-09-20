"""
v7_harness: Minimal reversible local orchestration harness.
Standard library only, zero external dependencies.
"""

from .benchmark_hook import BenchmarkHook, BenchmarkResult
from .context_lease import ContextLease, ContextLeaseValidator, LeaseValidationResult
from .intent_ledger import IntentEntry, IntentLedger
from .proof_receipt import ProofReceipt, ProofReceiptStore, compute_proof_hash, run_with_receipt
from .reporter import ExecutionReport, generate_report
from .snapshot import ManifestEntry, Snapshot, take_snapshot
from .stage_evaluator import AcceptanceCheck, StageEligibility, StageEvaluator
from .workflow_invariants import (
    ExecutionMode,
    FailClosedConflictError,
    InvalidTransitionError,
    OwnerInvariantError,
    TaskRecord,
    TaskStatus,
    WIPInvariantError,
    WorkflowEngine,
)

__version__ = "0.1.0"

__all__ = [
    "ContextLease",
    "ContextLeaseValidator",
    "LeaseValidationResult",
    "IntentEntry",
    "IntentLedger",
    "ProofReceipt",
    "ProofReceiptStore",
    "compute_proof_hash",
    "run_with_receipt",
    "WorkflowEngine",
    "TaskRecord",
    "TaskStatus",
    "ExecutionMode",
    "InvalidTransitionError",
    "WIPInvariantError",
    "OwnerInvariantError",
    "FailClosedConflictError",
    "Snapshot",
    "ManifestEntry",
    "take_snapshot",
    "ExecutionReport",
    "generate_report",
    "StageEvaluator",
    "AcceptanceCheck",
    "StageEligibility",
    "BenchmarkHook",
    "BenchmarkResult",
]
