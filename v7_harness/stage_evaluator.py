"""
Stage evaluator module for v7 harness.

Evaluates acceptance conditions and user approval gates to recommend next-stage eligibility.
Strictly read-only with respect to `.coord/PLAN.md` and subsequent task cards;
never mutates the master plan or activates next cards directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Sequence

# Gate actions that strictly require explicit user approval
USER_APPROVAL_GATES = {
    "DELETE",
    "OVERWRITE_PROTECTED",
    "GIT_PUSH",
    "DEPLOY",
    "PAYMENT",
    "CREDENTIAL_CHANGE",
    "PERMISSION_CHANGE",
}


@dataclass
class AcceptanceCheck:
    criterion_id: str
    description: str
    passed: bool
    evidence_receipt_id: Optional[str] = None
    notes: Optional[str] = None


@dataclass
class StageEligibility:
    current_task_id: str
    all_acceptance_passed: bool
    pending_approval_actions: list[str]
    is_eligible: bool
    recommended_next_task: Optional[str]
    reason: str
    plan_mutated: bool = False  # Always False by design invariant

    def to_dict(self) -> dict[str, Any]:
        return {
            "current_task_id": self.current_task_id,
            "all_acceptance_passed": self.all_acceptance_passed,
            "pending_approval_actions": self.pending_approval_actions,
            "is_eligible": self.is_eligible,
            "recommended_next_task": self.recommended_next_task,
            "reason": self.reason,
            "plan_mutated": self.plan_mutated,
        }


class StageEvaluator:
    """Evaluates task readiness and eligibility for the next stage without mutating master plan."""

    def __init__(self, protected_plan_path: Optional[str] = None):
        self.protected_plan_path = protected_plan_path

    def evaluate_eligibility(
        self,
        current_task_id: str,
        checks: Sequence[AcceptanceCheck],
        pending_actions: Sequence[str],
        next_task_candidate: Optional[str] = None,
    ) -> StageEligibility:
        failing_checks = [c for c in checks if not c.passed]
        all_passed = len(failing_checks) == 0

        # Check for any actions in the user approval gate
        triggered_approvals = [
            action for action in pending_actions
            if action.upper() in USER_APPROVAL_GATES or any(gate in action.upper() for gate in USER_APPROVAL_GATES)
        ]

        if not all_passed:
            failed_ids = [c.criterion_id for c in failing_checks]
            return StageEligibility(
                current_task_id=current_task_id,
                all_acceptance_passed=False,
                pending_approval_actions=triggered_approvals,
                is_eligible=False,
                recommended_next_task=None,
                reason=f"Acceptance criteria not satisfied: failed {failed_ids}",
                plan_mutated=False,
            )

        if triggered_approvals:
            return StageEligibility(
                current_task_id=current_task_id,
                all_acceptance_passed=True,
                pending_approval_actions=triggered_approvals,
                is_eligible=False,
                recommended_next_task=None,
                reason=f"User approval required before next stage: {triggered_approvals}",
                plan_mutated=False,
            )

        # All passed and no user approval needed -> eligible for next stage recommendation
        return StageEligibility(
            current_task_id=current_task_id,
            all_acceptance_passed=True,
            pending_approval_actions=[],
            is_eligible=True,
            recommended_next_task=next_task_candidate,
            reason=f"All {len(checks)} acceptance criteria met with receipts; no user approval gates pending.",
            plan_mutated=False,
        )
