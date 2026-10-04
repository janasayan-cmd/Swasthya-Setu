"""Core Clinical Task and Work Queue Service (Phase 36).

Orchestrates:
- Task lifecycle management (creation, assignment, acceptance, start, complete, verify, reject, cancel)
- Deduplication and idempotency
- Work queue queries (my, team, patient, facility, organization)
- Dependency engine resolution
- Alert & Notification integrations
- Clinical Safety boundaries (TRD Section 55)
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
from app.core.exceptions import (
    TaskAccessDeniedException,
    TaskAlreadyAcceptedException,
    TaskCancellationNotAllowedException,
    TaskCompletionNotAllowedException,
    TaskDependencyBlockedException,
    TaskDuplicateException,
    TaskInvalidStateException,
    TaskNotFoundException,
    TaskOperationNotAllowedException,
    TaskVerificationNotAllowedException,
)
from app.repositories.task_assignment_repository import TaskAssignmentRepository
from app.repositories.task_repository import TaskRepository
from app.schemas.alert import AlertRecord
from app.schemas.audit import AuditEventRecord, AuditEventType
from app.schemas.notification import NotificationCreate, NotificationType
from app.schemas.task import (
    TaskAcceptRequest,
    TaskCancelRequest,
    TaskCategory,
    TaskCompleteRequest,
    TaskCreate,
    TaskFilter,
    TaskListResponse,
    TaskPriority,
    TaskRecord,
    TaskRejectRequest,
    TaskStartRequest,
    TaskStatus,
    TaskVerifyRequest,
)
from app.schemas.task_assignment import (
    AssigneeType,
    TaskAssignRequest,
    TaskReassignRequest,
)
from app.schemas.task_history import TaskHistoryAction, TaskHistoryEntry
from app.schemas.user import AuthenticatedUserContext
from app.services.alert_service import AlertService
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService
from app.services.task_assignment_service import TaskAssignmentService
from app.services.task_dependency_service import TaskDependencyService
from app.services.task_validation_service import TaskValidationService


class TaskService:
    """Core domain service for clinical and operational task coordination."""

    def __init__(
        self,
        task_repo: Optional[TaskRepository] = None,
        assignment_repo: Optional[TaskAssignmentRepository] = None,
        validation_service: Optional[TaskValidationService] = None,
        assignment_service: Optional[TaskAssignmentService] = None,
        dependency_service: Optional[TaskDependencyService] = None,
        alert_service: Optional[AlertService] = None,
        notification_service: Optional[NotificationService] = None,
        audit_service: Optional[AuditService] = None,
    ) -> None:
        self.task_repo = task_repo or TaskRepository()
        self.assignment_repo = assignment_repo or TaskAssignmentRepository()
        self.val_service = validation_service or TaskValidationService()
        self.assignment_service = assignment_service or TaskAssignmentService(self.assignment_repo)
        self.dependency_service = dependency_service or TaskDependencyService(self.task_repo)
        self.alert_service = alert_service
        self.notification_service = notification_service
        self.audit_service = audit_service

    async def create_task(self, payload: TaskCreate, current_user: AuthenticatedUserContext) -> TaskRecord:
        """Create an actionable clinical or operational task idempotently."""
        # 1. Idempotency Check by explicit client key
        if payload.idempotency_key:
            existing = self.task_repo.get_by_idempotency_key(payload.idempotency_key)
            if existing:
                return existing

        # 2. Idempotency Check by logical identity (source_type, source_id, category, patient_id)
        existing_logical = self.task_repo.get_by_logical_identity(
            source_type=payload.provenance.source_type,
            source_id=payload.provenance.source_id,
            category=payload.category.value,
            patient_id=payload.patient_id,
        )
        if existing_logical:
            return existing_logical

        # 3. Determine initial status
        initial_status = TaskStatus.ASSIGNED if payload.assignee_id else TaskStatus.CREATED

        now = datetime.now(timezone.utc)
        task = TaskRecord(
            id="",
            title=payload.title,
            description=payload.description,
            category=payload.category,
            priority=payload.priority,
            status=initial_status,
            patient_id=payload.patient_id,
            encounter_id=payload.encounter_id,
            organization_id=payload.organization_id or current_user.organization_id,
            facility_id=payload.facility_id or current_user.facility_id,
            assignee_id=payload.assignee_id,
            assignee_type=payload.assignee_type,
            team_id=payload.team_id,
            created_by=current_user.user_id,
            due_at=payload.due_at,
            start_at=payload.start_at,
            verification_required=payload.verification_required,
            dependencies=payload.dependencies,
            provenance=payload.provenance,
            idempotency_key=payload.idempotency_key,
            created_at=now,
            updated_at=now,
        )

        # 4. Evaluate initial prerequisite dependencies (may transition to BLOCKED)
        task = self.dependency_service.evaluate_initial_dependencies(task)

        # 5. Persist
        saved = self.task_repo.save(task)

        # 6. Audit & History
        self.task_repo.add_history(
            task_id=saved.id,
            action=TaskHistoryAction.TASK_CREATED,
            to_status=saved.status.value,
            actor_id=current_user.user_id,
            actor_role=current_user.role,
            reason="Task created from domain event/request",
            metadata={"provenance": payload.provenance.model_dump()},
        )

        if self.audit_service:
            try:
                await self.audit_service.record_event(
                    AuditEventRecord(
                        event_type=AuditEventType.TASK_CREATED,
                        actor_id=current_user.user_id,
                        actor_role=current_user.role,
                        patient_id=saved.patient_id,
                        resource_id=saved.id,
                        action="CREATE_TASK",
                        description=f"Clinical task {saved.id} created ({saved.category.value}).",
                    )
                )
            except Exception:
                pass

        # 7. Assignment notification if assigned
        if saved.assignee_id and self.notification_service:
            try:
                notif = NotificationCreate(
                    recipient_id=saved.assignee_id,
                    recipient_type="CLINICIAN",
                    notification_type=NotificationType.TASK_ASSIGNED,
                    priority=saved.priority.value,
                    title=f"Task Assigned: {saved.title}",
                    body=f"Task {saved.id} ({saved.priority.value}) assigned to you.",
                    variables={
                        "task_title": saved.title,
                        "task_id": saved.id,
                        "priority": saved.priority.value,
                        "category": saved.category.value,
                    },
                    facility_id=saved.facility_id,
                    organization_id=saved.organization_id,
                )
                await self.notification_service.send_notification(notif)
            except Exception:
                pass

        return saved

    async def get_task(self, task_id: str, current_user: AuthenticatedUserContext) -> TaskRecord:
        """Retrieve task by ID with multi-tenant and clinical relationship checks."""
        task = self.task_repo.get_by_id(task_id)
        if not task:
            raise TaskNotFoundException(f"Task '{task_id}' not found.", task_id=task_id)

        # Patient BOLA check
        if current_user.role == "PATIENT":
            if not task.patient_id or (task.patient_id != current_user.patient_id and task.patient_id != current_user.user_id):
                raise TaskAccessDeniedException(f"Patient is not authorized to access task {task_id}.")

        # Multi-tenant facility/organization check for non-admin staff
        if current_user.role not in {"ADMIN", "SYSTEM_ADMIN", "OPERATIONS_ADMIN", "PATIENT"}:
            if current_user.facility_id and task.facility_id and current_user.facility_id != task.facility_id:
                raise TaskAccessDeniedException(f"Clinician is not authorized to access task in facility {task.facility_id}.")

        return task

    async def list_tasks(self, filters: TaskFilter, current_user: AuthenticatedUserContext) -> TaskListResponse:
        """List tasks with tenant scoping, relationship checks, and pagination."""
        allowed_patients: Optional[Set[str]] = None
        org_id = None
        fac_id = None

        if current_user.role == "PATIENT":
            allowed_patients = {current_user.patient_id or current_user.user_id}
        elif current_user.role not in {"ADMIN", "SYSTEM_ADMIN", "OPERATIONS_ADMIN"}:
            org_id = current_user.organization_id
            fac_id = current_user.facility_id

        tasks, total = self.task_repo.list_tasks(
            filters=filters,
            allowed_patient_ids=allowed_patients,
            organization_id=org_id,
            facility_id=fac_id,
        )
        total_pages = math.ceil(total / filters.page_size) if total > 0 else 1
        return TaskListResponse(
            tasks=tasks,
            total=total,
            page=filters.page,
            page_size=filters.page_size,
            total_pages=total_pages,
        )

    async def list_my_tasks(
        self,
        filters: Optional[TaskFilter] = None,
        current_user: Optional[AuthenticatedUserContext] = None,
        **kwargs: Any,
    ) -> TaskListResponse:
        """List tasks assigned to the current user."""
        if isinstance(filters, AuthenticatedUserContext):
            current_user, filters = filters, current_user
        if current_user is None and "current_user" in kwargs:
            current_user = kwargs["current_user"]
        if not current_user:
            raise TaskAccessDeniedException("User context required.")
        f = (filters or TaskFilter()).model_copy(update={"assignee_id": current_user.user_id})
        return await self.list_tasks(f, current_user)

    async def list_team_tasks(
        self,
        team_id: str,
        filters: Optional[TaskFilter] = None,
        current_user: Optional[AuthenticatedUserContext] = None,
        **kwargs: Any,
    ) -> TaskListResponse:
        """List tasks assigned to a specific team."""
        if isinstance(filters, AuthenticatedUserContext):
            current_user, filters = filters, current_user
        if current_user is None and "current_user" in kwargs:
            current_user = kwargs["current_user"]
        if not current_user:
            raise TaskAccessDeniedException("User context required.")
        f = (filters or TaskFilter()).model_copy(update={"team_id": team_id})
        return await self.list_tasks(f, current_user)

    async def list_patient_tasks(
        self,
        patient_id: str,
        filters: Optional[TaskFilter] = None,
        current_user: Optional[AuthenticatedUserContext] = None,
        **kwargs: Any,
    ) -> TaskListResponse:
        """List tasks linked to a specific patient with BOLA verification."""
        if isinstance(filters, AuthenticatedUserContext):
            current_user, filters = filters, current_user
        if current_user is None and "current_user" in kwargs:
            current_user = kwargs["current_user"]
        if not current_user:
            raise TaskAccessDeniedException("User context required.")
        if current_user.role == "PATIENT":
            if current_user.patient_id != patient_id and current_user.user_id != patient_id:
                raise TaskAccessDeniedException("Cannot access tasks of another patient.")
        f = (filters or TaskFilter()).model_copy(update={"patient_id": patient_id})
        return await self.list_tasks(f, current_user)

    async def list_facility_tasks(
        self,
        facility_id: str,
        filters: Optional[TaskFilter] = None,
        current_user: Optional[AuthenticatedUserContext] = None,
        **kwargs: Any,
    ) -> TaskListResponse:
        """List tasks in a facility queue."""
        if isinstance(filters, AuthenticatedUserContext):
            current_user, filters = filters, current_user
        if current_user is None and "current_user" in kwargs:
            current_user = kwargs["current_user"]
        if not current_user:
            raise TaskAccessDeniedException("User context required.")
        if current_user.role not in {"ADMIN", "SYSTEM_ADMIN", "OPERATIONS_ADMIN"}:
            if current_user.facility_id and current_user.facility_id != facility_id:
                raise TaskAccessDeniedException("Unauthorized to access other facility task queues.")
        f = (filters or TaskFilter()).model_copy(update={"facility_id": facility_id})
        return await self.list_tasks(f, current_user)

    async def list_organization_tasks(
        self,
        organization_id: str,
        filters: Optional[TaskFilter] = None,
        current_user: Optional[AuthenticatedUserContext] = None,
        **kwargs: Any,
    ) -> TaskListResponse:
        """List tasks in an organization queue."""
        if isinstance(filters, AuthenticatedUserContext):
            current_user, filters = filters, current_user
        if current_user is None and "current_user" in kwargs:
            current_user = kwargs["current_user"]
        if not current_user:
            raise TaskAccessDeniedException("User context required.")
        if current_user.role not in {"ADMIN", "SYSTEM_ADMIN", "OPERATIONS_ADMIN"}:
            if current_user.organization_id and current_user.organization_id != organization_id:
                raise TaskAccessDeniedException("Unauthorized to access other organization task queues.")
        f = (filters or TaskFilter()).model_copy(update={"organization_id": organization_id})
        return await self.list_tasks(f, current_user)

    async def assign_task(
        self,
        task_id: str,
        request: TaskAssignRequest,
        current_user: AuthenticatedUserContext,
    ) -> TaskRecord:
        """Assign task to target user or team."""
        task = await self.get_task(task_id, current_user)
        self.val_service.validate_transition(task.status, TaskStatus.ASSIGNED)

        updated_task = self.assignment_service.assign_task(task, request, current_user)
        saved = self.task_repo.save(updated_task)

        self.task_repo.add_history(
            task_id=saved.id,
            action=TaskHistoryAction.TASK_ASSIGNED,
            from_status=task.status.value,
            to_status=saved.status.value,
            actor_id=current_user.user_id,
            actor_role=current_user.role,
            reason=request.notes or "Task assigned",
            metadata={"assignee_id": request.assignee_id, "assignee_type": request.assignee_type.value},
        )

        if self.notification_service:
            try:
                notif = NotificationCreate(
                    recipient_id=request.assignee_id,
                    recipient_type="CLINICIAN",
                    notification_type=NotificationType.TASK_ASSIGNED,
                    priority=saved.priority.value,
                    title=f"Task Assigned: {saved.title}",
                    body=f"Task {saved.id} assigned to you.",
                    variables={"task_title": saved.title, "task_id": saved.id, "priority": saved.priority.value, "category": saved.category.value},
                    facility_id=saved.facility_id,
                    organization_id=saved.organization_id,
                )
                await self.notification_service.send_notification(notif)
            except Exception:
                pass

        return saved

    async def reassign_task(
        self,
        task_id: str,
        request: TaskReassignRequest,
        current_user: AuthenticatedUserContext,
    ) -> TaskRecord:
        """Reassign task with mandatory justification."""
        task = await self.get_task(task_id, current_user)

        updated_task = self.assignment_service.reassign_task(task, request, current_user)
        saved = self.task_repo.save(updated_task)

        self.task_repo.add_history(
            task_id=saved.id,
            action=TaskHistoryAction.TASK_REASSIGNED,
            from_status=task.status.value,
            to_status=saved.status.value,
            actor_id=current_user.user_id,
            actor_role=current_user.role,
            reason=request.reason,
            metadata={"new_assignee_id": request.new_assignee_id, "previous_assignee_id": task.assignee_id},
        )

        if self.notification_service:
            try:
                notif = NotificationCreate(
                    recipient_id=request.new_assignee_id,
                    recipient_type="CLINICIAN",
                    notification_type=NotificationType.TASK_REASSIGNED,
                    priority=saved.priority.value,
                    title=f"Task Reassigned: {saved.title}",
                    body=f"Task {saved.id} reassigned to you. Reason: {request.reason}",
                    variables={"task_title": saved.title, "task_id": saved.id, "new_assignee_id": request.new_assignee_id, "reason": request.reason},
                    facility_id=saved.facility_id,
                    organization_id=saved.organization_id,
                )
                await self.notification_service.send_notification(notif)
            except Exception:
                pass

        return saved

    async def accept_task(
        self,
        task_id: str,
        request: TaskAcceptRequest,
        current_user: AuthenticatedUserContext,
    ) -> TaskRecord:
        """Explicitly accept task responsibility."""
        task = await self.get_task(task_id, current_user)

        # Idempotent return if already accepted by this user
        if task.status == TaskStatus.ACCEPTED and task.accepted_by == current_user.user_id:
            return task

        if task.status == TaskStatus.ACCEPTED and task.accepted_by and task.accepted_by != current_user.user_id:
            raise TaskAlreadyAcceptedException(f"Task {task_id} has already been accepted by user '{task.accepted_by}'.")

        # Validate transition from ASSIGNED (or CREATED if assigning upon accept)
        self.val_service.validate_transition(task.status, TaskStatus.ACCEPTED)

        # Assignee authorization check: Must be designated assignee, team member, or clinician/admin
        if task.assignee_id and task.assignee_id != current_user.user_id:
            if current_user.role not in {"ADMIN", "SYSTEM_ADMIN", "DOCTOR", "CLINICIAN"}:
                raise TaskAccessDeniedException("Only the designated assignee or authorized clinician can accept this task.")

        now = datetime.now(timezone.utc)
        updated = task.model_copy(
            update={
                "status": TaskStatus.ACCEPTED,
                "assignee_id": current_user.user_id,
                "accepted_by": current_user.user_id,
                "accepted_at": now,
                "updated_at": now,
            }
        )
        saved = self.task_repo.save(updated)

        self.task_repo.add_history(
            task_id=saved.id,
            action=TaskHistoryAction.TASK_ACCEPTED,
            from_status=task.status.value,
            to_status=saved.status.value,
            actor_id=current_user.user_id,
            actor_role=current_user.role,
            reason=request.note or "Task accepted",
        )
        return saved

    async def start_task(
        self,
        task_id: str,
        request: TaskStartRequest,
        current_user: AuthenticatedUserContext,
    ) -> TaskRecord:
        """Transition accepted task into IN_PROGRESS."""
        task = await self.get_task(task_id, current_user)

        if task.status == TaskStatus.IN_PROGRESS:
            return task  # Idempotent

        # Ensure dependencies are satisfied before starting
        if not self.dependency_service.check_prerequisites_met(task):
            raise TaskDependencyBlockedException("Cannot start task; prerequisite dependencies are not satisfied.")

        self.val_service.validate_transition(task.status, TaskStatus.IN_PROGRESS)

        now = datetime.now(timezone.utc)
        updated = task.model_copy(
            update={
                "status": TaskStatus.IN_PROGRESS,
                "started_at": now,
                "updated_at": now,
            }
        )
        saved = self.task_repo.save(updated)

        self.task_repo.add_history(
            task_id=saved.id,
            action=TaskHistoryAction.TASK_STARTED,
            from_status=task.status.value,
            to_status=saved.status.value,
            actor_id=current_user.user_id,
            actor_role=current_user.role,
            reason=request.note or "Work started on task",
        )
        return saved

    async def complete_task(
        self,
        task_id: str,
        request: TaskCompleteRequest,
        current_user: AuthenticatedUserContext,
    ) -> TaskRecord:
        """Report task work completed."""
        task = await self.get_task(task_id, current_user)

        if task.status in {TaskStatus.COMPLETED, TaskStatus.VERIFIED}:
            return task  # Idempotent completion return

        # Validate caller authority: Patients cannot complete clinical tasks
        if current_user.role == "PATIENT" and task.category != TaskCategory.PATIENT_CONTACT_TASK:
            raise TaskCompletionNotAllowedException("Patients cannot complete clinical tasks.")

        self.val_service.validate_transition(task.status, TaskStatus.COMPLETED)

        now = datetime.now(timezone.utc)
        target_status = TaskStatus.VERIFICATION_PENDING if task.verification_required else TaskStatus.COMPLETED

        updated = task.model_copy(
            update={
                "status": target_status,
                "completed_by": current_user.user_id,
                "completed_at": now,
                "completion_notes": request.completion_notes,
                "updated_at": now,
            }
        )
        saved = self.task_repo.save(updated)

        action = TaskHistoryAction.TASK_VERIFICATION_REQUESTED if task.verification_required else TaskHistoryAction.TASK_COMPLETED
        self.task_repo.add_history(
            task_id=saved.id,
            action=action,
            from_status=task.status.value,
            to_status=saved.status.value,
            actor_id=current_user.user_id,
            actor_role=current_user.role,
            reason=request.completion_notes or "Task work completed",
        )

        # Cascade unblock dependent tasks if no verification required (or after verification)
        if not task.verification_required:
            self.dependency_service.resolve_completed_prerequisite(
                completed_task_id=saved.id,
                actor_id=current_user.user_id,
                actor_role=current_user.role,
            )

        # Notify supervisor if verification required
        if task.verification_required and self.notification_service and saved.facility_id:
            try:
                notif = NotificationCreate(
                    recipient_id=f"supervisor_{saved.facility_id}",
                    recipient_type="CLINICIAN",
                    notification_type=NotificationType.TASK_VERIFICATION_REQUIRED,
                    priority=saved.priority.value,
                    title=f"Verification Required: {saved.title}",
                    body=f"Task {saved.id} completed by {current_user.user_id}; verification review required.",
                    variables={"task_title": saved.title, "task_id": saved.id},
                    facility_id=saved.facility_id,
                    organization_id=saved.organization_id,
                )
                await self.notification_service.send_notification(notif)
            except Exception:
                pass

        return saved

    async def verify_task(
        self,
        task_id: str,
        request: TaskVerifyRequest,
        current_user: AuthenticatedUserContext,
    ) -> TaskRecord:
        """Formally verify or reject verification for a completed task."""
        task = await self.get_task(task_id, current_user)

        self.val_service.validate_verifier(task, current_user)

        if task.status not in {TaskStatus.COMPLETED, TaskStatus.VERIFICATION_PENDING}:
            raise TaskInvalidStateException(
                f"Cannot verify task in status '{task.status.value}'. Must be COMPLETED or VERIFICATION_PENDING."
            )

        now = datetime.now(timezone.utc)
        if request.approved:
            updated = task.model_copy(
                update={
                    "status": TaskStatus.VERIFIED,
                    "verified_by": current_user.user_id,
                    "verified_at": now,
                    "verification_notes": request.verification_notes,
                    "updated_at": now,
                }
            )
            saved = self.task_repo.save(updated)

            self.task_repo.add_history(
                task_id=saved.id,
                action=TaskHistoryAction.TASK_VERIFIED,
                from_status=task.status.value,
                to_status=saved.status.value,
                actor_id=current_user.user_id,
                actor_role=current_user.role,
                reason=request.verification_notes or "Task verified by supervisor",
            )

            # Cascade unblock dependent tasks
            self.dependency_service.resolve_completed_prerequisite(
                completed_task_id=saved.id,
                actor_id=current_user.user_id,
                actor_role=current_user.role,
            )
            return saved
        else:
            # Verification rejected -> return task to REJECTED or ASSIGNED for rework
            updated = task.model_copy(
                update={
                    "status": TaskStatus.REJECTED,
                    "verification_notes": request.verification_notes,
                    "updated_at": now,
                }
            )
            saved = self.task_repo.save(updated)

            self.task_repo.add_history(
                task_id=saved.id,
                action=TaskHistoryAction.TASK_REJECTED,
                from_status=task.status.value,
                to_status=saved.status.value,
                actor_id=current_user.user_id,
                actor_role=current_user.role,
                reason=request.verification_notes or "Task verification failed; rework required.",
            )
            return saved

    async def reject_task(
        self,
        task_id: str,
        request: TaskRejectRequest,
        current_user: AuthenticatedUserContext,
    ) -> TaskRecord:
        """Reject assignment or task execution with mandatory reason."""
        task = await self.get_task(task_id, current_user)
        self.val_service.validate_transition(task.status, TaskStatus.REJECTED)

        now = datetime.now(timezone.utc)
        updated = task.model_copy(
            update={
                "status": TaskStatus.REJECTED,
                "rejected_by": current_user.user_id,
                "rejected_at": now,
                "rejection_reason": request.reason,
                "updated_at": now,
            }
        )
        saved = self.task_repo.save(updated)

        self.task_repo.add_history(
            task_id=saved.id,
            action=TaskHistoryAction.TASK_REJECTED,
            from_status=task.status.value,
            to_status=saved.status.value,
            actor_id=current_user.user_id,
            actor_role=current_user.role,
            reason=request.reason,
        )
        return saved

    async def cancel_task(
        self,
        task_id: str,
        request: TaskCancelRequest,
        current_user: AuthenticatedUserContext,
    ) -> TaskRecord:
        """Cancel an active task with mandatory justification."""
        task = await self.get_task(task_id, current_user)

        if task.status in {TaskStatus.COMPLETED, TaskStatus.VERIFIED}:
            raise TaskCancellationNotAllowedException("Completed or verified tasks cannot be cancelled.")

        self.val_service.validate_transition(task.status, TaskStatus.CANCELLED)

        now = datetime.now(timezone.utc)
        updated = task.model_copy(
            update={
                "status": TaskStatus.CANCELLED,
                "cancelled_by": current_user.user_id,
                "cancelled_at": now,
                "cancellation_reason": request.reason,
                "updated_at": now,
            }
        )
        saved = self.task_repo.save(updated)

        self.task_repo.add_history(
            task_id=saved.id,
            action=TaskHistoryAction.TASK_CANCELLED,
            from_status=task.status.value,
            to_status=saved.status.value,
            actor_id=current_user.user_id,
            actor_role=current_user.role,
            reason=request.reason,
        )
        return saved

    async def get_task_history(self, task_id: str, current_user: AuthenticatedUserContext) -> List[TaskHistoryEntry]:
        """Retrieve audit history ledger for a task."""
        # Ensure user has access to task
        await self.get_task(task_id, current_user)
        return self.task_repo.get_history(task_id)

    async def create_task_from_alert(self, alert_id: str, current_user: AuthenticatedUserContext) -> TaskRecord:
        """Create a clinical follow-up task from an acknowledged alert (TRD Section 22)."""
        if not self.alert_service:
            raise TaskOperationNotAllowedException("AlertService integration is not configured.")

        alert = await self.alert_service.get_alert(alert_id, current_user)
        if alert.status.value not in {"ACKNOWLEDGED", "CREATED", "DELIVERED"}:
            raise TaskInvalidStateException(f"Cannot generate task from alert in status '{alert.status.value}'.")

        # Map alert category to task category
        category_map = {
            "DIAGNOSTIC_RESULT_ALERT": TaskCategory.DIAGNOSTIC_REVIEW_TASK,
            "MEDICATION_SAFETY_ALERT": TaskCategory.MEDICATION_REVIEW_TASK,
            "TRIAGE_ALERT": TaskCategory.CLINICAL_TASK,
            "APPOINTMENT_ALERT": TaskCategory.APPOINTMENT_TASK,
            "TRANSFER_ALERT": TaskCategory.TRANSFER_TASK,
            "INTEROPERABILITY_ALERT": TaskCategory.INTEROPERABILITY_TASK,
            "DATA_QUALITY_ALERT": TaskCategory.DATA_QUALITY_TASK,
        }
        task_category = category_map.get(alert.category.value, TaskCategory.CLINICAL_TASK)

        # Map priority from policy/severity: CRITICAL -> URGENT, HIGH -> HIGH, else NORMAL
        priority = TaskPriority.URGENT if alert.severity.value == "CRITICAL" else (
            TaskPriority.HIGH if alert.severity.value == "HIGH" else TaskPriority.NORMAL
        )

        clinician_id = getattr(alert, "responsible_clinician_id", None)
        if not clinician_id and alert.acknowledged_by:
            clinician_id = alert.acknowledged_by
        elif not clinician_id and alert.recipients:
            clinician_id = alert.recipients[0].recipient_id

        from app.schemas.task import TaskProvenance
        create_payload = TaskCreate(
            title=f"Review: {alert.title}",
            description=f"Action task created from Alert {alert.id}. Category: {alert.category.value}.",
            category=task_category,
            priority=priority,
            patient_id=alert.patient_id,
            facility_id=alert.facility_id,
            organization_id=alert.organization_id,
            assignee_id=clinician_id,
            assignee_type=AssigneeType.USER if clinician_id else None,
            verification_required=alert.severity.value == "CRITICAL",
            provenance=TaskProvenance(
                source_type="alert",
                source_id=alert.id,
                source_event_id=alert.provenance.source_event_id if alert.provenance else None,
                source_system="alert_service",
                policy_id="POLICY_ALERT_FOLLOW_UP_TASK",
                policy_version="1.0",
            ),
            idempotency_key=f"IDEMP-TASK-ALERT-{alert.id}",
        )
        return await self.create_task(create_payload, current_user)
