"""
Tests for Stage Evaluator (Acceptance #8).
"""

import tempfile
import unittest
from pathlib import Path

from v7_harness.stage_evaluator import AcceptanceCheck, StageEvaluator


class TestStageEvaluator(unittest.TestCase):

    def setUp(self):
        self.evaluator = StageEvaluator()

    def test_eligible_when_all_checks_pass_and_no_approval_actions(self):
        checks = [
            AcceptanceCheck(criterion_id="AC-1", description="Lease validated", passed=True),
            AcceptanceCheck(criterion_id="AC-2", description="Ledger verified", passed=True),
            AcceptanceCheck(criterion_id="AC-3", description="Proof receipt created", passed=True),
        ]
        res = self.evaluator.evaluate_eligibility(
            current_task_id="U07",
            checks=checks,
            pending_actions=[],
            next_task_candidate="U08",
        )
        self.assertTrue(res.is_eligible)
        self.assertEqual(res.recommended_next_task, "U08")
        self.assertFalse(res.plan_mutated)

    def test_ineligible_when_any_check_fails(self):
        checks = [
            AcceptanceCheck(criterion_id="AC-1", description="Lease validated", passed=True),
            AcceptanceCheck(criterion_id="AC-2", description="Ledger verified", passed=False),
        ]
        res = self.evaluator.evaluate_eligibility(
            current_task_id="U07",
            checks=checks,
            pending_actions=[],
            next_task_candidate="U08",
        )
        self.assertFalse(res.is_eligible)
        self.assertIsNone(res.recommended_next_task)
        self.assertIn("AC-2", res.reason)
        self.assertFalse(res.plan_mutated)

    def test_ineligible_when_user_approval_action_pending(self):
        checks = [
            AcceptanceCheck(criterion_id="AC-1", description="All good", passed=True),
        ]
        # Actions requiring user approval: DELETE, DEPLOY, GIT_PUSH
        res = self.evaluator.evaluate_eligibility(
            current_task_id="U07",
            checks=checks,
            pending_actions=["DELETE_OBSOLETE_BRANCH", "GIT_PUSH"],
            next_task_candidate="U08",
        )
        self.assertFalse(res.is_eligible)
        self.assertTrue(len(res.pending_approval_actions) > 0)
        self.assertIn("User approval required", res.reason)
        self.assertFalse(res.plan_mutated)


if __name__ == "__main__":
    unittest.main()
