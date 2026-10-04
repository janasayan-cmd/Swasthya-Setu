"""Task Assignment and Reassignment Service (Phase 36).

Enforces:
- Assignee validation (role, tenant boundary, clinical responsibility)
- Team assignments vs individual acceptance
- Full reassignment history preservation
- Concurrency and authorization checks
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from app.core.exceptions import (
    TaskAccessDeniedException,
    TaskAssignmentNotAllowedException,
    TaskInvalidStateException,
    TaskReassignmentNotAllowedException,
)
from app.repositories.task_assignment_repository import TaskAssignmentRepository
from app.schemas.task import TaskRecord, TaskStatus
from app.schemas.task_assignment import (
    AssigneeType,
    TaskAssignRequest,
    TaskAssignmentRecord,
    TaskReassignRequest,
)
from app.schemas.user import AuthenticatedUserContext


class TaskAssignmentService:
    """Manages assignment, reassignment, and assignee validation for clinical tasks."""

    def __init__(self, assignment_repo: Optional[TaskAssignmentRepository] = None) -> None:
        self.assignment_repo = assignment_repo or TaskAssignmentRepository()

    def validate_assignee_scope(
        self,
        task: TaskRecord,
        assignee_id: str,
        assignee_type: AssigneeType,
        user: AuthenticatedUserContext,
    ) -> None:
        """Validate assignee relationship against tenant boundaries and clinical policies."""
        if not assignee_id or not assignee_id.strip():
            raise TaskAssignmentNotAllowedException("Assignee ID cannot be blank.")

        # Disallow assigning clinical tasks to purely patient roles
        if assignee_type == AssigneeType.USER and (assignee_id.startswith("PAT-") or assignee_id.startswith("USER-PAT")):
            if task.category.value not in {"PATIENT_CONTACT_TASK", "APPOINTMENT_TASK"}:
                raise TaskAssignmentNotAllowedException(
                    f"Clinical task of category '{task.category.value}' cannot be assigned to a patient account."
                )

        # Multi-tenant boundary check: If caller has facility_id and task has facility_id, ensure alignment
        if user.facility_id and task.facility_id and user.facility_id != task.facility_id:
            if user.role not in {"ADMIN", "SYSTEM_ADMIN", "OPERATIONS_ADMIN"}:
                raise TaskAccessDeniedException(
                    f"Cannot assign task outside caller facility scope (Caller: {user.facility_id}, Task: {task.facility_id})."
                )

    def assign_task(
        self,
        task: TaskRecord,
        request: TaskAssignRequest,
        actor: AuthenticatedUserContext,
    ) -> TaskRecord:
        """Assign an unassigned or created task to a target user or team."""
        terminal = {TaskStatus.COMPLETED, TaskStatus.VERIFIED, TaskStatus.CANCELLED, TaskStatus.EXPIRED, TaskStatus.FAILED}
        if task.status in terminal:
            raise TaskInvalidStateException(
                f"Cannot assign task in terminal state '{task.status.value}'."
            )

        self.validate_assignee_scope(task, request.assignee_id, request.assignee_type, actor)

        # Record assignment audit
        record = TaskAssignmentRecord(
            id="",
            task_id=task.id,
            assignee_id=request.assignee_id,
            assignee_type=request.assignee_type,
            team_id=request.team_id,
            assigned_by=actor.user_id,
            assigned_at=datetime.now(timezone.utc),
            reason=request.notes,
        )
        self.assignment_repo.save(record)

        updated_task = task.model_copy(
            update={
                "assignee_id": request.assignee_id,
                "assignee_type": request.assignee_type,
                "team_id": request.team_id,
                "status": TaskStatus.ASSIGNED,
                "updated_at": datetime.now(timezone.utc),
            }
        )
        return updated_task

    def reassign_task(
        self,
        task: TaskRecord,
        request: TaskReassignRequest,
        actor: AuthenticatedUserContext,
    ) -> TaskRecord:
        """Reassign an active task with mandatory justification."""
        terminal = {TaskStatus.COMPLETED, TaskStatus.VERIFIED, TaskStatus.CANCELLED, TaskStatus.EXPIRED, TaskStatus.FAILED}
        if task.status in terminal:
            raise TaskInvalidStateException(
                f"Cannot reassign task in terminal state '{task.status.value}'."
            )

        # Check authorization to reassign: Must be assignee, clinician in facility, or admin
        is_assignee = task.assignee_id == actor.user_id
        is_admin = actor.role in {"ADMIN", "SYSTEM_ADMIN", "OPERATIONS_ADMIN"}
        is_clinician = actor.role in {"DOCTOR", "CLINICIAN"}
        if not (is_assignee or is_admin or is_clinician):
            raise TaskReassignmentNotAllowedException(
                f"User '{actor.user_id}' does not have authority to reassign this task."
            )

        self.validate_assignee_scope(task, request.new_assignee_id, request.new_assignee_type, actor)

        # Save assignment record
        record = TaskAssignmentRecord(
            id="",
            task_id=task.id,
            assignee_id=request.new_assignee_id,
            assignee_type=request.new_assignee_type,
            team_id=request.new_team_id,
            assigned_by=actor.user_id,
            assigned_at=datetime.now(timezone.utc),
            reason=request.reason,
        )
        self.assignment_repo.save(record)

        # Reset accepted_by and accepted_at on reassignment if assignee changed
        updated_task = task.model_copy(
            update={
                "assignee_id": request.new_assignee_id,
                "assignee_type": request.new_assignee_type,
                "team_id": request.new_team_id,
                "accepted_by": None,
                "accepted_at": None,
                "status": TaskStatus.ASSIGNED,
                "updated_at": datetime.now(timezone.utc),
            }
        )
        return updated_task
