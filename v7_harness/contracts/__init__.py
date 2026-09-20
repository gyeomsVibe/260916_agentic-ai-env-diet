"""U10 versioned contracts for the future broker core.

This package is deliberately runtime-neutral: only tests may open SQLite here.
"""

from .authority import AuthorityDecision, validate_authority
from .compatibility import CompatibilityDecision, evaluate_compatibility
from .database import (
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
)
from .schemas import SchemaValidationError, load_schema, validate_document
from .execution import WorkerDecision, interpret_worker_result

__all__ = [
    "AuthorityDecision",
    "CompatibilityDecision",
    "MIGRATIONS",
    "MigrationError",
    "SchemaValidationError",
    "WorkerDecision",
    "ack_delivery",
    "apply_migrations",
    "claim_lease",
    "create_checkpoint",
    "create_effect",
    "create_receipt",
    "evaluate_compatibility",
    "load_schema",
    "interpret_worker_result",
    "mark_attempt_succeeded",
    "validate_promotion_candidate",
    "validate_authority",
    "validate_document",
]
