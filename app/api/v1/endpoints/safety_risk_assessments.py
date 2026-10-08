"""Phase 62: Clinical Safety Risk Signal Consolidation, Cross-Domain Correlation & Governed Risk Assessment Endpoints.

TRD Section 35 Endpoints:
  POST /safety-risk-assessments
  GET  /safety-risk-assessments/review-required
  GET  /safety-risk-assessments/high-priority
  GET  /safety-risk-assessments/escalation-required
  GET  /safety-risk-assessments/reassessment-required
  GET  /safety-risk-assessments/conflicted
  GET  /safety-risk-assessments
  GET  /safety-risk-assessments/{assessment_id}
  GET  /safety-risk-assessments/{assessment_id}/status
  GET  /safety-risk-assessments/{assessment_id}/findings
  GET  /safety-risk-assessments/{assessment_id}/evidence
  GET  /safety-risk-assessments/{assessment_id}/correlations
  GET  /safety-risk-assessments/{assessment_id}/risk-context
  GET  /safety-risk-assessments/{assessment_id}/history
  POST /safety-risk-assessments/{assessment_id}/consolidate
  POST /safety-risk-assessments/{assessment_id}/reconcile
  POST /safety-risk-assessments/{assessment_id}/assess
  POST /safety-risk-assessments/{assessment_id}/review
  POST /safety-risk-assessments/{assessment_id}/route
  POST /safety-risk-assessments/{assessment_id}/reassess
  POST /safety-risk-assessments/{assessment_id}/reanalyze
"""

from typing import Annotated, Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query, Request, Response, status

from app.api.deps import get_current_user
from app.core.exceptions import AppException, ErrorCode
from app.core.logging import request_id_ctx_var
from app.schemas.response import StandardSuccessResponse
from app.schemas.safety_risk_assessment import (
    AssessmentLifecycleState,
    ConsolidateFindingsRequest,
    ConsolidatedRiskContext,
    ConsolidatedSourceFindingReference,
    CreateRiskAssessmentRequest,
    CrossDomainCorrelationLink,
    ExecuteRiskAssessmentRequest,
    ReanalyzeRiskAssessmentRequest,
    ReassessRiskAssessmentRequest,
    ReconcileEvidenceRequest,
    ReconciledEvidenceItem,
    ReviewRiskAssessmentRequest,
    RiskAssessmentHistoryEntry,
    RouteRiskAssessmentRequest,
    SafetyRiskAssessmentRecord,
)
from app.schemas.user import AuthenticatedUserContext
from app.services.safety_risk_assessment_service import (
    SafetyRiskAssessmentService,
    get_safety_risk_assessment_service,
)
from app.services.safety_risk_async_service import (
    SafetyRiskAsyncService,
    get_safety_risk_async_service,
)

router = APIRouter(
    prefix="/safety-risk-assessments",
    tags=["Clinical Safety Risk Signal Consolidation, Cross-Domain Correlation & Governed Risk Assessment"],
)


def _req_id(request: Request) -> str:
    return getattr(request.state, "request_id", None) or request_id_ctx_var.get() or "req-unknown"


def _check_tenant(current_user: AuthenticatedUserContext, record: SafetyRiskAssessmentRecord) -> None:
    user_org = getattr(current_user, "organization_id", None)
    record_org = record.organization_id or getattr(record.scope, "organization_id", None)
    if user_org and record_org and record_org != user_org:
        raise AppException(
            code=ErrorCode.ACCESS_DENIED,
            message="Access denied to cross-tenant safety risk assessment record",
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
    response_model=StandardSuccessResponse[SafetyRiskAssessmentRecord],
    status_code=status.HTTP_201_CREATED,
    summary="Create Safety Risk Assessment",
)
async def create_assessment(
    http_request: Request,
    request: CreateRiskAssessmentRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: Annotated[SafetyRiskAssessmentService, Depends(get_safety_risk_assessment_service)],
) -> StandardSuccessResponse[SafetyRiskAssessmentRecord]:
    actor_id, actor_role = _actor_info(current_user)
    org_id = current_user.organization_id or (request.scope.organization_id if request.scope else "org-default")

    record = service.create_assessment(
        request=request,
        organization_id=org_id,
        actor_id=actor_id,
        actor_role=actor_role,
    )
    return StandardSuccessResponse(data=record, request_id=_req_id(http_request))


@router.get(
    "/review-required",
    response_model=StandardSuccessResponse[List[SafetyRiskAssessmentRecord]],
    summary="List Assessments Requiring Human Review",
)
async def list_review_required(
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: Annotated[SafetyRiskAssessmentService, Depends(get_safety_risk_assessment_service)],
) -> StandardSuccessResponse[List[SafetyRiskAssessmentRecord]]:
    results = service.repo.list_review_required(organization_id=current_user.organization_id)
    return StandardSuccessResponse(data=results, request_id=_req_id(http_request))


@router.get(
    "/high-priority",
    response_model=StandardSuccessResponse[List[SafetyRiskAssessmentRecord]],
    summary="List High Priority Assessments",
)
async def list_high_priority(
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: Annotated[SafetyRiskAssessmentService, Depends(get_safety_risk_assessment_service)],
) -> StandardSuccessResponse[List[SafetyRiskAssessmentRecord]]:
    results = service.repo.list_high_priority(organization_id=current_user.organization_id)
    return StandardSuccessResponse(data=results, request_id=_req_id(http_request))


@router.get(
    "/escalation-required",
    response_model=StandardSuccessResponse[List[SafetyRiskAssessmentRecord]],
    summary="List Assessments Requiring Governed Escalation",
)
async def list_escalation_required(
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: Annotated[SafetyRiskAssessmentService, Depends(get_safety_risk_assessment_service)],
) -> StandardSuccessResponse[List[SafetyRiskAssessmentRecord]]:
    results = service.repo.list_escalation_required(organization_id=current_user.organization_id)
    return StandardSuccessResponse(data=results, request_id=_req_id(http_request))


@router.get(
    "/reassessment-required",
    response_model=StandardSuccessResponse[List[SafetyRiskAssessmentRecord]],
    summary="List Assessments Requiring Signal Reassessment",
)
async def list_reassessment_required(
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: Annotated[SafetyRiskAssessmentService, Depends(get_safety_risk_assessment_service)],
) -> StandardSuccessResponse[List[SafetyRiskAssessmentRecord]]:
    results = service.repo.list_reassessment_required(organization_id=current_user.organization_id)
    return StandardSuccessResponse(data=results, request_id=_req_id(http_request))


@router.get(
    "/conflicted",
    response_model=StandardSuccessResponse[List[SafetyRiskAssessmentRecord]],
    summary="List Assessments With Evidence Conflicts",
)
async def list_conflicted(
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: Annotated[SafetyRiskAssessmentService, Depends(get_safety_risk_assessment_service)],
) -> StandardSuccessResponse[List[SafetyRiskAssessmentRecord]]:
    results = service.repo.list_conflicted(organization_id=current_user.organization_id)
    return StandardSuccessResponse(data=results, request_id=_req_id(http_request))


@router.get(
    "",
    response_model=StandardSuccessResponse[List[SafetyRiskAssessmentRecord]],
    summary="List Authorized Risk Assessments",
)
async def list_assessments(
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: Annotated[SafetyRiskAssessmentService, Depends(get_safety_risk_assessment_service)],
    facility_id: Optional[str] = Query(None),
    lifecycle_state: Optional[AssessmentLifecycleState] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> StandardSuccessResponse[List[SafetyRiskAssessmentRecord]]:
    results = service.repo.list_assessments(
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
    "/{assessment_id}",
    response_model=StandardSuccessResponse[SafetyRiskAssessmentRecord],
    summary="Get Risk Assessment Record",
)
async def get_assessment(
    http_request: Request,
    assessment_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: Annotated[SafetyRiskAssessmentService, Depends(get_safety_risk_assessment_service)],
) -> StandardSuccessResponse[SafetyRiskAssessmentRecord]:
    record = service.repo.get(assessment_id)
    if not record:
        raise AppException(
            code=ErrorCode.SAFETY_RISK_ASSESSMENT_NOT_FOUND,
            message=f"Risk assessment {assessment_id} not found",
            status_code=404,
        )
    _check_tenant(current_user, record)
    return StandardSuccessResponse(data=record, request_id=_req_id(http_request))


@router.get(
    "/{assessment_id}/status",
    response_model=StandardSuccessResponse[Dict[str, Any]],
    summary="Get Risk Assessment Execution Status",
)
async def get_assessment_status(
    http_request: Request,
    assessment_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: Annotated[SafetyRiskAssessmentService, Depends(get_safety_risk_assessment_service)],
) -> StandardSuccessResponse[Dict[str, Any]]:
    record = service.repo.get(assessment_id)
    if not record:
        raise AppException(
            code=ErrorCode.SAFETY_RISK_ASSESSMENT_NOT_FOUND,
            message=f"Risk assessment {assessment_id} not found",
            status_code=404,
        )
    _check_tenant(current_user, record)
    status_data = {
        "assessment_id": record.assessment_id,
        "lifecycle_state": record.lifecycle_state,
        "readiness_state": record.readiness_state,
        "overall_uncertainty": record.overall_uncertainty,
        "requires_human_review": record.requires_human_review,
        "requires_escalation": record.requires_escalation,
        "requires_reassessment": record.requires_reassessment,
        "has_unresolved_conflicts": record.has_unresolved_conflicts,
        "source_findings_count": len(record.source_findings),
        "excluded_findings_count": len(record.excluded_findings),
        "correlations_count": len(record.correlations),
        "evidence_items_count": len(record.evidence_items),
        "completed_at": record.completed_at,
        "updated_at": record.updated_at,
    }
    return StandardSuccessResponse(data=status_data, request_id=_req_id(http_request))


@router.get(
    "/{assessment_id}/findings",
    response_model=StandardSuccessResponse[Dict[str, List[ConsolidatedSourceFindingReference]]],
    summary="Get Source Findings",
)
async def get_assessment_findings(
    http_request: Request,
    assessment_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: Annotated[SafetyRiskAssessmentService, Depends(get_safety_risk_assessment_service)],
) -> StandardSuccessResponse[Dict[str, List[ConsolidatedSourceFindingReference]]]:
    record = service.repo.get(assessment_id)
    if not record:
        raise AppException(
            code=ErrorCode.SAFETY_RISK_ASSESSMENT_NOT_FOUND,
            message=f"Risk assessment {assessment_id} not found",
            status_code=404,
        )
    _check_tenant(current_user, record)
    return StandardSuccessResponse(
        data={"eligible": record.source_findings, "excluded": record.excluded_findings},
        request_id=_req_id(http_request),
    )


@router.get(
    "/{assessment_id}/evidence",
    response_model=StandardSuccessResponse[List[ReconciledEvidenceItem]],
    summary="Get Reconciled Evidence Items",
)
async def get_assessment_evidence(
    http_request: Request,
    assessment_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: Annotated[SafetyRiskAssessmentService, Depends(get_safety_risk_assessment_service)],
) -> StandardSuccessResponse[List[ReconciledEvidenceItem]]:
    record = service.repo.get(assessment_id)
    if not record:
        raise AppException(
            code=ErrorCode.SAFETY_RISK_ASSESSMENT_NOT_FOUND,
            message=f"Risk assessment {assessment_id} not found",
            status_code=404,
        )
    _check_tenant(current_user, record)
    return StandardSuccessResponse(data=record.evidence_items, request_id=_req_id(http_request))


@router.get(
    "/{assessment_id}/correlations",
    response_model=StandardSuccessResponse[List[CrossDomainCorrelationLink]],
    summary="Get Cross-Domain Correlations",
)
async def get_assessment_correlations(
    http_request: Request,
    assessment_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: Annotated[SafetyRiskAssessmentService, Depends(get_safety_risk_assessment_service)],
) -> StandardSuccessResponse[List[CrossDomainCorrelationLink]]:
    record = service.repo.get(assessment_id)
    if not record:
        raise AppException(
            code=ErrorCode.SAFETY_RISK_ASSESSMENT_NOT_FOUND,
            message=f"Risk assessment {assessment_id} not found",
            status_code=404,
        )
    _check_tenant(current_user, record)
    return StandardSuccessResponse(data=record.correlations, request_id=_req_id(http_request))


@router.get(
    "/{assessment_id}/risk-context",
    response_model=StandardSuccessResponse[Optional[ConsolidatedRiskContext]],
    summary="Get Consolidated Risk Context",
)
async def get_assessment_risk_context(
    http_request: Request,
    assessment_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: Annotated[SafetyRiskAssessmentService, Depends(get_safety_risk_assessment_service)],
) -> StandardSuccessResponse[Optional[ConsolidatedRiskContext]]:
    record = service.repo.get(assessment_id)
    if not record:
        raise AppException(
            code=ErrorCode.SAFETY_RISK_ASSESSMENT_NOT_FOUND,
            message=f"Risk assessment {assessment_id} not found",
            status_code=404,
        )
    _check_tenant(current_user, record)
    return StandardSuccessResponse(data=record.risk_context, request_id=_req_id(http_request))


@router.get(
    "/{assessment_id}/history",
    response_model=StandardSuccessResponse[List[RiskAssessmentHistoryEntry]],
    summary="Get Risk Assessment History",
)
async def get_assessment_history(
    http_request: Request,
    assessment_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: Annotated[SafetyRiskAssessmentService, Depends(get_safety_risk_assessment_service)],
) -> StandardSuccessResponse[List[RiskAssessmentHistoryEntry]]:
    record = service.repo.get(assessment_id)
    if not record:
        raise AppException(
            code=ErrorCode.SAFETY_RISK_ASSESSMENT_NOT_FOUND,
            message=f"Risk assessment {assessment_id} not found",
            status_code=404,
        )
    _check_tenant(current_user, record)
    return StandardSuccessResponse(data=record.history, request_id=_req_id(http_request))


@router.post(
    "/{assessment_id}/consolidate",
    response_model=StandardSuccessResponse[SafetyRiskAssessmentRecord],
    summary="Consolidate Related Findings",
)
async def consolidate_findings(
    http_request: Request,
    assessment_id: str,
    payload: ConsolidateFindingsRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: Annotated[SafetyRiskAssessmentService, Depends(get_safety_risk_assessment_service)],
) -> StandardSuccessResponse[SafetyRiskAssessmentRecord]:
    record = service.repo.get(assessment_id)
    if not record:
        raise AppException(
            code=ErrorCode.SAFETY_RISK_ASSESSMENT_NOT_FOUND,
            message=f"Risk assessment {assessment_id} not found",
            status_code=404,
        )
    _check_tenant(current_user, record)
    actor_id, actor_role = _actor_info(current_user)

    updated = service.consolidate(
        assessment_id=assessment_id,
        actor_id=actor_id,
        actor_role=actor_role,
        concern_summary=payload.concern_summary,
    )
    return StandardSuccessResponse(data=updated, request_id=_req_id(http_request))


@router.post(
    "/{assessment_id}/reconcile",
    response_model=StandardSuccessResponse[SafetyRiskAssessmentRecord],
    summary="Reconcile Authoritative Evidence",
)
async def reconcile_evidence(
    http_request: Request,
    assessment_id: str,
    payload: ReconcileEvidenceRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: Annotated[SafetyRiskAssessmentService, Depends(get_safety_risk_assessment_service)],
) -> StandardSuccessResponse[SafetyRiskAssessmentRecord]:
    record = service.repo.get(assessment_id)
    if not record:
        raise AppException(
            code=ErrorCode.SAFETY_RISK_ASSESSMENT_NOT_FOUND,
            message=f"Risk assessment {assessment_id} not found",
            status_code=404,
        )
    _check_tenant(current_user, record)
    actor_id, actor_role = _actor_info(current_user)

    updated = service.reconcile_evidence(
        assessment_id=assessment_id,
        actor_id=actor_id,
        actor_role=actor_role,
        external_evidence=payload.external_evidence,
    )
    return StandardSuccessResponse(data=updated, request_id=_req_id(http_request))


@router.post(
    "/{assessment_id}/assess",
    response_model=StandardSuccessResponse[Any],
    summary="Execute Governed Risk Characterization",
)
async def assess_risk(
    http_request: Request,
    assessment_id: str,
    payload: ExecuteRiskAssessmentRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: Annotated[SafetyRiskAssessmentService, Depends(get_safety_risk_assessment_service)],
    async_service: Annotated[SafetyRiskAsyncService, Depends(get_safety_risk_async_service)],
) -> StandardSuccessResponse[Any]:
    record = service.repo.get(assessment_id)
    if not record:
        raise AppException(
            code=ErrorCode.SAFETY_RISK_ASSESSMENT_NOT_FOUND,
            message=f"Risk assessment {assessment_id} not found",
            status_code=404,
        )
    _check_tenant(current_user, record)
    actor_id, actor_role = _actor_info(current_user)

    if payload.is_async:
        job = await async_service.enqueue_assessment_run(
            assessment_id=assessment_id,
            actor_id=actor_id,
            actor_role=actor_role,
        )
        return StandardSuccessResponse(data=job, request_id=_req_id(http_request))

    updated = service.assess_risk(
        assessment_id=assessment_id,
        actor_id=actor_id,
        actor_role=actor_role,
    )
    return StandardSuccessResponse(data=updated, request_id=_req_id(http_request))


@router.post(
    "/{assessment_id}/review",
    response_model=StandardSuccessResponse[SafetyRiskAssessmentRecord],
    summary="Record Human Risk Assessment Review",
)
async def review_assessment(
    http_request: Request,
    assessment_id: str,
    payload: ReviewRiskAssessmentRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: Annotated[SafetyRiskAssessmentService, Depends(get_safety_risk_assessment_service)],
) -> StandardSuccessResponse[SafetyRiskAssessmentRecord]:
    record = service.repo.get(assessment_id)
    if not record:
        raise AppException(
            code=ErrorCode.SAFETY_RISK_ASSESSMENT_NOT_FOUND,
            message=f"Risk assessment {assessment_id} not found",
            status_code=404,
        )
    _check_tenant(current_user, record)
    reviewer_id, reviewer_role = _actor_info(current_user)

    updated = service.submit_review(
        assessment_id=assessment_id,
        reviewer_id=reviewer_id,
        reviewer_role=reviewer_role,
        decision=payload.decision,
        reason=payload.reason,
        resulting_routes=payload.resulting_routes,
        is_ai=payload.is_ai,
    )
    return StandardSuccessResponse(data=updated, request_id=_req_id(http_request))


@router.post(
    "/{assessment_id}/route",
    response_model=StandardSuccessResponse[SafetyRiskAssessmentRecord],
    summary="Route Consolidated Risk Assessment",
)
async def route_assessment(
    http_request: Request,
    assessment_id: str,
    payload: RouteRiskAssessmentRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: Annotated[SafetyRiskAssessmentService, Depends(get_safety_risk_assessment_service)],
) -> StandardSuccessResponse[SafetyRiskAssessmentRecord]:
    record = service.repo.get(assessment_id)
    if not record:
        raise AppException(
            code=ErrorCode.SAFETY_RISK_ASSESSMENT_NOT_FOUND,
            message=f"Risk assessment {assessment_id} not found",
            status_code=404,
        )
    _check_tenant(current_user, record)
    actor_id, actor_role = _actor_info(current_user)

    updated = service.route_assessment(
        assessment_id=assessment_id,
        destinations=payload.destinations,
        actor_id=actor_id,
        actor_role=actor_role,
        reason=payload.reason,
        target_reference=payload.target_reference,
    )
    return StandardSuccessResponse(data=updated, request_id=_req_id(http_request))


@router.post(
    "/{assessment_id}/reassess",
    response_model=StandardSuccessResponse[SafetyRiskAssessmentRecord],
    summary="Request Phase 60 Signal Reassessment",
)
async def reassess_assessment(
    http_request: Request,
    assessment_id: str,
    payload: ReassessRiskAssessmentRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: Annotated[SafetyRiskAssessmentService, Depends(get_safety_risk_assessment_service)],
) -> StandardSuccessResponse[SafetyRiskAssessmentRecord]:
    record = service.repo.get(assessment_id)
    if not record:
        raise AppException(
            code=ErrorCode.SAFETY_RISK_ASSESSMENT_NOT_FOUND,
            message=f"Risk assessment {assessment_id} not found",
            status_code=404,
        )
    _check_tenant(current_user, record)
    actor_id, actor_role = _actor_info(current_user)

    updated = service.request_reassessment(
        assessment_id=assessment_id,
        reason=payload.reason,
        actor_id=actor_id,
        actor_role=actor_role,
        signal_ids=payload.signal_ids,
    )
    return StandardSuccessResponse(data=updated, request_id=_req_id(http_request))


@router.post(
    "/{assessment_id}/reanalyze",
    response_model=StandardSuccessResponse[SafetyRiskAssessmentRecord],
    summary="Request Phase 61 Longitudinal Reanalysis",
)
async def reanalyze_assessment(
    http_request: Request,
    assessment_id: str,
    payload: ReanalyzeRiskAssessmentRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: Annotated[SafetyRiskAssessmentService, Depends(get_safety_risk_assessment_service)],
) -> StandardSuccessResponse[SafetyRiskAssessmentRecord]:
    record = service.repo.get(assessment_id)
    if not record:
        raise AppException(
            code=ErrorCode.SAFETY_RISK_ASSESSMENT_NOT_FOUND,
            message=f"Risk assessment {assessment_id} not found",
            status_code=404,
        )
    _check_tenant(current_user, record)
    actor_id, actor_role = _actor_info(current_user)

    updated = service.request_reanalysis(
        assessment_id=assessment_id,
        reason=payload.reason,
        actor_id=actor_id,
        actor_role=actor_role,
        finding_ids=payload.finding_ids,
    )
    return StandardSuccessResponse(data=updated, request_id=_req_id(http_request))
