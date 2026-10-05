"""Clinical Order Review, Approval Gates & Controlled Authorization Management Endpoints (Phase 40).

CRITICAL ARCHITECTURAL CONTRACT & CORE SAFETY PRINCIPLES:
- REVIEW != CLINICAL DECISION
- REVIEW != DIAGNOSIS
- REVIEW != TREATMENT
- REVIEW != PRESCRIPTION
- APPROVAL REQUEST != APPROVAL
- APPROVAL != CLINICAL TRUTH
- APPROVAL != CLINICAL OUTCOME
- AUTHORIZATION != EXECUTION
- AUTHORIZATION != PROVIDER ACCEPTANCE
- REJECTION != CLINICAL DIAGNOSIS
- TASK COMPLETION != CLINICAL OUTCOME
- AI SUGGESTION != APPROVAL
- AUTOMATED WORKFLOW != CLINICAL AUTHORITY
- DATABASE REMAINS THE SOURCE OF TRUTH
- NO AUTONOMOUS CLINICAL AUTHORITY
"""

from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter, Depends, Header, Query, status

from app.api.deps import (
    get_approval_service,
    get_current_user,
)
from app.schemas.approval import (
    ApprovalCancelRequest,
    ApprovalDecisionRecord,
    ApprovalDecisionRequest,
    ApprovalDelegateRequest,
    ApprovalEscalateRequest,
    ApprovalListResponse,
    ApprovalRecord,
    ApprovalRequestCreate,
    ApprovalRevisionRequest,
    ApprovalStatus,
    ApprovalType,
)
from app.schemas.user import AuthenticatedUserContext
from app.services.approval_service import ApprovalService

router = APIRouter(tags=["Clinical Order Review & Approvals"])


# ---------------------------------------------------------------------------
# Approval Request Creation (TRD Section 33)
# ---------------------------------------------------------------------------

@router.post(
    "/approvals",
    response_model=ApprovalRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new clinical approval request",
)
async def create_approval(
    payload: ApprovalRequestCreate,
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
    actor: AuthenticatedUserContext = Depends(get_current_user),
    service: ApprovalService = Depends(get_approval_service),
) -> ApprovalRecord:
    """Submit a clinical action candidate into the approval gating layer."""
    if x_idempotency_key:
        payload.idempotency_key = x_idempotency_key
    return await service.create_approval_request(payload, actor)


# ---------------------------------------------------------------------------
# Status & Query Endpoints (TRD Section 31)
# ---------------------------------------------------------------------------

@router.get(
    "/approvals",
    response_model=ApprovalListResponse,
    summary="List clinical approvals with multi-tenant filtering",
)
async def list_approvals(
    status: Optional[ApprovalStatus] = Query(None, description="Filter by lifecycle status"),
    approval_type: Optional[ApprovalType] = Query(None, description="Filter by approval category"),
    patient_id: Optional[str] = Query(None, description="Filter by patient ID"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    actor: AuthenticatedUserContext = Depends(get_current_user),
    service: ApprovalService = Depends(get_approval_service),
) -> ApprovalListResponse:
    """List clinical approval requests scoped to caller privileges."""
    offset = (page - 1) * limit
    items = await service.list_approvals(
        actor=actor,
        status=status,
        approval_type=approval_type,
        patient_id=patient_id,
        limit=limit,
        offset=offset,
    )
    return ApprovalListResponse(
        items=items,
        total=len(items),
        page=page,
        page_size=limit,
    )


@router.get(
    "/approvals/pending",
    response_model=ApprovalListResponse,
    summary="List pending approval queue for review",
)
async def list_pending_approvals(
    approval_type: Optional[ApprovalType] = Query(None, description="Filter by approval category"),
    patient_id: Optional[str] = Query(None, description="Filter by patient ID"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    actor: AuthenticatedUserContext = Depends(get_current_user),
    service: ApprovalService = Depends(get_approval_service),
) -> ApprovalListResponse:
    """Retrieve approvals pending review within caller's purview."""
    offset = (page - 1) * limit
    items = await service.list_approvals(
        actor=actor,
        status=ApprovalStatus.PENDING_REVIEW,
        approval_type=approval_type,
        patient_id=patient_id,
        limit=limit,
        offset=offset,
    )
    return ApprovalListResponse(
        items=items,
        total=len(items),
        page=page,
        page_size=limit,
    )


@router.get(
    "/approvals/{approval_id}",
    response_model=ApprovalRecord,
    summary="Get clinical approval record by ID",
)
async def get_approval(
    approval_id: str,
    actor: AuthenticatedUserContext = Depends(get_current_user),
    service: ApprovalService = Depends(get_approval_service),
) -> ApprovalRecord:
    """Fetch an authoritative approval record by its ID."""
    return await service.get_approval(approval_id, actor)


@router.get(
    "/approvals/{approval_id}/history",
    response_model=List[ApprovalDecisionRecord],
    summary="Get clinical approval decision chain history",
)
async def get_approval_history(
    approval_id: str,
    actor: AuthenticatedUserContext = Depends(get_current_user),
    service: ApprovalService = Depends(get_approval_service),
) -> List[ApprovalDecisionRecord]:
    """Retrieve the immutable chain of review decisions for an approval request."""
    approval = await service.get_approval(approval_id, actor)
    return approval.decisions


@router.get(
    "/patients/{patient_id}/approvals",
    response_model=ApprovalListResponse,
    summary="Get clinical approvals for a specific patient",
)
async def get_patient_approvals(
    patient_id: str,
    status: Optional[ApprovalStatus] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    actor: AuthenticatedUserContext = Depends(get_current_user),
    service: ApprovalService = Depends(get_approval_service),
) -> ApprovalListResponse:
    """List all approvals associated with a patient."""
    offset = (page - 1) * limit
    items = await service.list_approvals(
        actor=actor,
        patient_id=patient_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    return ApprovalListResponse(
        items=items,
        total=len(items),
        page=page,
        page_size=limit,
    )


@router.get(
    "/clinicians/me/approvals",
    response_model=ApprovalListResponse,
    summary="Get clinical approvals assigned to or pending review by the authenticated clinician",
)
async def get_my_approvals(
    status: Optional[ApprovalStatus] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    actor: AuthenticatedUserContext = Depends(get_current_user),
    service: ApprovalService = Depends(get_approval_service),
) -> ApprovalListResponse:
    """List clinical approval requests assigned directly to the authenticated clinician."""
    offset = (page - 1) * limit
    items = await service.list_approvals(
        actor=actor,
        assigned_to_me=True,
        status=status,
        limit=limit,
        offset=offset,
    )
    return ApprovalListResponse(
        items=items,
        total=len(items),
        page=page,
        page_size=limit,
    )


@router.get(
    "/orders/{order_id}/approval",
    response_model=ApprovalRecord,
    summary="Get clinical approval record for an order",
)
async def get_order_approval(
    order_id: str,
    actor: AuthenticatedUserContext = Depends(get_current_user),
    service: ApprovalService = Depends(get_approval_service),
) -> ApprovalRecord:
    """Retrieve the authoritative approval record for a Phase 38 clinical order."""
    return await service.get_latest_approval_for_target(
        target_type="order",
        target_id=order_id,
        actor=actor,
    )


@router.get(
    "/order-set-executions/{execution_id}/approval",
    response_model=ApprovalRecord,
    summary="Get clinical approval record for an order-set execution",
)
async def get_order_set_execution_approval(
    execution_id: str,
    actor: AuthenticatedUserContext = Depends(get_current_user),
    service: ApprovalService = Depends(get_approval_service),
) -> ApprovalRecord:
    """Retrieve the authoritative approval record for a Phase 39 order set execution."""
    return await service.get_latest_approval_for_target(
        target_type="order_set_execution",
        target_id=execution_id,
        actor=actor,
    )


# ---------------------------------------------------------------------------
# Decision Action Endpoints (TRD Section 32)
# ---------------------------------------------------------------------------

@router.post(
    "/approvals/{approval_id}/approve",
    response_model=ApprovalRecord,
    summary="Explicitly authorize a clinical approval request",
)
async def approve(
    approval_id: str,
    payload: ApprovalDecisionRequest,
    actor: AuthenticatedUserContext = Depends(get_current_user),
    service: ApprovalService = Depends(get_approval_service),
) -> ApprovalRecord:
    """Approve a pending clinical action request."""
    return await service.approve(approval_id, payload, actor)


@router.post(
    "/approvals/{approval_id}/reject",
    response_model=ApprovalRecord,
    summary="Explicitly reject a clinical approval request",
)
async def reject(
    approval_id: str,
    payload: ApprovalDecisionRequest,
    actor: AuthenticatedUserContext = Depends(get_current_user),
    service: ApprovalService = Depends(get_approval_service),
) -> ApprovalRecord:
    """Reject a pending clinical action request."""
    return await service.reject(approval_id, payload, actor)


@router.post(
    "/approvals/{approval_id}/request-revision",
    response_model=ApprovalRecord,
    summary="Request revisions on a pending clinical approval request",
)
async def request_revision(
    approval_id: str,
    payload: ApprovalRevisionRequest,
    actor: AuthenticatedUserContext = Depends(get_current_user),
    service: ApprovalService = Depends(get_approval_service),
) -> ApprovalRecord:
    """Return a clinical action to the requester for specified revisions."""
    return await service.request_revision(approval_id, payload, actor)


@router.post(
    "/approvals/{approval_id}/cancel",
    response_model=ApprovalRecord,
    summary="Cancel an open approval request",
)
async def cancel(
    approval_id: str,
    payload: Optional[ApprovalCancelRequest] = None,
    actor: AuthenticatedUserContext = Depends(get_current_user),
    service: ApprovalService = Depends(get_approval_service),
) -> ApprovalRecord:
    """Cancel an approval request prior to final decision."""
    reason = payload.reason if payload else "Cancelled by requester"
    return await service.cancel(approval_id, reason, actor)


@router.post(
    "/approvals/{approval_id}/delegate",
    response_model=ApprovalRecord,
    summary="Delegate approval authority to another clinician",
)
async def delegate(
    approval_id: str,
    payload: ApprovalDelegateRequest,
    actor: AuthenticatedUserContext = Depends(get_current_user),
    service: ApprovalService = Depends(get_approval_service),
) -> ApprovalRecord:
    """Delegate review of this request to an eligible peer."""
    return await service.delegate(approval_id, payload, actor)


@router.post(
    "/approvals/{approval_id}/escalate",
    response_model=ApprovalRecord,
    summary="Escalate an approval request to higher supervisory tier",
)
async def escalate(
    approval_id: str,
    payload: ApprovalEscalateRequest,
    actor: AuthenticatedUserContext = Depends(get_current_user),
    service: ApprovalService = Depends(get_approval_service),
) -> ApprovalRecord:
    """Escalate an approval request to an elevated role or reviewer tier."""
    return await service.escalate(approval_id, payload, actor)
