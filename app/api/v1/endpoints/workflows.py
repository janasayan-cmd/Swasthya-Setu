"""Clinical Workflow Orchestration, Order Management & Controlled Action Chains Endpoints (Phase 37).

CORE SAFETY PRINCIPLES:
- WORKFLOW != CLINICAL DECISION
- WORKFLOW != DIAGNOSIS
- WORKFLOW != TREATMENT
- WORKFLOW != PRESCRIPTION
- WORKFLOW != MEDICATION CHANGE
- WORKFLOW != TRIAGE
- WORKFLOW != EMERGENCY DISPATCH
- WORKFLOW DEFINITION != WORKFLOW INSTANCE
- WORKFLOW STEP != CLINICAL ACTION
- TASK COMPLETION != CLINICAL OUTCOME
- AUTOMATED TRANSITION != CLINICAL AUTHORITY
- APPROVAL REQUEST != APPROVAL
- APPROVAL != CLINICAL TRUTH
- AI SUGGESTION != WORKFLOW AUTHORIZATION
- Database remains the source of truth.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, status

from app.api.deps import (
    get_current_user,
    get_workflow_approval_service,
    get_workflow_definition_service,
    get_workflow_service,
)
from app.core.exceptions import (
    WorkflowAccessDeniedException,
    WorkflowOperationNotAllowedException,
)
from app.schemas.user import AuthenticatedUserContext
from app.schemas.workflow import (
    WorkflowCancelRequest,
    WorkflowCategory,
    WorkflowCreate,
    WorkflowDefinition,
    WorkflowFilter,
    WorkflowListResponse,
    WorkflowPauseRequest,
    WorkflowRecord,
    WorkflowResumeRequest,
    WorkflowStatus,
)
from app.schemas.workflow_approval import (
    WorkflowApprovalDecision,
    WorkflowApprovalRecord,
    WorkflowApprovalRequest,
)
from app.schemas.workflow_history import WorkflowHistoryEntry
from app.schemas.workflow_step import WorkflowStepRecord
from app.services.workflow_approval_service import WorkflowApprovalService
from app.services.workflow_definition_service import WorkflowDefinitionService
from app.services.workflow_service import WorkflowService

router = APIRouter(tags=["Clinical Workflows & Order Management"])


# ---------------------------------------------------------------------------
# Workflow Creation & Instantiation (TRD Section 9, 31)
# ---------------------------------------------------------------------------

@router.post(
    "/workflows",
    response_model=WorkflowRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Create or trigger an approved clinical workflow instance idempotently",
)
async def create_workflow(
    payload: WorkflowCreate,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    workflow_service: WorkflowService = Depends(get_workflow_service),
) -> WorkflowRecord:
    """Instantiate a controlled clinical workflow from an approved definition."""
    return await workflow_service.start_workflow(payload, current_user)


# ---------------------------------------------------------------------------
# Workflow Queries & Status (TRD Section 30)
# ---------------------------------------------------------------------------

@router.get(
    "/workflows",
    response_model=WorkflowListResponse,
    summary="List workflows with multi-tenant filtering and pagination",
)
async def list_workflows(
    status_filter: Optional[WorkflowStatus] = Query(None, alias="status"),
    category: Optional[WorkflowCategory] = Query(None),
    definition_id: Optional[str] = Query(None),
    patient_id: Optional[str] = Query(None),
    facility_id: Optional[str] = Query(None),
    correlation_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    workflow_service: WorkflowService = Depends(get_workflow_service),
) -> WorkflowListResponse:
    """List workflow instances scoped by tenant, facility, and permissions."""
    filters = WorkflowFilter(
        status=status_filter,
        category=category,
        definition_id=definition_id,
        patient_id=patient_id,
        facility_id=facility_id,
        correlation_id=correlation_id,
        page=page,
        page_size=page_size,
    )
    return await workflow_service.list_workflows(filters, current_user)


@router.get(
    "/workflows/{workflow_id}",
    response_model=WorkflowRecord,
    summary="Retrieve workflow details by ID",
)
async def get_workflow(
    workflow_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    workflow_service: WorkflowService = Depends(get_workflow_service),
) -> WorkflowRecord:
    """Retrieve full workflow state and step snapshots."""
    return await workflow_service.get_workflow(workflow_id, current_user)


@router.get(
    "/workflows/{workflow_id}/steps",
    response_model=List[WorkflowStepRecord],
    summary="Retrieve ordered step instances for a workflow",
)
async def get_workflow_steps(
    workflow_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    workflow_service: WorkflowService = Depends(get_workflow_service),
) -> List[WorkflowStepRecord]:
    """Retrieve ordered execution steps for the workflow instance."""
    return await workflow_service.get_workflow_steps(workflow_id, current_user)


@router.get(
    "/workflows/{workflow_id}/history",
    response_model=List[WorkflowHistoryEntry],
    summary="Retrieve immutable execution history and transition provenance",
)
async def get_workflow_history(
    workflow_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    workflow_service: WorkflowService = Depends(get_workflow_service),
) -> List[WorkflowHistoryEntry]:
    """Fetch complete transition history audit trail."""
    return await workflow_service.get_workflow_history(workflow_id, current_user)


@router.get(
    "/workflows/{workflow_id}/approvals",
    response_model=List[WorkflowApprovalRecord],
    summary="Retrieve recorded human approval decisions for a workflow",
)
async def get_workflow_approvals(
    workflow_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    workflow_service: WorkflowService = Depends(get_workflow_service),
) -> List[WorkflowApprovalRecord]:
    """Fetch recorded human approval decisions."""
    return await workflow_service.get_workflow_approvals(workflow_id, current_user)


# ---------------------------------------------------------------------------
# Human Approval Gates (TRD Section 13, 14, 15)
# ---------------------------------------------------------------------------

@router.post(
    "/workflows/{workflow_id}/steps/{step_id}/approve",
    response_model=WorkflowRecord,
    summary="Authorize and approve a human approval gate step",
)
async def approve_workflow_step(
    workflow_id: str,
    step_id: str,
    payload: Optional[WorkflowApprovalRequest] = None,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    approval_service: WorkflowApprovalService = Depends(get_workflow_approval_service),
    workflow_service: WorkflowService = Depends(get_workflow_service),
) -> WorkflowRecord:
    """Approve a workflow step gatekeeper. Advances workflow upon completion."""
    req = payload or WorkflowApprovalRequest(decision=WorkflowApprovalDecision.APPROVED)
    if req.decision != WorkflowApprovalDecision.APPROVED:
        req = req.model_copy(update={"decision": WorkflowApprovalDecision.APPROVED})

    await approval_service.evaluate_approval(workflow_id, step_id, req, current_user)
    return await workflow_service.advance_workflow(workflow_id, current_user)


@router.post(
    "/workflows/{workflow_id}/steps/{step_id}/reject",
    response_model=WorkflowRecord,
    summary="Reject a human approval gate step",
)
async def reject_workflow_step(
    workflow_id: str,
    step_id: str,
    payload: Optional[WorkflowApprovalRequest] = None,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    approval_service: WorkflowApprovalService = Depends(get_workflow_approval_service),
    workflow_service: WorkflowService = Depends(get_workflow_service),
) -> WorkflowRecord:
    """Explicitly reject a workflow step gatekeeper."""
    req = payload or WorkflowApprovalRequest(decision=WorkflowApprovalDecision.REJECTED)
    if req.decision != WorkflowApprovalDecision.REJECTED:
        req = req.model_copy(update={"decision": WorkflowApprovalDecision.REJECTED})

    await approval_service.evaluate_approval(workflow_id, step_id, req, current_user)
    return await workflow_service.advance_workflow(workflow_id, current_user)


# ---------------------------------------------------------------------------
# Workflow Control: Pause, Resume, Cancel (TRD Section 24, 25, 26)
# ---------------------------------------------------------------------------

@router.post(
    "/workflows/{workflow_id}/pause",
    response_model=WorkflowRecord,
    summary="Pause active workflow execution",
)
async def pause_workflow(
    workflow_id: str,
    payload: WorkflowPauseRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    workflow_service: WorkflowService = Depends(get_workflow_service),
) -> WorkflowRecord:
    """Pause execution of a running workflow."""
    return await workflow_service.pause_workflow(workflow_id, payload, current_user)


@router.post(
    "/workflows/{workflow_id}/resume",
    response_model=WorkflowRecord,
    summary="Resume execution of a paused workflow",
)
async def resume_workflow(
    workflow_id: str,
    payload: Optional[WorkflowResumeRequest] = None,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    workflow_service: WorkflowService = Depends(get_workflow_service),
) -> WorkflowRecord:
    """Resume execution of a paused workflow after dependency verification."""
    req = payload or WorkflowResumeRequest()
    return await workflow_service.resume_workflow(workflow_id, req, current_user)


@router.post(
    "/workflows/{workflow_id}/cancel",
    response_model=WorkflowRecord,
    summary="Cancel active workflow instance",
)
async def cancel_workflow(
    workflow_id: str,
    payload: WorkflowCancelRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    workflow_service: WorkflowService = Depends(get_workflow_service),
) -> WorkflowRecord:
    """Cancel an active workflow instance without erasing history."""
    return await workflow_service.cancel_workflow(workflow_id, payload, current_user)


# ---------------------------------------------------------------------------
# Patient and Clinician Scoped Workflows (TRD Section 30)
# ---------------------------------------------------------------------------

@router.get(
    "/patients/{patient_id}/workflows",
    response_model=WorkflowListResponse,
    summary="List workflows for a specific patient",
)
async def get_patient_workflows(
    patient_id: str,
    status_filter: Optional[WorkflowStatus] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    workflow_service: WorkflowService = Depends(get_workflow_service),
) -> WorkflowListResponse:
    """List workflows for a specific patient with consent and BOLA validation."""
    if current_user.role == "PATIENT":
        if patient_id != current_user.patient_id and patient_id != current_user.user_id:
            raise WorkflowAccessDeniedException("Patients can only view their own workflows.")

    filters = WorkflowFilter(
        patient_id=patient_id,
        status=status_filter,
        page=page,
        page_size=page_size,
    )
    return await workflow_service.list_workflows(filters, current_user)


@router.get(
    "/clinicians/me/workflows",
    response_model=WorkflowListResponse,
    summary="List workflows relevant to current clinician's facility",
)
async def get_my_workflows(
    status_filter: Optional[WorkflowStatus] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    workflow_service: WorkflowService = Depends(get_workflow_service),
) -> WorkflowListResponse:
    """List workflows for the clinician's active facility."""
    filters = WorkflowFilter(
        facility_id=current_user.facility_id,
        status=status_filter,
        page=page,
        page_size=page_size,
    )
    return await workflow_service.list_workflows(filters, current_user)


# ---------------------------------------------------------------------------
# Administration & Governance Endpoints (TRD Section 32, 57)
# ---------------------------------------------------------------------------

@router.get(
    "/admin/workflows",
    response_model=WorkflowListResponse,
    summary="Admin listing of all system workflows",
)
async def admin_list_workflows(
    status_filter: Optional[WorkflowStatus] = Query(None, alias="status"),
    category: Optional[WorkflowCategory] = Query(None),
    definition_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    workflow_service: WorkflowService = Depends(get_workflow_service),
) -> WorkflowListResponse:
    """Administrative access to all system workflows across facilities."""
    if current_user.role not in {"ADMIN", "SYSTEM_ADMIN", "OPERATIONS_ADMIN"}:
        raise WorkflowAccessDeniedException("Administrative privileges required.")

    filters = WorkflowFilter(
        status=status_filter,
        category=category,
        definition_id=definition_id,
        page=page,
        page_size=page_size,
    )
    return await workflow_service.list_workflows(filters, current_user)


@router.get(
    "/admin/workflows/{workflow_id}",
    response_model=WorkflowRecord,
    summary="Admin inspection of workflow state",
)
async def admin_get_workflow(
    workflow_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    workflow_service: WorkflowService = Depends(get_workflow_service),
) -> WorkflowRecord:
    """Administrative view into detailed workflow state."""
    if current_user.role not in {"ADMIN", "SYSTEM_ADMIN", "OPERATIONS_ADMIN"}:
        raise WorkflowAccessDeniedException("Administrative privileges required.")
    return await workflow_service.get_workflow(workflow_id, current_user)


@router.get(
    "/admin/workflow-definitions",
    response_model=List[WorkflowDefinition],
    summary="List approved workflow definitions and versions",
)
async def admin_list_definitions(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    def_service: WorkflowDefinitionService = Depends(get_workflow_definition_service),
) -> List[WorkflowDefinition]:
    """List approved, versioned workflow templates."""
    if current_user.role not in {"ADMIN", "SYSTEM_ADMIN", "OPERATIONS_ADMIN", "DOCTOR"}:
        raise WorkflowAccessDeniedException("Privileged role required to inspect workflow definitions.")
    return def_service.list_definitions()


@router.get(
    "/admin/workflow-failures",
    response_model=WorkflowListResponse,
    summary="Inspect failed workflows for operational triage",
)
async def admin_list_failures(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    workflow_service: WorkflowService = Depends(get_workflow_service),
) -> WorkflowListResponse:
    """List failed workflows for audit and recovery analysis."""
    if current_user.role not in {"ADMIN", "SYSTEM_ADMIN", "OPERATIONS_ADMIN"}:
        raise WorkflowAccessDeniedException("Administrative privileges required.")

    filters = WorkflowFilter(status=WorkflowStatus.FAILED, page=page, page_size=page_size)
    return await workflow_service.list_workflows(filters, current_user)


@router.get(
    "/admin/workflow-metrics",
    response_model=Dict[str, Any],
    summary="Operational metrics for workflows",
)
async def admin_get_workflow_metrics(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    workflow_service: WorkflowService = Depends(get_workflow_service),
) -> Dict[str, Any]:
    """Retrieve operational count and status metrics without PHI."""
    if current_user.role not in {"ADMIN", "SYSTEM_ADMIN", "OPERATIONS_ADMIN"}:
        raise WorkflowAccessDeniedException("Administrative privileges required.")

    workflows = list(workflow_service.workflow_repo._workflows.values())
    metrics: Dict[str, int] = {
        "total": len(workflows),
        "created": sum(1 for w in workflows if w.status == WorkflowStatus.CREATED),
        "ready": sum(1 for w in workflows if w.status == WorkflowStatus.READY),
        "running": sum(1 for w in workflows if w.status == WorkflowStatus.RUNNING),
        "waiting": sum(1 for w in workflows if w.status == WorkflowStatus.WAITING),
        "awaiting_approval": sum(1 for w in workflows if w.status == WorkflowStatus.AWAITING_APPROVAL),
        "paused": sum(1 for w in workflows if w.status == WorkflowStatus.PAUSED),
        "completed": sum(1 for w in workflows if w.status == WorkflowStatus.COMPLETED),
        "failed": sum(1 for w in workflows if w.status == WorkflowStatus.FAILED),
        "cancelled": sum(1 for w in workflows if w.status == WorkflowStatus.CANCELLED),
    }
    return metrics
