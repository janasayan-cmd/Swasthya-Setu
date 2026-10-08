"""Phase 60: Clinical Safety Surveillance Analysis, Signal Triage & Governed Risk Escalation Endpoints.

TRD Section 39 Endpoints:
  POST /safety-triage
  GET  /safety-triage/review-required
  GET  /safety-triage/high-priority
  GET  /safety-triage/escalation-required
  GET  /safety-triage/reopen-required
  GET  /safety-triage/incident-routing-required
  GET  /safety-triage/governance-routing-required
  GET  /safety-triage
  GET  /safety-triage/{triage_id}
  GET  /safety-triage/{triage_id}/status
  GET  /safety-triage/{triage_id}/signals
  GET  /safety-triage/{triage_id}/evidence
  GET  /safety-triage/{triage_id}/history
  POST /safety-triage/{triage_id}/classify
  POST /safety-triage/{triage_id}/evaluate-severity
  POST /safety-triage/{triage_id}/evaluate
  POST /safety-triage/{triage_id}/review
  POST /safety-triage/{triage_id}/route
  POST /safety-triage/{triage_id}/reassess
  POST /safety-triage/{triage_id}/reanalysis
"""

from typing import Annotated, Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query, Request, Response, status

from app.api.deps import get_current_user
from app.core.exceptions import AppException, ErrorCode
from app.core.logging import request_id_ctx_var
from app.schemas.response import StandardSuccessResponse
from app.schemas.safety_triage import (
    ClassifySignalRequest,
    CreateTriageRequest,
    EvaluateSeverityRequest,
    EvaluateTriageRequest,
    ExecuteRoutingRequest,
    GovernedSignalSeverity,
    ReanalysisTriageRequest,
    RequestTriageReassessmentRequest,
    RoutingDecisionRecord,
    SafetyTriageRecord,
    SubmitTriageReviewRequest,
    TriageEvaluationResponse,
    TriageEvidenceItem,
    TriageHistoryEntry,
    TriageLifecycleState,
    TriageReviewRecord,
    TriageSignalItem,
    TriageStatusResponse,
)
from app.schemas.user import AuthenticatedUserContext
from app.services.safety_triage_service import (
    SafetyTriageService,
    get_safety_triage_service,
)

router = APIRouter(
    prefix="/safety-triage",
    tags=["Clinical Safety Surveillance Analysis, Signal Triage & Governed Risk Escalation"],
)


def _req_id(request: Request) -> str:
    return getattr(request.state, "request_id", None) or request_id_ctx_var.get() or "req-unknown"


def _check_tenant(current_user: AuthenticatedUserContext, record: SafetyTriageRecord) -> None:
    user_org = getattr(current_user, "organization_id", None)
    record_org = record.organization_id or getattr(record.scope, "organization_id", None)
    if user_org and record_org and record_org != user_org:
        raise AppException(
            code=ErrorCode.ACCESS_DENIED,
            message="Access denied to cross-tenant safety triage record",
            status_code=403,
        )


def _actor_info(current_user: AuthenticatedUserContext) -> tuple[str, str]:
    actor_id = str(getattr(current_user, "id", None) or getattr(current_user, "user_id", "unknown"))
    role_obj = getattr(current_user, "role", "SAFETY_OFFICER")
    actor_role = getattr(role_obj, "value", str(role_obj)).replace("UserRole.", "").upper()
    return actor_id, actor_role


# ---------------------------------------------------------------------------
# Static Subpaths First
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=StandardSuccessResponse[SafetyTriageRecord],
    status_code=status.HTTP_201_CREATED,
    summary="Create Safety Signal Triage Context",
)
async def create_triage(
    http_request: Request,
    request_body: CreateTriageRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyTriageService = Depends(get_safety_triage_service),
) -> StandardSuccessResponse[SafetyTriageRecord]:
    req_id = _req_id(http_request)
    actor_id, actor_role = _actor_info(current_user)
    user_org = getattr(current_user, "organization_id", None)

    idem_key = http_request.headers.get("X-Idempotency-Key") or request_body.idempotency_key
    if idem_key and not request_body.idempotency_key:
        request_body.idempotency_key = idem_key

    record = service.create_triage(
        request=request_body,
        actor_id=actor_id,
        actor_role=actor_role,
        actor_organization_id=user_org,
    )
    return StandardSuccessResponse(data=record, request_id=req_id)


@router.get(
    "/review-required",
    response_model=StandardSuccessResponse[List[SafetyTriageRecord]],
    status_code=status.HTTP_200_OK,
    summary="List Triage Records Requiring Human Review",
)
async def list_review_required_triage(
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    organization_id: Optional[str] = Query(None),
    service: SafetyTriageService = Depends(get_safety_triage_service),
) -> StandardSuccessResponse[List[SafetyTriageRecord]]:
    req_id = _req_id(http_request)
    user_org = getattr(current_user, "organization_id", None)
    target_org = organization_id or user_org
    records = service.list_review_required(organization_id=target_org)
    return StandardSuccessResponse(data=records, request_id=req_id)


@router.get(
    "/high-priority",
    response_model=StandardSuccessResponse[List[SafetyTriageRecord]],
    status_code=status.HTTP_200_OK,
    summary="List High-Priority Safety Triage Records",
)
async def list_high_priority_triage(
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    organization_id: Optional[str] = Query(None),
    service: SafetyTriageService = Depends(get_safety_triage_service),
) -> StandardSuccessResponse[List[SafetyTriageRecord]]:
    req_id = _req_id(http_request)
    user_org = getattr(current_user, "organization_id", None)
    target_org = organization_id or user_org
    records = service.list_high_priority(organization_id=target_org)
    return StandardSuccessResponse(data=records, request_id=req_id)


@router.get(
    "/escalation-required",
    response_model=StandardSuccessResponse[List[SafetyTriageRecord]],
    status_code=status.HTTP_200_OK,
    summary="List Triage Records Requiring Escalation",
)
async def list_escalation_required_triage(
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    organization_id: Optional[str] = Query(None),
    service: SafetyTriageService = Depends(get_safety_triage_service),
) -> StandardSuccessResponse[List[SafetyTriageRecord]]:
    req_id = _req_id(http_request)
    user_org = getattr(current_user, "organization_id", None)
    target_org = organization_id or user_org
    records = service.list_escalation_required(organization_id=target_org)
    return StandardSuccessResponse(data=records, request_id=req_id)


@router.get(
    "/reopen-required",
    response_model=StandardSuccessResponse[List[SafetyTriageRecord]],
    status_code=status.HTTP_200_OK,
    summary="List Triage Records Requiring Phase 58 Reopen Review",
)
async def list_reopen_required_triage(
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    organization_id: Optional[str] = Query(None),
    service: SafetyTriageService = Depends(get_safety_triage_service),
) -> StandardSuccessResponse[List[SafetyTriageRecord]]:
    req_id = _req_id(http_request)
    user_org = getattr(current_user, "organization_id", None)
    target_org = organization_id or user_org
    records = service.list_reopen_required(organization_id=target_org)
    return StandardSuccessResponse(data=records, request_id=req_id)


@router.get(
    "/incident-routing-required",
    response_model=StandardSuccessResponse[List[SafetyTriageRecord]],
    status_code=status.HTTP_200_OK,
    summary="List Triage Records Requiring Phase 49 Incident Routing",
)
async def list_incident_routing_required_triage(
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    organization_id: Optional[str] = Query(None),
    service: SafetyTriageService = Depends(get_safety_triage_service),
) -> StandardSuccessResponse[List[SafetyTriageRecord]]:
    req_id = _req_id(http_request)
    user_org = getattr(current_user, "organization_id", None)
    target_org = organization_id or user_org
    records = service.list_incident_routing_required(organization_id=target_org)
    return StandardSuccessResponse(data=records, request_id=req_id)


@router.get(
    "/governance-routing-required",
    response_model=StandardSuccessResponse[List[SafetyTriageRecord]],
    status_code=status.HTTP_200_OK,
    summary="List Triage Records Requiring Phase 51 Governance Routing",
)
async def list_governance_routing_required_triage(
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    organization_id: Optional[str] = Query(None),
    service: SafetyTriageService = Depends(get_safety_triage_service),
) -> StandardSuccessResponse[List[SafetyTriageRecord]]:
    req_id = _req_id(http_request)
    user_org = getattr(current_user, "organization_id", None)
    target_org = organization_id or user_org
    records = service.list_governance_routing_required(organization_id=target_org)
    return StandardSuccessResponse(data=records, request_id=req_id)


@router.post(
    "/reanalysis",
    response_model=StandardSuccessResponse[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Batch Reanalysis of Triage Contexts",
)
async def batch_reanalysis(
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    request_body: Optional[ReanalysisTriageRequest] = None,
    service: SafetyTriageService = Depends(get_safety_triage_service),
) -> StandardSuccessResponse[Dict[str, Any]]:
    req_id = _req_id(http_request)
    actor_id, actor_role = _actor_info(current_user)

    req = request_body or ReanalysisTriageRequest(reason="Periodic triage reanalysis")
    results = service.reanalysis(
        request=req,
        actor_id=actor_id,
        actor_role=actor_role,
    )
    return StandardSuccessResponse(
        data={
            "reanalysis_completed": True,
            "reanalyzed_count": len(results),
            "results": results,
        },
        request_id=req_id,
    )


@router.get(
    "",
    response_model=StandardSuccessResponse[List[SafetyTriageRecord]],
    status_code=status.HTTP_200_OK,
    summary="List Safety Triage Records",
)
async def list_triage(
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    organization_id: Optional[str] = Query(None),
    facility_id: Optional[str] = Query(None),
    lifecycle_state: Optional[TriageLifecycleState] = Query(None),
    severity: Optional[GovernedSignalSeverity] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    service: SafetyTriageService = Depends(get_safety_triage_service),
) -> StandardSuccessResponse[List[SafetyTriageRecord]]:
    req_id = _req_id(http_request)
    user_org = getattr(current_user, "organization_id", None)
    target_org = organization_id or user_org

    records = service.list_triage(
        organization_id=target_org,
        facility_id=facility_id,
        lifecycle_state=lifecycle_state,
        severity=severity,
        limit=limit,
        offset=offset,
    )
    return StandardSuccessResponse(data=records, request_id=req_id)


# ---------------------------------------------------------------------------
# Item Subpaths
# ---------------------------------------------------------------------------


@router.get(
    "/{triage_id}",
    response_model=StandardSuccessResponse[SafetyTriageRecord],
    status_code=status.HTTP_200_OK,
    summary="Get Safety Triage Context",
)
async def get_triage(
    http_request: Request,
    triage_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyTriageService = Depends(get_safety_triage_service),
) -> StandardSuccessResponse[SafetyTriageRecord]:
    req_id = _req_id(http_request)
    record = service.get_triage(triage_id)
    _check_tenant(current_user, record)
    return StandardSuccessResponse(data=record, request_id=req_id)


@router.get(
    "/{triage_id}/status",
    response_model=StandardSuccessResponse[TriageStatusResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Triage Status",
)
async def get_triage_status(
    http_request: Request,
    triage_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyTriageService = Depends(get_safety_triage_service),
) -> StandardSuccessResponse[TriageStatusResponse]:
    req_id = _req_id(http_request)
    record = service.get_triage(triage_id)
    _check_tenant(current_user, record)
    status_resp = service.get_status(triage_id)
    return StandardSuccessResponse(data=status_resp, request_id=req_id)


@router.get(
    "/{triage_id}/signals",
    response_model=StandardSuccessResponse[List[TriageSignalItem]],
    status_code=status.HTTP_200_OK,
    summary="Get Triage Signals",
)
async def get_triage_signals(
    http_request: Request,
    triage_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyTriageService = Depends(get_safety_triage_service),
) -> StandardSuccessResponse[List[TriageSignalItem]]:
    req_id = _req_id(http_request)
    record = service.get_triage(triage_id)
    _check_tenant(current_user, record)
    signals = service.get_signals(triage_id)
    return StandardSuccessResponse(data=signals, request_id=req_id)


@router.get(
    "/{triage_id}/evidence",
    response_model=StandardSuccessResponse[List[TriageEvidenceItem]],
    status_code=status.HTTP_200_OK,
    summary="Get Triage Evidence References",
)
async def get_triage_evidence(
    http_request: Request,
    triage_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyTriageService = Depends(get_safety_triage_service),
) -> StandardSuccessResponse[List[TriageEvidenceItem]]:
    req_id = _req_id(http_request)
    record = service.get_triage(triage_id)
    _check_tenant(current_user, record)
    evidence = service.get_evidence(triage_id)
    return StandardSuccessResponse(data=evidence, request_id=req_id)


@router.get(
    "/{triage_id}/history",
    response_model=StandardSuccessResponse[List[TriageHistoryEntry]],
    status_code=status.HTTP_200_OK,
    summary="Get Triage History",
)
async def get_triage_history(
    http_request: Request,
    triage_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyTriageService = Depends(get_safety_triage_service),
) -> StandardSuccessResponse[List[TriageHistoryEntry]]:
    req_id = _req_id(http_request)
    record = service.get_triage(triage_id)
    _check_tenant(current_user, record)
    history = service.get_history(triage_id)
    return StandardSuccessResponse(data=history, request_id=req_id)


@router.post(
    "/{triage_id}/classify",
    response_model=StandardSuccessResponse[SafetyTriageRecord],
    status_code=status.HTTP_200_OK,
    summary="Classify Signal Category",
)
async def classify_signal(
    http_request: Request,
    triage_id: str,
    request_body: ClassifySignalRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyTriageService = Depends(get_safety_triage_service),
) -> StandardSuccessResponse[SafetyTriageRecord]:
    req_id = _req_id(http_request)
    record = service.get_triage(triage_id)
    _check_tenant(current_user, record)
    actor_id, actor_role = _actor_info(current_user)

    updated = service.classify_signal(
        triage_id=triage_id,
        request=request_body,
        actor_id=actor_id,
        actor_role=actor_role,
    )
    return StandardSuccessResponse(data=updated, request_id=req_id)


@router.post(
    "/{triage_id}/evaluate-severity",
    response_model=StandardSuccessResponse[SafetyTriageRecord],
    status_code=status.HTTP_200_OK,
    summary="Evaluate Governed Signal Severity and Uncertainty",
)
async def evaluate_severity(
    http_request: Request,
    triage_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    request_body: Optional[EvaluateSeverityRequest] = None,
    service: SafetyTriageService = Depends(get_safety_triage_service),
) -> StandardSuccessResponse[SafetyTriageRecord]:
    req_id = _req_id(http_request)
    record = service.get_triage(triage_id)
    _check_tenant(current_user, record)
    actor_id, actor_role = _actor_info(current_user)

    req = request_body or EvaluateSeverityRequest()
    updated = service.evaluate_severity(
        triage_id=triage_id,
        request=req,
        actor_id=actor_id,
        actor_role=actor_role,
    )
    return StandardSuccessResponse(data=updated, request_id=req_id)


@router.post(
    "/{triage_id}/evaluate",
    response_model=StandardSuccessResponse[TriageEvaluationResponse],
    status_code=status.HTTP_200_OK,
    summary="Run End-to-End Triage Evaluation",
)
async def evaluate_triage(
    http_request: Request,
    triage_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    request_body: Optional[EvaluateTriageRequest] = None,
    service: SafetyTriageService = Depends(get_safety_triage_service),
) -> StandardSuccessResponse[TriageEvaluationResponse]:
    req_id = _req_id(http_request)
    record = service.get_triage(triage_id)
    _check_tenant(current_user, record)
    actor_id, actor_role = _actor_info(current_user)

    req = request_body or EvaluateTriageRequest()
    evaluation = service.evaluate_triage(
        triage_id=triage_id,
        request=req,
        actor_id=actor_id,
        actor_role=actor_role,
    )
    return StandardSuccessResponse(data=evaluation, request_id=req_id)


@router.post(
    "/{triage_id}/review",
    response_model=StandardSuccessResponse[TriageReviewRecord],
    status_code=status.HTTP_200_OK,
    summary="Submit Human Triage Review Decision",
)
async def submit_review(
    http_request: Request,
    triage_id: str,
    request_body: SubmitTriageReviewRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyTriageService = Depends(get_safety_triage_service),
) -> StandardSuccessResponse[TriageReviewRecord]:
    req_id = _req_id(http_request)
    record = service.get_triage(triage_id)
    _check_tenant(current_user, record)
    actor_id, actor_role = _actor_info(current_user)

    rev = service.submit_review(
        triage_id=triage_id,
        request=request_body,
        actor_id=actor_id,
        actor_role=actor_role,
    )
    return StandardSuccessResponse(data=rev, request_id=req_id)


@router.post(
    "/{triage_id}/route",
    response_model=StandardSuccessResponse[RoutingDecisionRecord],
    status_code=status.HTTP_200_OK,
    summary="Execute Authorized Routing",
)
async def execute_routing(
    http_request: Request,
    triage_id: str,
    request_body: ExecuteRoutingRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyTriageService = Depends(get_safety_triage_service),
) -> StandardSuccessResponse[RoutingDecisionRecord]:
    req_id = _req_id(http_request)
    record = service.get_triage(triage_id)
    _check_tenant(current_user, record)
    actor_id, actor_role = _actor_info(current_user)

    dec = service.execute_routing(
        triage_id=triage_id,
        request=request_body,
        actor_id=actor_id,
        actor_role=actor_role,
    )
    return StandardSuccessResponse(data=dec, request_id=req_id)


@router.post(
    "/{triage_id}/reassess",
    response_model=StandardSuccessResponse[RoutingDecisionRecord],
    status_code=status.HTTP_200_OK,
    summary="Request Reassessment Trigger",
)
async def request_reassessment(
    http_request: Request,
    triage_id: str,
    request_body: RequestTriageReassessmentRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyTriageService = Depends(get_safety_triage_service),
) -> StandardSuccessResponse[RoutingDecisionRecord]:
    req_id = _req_id(http_request)
    record = service.get_triage(triage_id)
    _check_tenant(current_user, record)
    actor_id, actor_role = _actor_info(current_user)

    dec = service.request_reassessment(
        triage_id=triage_id,
        request=request_body,
        actor_id=actor_id,
        actor_role=actor_role,
    )
    return StandardSuccessResponse(data=dec, request_id=req_id)


@router.post(
    "/{triage_id}/reanalysis",
    response_model=StandardSuccessResponse[TriageEvaluationResponse],
    status_code=status.HTTP_200_OK,
    summary="Run Governed Reanalysis for Single Triage Record",
)
async def reanalysis_single_triage(
    http_request: Request,
    triage_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    request_body: Optional[ReanalysisTriageRequest] = None,
    service: SafetyTriageService = Depends(get_safety_triage_service),
) -> StandardSuccessResponse[TriageEvaluationResponse]:
    req_id = _req_id(http_request)
    record = service.get_triage(triage_id)
    _check_tenant(current_user, record)
    actor_id, actor_role = _actor_info(current_user)

    eval_req = EvaluateTriageRequest(force_reevaluation=True)
    evaluation = service.evaluate_triage(
        triage_id=triage_id,
        request=eval_req,
        actor_id=actor_id,
        actor_role=actor_role,
    )
    return StandardSuccessResponse(data=evaluation, request_id=req_id)
