"""Clinical Tasks, Work Queues & Action Management Endpoints (Phase 36).

CORE SAFETY PRINCIPLES:
- TASK != CLINICAL DECISION
- TASK != DIAGNOSIS
- TASK != PRESCRIPTION
- TASK != TREATMENT
- TASK != MEDICATION CHANGE
- TASK != TRIAGE
- TASK != EMERGENCY DISPATCH
- ALERT != TASK
- TASK CREATED != TASK STARTED
- TASK STARTED != TASK COMPLETED
- TASK COMPLETED != CLINICAL OUTCOME
- TASK ASSIGNED != TASK ACCEPTED
- TASK ACCEPTED != TASK PERFORMED
- TASK PERFORMED != TASK VERIFIED
- AI-GENERATED SUGGESTION != AUTHORIZED CLINICAL TASK
- Database remains the source of truth.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status

from app.api.deps import (
    get_current_user,
    get_task_escalation_service,
    get_task_service,
)
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
    TaskAssignRequest,
    TaskReassignRequest,
)
from app.schemas.task_history import TaskHistoryEntry
from app.schemas.user import AuthenticatedUserContext
from app.services.task_escalation_service import TaskEscalationService
from app.services.task_service import TaskService

router = APIRouter(tags=["Clinical Tasks & Work Queues"])


# ---------------------------------------------------------------------------
# Task Creation & Ingestion (TRD Section 6, 7 & 48)
# ---------------------------------------------------------------------------

@router.post(
    "/tasks",
    response_model=TaskRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new actionable clinical or operational task idempotently",
)
async def create_task(
    payload: TaskCreate,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    task_service: TaskService = Depends(get_task_service),
) -> TaskRecord:
    """Create a task with strict idempotency and clinical safety boundary checks."""
    return await task_service.create_task(payload, current_user)


@router.post(
    "/tasks/from-alert/{alert_id}",
    response_model=TaskRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Create actionable follow-up task from acknowledged clinical alert (TRD Section 22)",
)
async def create_task_from_alert(
    alert_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    task_service: TaskService = Depends(get_task_service),
) -> TaskRecord:
    """Transform an acknowledged alert into an actionable task per approved clinical policy."""
    return await task_service.create_task_from_alert(alert_id, current_user)


# ---------------------------------------------------------------------------
# Task Queues & Retrieval (TRD Section 20, 21 & 48)
# ---------------------------------------------------------------------------

@router.get(
    "/tasks",
    response_model=TaskListResponse,
    summary="List tasks with multi-tenant filtering and pagination",
)
async def list_tasks(
    status_filter: Optional[TaskStatus] = Query(None, alias="status"),
    category: Optional[TaskCategory] = Query(None),
    priority: Optional[TaskPriority] = Query(None),
    patient_id: Optional[str] = Query(None),
    facility_id: Optional[str] = Query(None),
    organization_id: Optional[str] = Query(None),
    assignee_id: Optional[str] = Query(None),
    team_id: Optional[str] = Query(None),
    overdue_only: Optional[bool] = Query(None),
    verification_required: Optional[bool] = Query(None),
    created_from: Optional[datetime] = Query(None),
    created_to: Optional[datetime] = Query(None),
    due_from: Optional[datetime] = Query(None),
    due_to: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    task_service: TaskService = Depends(get_task_service),
) -> TaskListResponse:
    """List tasks scoped to caller permissions and tenancy."""
    filters = TaskFilter(
        status=status_filter,
        category=category,
        priority=priority,
        patient_id=patient_id,
        facility_id=facility_id,
        organization_id=organization_id,
        assignee_id=assignee_id,
        team_id=team_id,
        overdue_only=overdue_only,
        verification_required=verification_required,
        created_from=created_from,
        created_to=created_to,
        due_from=due_from,
        due_to=due_to,
        page=page,
        page_size=page_size,
    )
    return await task_service.list_tasks(filters, current_user)


@router.get(
    "/tasks/my",
    response_model=TaskListResponse,
    summary="Retrieve current user's personal task queue",
)
async def get_my_tasks(
    status_filter: Optional[TaskStatus] = Query(None, alias="status"),
    priority: Optional[TaskPriority] = Query(None),
    overdue_only: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    task_service: TaskService = Depends(get_task_service),
) -> TaskListResponse:
    """Retrieve personal work queue for authenticated practitioner."""
    filters = TaskFilter(
        status=status_filter,
        priority=priority,
        overdue_only=overdue_only,
        page=page,
        page_size=page_size,
    )
    return await task_service.list_my_tasks(filters=filters, current_user=current_user)


@router.get(
    "/clinicians/me/tasks",
    response_model=TaskListResponse,
    summary="Clinician personal work queue alias",
)
async def get_clinician_my_tasks(
    status_filter: Optional[TaskStatus] = Query(None, alias="status"),
    priority: Optional[TaskPriority] = Query(None),
    overdue_only: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    task_service: TaskService = Depends(get_task_service),
) -> TaskListResponse:
    """Retrieve clinician-specific active tasks."""
    filters = TaskFilter(
        status=status_filter,
        priority=priority,
        overdue_only=overdue_only,
        page=page,
        page_size=page_size,
    )
    return await task_service.list_my_tasks(filters=filters, current_user=current_user)


@router.get(
    "/patients/{patient_id}/tasks",
    response_model=TaskListResponse,
    summary="Retrieve clinical tasks associated with a patient",
)
async def get_patient_tasks(
    patient_id: str,
    status_filter: Optional[TaskStatus] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    task_service: TaskService = Depends(get_task_service),
) -> TaskListResponse:
    """Retrieve patient tasks with strict IDOR/BOLA authorization enforcement."""
    filters = TaskFilter(
        status=status_filter,
        page=page,
        page_size=page_size,
    )
    return await task_service.list_patient_tasks(patient_id=patient_id, filters=filters, current_user=current_user)


@router.get(
    "/facilities/{facility_id}/tasks",
    response_model=TaskListResponse,
    summary="Retrieve facility-level task queue",
)
async def get_facility_tasks(
    facility_id: str,
    status_filter: Optional[TaskStatus] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    task_service: TaskService = Depends(get_task_service),
) -> TaskListResponse:
    """Retrieve all operational and clinical tasks scoped to the designated facility."""
    filters = TaskFilter(
        status=status_filter,
        page=page,
        page_size=page_size,
    )
    return await task_service.list_facility_tasks(facility_id=facility_id, filters=filters, current_user=current_user)


@router.get(
    "/organizations/{organization_id}/tasks",
    response_model=TaskListResponse,
    summary="Retrieve organization-level task queue",
)
async def get_organization_tasks(
    organization_id: str,
    status_filter: Optional[TaskStatus] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    task_service: TaskService = Depends(get_task_service),
) -> TaskListResponse:
    """Retrieve all tasks within an organization boundary for authorized administrators."""
    filters = TaskFilter(
        status=status_filter,
        page=page,
        page_size=page_size,
    )
    return await task_service.list_organization_tasks(organization_id=organization_id, filters=filters, current_user=current_user)


@router.get(
    "/tasks/{task_id}",
    response_model=TaskRecord,
    summary="Retrieve a single task by ID",
)
async def get_task(
    task_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    task_service: TaskService = Depends(get_task_service),
) -> TaskRecord:
    """Retrieve task details with tenancy and consent authorization verification."""
    return await task_service.get_task(task_id, current_user)


@router.get(
    "/tasks/{task_id}/history",
    response_model=List[TaskHistoryEntry],
    summary="Retrieve audit and provenance history ledger for a task",
)
async def get_task_history(
    task_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    task_service: TaskService = Depends(get_task_service),
) -> List[TaskHistoryEntry]:
    """Retrieve immutable chronological audit trail of all transitions and assignments."""
    return await task_service.get_task_history(task_id, current_user)


# ---------------------------------------------------------------------------
# Task Lifecycle Transitions & Mutations (TRD Section 8-16, 49)
# ---------------------------------------------------------------------------

@router.post(
    "/tasks/{task_id}/assign",
    response_model=TaskRecord,
    summary="Assign a task to an authorized practitioner or care team",
)
async def assign_task(
    task_id: str,
    payload: TaskAssignRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    task_service: TaskService = Depends(get_task_service),
) -> TaskRecord:
    """Assign task with role compatibility and scope verification."""
    return await task_service.assign_task(task_id, payload, current_user)


@router.post(
    "/tasks/{task_id}/reassign",
    response_model=TaskRecord,
    summary="Reassign an active task to a different owner",
)
async def reassign_task(
    task_id: str,
    payload: TaskReassignRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    task_service: TaskService = Depends(get_task_service),
) -> TaskRecord:
    """Reassign task with audit logging and previous assignee notification."""
    return await task_service.reassign_task(task_id, payload, current_user)


@router.post(
    "/tasks/{task_id}/accept",
    response_model=TaskRecord,
    summary="Explicitly accept task responsibility (TASK ASSIGNED != TASK ACCEPTED)",
)
async def accept_task(
    task_id: str,
    payload: Optional[TaskAcceptRequest] = None,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    task_service: TaskService = Depends(get_task_service),
) -> TaskRecord:
    """Record practitioner acknowledgment and formal commitment to task."""
    request = payload or TaskAcceptRequest()
    return await task_service.accept_task(task_id, request, current_user)


@router.post(
    "/tasks/{task_id}/start",
    response_model=TaskRecord,
    summary="Transition task to IN_PROGRESS (TASK ACCEPTED != TASK STARTED)",
)
async def start_task(
    task_id: str,
    payload: Optional[TaskStartRequest] = None,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    task_service: TaskService = Depends(get_task_service),
) -> TaskRecord:
    """Mark work actively underway with dependency prerequisite checks."""
    request = payload or TaskStartRequest()
    return await task_service.start_task(task_id, request, current_user)


@router.post(
    "/tasks/{task_id}/complete",
    response_model=TaskRecord,
    summary="Report task completion (TASK COMPLETED != CLINICAL OUTCOME)",
)
async def complete_task(
    task_id: str,
    payload: Optional[TaskCompleteRequest] = None,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    task_service: TaskService = Depends(get_task_service),
) -> TaskRecord:
    """Complete task work; automatically marks dependent waiting tasks as READY."""
    request = payload or TaskCompleteRequest()
    return await task_service.complete_task(task_id, request, current_user)


@router.post(
    "/tasks/{task_id}/verify",
    response_model=TaskRecord,
    summary="Supervisor or peer verification review of completed task",
)
async def verify_task(
    task_id: str,
    payload: TaskVerifyRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    task_service: TaskService = Depends(get_task_service),
) -> TaskRecord:
    """Record formal supervisor review and mark VERIFIED or reject back to assignee."""
    return await task_service.verify_task(task_id, payload, current_user)


@router.post(
    "/tasks/{task_id}/reject",
    response_model=TaskRecord,
    summary="Reject an assigned task with documented justification",
)
async def reject_task(
    task_id: str,
    payload: TaskRejectRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    task_service: TaskService = Depends(get_task_service),
) -> TaskRecord:
    """Reject assignment and return task to unassigned pool with reason logged."""
    return await task_service.reject_task(task_id, payload, current_user)


@router.post(
    "/tasks/{task_id}/cancel",
    response_model=TaskRecord,
    summary="Cancel a task with reason",
)
async def cancel_task(
    task_id: str,
    payload: TaskCancelRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    task_service: TaskService = Depends(get_task_service),
) -> TaskRecord:
    """Cancel task preventing further execution while preserving full provenance."""
    return await task_service.cancel_task(task_id, payload, current_user)


# ---------------------------------------------------------------------------
# Escalation & Overdue Evaluation (TRD Section 26, 41 & 48)
# ---------------------------------------------------------------------------

@router.post(
    "/tasks/{task_id}/escalate",
    response_model=Optional[TaskRecord],
    summary="Advance escalation level of an overdue or high-priority task",
)
async def escalate_task(
    task_id: str,
    reason: str = Query("Manual or policy-triggered escalation", description="Reason for escalation"),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    escalation_service: TaskEscalationService = Depends(get_task_escalation_service),
) -> Optional[TaskRecord]:
    """Trigger multi-tier escalation with stop conditions for terminal tasks."""
    return await escalation_service.escalate_task(task_id, reason=reason)


@router.post(
    "/tasks/evaluate-overdue",
    response_model=List[TaskRecord],
    summary="Trigger evaluation of overdue tasks across the system",
)
async def evaluate_overdue_tasks(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    escalation_service: TaskEscalationService = Depends(get_task_escalation_service),
) -> List[TaskRecord]:
    """Evaluate overdue tasks and trigger configured escalation tiers."""
    return await escalation_service.evaluate_overdue_tasks()
