"""Phase 61: Clinical Safety Surveillance Analytics, Signal Correlation & Governed Risk Intelligence Endpoints.

TRD Section 33 Endpoints:
  POST /safety-analytics
  GET  /safety-analytics/review-required
  GET  /safety-analytics/risk-indicators
  GET  /safety-analytics/escalation-required
  GET  /safety-analytics/reassessment-required
  GET  /safety-analytics/reanalysis-required
  GET  /safety-analytics
  GET  /safety-analytics/{analysis_id}
  GET  /safety-analytics/{analysis_id}/status
  GET  /safety-analytics/{analysis_id}/signals
  GET  /safety-analytics/{analysis_id}/trends
  GET  /safety-analytics/{analysis_id}/patterns
  GET  /safety-analytics/{analysis_id}/correlations
  GET  /safety-analytics/{analysis_id}/risk-indicators
  GET  /safety-analytics/{analysis_id}/evidence
  GET  /safety-analytics/{analysis_id}/history
  POST /safety-analytics/{analysis_id}/analyze
  POST /safety-analytics/{analysis_id}/reanalyze
  POST /safety-analytics/{analysis_id}/review
  POST /safety-analytics/{analysis_id}/route
  POST /safety-analytics/{analysis_id}/reassess
"""

from typing import Annotated, Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query, Request, Response, status

from app.api.deps import get_current_user
from app.core.exceptions import AppException, ErrorCode
from app.core.logging import request_id_ctx_var
from app.schemas.response import StandardSuccessResponse
from app.schemas.safety_analytics import (
    AnalysisHistoryEntry,
    AnalysisLifecycleState,
    AnalyticalEvidenceReference,
    AnalyticsReviewRecord,
    AnalyticsRoutingRecord,
    ConcentrationFinding,
    CorrelationFinding,
    CreateAnalysisRequest,
    DistributionFinding,
    EligibleSignalReference,
    ExecuteAnalysisRequest,
    ReanalyzeRequest,
    ReassessAnalysisRequest,
    RecurrenceFinding,
    ReviewAnalysisRequest,
    RouteAnalysisRequest,
    SafetyAnalysisRecord,
    SafetyPatternFinding,
    SafetyRiskIndicatorFinding,
    TrendFinding,
)
from app.schemas.user import AuthenticatedUserContext
from app.services.safety_analytics_async_service import (
    SafetyAnalyticsAsyncService,
    get_safety_analytics_async_service,
)
from app.services.safety_analytics_service import (
    SafetyAnalyticsService,
    get_safety_analytics_service,
)

router = APIRouter(
    prefix="/safety-analytics",
    tags=["Clinical Safety Surveillance Analytics, Signal Correlation & Governed Risk Intelligence"],
)


def _req_id(request: Request) -> str:
    return getattr(request.state, "request_id", None) or request_id_ctx_var.get() or "req-unknown"


def _check_tenant(current_user: AuthenticatedUserContext, record: SafetyAnalysisRecord) -> None:
    user_org = getattr(current_user, "organization_id", None)
    record_org = record.organization_id or getattr(record.scope, "organization_id", None)
    if user_org and record_org and record_org != user_org:
        raise AppException(
            code=ErrorCode.ACCESS_DENIED,
            message="Access denied to cross-tenant safety surveillance record",
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
    response_model=StandardSuccessResponse[SafetyAnalysisRecord],
    status_code=status.HTTP_201_CREATED,
    summary="Create Safety Surveillance Analysis",
)
async def create_analysis(
    http_request: Request,
    request: CreateAnalysisRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: Annotated[SafetyAnalyticsService, Depends(get_safety_analytics_service)],
) -> StandardSuccessResponse[SafetyAnalysisRecord]:
    actor_id, actor_role = _actor_info(current_user)
    org_id = current_user.organization_id or (request.scope.organization_id if request.scope else "org-default")

    record = service.create_analysis(
        request=request,
        organization_id=org_id,
        actor_id=actor_id,
        actor_role=actor_role,
    )
    return StandardSuccessResponse(data=record, request_id=_req_id(http_request))


@router.get(
    "/review-required",
    response_model=StandardSuccessResponse[List[SafetyAnalysisRecord]],
    summary="List Analyses Requiring Human Review",
)
async def list_review_required(
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: Annotated[SafetyAnalyticsService, Depends(get_safety_analytics_service)],
) -> StandardSuccessResponse[List[SafetyAnalysisRecord]]:
    results = service.repo.list_review_required(organization_id=current_user.organization_id)
    return StandardSuccessResponse(data=results, request_id=_req_id(http_request))


@router.get(
    "/risk-indicators",
    response_model=StandardSuccessResponse[List[SafetyRiskIndicatorFinding]],
    summary="List Active Governed Risk Indicators",
)
async def list_risk_indicators(
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: Annotated[SafetyAnalyticsService, Depends(get_safety_analytics_service)],
) -> StandardSuccessResponse[List[SafetyRiskIndicatorFinding]]:
    results = service.repo.list_risk_indicators(organization_id=current_user.organization_id)
    return StandardSuccessResponse(data=results, request_id=_req_id(http_request))


@router.get(
    "/escalation-required",
    response_model=StandardSuccessResponse[List[SafetyAnalysisRecord]],
    summary="List Analyses Requiring Governed Escalation",
)
async def list_escalation_required(
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: Annotated[SafetyAnalyticsService, Depends(get_safety_analytics_service)],
) -> StandardSuccessResponse[List[SafetyAnalysisRecord]]:
    results = service.repo.list_escalation_required(organization_id=current_user.organization_id)
    return StandardSuccessResponse(data=results, request_id=_req_id(http_request))


@router.get(
    "/reassessment-required",
    response_model=StandardSuccessResponse[List[SafetyAnalysisRecord]],
    summary="List Analyses Requiring Phase 60 Reassessment",
)
async def list_reassessment_required(
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: Annotated[SafetyAnalyticsService, Depends(get_safety_analytics_service)],
) -> StandardSuccessResponse[List[SafetyAnalysisRecord]]:
    results = service.repo.list_reassessment_required(organization_id=current_user.organization_id)
    return StandardSuccessResponse(data=results, request_id=_req_id(http_request))


@router.get(
    "/reanalysis-required",
    response_model=StandardSuccessResponse[List[SafetyAnalysisRecord]],
    summary="List Stale Analyses Requiring Reanalysis",
)
async def list_reanalysis_required(
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: Annotated[SafetyAnalyticsService, Depends(get_safety_analytics_service)],
) -> StandardSuccessResponse[List[SafetyAnalysisRecord]]:
    results = service.repo.list_reanalysis_required(organization_id=current_user.organization_id)
    return StandardSuccessResponse(data=results, request_id=_req_id(http_request))


@router.get(
    "",
    response_model=StandardSuccessResponse[List[SafetyAnalysisRecord]],
    summary="List Authorized Safety Analyses",
)
async def list_analyses(
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: Annotated[SafetyAnalyticsService, Depends(get_safety_analytics_service)],
    facility_id: Optional[str] = Query(None),
    lifecycle_state: Optional[AnalysisLifecycleState] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> StandardSuccessResponse[List[SafetyAnalysisRecord]]:
    results = service.repo.list_analyses(
        organization_id=current_user.organization_id,
        facility_id=facility_id,
        lifecycle_state=lifecycle_state,
        limit=limit,
        offset=offset,
    )
    return StandardSuccessResponse(data=results, request_id=_req_id(http_request))


# ---------------------------------------------------------------------------
# Parameterized Subpaths
# ---------------------------------------------------------------------------


@router.get(
    "/{analysis_id}",
    response_model=StandardSuccessResponse[SafetyAnalysisRecord],
    summary="Get Safety Analysis Record",
)
async def get_analysis(
    http_request: Request,
    analysis_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: Annotated[SafetyAnalyticsService, Depends(get_safety_analytics_service)],
) -> StandardSuccessResponse[SafetyAnalysisRecord]:
    record = service.repo.get(analysis_id)
    if not record:
        raise AppException(
            code=ErrorCode.SAFETY_ANALYTICS_NOT_FOUND,
            message=f"Safety analysis {analysis_id} not found",
            status_code=404,
        )
    _check_tenant(current_user, record)
    return StandardSuccessResponse(data=record, request_id=_req_id(http_request))


@router.get(
    "/{analysis_id}/status",
    response_model=StandardSuccessResponse[Dict[str, Any]],
    summary="Get Safety Analysis Execution Status",
)
async def get_analysis_status(
    http_request: Request,
    analysis_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: Annotated[SafetyAnalyticsService, Depends(get_safety_analytics_service)],
) -> StandardSuccessResponse[Dict[str, Any]]:
    record = service.repo.get(analysis_id)
    if not record:
        raise AppException(
            code=ErrorCode.SAFETY_ANALYTICS_NOT_FOUND,
            message=f"Safety analysis {analysis_id} not found",
            status_code=404,
        )
    _check_tenant(current_user, record)
    status_data = {
        "analysis_id": record.analysis_id,
        "lifecycle_state": record.lifecycle_state,
        "overall_uncertainty": record.overall_uncertainty,
        "requires_human_review": record.requires_human_review,
        "requires_escalation": record.requires_escalation,
        "requires_reassessment": record.requires_reassessment,
        "patterns_count": len(record.pattern_findings),
        "risk_indicators_count": len(record.risk_indicators),
        "eligible_signals_count": len(record.eligible_signals),
        "excluded_signals_count": len(record.excluded_signals),
        "completed_at": record.completed_at,
        "updated_at": record.updated_at,
    }
    return StandardSuccessResponse(data=status_data, request_id=_req_id(http_request))


@router.get(
    "/{analysis_id}/signals",
    response_model=StandardSuccessResponse[Dict[str, List[EligibleSignalReference]]],
    summary="Get Analyzed Signals",
)
async def get_analysis_signals(
    http_request: Request,
    analysis_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: Annotated[SafetyAnalyticsService, Depends(get_safety_analytics_service)],
) -> StandardSuccessResponse[Dict[str, List[EligibleSignalReference]]]:
    record = service.repo.get(analysis_id)
    if not record:
        raise AppException(
            code=ErrorCode.SAFETY_ANALYTICS_NOT_FOUND,
            message=f"Safety analysis {analysis_id} not found",
            status_code=404,
        )
    _check_tenant(current_user, record)
    return StandardSuccessResponse(
        data={"eligible": record.eligible_signals, "excluded": record.excluded_signals},
        request_id=_req_id(http_request),
    )


@router.get(
    "/{analysis_id}/trends",
    response_model=StandardSuccessResponse[List[TrendFinding]],
    summary="Get Trend Findings",
)
async def get_analysis_trends(
    http_request: Request,
    analysis_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: Annotated[SafetyAnalyticsService, Depends(get_safety_analytics_service)],
) -> StandardSuccessResponse[List[TrendFinding]]:
    record = service.repo.get(analysis_id)
    if not record:
        raise AppException(
            code=ErrorCode.SAFETY_ANALYTICS_NOT_FOUND,
            message=f"Safety analysis {analysis_id} not found",
            status_code=404,
        )
    _check_tenant(current_user, record)
    return StandardSuccessResponse(data=record.trend_findings, request_id=_req_id(http_request))


@router.get(
    "/{analysis_id}/patterns",
    response_model=StandardSuccessResponse[List[SafetyPatternFinding]],
    summary="Get Detected Patterns",
)
async def get_analysis_patterns(
    http_request: Request,
    analysis_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: Annotated[SafetyAnalyticsService, Depends(get_safety_analytics_service)],
) -> StandardSuccessResponse[List[SafetyPatternFinding]]:
    record = service.repo.get(analysis_id)
    if not record:
        raise AppException(
            code=ErrorCode.SAFETY_ANALYTICS_NOT_FOUND,
            message=f"Safety analysis {analysis_id} not found",
            status_code=404,
        )
    _check_tenant(current_user, record)
    return StandardSuccessResponse(data=record.pattern_findings, request_id=_req_id(http_request))


@router.get(
    "/{analysis_id}/correlations",
    response_model=StandardSuccessResponse[List[CorrelationFinding]],
    summary="Get Correlation Findings",
)
async def get_analysis_correlations(
    http_request: Request,
    analysis_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: Annotated[SafetyAnalyticsService, Depends(get_safety_analytics_service)],
) -> StandardSuccessResponse[List[CorrelationFinding]]:
    record = service.repo.get(analysis_id)
    if not record:
        raise AppException(
            code=ErrorCode.SAFETY_ANALYTICS_NOT_FOUND,
            message=f"Safety analysis {analysis_id} not found",
            status_code=404,
        )
    _check_tenant(current_user, record)
    return StandardSuccessResponse(data=record.correlation_findings, request_id=_req_id(http_request))


@router.get(
    "/{analysis_id}/risk-indicators",
    response_model=StandardSuccessResponse[List[SafetyRiskIndicatorFinding]],
    summary="Get Analysis Risk Indicators",
)
async def get_analysis_risk_indicators(
    http_request: Request,
    analysis_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: Annotated[SafetyAnalyticsService, Depends(get_safety_analytics_service)],
) -> StandardSuccessResponse[List[SafetyRiskIndicatorFinding]]:
    record = service.repo.get(analysis_id)
    if not record:
        raise AppException(
            code=ErrorCode.SAFETY_ANALYTICS_NOT_FOUND,
            message=f"Safety analysis {analysis_id} not found",
            status_code=404,
        )
    _check_tenant(current_user, record)
    return StandardSuccessResponse(data=record.risk_indicators, request_id=_req_id(http_request))


@router.get(
    "/{analysis_id}/evidence",
    response_model=StandardSuccessResponse[List[AnalyticalEvidenceReference]],
    summary="Get Analytical Evidence",
)
async def get_analysis_evidence(
    http_request: Request,
    analysis_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: Annotated[SafetyAnalyticsService, Depends(get_safety_analytics_service)],
) -> StandardSuccessResponse[List[AnalyticalEvidenceReference]]:
    record = service.repo.get(analysis_id)
    if not record:
        raise AppException(
            code=ErrorCode.SAFETY_ANALYTICS_NOT_FOUND,
            message=f"Safety analysis {analysis_id} not found",
            status_code=404,
        )
    _check_tenant(current_user, record)
    return StandardSuccessResponse(data=record.evidence_references, request_id=_req_id(http_request))


@router.get(
    "/{analysis_id}/history",
    response_model=StandardSuccessResponse[List[AnalysisHistoryEntry]],
    summary="Get Analysis Audit History",
)
async def get_analysis_history(
    http_request: Request,
    analysis_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: Annotated[SafetyAnalyticsService, Depends(get_safety_analytics_service)],
) -> StandardSuccessResponse[List[AnalysisHistoryEntry]]:
    record = service.repo.get(analysis_id)
    if not record:
        raise AppException(
            code=ErrorCode.SAFETY_ANALYTICS_NOT_FOUND,
            message=f"Safety analysis {analysis_id} not found",
            status_code=404,
        )
    _check_tenant(current_user, record)
    return StandardSuccessResponse(data=record.history, request_id=_req_id(http_request))


@router.post(
    "/{analysis_id}/analyze",
    response_model=StandardSuccessResponse[Any],
    summary="Execute Surveillance Analysis",
)
async def analyze(
    http_request: Request,
    analysis_id: str,
    payload: ExecuteAnalysisRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: Annotated[SafetyAnalyticsService, Depends(get_safety_analytics_service)],
    async_service: Annotated[SafetyAnalyticsAsyncService, Depends(get_safety_analytics_async_service)],
) -> StandardSuccessResponse[Any]:
    record = service.repo.get(analysis_id)
    if not record:
        raise AppException(
            code=ErrorCode.SAFETY_ANALYTICS_NOT_FOUND,
            message=f"Safety analysis {analysis_id} not found",
            status_code=404,
        )
    _check_tenant(current_user, record)
    actor_id, actor_role = _actor_info(current_user)

    if payload.is_async:
        job = await async_service.enqueue_analysis_run(
            analysis_id=analysis_id,
            actor_id=actor_id,
            actor_role=actor_role,
            analysis_types=payload.analysis_types,
        )
        return StandardSuccessResponse(data=job, request_id=_req_id(http_request))

    updated = service.execute_analysis(
        analysis_id=analysis_id,
        actor_id=actor_id,
        actor_role=actor_role,
        analysis_types=payload.analysis_types,
    )
    return StandardSuccessResponse(data=updated, request_id=_req_id(http_request))


@router.post(
    "/{analysis_id}/reanalyze",
    response_model=StandardSuccessResponse[SafetyAnalysisRecord],
    summary="Re-execute Analysis",
)
async def reanalyze(
    http_request: Request,
    analysis_id: str,
    payload: ReanalyzeRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: Annotated[SafetyAnalyticsService, Depends(get_safety_analytics_service)],
) -> StandardSuccessResponse[SafetyAnalysisRecord]:
    record = service.repo.get(analysis_id)
    if not record:
        raise AppException(
            code=ErrorCode.SAFETY_ANALYTICS_NOT_FOUND,
            message=f"Safety analysis {analysis_id} not found",
            status_code=404,
        )
    _check_tenant(current_user, record)
    actor_id, actor_role = _actor_info(current_user)

    updated = service.reanalyze(
        analysis_id=analysis_id,
        reason=payload.reason,
        actor_id=actor_id,
        actor_role=actor_role,
        updated_version=payload.updated_version,
    )
    return StandardSuccessResponse(data=updated, request_id=_req_id(http_request))


@router.post(
    "/{analysis_id}/review",
    response_model=StandardSuccessResponse[SafetyAnalysisRecord],
    summary="Record Human Analytics Review",
)
async def review_analysis(
    http_request: Request,
    analysis_id: str,
    payload: ReviewAnalysisRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: Annotated[SafetyAnalyticsService, Depends(get_safety_analytics_service)],
) -> StandardSuccessResponse[SafetyAnalysisRecord]:
    record = service.repo.get(analysis_id)
    if not record:
        raise AppException(
            code=ErrorCode.SAFETY_ANALYTICS_NOT_FOUND,
            message=f"Safety analysis {analysis_id} not found",
            status_code=404,
        )
    _check_tenant(current_user, record)
    reviewer_id, reviewer_role = _actor_info(current_user)

    updated = service.submit_review(
        analysis_id=analysis_id,
        reviewer_id=reviewer_id,
        reviewer_role=reviewer_role,
        decision=payload.decision,
        reason=payload.reason,
        resulting_routes=payload.resulting_routes,
        is_ai=payload.is_ai,
    )
    return StandardSuccessResponse(data=updated, request_id=_req_id(http_request))


@router.post(
    "/{analysis_id}/route",
    response_model=StandardSuccessResponse[SafetyAnalysisRecord],
    summary="Route Analytical Findings",
)
async def route_analysis(
    http_request: Request,
    analysis_id: str,
    payload: RouteAnalysisRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: Annotated[SafetyAnalyticsService, Depends(get_safety_analytics_service)],
) -> StandardSuccessResponse[SafetyAnalysisRecord]:
    record = service.repo.get(analysis_id)
    if not record:
        raise AppException(
            code=ErrorCode.SAFETY_ANALYTICS_NOT_FOUND,
            message=f"Safety analysis {analysis_id} not found",
            status_code=404,
        )
    _check_tenant(current_user, record)
    actor_id, actor_role = _actor_info(current_user)

    updated = service.route_findings(
        analysis_id=analysis_id,
        destinations=payload.destinations,
        actor_id=actor_id,
        actor_role=actor_role,
        reason=payload.reason,
        target_reference=payload.target_reference,
    )
    return StandardSuccessResponse(data=updated, request_id=_req_id(http_request))


@router.post(
    "/{analysis_id}/reassess",
    response_model=StandardSuccessResponse[SafetyAnalysisRecord],
    summary="Request Phase 60 Reassessment",
)
async def reassess_analysis(
    http_request: Request,
    analysis_id: str,
    payload: ReassessAnalysisRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: Annotated[SafetyAnalyticsService, Depends(get_safety_analytics_service)],
) -> StandardSuccessResponse[SafetyAnalysisRecord]:
    record = service.repo.get(analysis_id)
    if not record:
        raise AppException(
            code=ErrorCode.SAFETY_ANALYTICS_NOT_FOUND,
            message=f"Safety analysis {analysis_id} not found",
            status_code=404,
        )
    _check_tenant(current_user, record)
    actor_id, actor_role = _actor_info(current_user)

    updated = service.request_reassessment(
        analysis_id=analysis_id,
        reason=payload.reason,
        actor_id=actor_id,
        actor_role=actor_role,
        signal_ids=payload.signal_ids,
    )
    return StandardSuccessResponse(data=updated, request_id=_req_id(http_request))
