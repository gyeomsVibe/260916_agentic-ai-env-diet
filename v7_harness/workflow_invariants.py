"""
Workflow invariants and state transition module for v7 harness.

Enforces:
1. Permitted status transitions: READY -> ACTIVE -> REVIEW -> DONE, with BLOCKED/rework paths.
2. Workspace-wide WIP invariant: at most ONE task in ACTIVE status at any time.
3. Single owner invariant: every ACTIVE task must have a valid non-empty single owner.
4. Fail-closed concurrency conflicts: Managed vs Standalone executions fail closed
   if attempting to claim or execute an already occupied or conflicting task/scope.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class TaskStatus(str, Enum):
    BACKLOG = "BACKLOG"
    READY = "READY"
    ACTIVE = "ACTIVE"
    REVIEW = "REVIEW"
    DONE = "DONE"
    BLOCKED = "BLOCKED"


class ExecutionMode(str, Enum):
    MANAGED = "MANAGED"
    STANDALONE = "STANDALONE"


# Valid state transitions
VALID_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.BACKLOG: {TaskStatus.READY, TaskStatus.BLOCKED},
    TaskStatus.READY: {TaskStatus.ACTIVE, TaskStatus.BLOCKED},
    TaskStatus.ACTIVE: {TaskStatus.REVIEW, TaskStatus.BLOCKED},
    TaskStatus.REVIEW: {TaskStatus.DONE, TaskStatus.ACTIVE, TaskStatus.BLOCKED},
    TaskStatus.BLOCKED: {TaskStatus.READY},
    TaskStatus.DONE: set(),  # Terminal state
}


class WorkflowError(Exception):
    """Base exception for workflow invariant violations."""
    pass


class InvalidTransitionError(WorkflowError):
    """Raised when an illegal status transition is attempted."""
    pass


class WIPInvariantError(WorkflowError):
    """Raised when more than one task attempts to become ACTIVE concurrently."""
    pass


class OwnerInvariantError(WorkflowError):
    """Raised when an ACTIVE task lacks a valid designated single owner."""
    pass


class FailClosedConflictError(WorkflowError):
    """Raised when Managed/Standalone executions encounter an active ownership conflict."""
    pass


@dataclass
class TaskRecord:
    task_id: str
    status: TaskStatus
    owner: Optional[str] = None
    scope: list[str] = field(default_factory=list)
    active_claim_session: Optional[str] = None
    active_claim_mode: Optional[ExecutionMode] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "owner": self.owner,
            "scope": self.scope,
            "active_claim_session": self.active_claim_session,
            "active_claim_mode": self.active_claim_mode.value if self.active_claim_mode else None,
        }


class WorkflowEngine:
    """Enforces state transitions, single-active WIP, single-owner, and conflict fail-closed invariants."""

    def __init__(self, tasks: Optional[dict[str, TaskRecord]] = None):
        self._tasks: dict[str, TaskRecord] = tasks or {}

    @property
    def tasks(self) -> dict[str, TaskRecord]:
        return dict(self._tasks)

    def register_task(
        self,
        task_id: str,
        initial_status: TaskStatus = TaskStatus.READY,
        owner: Optional[str] = None,
        scope: Optional[list[str]] = None,
    ) -> TaskRecord:
        if task_id in self._tasks:
            raise ValueError(f"Task '{task_id}' already registered")
        record = TaskRecord(
            task_id=task_id,
            status=initial_status,
            owner=owner,
            scope=scope or ["*"],
        )
        self._tasks[task_id] = record
        return record

    def get_active_task(self) -> Optional[TaskRecord]:
        """Returns the currently ACTIVE task, or None."""
        active_list = [t for t in self._tasks.values() if t.status == TaskStatus.ACTIVE]
        if len(active_list) > 1:
            raise WIPInvariantError(
                f"WIP invariant violated! Multiple active tasks found: {[t.task_id for t in active_list]}"
            )
        return active_list[0] if active_list else None

    def transition_status(
        self,
        task_id: str,
        target_status: TaskStatus,
        owner: Optional[str] = None,
    ) -> TaskRecord:
        """
        Transition task to target_status while enforcing:
        1. Allowed transition table.
        2. WIP invariant (at most 1 ACTIVE task in the entire system).
        3. Owner invariant (ACTIVE requires a non-empty single owner).
        """
        if task_id not in self._tasks:
            raise KeyError(f"Task '{task_id}' not found")

        current = self._tasks[task_id]
        from_status = current.status

        # 1. Transition check
        allowed = VALID_TRANSITIONS.get(from_status, set())
        if target_status not in allowed:
            raise InvalidTransitionError(
                f"Illegal transition for task '{task_id}': {from_status.value} -> {target_status.value}. "
                f"Allowed from {from_status.value}: {[s.value for s in allowed]}"
            )

        # 2. WIP check
        if target_status == TaskStatus.ACTIVE:
            current_active = self.get_active_task()
            if current_active is not None and current_active.task_id != task_id:
                raise WIPInvariantError(
                    f"WIP limit exceeded: Task '{current_active.task_id}' is already ACTIVE. "
                    f"Cannot activate '{task_id}' until active task transitions out of ACTIVE."
                )

        # 3. Owner check
        effective_owner = owner or current.owner
        if target_status == TaskStatus.ACTIVE:
            if not effective_owner or not effective_owner.strip():
                raise OwnerInvariantError(
                    f"Owner invariant violated: Task '{task_id}' cannot become ACTIVE without a designated owner."
                )

        current.status = target_status
        if owner is not None:
            current.owner = owner

        # If transitioning out of ACTIVE, clear any active claim session
        if target_status != TaskStatus.ACTIVE:
            current.active_claim_session = None
            current.active_claim_mode = None

        return current

    def claim_execution(
        self,
        task_id: str,
        actor: str,
        session_id: str,
        mode: ExecutionMode,
    ) -> TaskRecord:
        """
        Claim execution of a task by a managed or standalone runner.
        Fails closed on any conflict.
        """
        if task_id not in self._tasks:
            raise KeyError(f"Task '{task_id}' not found")

        task = self._tasks[task_id]

        # Check if another task is ACTIVE
        active_task = self.get_active_task()
        if active_task and active_task.task_id != task_id:
            raise FailClosedConflictError(
                f"Fail-closed: Cannot claim '{task_id}' because task '{active_task.task_id}' is currently ACTIVE."
            )

        # Check existing active claim session
        if task.active_claim_session and task.active_claim_session != session_id:
            raise FailClosedConflictError(
                f"Fail-closed: Task '{task_id}' is already claimed by session '{task.active_claim_session}' "
                f"(mode: {task.active_claim_mode}). Current claim attempt by session '{session_id}' (actor: {actor}) rejected."
            )

        # Check owner match
        if task.owner and task.owner != actor:
            raise FailClosedConflictError(
                f"Fail-closed: Task '{task_id}' owner is '{task.owner}', but claim was made by actor '{actor}'."
            )

        # Ensure task is ACTIVE
        if task.status != TaskStatus.ACTIVE:
            self.transition_status(task_id, TaskStatus.ACTIVE, owner=actor)

        task.active_claim_session = session_id
        task.active_claim_mode = mode
        return task

    def release_execution(
        self,
        task_id: str,
        session_id: str,
        target_status: TaskStatus = TaskStatus.REVIEW,
    ) -> TaskRecord:
        """Release an execution claim, advancing status to REVIEW (or BLOCKED)."""
        if task_id not in self._tasks:
            raise KeyError(f"Task '{task_id}' not found")

        task = self._tasks[task_id]
        if task.active_claim_session and task.active_claim_session != session_id:
            raise FailClosedConflictError(
                f"Fail-closed: Cannot release task '{task_id}' from session '{session_id}' "
                f"because it is held by session '{task.active_claim_session}'."
            )

        return self.transition_status(task_id, target_status)
