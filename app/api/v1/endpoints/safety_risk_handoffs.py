"""Phase 64: Clinical Safety Risk Handoff Endpoints.

Base Path: /api/v1/safety-risk-handoffs
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_current_user
from app.schemas.safety_risk_handoff import (
    CreateSafetyRiskHandoffRequest,
    DestinationAcknowledgement,
    HandoffDestinationPhase,
    HandoffHistoryEntry,
    HandoffLifecycleState,
    SafetyRiskHandoffRecord,
)
from app.schemas.safety_risk_handoff_action import (
    CancelHandoffRequest,
    EscalateHandoffRequest,
    ReconcileHandoffRequest,
    RetryHandoffRequest,
    SubmitHandoffRequest,
)
from app.schemas.safety_risk_handoff_outcome import (
    HandoffOutcomeRecord,
    IngestOutcomeRequest,
)
from app.schemas.safety_risk_handoff_reconciliation import (
    HandoffReconciliationRecord,
)
from app.schemas.safety_risk_handoff_status import HandoffStatusResponse
from app.schemas.user import AuthenticatedUserContext
from app.services.safety_risk_handoff_service import (
    SafetyRiskHandoffService,
    get_safety_risk_handoff_service,
)

router = APIRouter(prefix="/safety-risk-handoffs", tags=["Phase 64 - Safety Risk Handoffs"])


# ---------------------------------------------------------------------------
# Filtered List Endpoints (Declared before /{handoff_id} to avoid path conflict)
# ---------------------------------------------------------------------------


@router.get(
    "/pending",
    response_model=List[SafetyRiskHandoffRecord],
    summary="List pending handoffs awaiting transmission, acknowledgement, or completion",
)
def list_pending_handoffs(
    facility_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    service: SafetyRiskHandoffService = Depends(get_safety_risk_handoff_service),
    user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[SafetyRiskHandoffRecord]:
    return service.list_pending(user, facility_id=facility_id, limit=limit, offset=offset)


@router.get(
    "/reconciliation-required",
    response_model=List[SafetyRiskHandoffRecord],
    summary="List handoffs requiring outcome reconciliation",
)
def list_reconciliation_required(
    facility_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    service: SafetyRiskHandoffService = Depends(get_safety_risk_handoff_service),
    user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[SafetyRiskHandoffRecord]:
    return service.list_reconciliation_required(user, facility_id=facility_id, limit=limit, offset=offset)


@router.get(
    "/retry-exhausted",
    response_model=List[SafetyRiskHandoffRecord],
    summary="List handoffs that have exhausted all bounded retries",
)
def list_retry_exhausted(
    facility_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    service: SafetyRiskHandoffService = Depends(get_safety_risk_handoff_service),
    user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[SafetyRiskHandoffRecord]:
    return service.list_retry_exhausted(user, facility_id=facility_id, limit=limit, offset=offset)


@router.get(
    "/escalation-required",
    response_model=List[SafetyRiskHandoffRecord],
    summary="List handoffs requiring operational governance escalation",
)
def list_escalation_required(
    facility_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    service: SafetyRiskHandoffService = Depends(get_safety_risk_handoff_service),
    user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[SafetyRiskHandoffRecord]:
    return service.list_escalation_required(user, facility_id=facility_id, limit=limit, offset=offset)


@router.get(
    "",
    response_model=List[SafetyRiskHandoffRecord],
    summary="List authorized safety risk handoffs with filters and pagination",
)
def list_handoffs(
    facility_id: Optional[str] = Query(None),
    state: Optional[HandoffLifecycleState] = Query(None),
    destination_phase: Optional[HandoffDestinationPhase] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    service: SafetyRiskHandoffService = Depends(get_safety_risk_handoff_service),
    user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[SafetyRiskHandoffRecord]:
    return service.list_handoffs(
        user,
        facility_id=facility_id,
        state=state,
        destination_phase=destination_phase,
        limit=limit,
        offset=offset,
    )


# ---------------------------------------------------------------------------
# Creation Endpoint
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=SafetyRiskHandoffRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Create a governed handoff from an authorized Phase 63 disposition",
)
def create_handoff(
    request: CreateSafetyRiskHandoffRequest,
    service: SafetyRiskHandoffService = Depends(get_safety_risk_handoff_service),
    user: AuthenticatedUserContext = Depends(get_current_user),
) -> SafetyRiskHandoffRecord:
    return service.create_handoff(request, user)


# ---------------------------------------------------------------------------
# Detail & Subpath Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/{handoff_id}",
    response_model=SafetyRiskHandoffRecord,
    summary="Retrieve an authorized safety risk handoff by ID",
)
def get_handoff(
    handoff_id: str,
    service: SafetyRiskHandoffService = Depends(get_safety_risk_handoff_service),
    user: AuthenticatedUserContext = Depends(get_current_user),
) -> SafetyRiskHandoffRecord:
    return service.get_handoff(handoff_id, user)


@router.get(
    "/{handoff_id}/status",
    response_model=HandoffStatusResponse,
    summary="Retrieve current operational status of a handoff",
)
def get_handoff_status(
    handoff_id: str,
    service: SafetyRiskHandoffService = Depends(get_safety_risk_handoff_service),
    user: AuthenticatedUserContext = Depends(get_current_user),
) -> HandoffStatusResponse:
    return service.get_status(handoff_id, user)


@router.get(
    "/{handoff_id}/history",
    response_model=List[HandoffHistoryEntry],
    summary="Retrieve immutable handoff state transition audit trail",
)
def get_handoff_history(
    handoff_id: str,
    service: SafetyRiskHandoffService = Depends(get_safety_risk_handoff_service),
    user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[HandoffHistoryEntry]:
    return service.get_history(handoff_id, user)


@router.get(
    "/{handoff_id}/outcomes",
    response_model=List[Dict[str, Any]],
    summary="Retrieve authorized received outcome records",
)
def get_handoff_outcomes(
    handoff_id: str,
    service: SafetyRiskHandoffService = Depends(get_safety_risk_handoff_service),
    user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    return service.get_outcomes(handoff_id, user)


# ---------------------------------------------------------------------------
# Action Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/{handoff_id}/submit",
    response_model=DestinationAcknowledgement,
    summary="Submit a pending handoff through its authoritative destination adapter",
)
def submit_handoff(
    handoff_id: str,
    request: SubmitHandoffRequest,
    service: SafetyRiskHandoffService = Depends(get_safety_risk_handoff_service),
    user: AuthenticatedUserContext = Depends(get_current_user),
) -> DestinationAcknowledgement:
    return service.submit_handoff(handoff_id, request, user)


@router.post(
    "/{handoff_id}/outcomes",
    response_model=HandoffOutcomeRecord,
    summary="Ingest an outcome reported by a destination workflow",
)
def ingest_outcome(
    handoff_id: str,
    request: IngestOutcomeRequest,
    service: SafetyRiskHandoffService = Depends(get_safety_risk_handoff_service),
    user: AuthenticatedUserContext = Depends(get_current_user),
) -> HandoffOutcomeRecord:
    return service.ingest_outcome(handoff_id, request, user)


@router.post(
    "/{handoff_id}/reconcile",
    response_model=HandoffReconciliationRecord,
    summary="Request controlled outcome reconciliation",
)
def reconcile_handoff(
    handoff_id: str,
    request: ReconcileHandoffRequest,
    service: SafetyRiskHandoffService = Depends(get_safety_risk_handoff_service),
    user: AuthenticatedUserContext = Depends(get_current_user),
) -> HandoffReconciliationRecord:
    return service.reconcile_handoff(handoff_id, request, user)


@router.post(
    "/{handoff_id}/retry",
    response_model=SafetyRiskHandoffRecord,
    summary="Schedule a permitted bounded retry for a failed or interrupted handoff",
)
def retry_handoff(
    handoff_id: str,
    request: RetryHandoffRequest,
    service: SafetyRiskHandoffService = Depends(get_safety_risk_handoff_service),
    user: AuthenticatedUserContext = Depends(get_current_user),
) -> SafetyRiskHandoffRecord:
    return service.retry_handoff(handoff_id, request, user)


@router.post(
    "/{handoff_id}/cancel",
    response_model=SafetyRiskHandoffRecord,
    summary="Request handoff cancellation where supported by the destination contract",
)
def cancel_handoff(
    handoff_id: str,
    request: CancelHandoffRequest,
    service: SafetyRiskHandoffService = Depends(get_safety_risk_handoff_service),
    user: AuthenticatedUserContext = Depends(get_current_user),
) -> SafetyRiskHandoffRecord:
    return service.cancel_handoff(handoff_id, request, user)


@router.post(
    "/{handoff_id}/escalate",
    response_model=SafetyRiskHandoffRecord,
    summary="Escalate an unresolved operational handoff to manual review",
)
def escalate_handoff(
    handoff_id: str,
    request: EscalateHandoffRequest,
    service: SafetyRiskHandoffService = Depends(get_safety_risk_handoff_service),
    user: AuthenticatedUserContext = Depends(get_current_user),
) -> SafetyRiskHandoffRecord:
    return service.escalate_handoff(handoff_id, request, user)
