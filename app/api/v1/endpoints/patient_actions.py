"""Patient Engagement, Consented Self-Service & Care Journey Action Endpoints (Phase 42).

CRITICAL NON-NEGOTIABLE CLINICAL SAFETY BOUNDARIES:
- PATIENT SELF-SERVICE IS AN OPERATIONAL INTERACTION LAYER, NOT CLINICAL AUTHORITY.
- PATIENT ACTION != CLINICAL DECISION
- PATIENT RESPONSE != CLINICAL VERIFICATION
- PATIENT ACKNOWLEDGEMENT != CLINICAL UNDERSTANDING OR ADHERENCE
- PATIENT CONFIRMATION != CLINICAL CONSENT UNLESS EXPLICITLY DEFINED
- PATIENT SUBMISSION != VERIFIED MEDICAL DATA
- PATIENT REPORTED SYMPTOM != TRIAGE RESULT
- PATIENT MEDICATION ENTRY != VERIFIED MEDICATION
- PATIENT ALLERGY ENTRY != VERIFIED ALLERGY
- WORKFLOW COMPLETION != CLINICAL OUTCOME
- AI SUGGESTION != PATIENT AUTHORIZATION
"""

from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter, Depends, Header, Query, Request, status

from app.api.deps import (
    get_current_user,
    get_patient_action_service,
)
from app.schemas.patient_action import (
    ActionPriority,
    ActionStatus,
    ActionType,
    PatientActionAcknowledgeRequest,
    PatientActionCancelRequest,
    PatientActionCompleteRequest,
    PatientActionCorrectionRequest,
    PatientActionCreateRequest,
    PatientActionHistoryRecord,
    PatientActionListResponse,
    PatientActionRecord,
    PatientActionRefuseRequest,
    PatientActionReviewRequest,
    PatientActionStartRequest,
    PatientActionSubmitRequest,
)
from app.schemas.patient_submission import (
    DocumentSubmissionRecord,
    DocumentSubmissionRequest,
    PatientSubmissionRecord,
)
from app.schemas.user import AuthenticatedUserContext
from app.services.patient_action_service import PatientActionService

router = APIRouter(tags=["Patient Engagement & Self-Service Actions"])


# ---------------------------------------------------------------------------
# Patient Action Lifecycle & Management Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/patient-actions",
    response_model=PatientActionRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new patient action instance",
)
async def create_patient_action(
    payload: PatientActionCreateRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: PatientActionService = Depends(get_patient_action_service),
) -> PatientActionRecord:
    """Create a new action assigned to a patient."""
    actor_id = getattr(current_user, "id", None)
    return await service.create_action(payload, created_by=actor_id)


@router.get(
    "/patient-actions",
    response_model=PatientActionListResponse,
    summary="List patient actions for current user",
)
async def list_patient_actions(
    status: Optional[ActionStatus] = Query(None, description="Filter by action status"),
    action_type: Optional[ActionType] = Query(None, description="Filter by action type"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: PatientActionService = Depends(get_patient_action_service),
) -> PatientActionListResponse:
    """List actions assigned to current patient."""
    patient_id = getattr(current_user, "patient_id", None) or getattr(current_user, "id", None)
    items, total = await service.list_patient_actions(
        patient_id=patient_id,
        current_user=current_user,
        status=status,
        action_type=action_type,
        page=page,
        page_size=page_size,
    )
    return PatientActionListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_more=(page * page_size) < total,
    )


@router.get(
    "/patient-actions/{action_id}",
    response_model=PatientActionRecord,
    summary="Retrieve a specific patient action",
)
async def get_patient_action(
    action_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: PatientActionService = Depends(get_patient_action_service),
) -> PatientActionRecord:
    """Retrieve details for an action with patient/clinician scope validation."""
    return await service.get_action(action_id, current_user)


@router.post(
    "/patient-actions/{action_id}/start",
    response_model=PatientActionRecord,
    summary="Mark an action as started",
)
async def start_patient_action(
    action_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: PatientActionService = Depends(get_patient_action_service),
) -> PatientActionRecord:
    """Transition an action to STARTED."""
    return await service.start_action(action_id, current_user)


@router.post(
    "/patient-actions/{action_id}/submit",
    response_model=PatientSubmissionRecord,
    status_code=status.HTTP_200_OK,
    summary="Submit patient response for action",
)
async def submit_patient_action(
    action_id: str,
    payload: PatientActionSubmitRequest,
    req: Request,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: PatientActionService = Depends(get_patient_action_service),
) -> PatientSubmissionRecord:
    """Submit requested information or confirmation."""
    if idempotency_key and not payload.idempotency_key:
        payload.idempotency_key = idempotency_key

    client_ip = req.client.host if req.client else None
    user_agent = req.headers.get("user-agent")

    return await service.submit_action(
        action_id=action_id,
        current_user=current_user,
        request=payload,
        client_ip=client_ip,
        user_agent=user_agent,
    )


@router.post(
    "/patient-actions/{action_id}/complete",
    response_model=PatientActionRecord,
    summary="Mark an operational action completed",
)
async def complete_patient_action(
    action_id: str,
    payload: Optional[PatientActionCompleteRequest] = None,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: PatientActionService = Depends(get_patient_action_service),
) -> PatientActionRecord:
    """Mark an action as completed."""
    return await service.complete_action(action_id, current_user, payload)


@router.post(
    "/patient-actions/{action_id}/cancel",
    response_model=PatientActionRecord,
    summary="Cancel a patient action",
)
async def cancel_patient_action(
    action_id: str,
    payload: PatientActionCancelRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: PatientActionService = Depends(get_patient_action_service),
) -> PatientActionRecord:
    """Cancel a pending action with a reason."""
    return await service.cancel_action(action_id, current_user, payload)


@router.post(
    "/patient-actions/{action_id}/acknowledge",
    response_model=PatientActionRecord,
    summary="Acknowledge notice or care plan receipt",
)
async def acknowledge_patient_action(
    action_id: str,
    payload: Optional[PatientActionAcknowledgeRequest] = None,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: PatientActionService = Depends(get_patient_action_service),
) -> PatientActionRecord:
    """Acknowledge notice receipt. (ACKNOWLEDGED != ADHERENCE OR CLINICAL UNDERSTANDING)."""
    return await service.acknowledge_action(action_id, current_user, payload)


@router.post(
    "/patient-actions/{action_id}/refuse",
    response_model=PatientActionRecord,
    summary="Record explicit patient refusal to perform action",
)
async def refuse_patient_action(
    action_id: str,
    payload: PatientActionRefuseRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: PatientActionService = Depends(get_patient_action_service),
) -> PatientActionRecord:
    """Record patient refusal/opt-out distinctly from technical failure."""
    return await service.refuse_action(action_id, current_user, payload)


@router.post(
    "/patient-actions/{action_id}/correct",
    response_model=PatientSubmissionRecord,
    summary="Submit a correction without overwriting history",
)
async def correct_patient_submission(
    action_id: str,
    payload: PatientActionCorrectionRequest,
    req: Request,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: PatientActionService = Depends(get_patient_action_service),
) -> PatientSubmissionRecord:
    """Submit corrected answers preserving historical submissions (v1 -> v2)."""
    client_ip = req.client.host if req.client else None
    user_agent = req.headers.get("user-agent")

    return await service.submit_correction(
        action_id=action_id,
        current_user=current_user,
        request=payload,
        client_ip=client_ip,
        user_agent=user_agent,
    )


@router.get(
    "/patient-actions/{action_id}/history",
    response_model=List[PatientActionHistoryRecord],
    summary="Get action state transition history",
)
async def get_patient_action_history(
    action_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: PatientActionService = Depends(get_patient_action_service),
) -> List[PatientActionHistoryRecord]:
    """Retrieve full chronological state transition history for an action."""
    return await service.get_action_history(action_id, current_user)


# ---------------------------------------------------------------------------
# Patient-Scoped Actions Retrieval
# ---------------------------------------------------------------------------

@router.get(
    "/patients/{patient_id}/actions",
    response_model=PatientActionListResponse,
    summary="List actions scoped to specific patient",
)
async def list_actions_for_patient(
    patient_id: str,
    status: Optional[ActionStatus] = Query(None, description="Filter by status"),
    action_type: Optional[ActionType] = Query(None, description="Filter by action type"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: PatientActionService = Depends(get_patient_action_service),
) -> PatientActionListResponse:
    """Retrieve actions for target patient with IDOR protection."""
    items, total = await service.list_patient_actions(
        patient_id=patient_id,
        current_user=current_user,
        status=status,
        action_type=action_type,
        page=page,
        page_size=page_size,
    )
    return PatientActionListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_more=(page * page_size) < total,
    )


# ---------------------------------------------------------------------------
# Documents Linked to Patient Action
# ---------------------------------------------------------------------------

@router.post(
    "/patient-actions/{action_id}/documents",
    response_model=DocumentSubmissionRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Link an existing secure document to patient action",
)
async def attach_document_to_action(
    action_id: str,
    payload: DocumentSubmissionRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: PatientActionService = Depends(get_patient_action_service),
) -> DocumentSubmissionRecord:
    """Link uploaded Phase 5 document to action. (DOCUMENT != VERIFIED CLINICAL RECORD)."""
    return await service.attach_document(action_id, current_user, payload)


@router.get(
    "/patient-actions/{action_id}/documents",
    response_model=List[DocumentSubmissionRecord],
    summary="Get documents linked to action",
)
async def get_documents_for_action(
    action_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: PatientActionService = Depends(get_patient_action_service),
) -> List[DocumentSubmissionRecord]:
    """Retrieve all document links for an action."""
    return await service.get_documents(action_id, current_user)


# ---------------------------------------------------------------------------
# Admin & Clinician Operational Review Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/admin/patient-actions",
    response_model=PatientActionListResponse,
    summary="Admin/Clinician listing of patient actions",
)
async def list_admin_patient_actions(
    organization_id: Optional[str] = Query(None, description="Organization filter"),
    facility_id: Optional[str] = Query(None, description="Facility filter"),
    status: Optional[ActionStatus] = Query(None, description="Status filter"),
    action_type: Optional[ActionType] = Query(None, description="Action type filter"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: PatientActionService = Depends(get_patient_action_service),
) -> PatientActionListResponse:
    """Administrative / clinician overview of patient actions."""
    items, total = await service.list_admin_actions(
        current_user=current_user,
        organization_id=organization_id,
        facility_id=facility_id,
        status=status,
        action_type=action_type,
        page=page,
        page_size=page_size,
    )
    return PatientActionListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_more=(page * page_size) < total,
    )


@router.get(
    "/admin/patient-actions/{action_id}",
    response_model=PatientActionRecord,
    summary="Admin/Clinician retrieve single patient action",
)
async def get_admin_patient_action(
    action_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: PatientActionService = Depends(get_patient_action_service),
) -> PatientActionRecord:
    """Retrieve single patient action for clinician/support review."""
    return await service.get_action(action_id, current_user)


@router.post(
    "/admin/patient-actions/{action_id}/review",
    response_model=PatientActionRecord,
    summary="Clinician review of patient action submission",
)
async def review_patient_action(
    action_id: str,
    payload: PatientActionReviewRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: PatientActionService = Depends(get_patient_action_service),
) -> PatientActionRecord:
    """Review submitted action: ACCEPT, REJECT, or REQUEST_CORRECTION."""
    return await service.review_action(action_id, current_user, payload)
