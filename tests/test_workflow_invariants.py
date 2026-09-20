"""
Tests for Workflow Invariants, WIP limits, Owner invariant, and Fail-Closed Conflicts (Acceptance #4 & #5).
"""

import unittest

from v7_harness.workflow_invariants import (
    ExecutionMode,
    FailClosedConflictError,
    InvalidTransitionError,
    OwnerInvariantError,
    TaskStatus,
    WIPInvariantError,
    WorkflowEngine,
)


class TestWorkflowInvariants(unittest.TestCase):

    def setUp(self):
        self.engine = WorkflowEngine()
        self.engine.register_task("U07", initial_status=TaskStatus.READY, owner="Antigravity")
        self.engine.register_task("U08", initial_status=TaskStatus.READY, owner="Codex")

    def test_valid_lifecycle_transitions(self):
        # READY -> ACTIVE
        self.engine.transition_status("U07", TaskStatus.ACTIVE)
        self.assertEqual(self.engine.tasks["U07"].status, TaskStatus.ACTIVE)

        # ACTIVE -> REVIEW
        self.engine.transition_status("U07", TaskStatus.REVIEW)
        self.assertEqual(self.engine.tasks["U07"].status, TaskStatus.REVIEW)

        # REVIEW -> DONE
        self.engine.transition_status("U07", TaskStatus.DONE)
        self.assertEqual(self.engine.tasks["U07"].status, TaskStatus.DONE)

    def test_invalid_direct_transition_rejected(self):
        # READY -> DONE is illegal
        with self.assertRaises(InvalidTransitionError):
            self.engine.transition_status("U08", TaskStatus.DONE)

    def test_done_is_terminal(self):
        self.engine.transition_status("U07", TaskStatus.ACTIVE)
        self.engine.transition_status("U07", TaskStatus.REVIEW)
        self.engine.transition_status("U07", TaskStatus.DONE)
        with self.assertRaises(InvalidTransitionError):
            self.engine.transition_status("U07", TaskStatus.ACTIVE)

    def test_wip_invariant_single_active_only(self):
        self.engine.transition_status("U07", TaskStatus.ACTIVE)
        # Attempting to make U08 active while U07 is active must raise WIPInvariantError
        with self.assertRaises(WIPInvariantError):
            self.engine.transition_status("U08", TaskStatus.ACTIVE)

    def test_owner_invariant_enforced(self):
        self.engine.register_task("U09", initial_status=TaskStatus.READY, owner=None)
        # Attempting to activate U09 without owner must fail
        with self.assertRaises(OwnerInvariantError):
            self.engine.transition_status("U09", TaskStatus.ACTIVE, owner="")

    def test_claim_conflict_fails_closed_between_sessions(self):
        # Session 1 claims U07 in STANDALONE mode
        self.engine.claim_execution("U07", actor="Antigravity", session_id="sess-1", mode=ExecutionMode.STANDALONE)

        # Session 2 (e.g. MANAGED run by Codex or another runner) attempts to claim U07
        with self.assertRaises(FailClosedConflictError):
            self.engine.claim_execution("U07", actor="Antigravity", session_id="sess-2", mode=ExecutionMode.MANAGED)

    def test_claim_conflict_fails_closed_when_different_task_active(self):
        self.engine.claim_execution("U07", actor="Antigravity", session_id="sess-1", mode=ExecutionMode.STANDALONE)
        # Session trying to claim U08 while U07 is active fails closed
        with self.assertRaises(FailClosedConflictError):
            self.engine.claim_execution("U08", actor="Codex", session_id="sess-3", mode=ExecutionMode.MANAGED)

    def test_release_execution_advances_to_review(self):
        self.engine.claim_execution("U07", actor="Antigravity", session_id="sess-1", mode=ExecutionMode.STANDALONE)
        released = self.engine.release_execution("U07", session_id="sess-1", target_status=TaskStatus.REVIEW)
        self.assertEqual(released.status, TaskStatus.REVIEW)
        self.assertIsNone(released.active_claim_session)


if __name__ == "__main__":
    unittest.main()
