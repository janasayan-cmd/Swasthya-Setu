"""Phase 63: Clinical Safety Risk Decision Preparation, Governed Risk Review & Controlled Risk Disposition Endpoints.

Base Path: /api/v1/safety-risk-reviews
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_current_user
from app.schemas.safety_review_evidence import (
    EvidenceReference,
    RequestEvidenceRequest,
    SubmitEvidenceRequest,
)
from app.schemas.safety_review_package import SafetyReviewPackage
from app.schemas.safety_review_question import UnresolvedQuestionRecord
from app.schemas.safety_risk_disposition import (
    DispositionResponse,
    RecordDispositionRequest,
    RiskDispositionRecord,
)
from app.schemas.safety_risk_readiness import DecisionReadinessEvaluation
from app.schemas.safety_risk_review import (
    CreateSafetyRiskReviewRequest,
    ReanalyzeReviewRequest,
    ReassessReviewRequest,
    ReopenReviewRequest,
    ReviewHistoryEntry,
    ReviewLifecycleState,
    SafetyRiskReviewRecord,
    SafetyRiskReviewStatusResponse,
)
from app.schemas.safety_risk_review_action import (
    PerformReviewActionRequest,
    ReviewActionRecord,
)
from app.schemas.safety_routing import (
    RiskRoutingRecord,
    RouteReviewRequest,
    RoutingResponse,
)
from app.schemas.user import AuthenticatedUserContext
from app.services.safety_risk_review_service import (
    SafetyRiskReviewService,
    get_safety_risk_review_service,
)

router = APIRouter(prefix="/safety-risk-reviews", tags=["Phase 63 - Safety Risk Reviews"])


# ---------------------------------------------------------------------------
# Filtered List Endpoints (Declared before /{review_id} to prevent path conflict)
# ---------------------------------------------------------------------------


@router.get(
    "/pending",
    response_model=List[SafetyRiskReviewRecord],
    summary="List reviews pending action or decision",
)
def list_pending_reviews(
    facility_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    service: SafetyRiskReviewService = Depends(get_safety_risk_review_service),
    user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[SafetyRiskReviewRecord]:
    return service.list_pending(user, facility_id=facility_id, limit=limit, offset=offset)


@router.get(
    "/review-required",
    response_model=List[SafetyRiskReviewRecord],
    summary="List reviews requiring human clinical review",
)
def list_review_required(
    facility_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    service: SafetyRiskReviewService = Depends(get_safety_risk_review_service),
    user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[SafetyRiskReviewRecord]:
    return service.list_review_required(user, facility_id=facility_id, limit=limit, offset=offset)


@router.get(
    "/evidence-required",
    response_model=List[SafetyRiskReviewRecord],
    summary="List reviews requiring additional evidence",
)
def list_evidence_required(
    facility_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    service: SafetyRiskReviewService = Depends(get_safety_risk_review_service),
    user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[SafetyRiskReviewRecord]:
    return service.list_evidence_required(user, facility_id=facility_id, limit=limit, offset=offset)


@router.get(
    "/escalation-required",
    response_model=List[SafetyRiskReviewRecord],
    summary="List reviews requiring critical escalation",
)
def list_escalation_required(
    facility_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    service: SafetyRiskReviewService = Depends(get_safety_risk_review_service),
    user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[SafetyRiskReviewRecord]:
    return service.list_escalation_required(user, facility_id=facility_id, limit=limit, offset=offset)


@router.get(
    "/reassessment-required",
    response_model=List[SafetyRiskReviewRecord],
    summary="List reviews requiring reassessment",
)
def list_reassessment_required(
    facility_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    service: SafetyRiskReviewService = Depends(get_safety_risk_review_service),
    user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[SafetyRiskReviewRecord]:
    return service.list_reassessment_required(user, facility_id=facility_id, limit=limit, offset=offset)


@router.get(
    "",
    response_model=List[SafetyRiskReviewRecord],
    summary="List authorized safety risk reviews",
)
def list_reviews(
    facility_id: Optional[str] = Query(None),
    state: Optional[ReviewLifecycleState] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    service: SafetyRiskReviewService = Depends(get_safety_risk_review_service),
    user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[SafetyRiskReviewRecord]:
    return service.list_reviews(user, facility_id=facility_id, state=state, limit=limit, offset=offset)


# ---------------------------------------------------------------------------
# Creation
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=SafetyRiskReviewRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Create a governed risk review from Phase 62 risk context",
)
def create_safety_risk_review(
    request: CreateSafetyRiskReviewRequest,
    service: SafetyRiskReviewService = Depends(get_safety_risk_review_service),
    user: AuthenticatedUserContext = Depends(get_current_user),
) -> SafetyRiskReviewRecord:
    return service.create_review(request, user)


# ---------------------------------------------------------------------------
# Detail & Subpath Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/{review_id}",
    response_model=SafetyRiskReviewRecord,
    summary="Get risk review details",
)
def get_review(
    review_id: str,
    service: SafetyRiskReviewService = Depends(get_safety_risk_review_service),
    user: AuthenticatedUserContext = Depends(get_current_user),
) -> SafetyRiskReviewRecord:
    return service.get_review(review_id, user)


@router.get(
    "/{review_id}/status",
    response_model=SafetyRiskReviewStatusResponse,
    summary="Get current lifecycle status",
)
def get_review_status(
    review_id: str,
    service: SafetyRiskReviewService = Depends(get_safety_risk_review_service),
    user: AuthenticatedUserContext = Depends(get_current_user),
) -> SafetyRiskReviewStatusResponse:
    return service.get_status(review_id, user)


@router.get(
    "/{review_id}/readiness",
    response_model=DecisionReadinessEvaluation,
    summary="Get decision-readiness state",
)
def get_decision_readiness(
    review_id: str,
    service: SafetyRiskReviewService = Depends(get_safety_risk_review_service),
    user: AuthenticatedUserContext = Depends(get_current_user),
) -> DecisionReadinessEvaluation:
    return service.get_readiness(review_id, user)


@router.get(
    "/{review_id}/evidence",
    response_model=List[EvidenceReference],
    summary="Get authorized evidence references",
)
def get_review_evidence(
    review_id: str,
    service: SafetyRiskReviewService = Depends(get_safety_risk_review_service),
    user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[EvidenceReference]:
    return service.get_evidence(review_id, user)


@router.get(
    "/{review_id}/questions",
    response_model=List[UnresolvedQuestionRecord],
    summary="Get unresolved questions",
)
def get_review_questions(
    review_id: str,
    service: SafetyRiskReviewService = Depends(get_safety_risk_review_service),
    user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[UnresolvedQuestionRecord]:
    return service.get_questions(review_id, user)


@router.get(
    "/{review_id}/package",
    response_model=SafetyReviewPackage,
    summary="Get the authorized review package",
)
def get_review_package(
    review_id: str,
    service: SafetyRiskReviewService = Depends(get_safety_risk_review_service),
    user: AuthenticatedUserContext = Depends(get_current_user),
) -> SafetyReviewPackage:
    return service.get_package(review_id, user)


@router.get(
    "/{review_id}/history",
    response_model=List[ReviewHistoryEntry],
    summary="Get immutable review history",
)
def get_review_history(
    review_id: str,
    service: SafetyRiskReviewService = Depends(get_safety_risk_review_service),
    user: AuthenticatedUserContext = Depends(get_current_user),
) -> List[ReviewHistoryEntry]:
    return service.get_history(review_id, user)


# ---------------------------------------------------------------------------
# Action & Transition Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/{review_id}/validate",
    response_model=DecisionReadinessEvaluation,
    summary="Validate review context",
)
def validate_review_context(
    review_id: str,
    service: SafetyRiskReviewService = Depends(get_safety_risk_review_service),
    user: AuthenticatedUserContext = Depends(get_current_user),
) -> DecisionReadinessEvaluation:
    return service.validate_context(review_id, user)


@router.post(
    "/{review_id}/request-evidence",
    response_model=SafetyRiskReviewRecord,
    summary="Request additional evidence",
)
def request_evidence(
    review_id: str,
    request: RequestEvidenceRequest,
    service: SafetyRiskReviewService = Depends(get_safety_risk_review_service),
    user: AuthenticatedUserContext = Depends(get_current_user),
) -> SafetyRiskReviewRecord:
    return service.request_evidence(review_id, request, user)


@router.post(
    "/{review_id}/submit-evidence",
    response_model=EvidenceReference,
    summary="Submit or attach evidence",
)
def submit_evidence(
    review_id: str,
    request: SubmitEvidenceRequest,
    service: SafetyRiskReviewService = Depends(get_safety_risk_review_service),
    user: AuthenticatedUserContext = Depends(get_current_user),
) -> EvidenceReference:
    return service.submit_evidence(review_id, request, user)


@router.post(
    "/{review_id}/start-review",
    response_model=SafetyRiskReviewRecord,
    summary="Start authorized human review",
)
def start_review(
    review_id: str,
    service: SafetyRiskReviewService = Depends(get_safety_risk_review_service),
    user: AuthenticatedUserContext = Depends(get_current_user),
) -> SafetyRiskReviewRecord:
    return service.start_review(review_id, user)


@router.post(
    "/{review_id}/review",
    response_model=ReviewActionRecord,
    summary="Record reviewer action or outcome",
)
def perform_review_action(
    review_id: str,
    request: PerformReviewActionRequest,
    service: SafetyRiskReviewService = Depends(get_safety_risk_review_service),
    user: AuthenticatedUserContext = Depends(get_current_user),
) -> ReviewActionRecord:
    return service.perform_review_action(review_id, request, user)


@router.post(
    "/{review_id}/disposition",
    response_model=DispositionResponse,
    summary="Record governed risk disposition",
)
def record_risk_disposition(
    review_id: str,
    request: RecordDispositionRequest,
    service: SafetyRiskReviewService = Depends(get_safety_risk_review_service),
    user: AuthenticatedUserContext = Depends(get_current_user),
) -> DispositionResponse:
    rec = service.record_disposition(review_id, request, user)
    return DispositionResponse(
        disposition_id=rec.disposition_id,
        review_id=rec.review_id,
        disposition_type=rec.disposition_type,
        recorded_at=rec.recorded_at,
        message=f"Governed risk disposition '{rec.disposition_type.value}' successfully recorded.",
    )


@router.post(
    "/{review_id}/route",
    response_model=RoutingResponse,
    summary="Route to authoritative downstream phases",
)
def route_review(
    review_id: str,
    request: RouteReviewRequest,
    service: SafetyRiskReviewService = Depends(get_safety_risk_review_service),
    user: AuthenticatedUserContext = Depends(get_current_user),
) -> RoutingResponse:
    routes = service.route_review(review_id, request, user)
    return RoutingResponse(
        review_id=review_id,
        destinations=request.destinations,
        routes=routes,
        message=f"Successfully routed to {len(routes)} destination(s).",
    )


@router.post(
    "/{review_id}/reassess",
    response_model=SafetyRiskReviewRecord,
    summary="Request reassessment",
)
def reassess_review(
    review_id: str,
    request: ReassessReviewRequest,
    service: SafetyRiskReviewService = Depends(get_safety_risk_review_service),
    user: AuthenticatedUserContext = Depends(get_current_user),
) -> SafetyRiskReviewRecord:
    return service.reassess_review(review_id, request, user)


@router.post(
    "/{review_id}/reopen",
    response_model=SafetyRiskReviewRecord,
    summary="Reopen a review where permitted",
)
def reopen_review(
    review_id: str,
    request: ReopenReviewRequest,
    service: SafetyRiskReviewService = Depends(get_safety_risk_review_service),
    user: AuthenticatedUserContext = Depends(get_current_user),
) -> SafetyRiskReviewRecord:
    return service.reopen_review(review_id, request, user)


@router.post(
    "/{review_id}/reanalyze",
    response_model=SafetyRiskReviewRecord,
    summary="Request controlled reanalysis",
)
def reanalyze_review(
    review_id: str,
    request: ReanalyzeReviewRequest,
    service: SafetyRiskReviewService = Depends(get_safety_risk_review_service),
    user: AuthenticatedUserContext = Depends(get_current_user),
) -> SafetyRiskReviewRecord:
    return service.reanalyze_review(review_id, request, user)
