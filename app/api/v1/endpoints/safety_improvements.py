"""Phase 56: Clinical Safety Assurance Feedback, Control Adaptation & Governed Continuous Improvement APIs.

TRD Section 33 Endpoints:
  POST /safety-improvements
  GET  /safety-improvements/{improvement_id}
  GET  /safety-improvements/{improvement_id}/status
  GET  /safety-improvements/{improvement_id}/history
  GET  /safety-improvements/{improvement_id}/evidence
  POST /safety-improvements/{improvement_id}/classify
  POST /safety-improvements/{improvement_id}/change-proposal
  GET  /safety-improvements/{improvement_id}/change-proposal
  POST /safety-improvements/{improvement_id}/impact-assessment
  GET  /safety-improvements/{improvement_id}/readiness
  POST /safety-improvements/{improvement_id}/route-governance
  POST /safety-improvements/{improvement_id}/reassess
  POST /safety-improvements/{improvement_id}/escalate
  POST /safety-improvements/{improvement_id}/reopen
  POST /safety-improvements/{improvement_id}/close
  GET  /safety-improvements
  GET  /safety-improvements/pending
  GET  /safety-improvements/high-priority
  GET  /safety-improvements/regressions
  GET  /safety-improvements/recurring
  GET  /safety-improvements/change-candidates
  POST /safety-improvements/reanalysis
"""

from typing import Annotated, Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query, Request, status

from app.api.deps import get_current_user
from app.core.exceptions import AppException, ErrorCode
from app.core.logging import request_id_ctx_var
from app.schemas.response import StandardSuccessResponse
from app.schemas.safety_improvement import (
    ChangeProposalRecord,
    ClassifyImprovementRequest,
    CloseRequest,
    CreateChangeProposalRequest,
    CreateImprovementRequest,
    EscalateRequest,
    ImpactAssessmentRecord,
    ImprovementEvidenceReference,
    ImprovementHistoryEntry,
    ImprovementLifecycleState,
    ImprovementPriority,
    ReadinessResponse,
    ReanalysisRequest,
    ReassessmentRequest,
    ReopenRequest,
    RequestImpactAssessmentRequest,
    RouteGovernanceRequest,
    SafetyImprovementRecord,
    StatusResponse,
)
from app.schemas.user import AuthenticatedUserContext
from app.services.safety_improvement_service import (
    SafetyImprovementService,
    get_safety_improvement_service,
)

router = APIRouter(
    prefix="/safety-improvements",
    tags=["Clinical Safety Assurance Feedback, Control Adaptation & Governed Continuous Improvement"],
)


def _req_id(request: Request) -> str:
    return getattr(request.state, "request_id", None) or request_id_ctx_var.get() or "req-unknown"


@router.post(
    "",
    response_model=StandardSuccessResponse[SafetyImprovementRecord],
    status_code=status.HTTP_201_CREATED,
    summary="Create Continuous Safety Improvement Opportunity",
)
async def create_improvement(
    http_request: Request,
    request_body: CreateImprovementRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyImprovementService = Depends(get_safety_improvement_service),
) -> StandardSuccessResponse[SafetyImprovementRecord]:
    req_id = _req_id(http_request)
    actor_id = str(getattr(current_user, "id", "unknown"))
    actor_role = str(getattr(current_user, "role", "SAFETY_OFFICER"))

    record = service.create_improvement(
        request=request_body,
        actor_id=actor_id,
        actor_role=actor_role,
    )
    return StandardSuccessResponse(data=record, request_id=req_id)


@router.get(
    "/pending",
    response_model=StandardSuccessResponse[List[SafetyImprovementRecord]],
    status_code=status.HTTP_200_OK,
    summary="List Pending Safety Improvements",
)
async def list_pending_improvements(
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    organization_id: Optional[str] = Query(None),
    service: SafetyImprovementService = Depends(get_safety_improvement_service),
) -> StandardSuccessResponse[List[SafetyImprovementRecord]]:
    req_id = _req_id(http_request)
    user_org = getattr(current_user, "organization_id", None)
    target_org = organization_id or user_org
    records = service.list_pending(organization_id=target_org)
    return StandardSuccessResponse(data=records, request_id=req_id)


@router.get(
    "/high-priority",
    response_model=StandardSuccessResponse[List[SafetyImprovementRecord]],
    status_code=status.HTTP_200_OK,
    summary="List High Priority Improvements",
)
async def list_high_priority_improvements(
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    organization_id: Optional[str] = Query(None),
    service: SafetyImprovementService = Depends(get_safety_improvement_service),
) -> StandardSuccessResponse[List[SafetyImprovementRecord]]:
    req_id = _req_id(http_request)
    user_org = getattr(current_user, "organization_id", None)
    target_org = organization_id or user_org
    records = service.list_high_priority(organization_id=target_org)
    return StandardSuccessResponse(data=records, request_id=req_id)


@router.get(
    "/regressions",
    response_model=StandardSuccessResponse[List[SafetyImprovementRecord]],
    status_code=status.HTTP_200_OK,
    summary="List Regression Improvements",
)
async def list_regression_improvements(
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    organization_id: Optional[str] = Query(None),
    service: SafetyImprovementService = Depends(get_safety_improvement_service),
) -> StandardSuccessResponse[List[SafetyImprovementRecord]]:
    req_id = _req_id(http_request)
    user_org = getattr(current_user, "organization_id", None)
    target_org = organization_id or user_org
    records = service.list_regressions(organization_id=target_org)
    return StandardSuccessResponse(data=records, request_id=req_id)


@router.get(
    "/recurring",
    response_model=StandardSuccessResponse[List[SafetyImprovementRecord]],
    status_code=status.HTTP_200_OK,
    summary="List Recurring Improvement Patterns",
)
async def list_recurring_improvements(
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    organization_id: Optional[str] = Query(None),
    service: SafetyImprovementService = Depends(get_safety_improvement_service),
) -> StandardSuccessResponse[List[SafetyImprovementRecord]]:
    req_id = _req_id(http_request)
    user_org = getattr(current_user, "organization_id", None)
    target_org = organization_id or user_org
    records = service.list_recurring(organization_id=target_org)
    return StandardSuccessResponse(data=records, request_id=req_id)


@router.get(
    "/change-candidates",
    response_model=StandardSuccessResponse[List[SafetyImprovementRecord]],
    status_code=status.HTTP_200_OK,
    summary="List Change Candidates",
)
async def list_change_candidates(
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    organization_id: Optional[str] = Query(None),
    service: SafetyImprovementService = Depends(get_safety_improvement_service),
) -> StandardSuccessResponse[List[SafetyImprovementRecord]]:
    req_id = _req_id(http_request)
    user_org = getattr(current_user, "organization_id", None)
    target_org = organization_id or user_org
    records = service.list_change_candidates(organization_id=target_org)
    return StandardSuccessResponse(data=records, request_id=req_id)


@router.post(
    "/reanalysis",
    response_model=StandardSuccessResponse[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Trigger Improvement Reanalysis",
)
async def trigger_reanalysis(
    http_request: Request,
    request_body: ReanalysisRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyImprovementService = Depends(get_safety_improvement_service),
) -> StandardSuccessResponse[Dict[str, Any]]:
    req_id = _req_id(http_request)
    res = service.reanalysis(
        improvement_ids=request_body.improvement_ids,
        reason=request_body.reason,
    )
    return StandardSuccessResponse(data=res, request_id=req_id)


@router.get(
    "",
    response_model=StandardSuccessResponse[List[SafetyImprovementRecord]],
    status_code=status.HTTP_200_OK,
    summary="List Safety Improvements",
)
async def list_improvements(
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    organization_id: Optional[str] = Query(None),
    facility_id: Optional[str] = Query(None),
    lifecycle_state: Optional[ImprovementLifecycleState] = Query(None),
    priority: Optional[ImprovementPriority] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    service: SafetyImprovementService = Depends(get_safety_improvement_service),
) -> StandardSuccessResponse[List[SafetyImprovementRecord]]:
    req_id = _req_id(http_request)
    user_org = getattr(current_user, "organization_id", None)
    target_org = organization_id or user_org
    records = service.list_improvements(
        organization_id=target_org,
        facility_id=facility_id,
        lifecycle_state=lifecycle_state,
        priority=priority,
        limit=limit,
        offset=offset,
    )
    return StandardSuccessResponse(data=records, request_id=req_id)


@router.get(
    "/{improvement_id}",
    response_model=StandardSuccessResponse[SafetyImprovementRecord],
    status_code=status.HTTP_200_OK,
    summary="Get Safety Improvement Details",
)
async def get_improvement_details(
    http_request: Request,
    improvement_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyImprovementService = Depends(get_safety_improvement_service),
) -> StandardSuccessResponse[SafetyImprovementRecord]:
    req_id = _req_id(http_request)
    record = service.get_improvement(improvement_id)
    return StandardSuccessResponse(data=record, request_id=req_id)


@router.get(
    "/{improvement_id}/status",
    response_model=StandardSuccessResponse[StatusResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Safety Improvement Status",
)
async def get_improvement_status(
    http_request: Request,
    improvement_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyImprovementService = Depends(get_safety_improvement_service),
) -> StandardSuccessResponse[StatusResponse]:
    req_id = _req_id(http_request)
    rec = service.get_improvement(improvement_id)
    resp = StatusResponse(
        improvement_id=rec.improvement_id,
        lifecycle_state=rec.lifecycle_state,
        signal_type=rec.signal_type,
        response_type=rec.response_type,
        priority=rec.priority,
        is_recurring=rec.is_recurring,
        is_regression=rec.is_regression,
        version=rec.version,
        updated_at=rec.updated_at,
    )
    return StandardSuccessResponse(data=resp, request_id=req_id)


@router.get(
    "/{improvement_id}/history",
    response_model=StandardSuccessResponse[List[ImprovementHistoryEntry]],
    status_code=status.HTTP_200_OK,
    summary="Get Safety Improvement History",
)
async def get_improvement_history(
    http_request: Request,
    improvement_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyImprovementService = Depends(get_safety_improvement_service),
) -> StandardSuccessResponse[List[ImprovementHistoryEntry]]:
    req_id = _req_id(http_request)
    rec = service.get_improvement(improvement_id)
    return StandardSuccessResponse(data=rec.history, request_id=req_id)


@router.get(
    "/{improvement_id}/evidence",
    response_model=StandardSuccessResponse[List[ImprovementEvidenceReference]],
    status_code=status.HTTP_200_OK,
    summary="Get Linked Improvement Evidence",
)
async def get_improvement_evidence(
    http_request: Request,
    improvement_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyImprovementService = Depends(get_safety_improvement_service),
) -> StandardSuccessResponse[List[ImprovementEvidenceReference]]:
    req_id = _req_id(http_request)
    rec = service.get_improvement(improvement_id)
    return StandardSuccessResponse(data=rec.evidence_references, request_id=req_id)


@router.post(
    "/{improvement_id}/classify",
    response_model=StandardSuccessResponse[SafetyImprovementRecord],
    status_code=status.HTTP_200_OK,
    summary="Classify Improvement Opportunity",
)
async def classify_improvement(
    http_request: Request,
    improvement_id: str,
    request_body: ClassifyImprovementRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyImprovementService = Depends(get_safety_improvement_service),
) -> StandardSuccessResponse[SafetyImprovementRecord]:
    req_id = _req_id(http_request)
    actor_id = str(getattr(current_user, "id", "unknown"))
    actor_role = str(getattr(current_user, "role", "SAFETY_OFFICER"))

    rec = service.classify_improvement(
        improvement_id=improvement_id,
        request=request_body,
        actor_id=actor_id,
        actor_role=actor_role,
    )
    return StandardSuccessResponse(data=rec, request_id=req_id)


@router.post(
    "/{improvement_id}/change-proposal",
    response_model=StandardSuccessResponse[SafetyImprovementRecord],
    status_code=status.HTTP_200_OK,
    summary="Create Governed Safety Change Proposal",
)
async def create_change_proposal(
    http_request: Request,
    improvement_id: str,
    request_body: CreateChangeProposalRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyImprovementService = Depends(get_safety_improvement_service),
) -> StandardSuccessResponse[SafetyImprovementRecord]:
    req_id = _req_id(http_request)
    actor_id = str(getattr(current_user, "id", "unknown"))
    actor_role = str(getattr(current_user, "role", "SAFETY_OFFICER"))

    rec = service.create_change_proposal(
        improvement_id=improvement_id,
        request=request_body,
        actor_id=actor_id,
        actor_role=actor_role,
    )
    return StandardSuccessResponse(data=rec, request_id=req_id)


@router.get(
    "/{improvement_id}/change-proposal",
    response_model=StandardSuccessResponse[Optional[ChangeProposalRecord]],
    status_code=status.HTTP_200_OK,
    summary="Get Safety Change Proposal",
)
async def get_change_proposal(
    http_request: Request,
    improvement_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyImprovementService = Depends(get_safety_improvement_service),
) -> StandardSuccessResponse[Optional[ChangeProposalRecord]]:
    req_id = _req_id(http_request)
    rec = service.get_improvement(improvement_id)
    return StandardSuccessResponse(data=rec.change_proposal, request_id=req_id)


@router.post(
    "/{improvement_id}/impact-assessment",
    response_model=StandardSuccessResponse[SafetyImprovementRecord],
    status_code=status.HTTP_200_OK,
    summary="Request & Record Impact Assessment",
)
async def request_impact_assessment(
    http_request: Request,
    improvement_id: str,
    request_body: RequestImpactAssessmentRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyImprovementService = Depends(get_safety_improvement_service),
) -> StandardSuccessResponse[SafetyImprovementRecord]:
    req_id = _req_id(http_request)
    actor_id = str(getattr(current_user, "id", "unknown"))
    actor_role = str(getattr(current_user, "role", "SAFETY_OFFICER"))

    rec = service.request_impact_assessment(
        improvement_id=improvement_id,
        request=request_body,
        actor_id=actor_id,
        actor_role=actor_role,
    )
    return StandardSuccessResponse(data=rec, request_id=req_id)


@router.get(
    "/{improvement_id}/readiness",
    response_model=StandardSuccessResponse[ReadinessResponse],
    status_code=status.HTTP_200_OK,
    summary="Check Change Proposal Readiness",
)
async def check_change_readiness(
    http_request: Request,
    improvement_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyImprovementService = Depends(get_safety_improvement_service),
) -> StandardSuccessResponse[ReadinessResponse]:
    req_id = _req_id(http_request)
    readiness = service.check_readiness(improvement_id)
    return StandardSuccessResponse(data=readiness, request_id=req_id)


@router.post(
    "/{improvement_id}/route-governance",
    response_model=StandardSuccessResponse[SafetyImprovementRecord],
    status_code=status.HTTP_200_OK,
    summary="Route Ready Change Proposal to Governance",
)
async def route_to_governance(
    http_request: Request,
    improvement_id: str,
    request_body: RouteGovernanceRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyImprovementService = Depends(get_safety_improvement_service),
) -> StandardSuccessResponse[SafetyImprovementRecord]:
    req_id = _req_id(http_request)
    actor_id = str(getattr(current_user, "id", "unknown"))
    actor_role = str(getattr(current_user, "role", "SAFETY_OFFICER"))

    rec = service.route_to_governance(
        improvement_id=improvement_id,
        rationale=request_body.rationale,
        actor_id=actor_id,
        actor_role=actor_role,
    )
    return StandardSuccessResponse(data=rec, request_id=req_id)


@router.post(
    "/{improvement_id}/reassess",
    response_model=StandardSuccessResponse[SafetyImprovementRecord],
    status_code=status.HTTP_200_OK,
    summary="Request Reassessment",
)
async def reassess_improvement(
    http_request: Request,
    improvement_id: str,
    request_body: ReassessmentRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyImprovementService = Depends(get_safety_improvement_service),
) -> StandardSuccessResponse[SafetyImprovementRecord]:
    req_id = _req_id(http_request)
    actor_id = str(getattr(current_user, "id", "unknown"))
    actor_role = str(getattr(current_user, "role", "SAFETY_OFFICER"))

    rec = service.reassess_improvement(
        improvement_id=improvement_id,
        reason=request_body.reason,
        actor_id=actor_id,
        actor_role=actor_role,
    )
    return StandardSuccessResponse(data=rec, request_id=req_id)


@router.post(
    "/{improvement_id}/escalate",
    response_model=StandardSuccessResponse[SafetyImprovementRecord],
    status_code=status.HTTP_200_OK,
    summary="Escalate Safety Improvement Opportunity",
)
async def escalate_improvement(
    http_request: Request,
    improvement_id: str,
    request_body: EscalateRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyImprovementService = Depends(get_safety_improvement_service),
) -> StandardSuccessResponse[SafetyImprovementRecord]:
    req_id = _req_id(http_request)
    actor_id = str(getattr(current_user, "id", "unknown"))
    actor_role = str(getattr(current_user, "role", "SAFETY_OFFICER"))

    rec = service.escalate_improvement(
        improvement_id=improvement_id,
        target=request_body.target,
        reason=request_body.reason,
        actor_id=actor_id,
        actor_role=actor_role,
    )
    return StandardSuccessResponse(data=rec, request_id=req_id)


@router.post(
    "/{improvement_id}/reopen",
    response_model=StandardSuccessResponse[SafetyImprovementRecord],
    status_code=status.HTTP_200_OK,
    summary="Reopen Safety Improvement Opportunity",
)
async def reopen_improvement(
    http_request: Request,
    improvement_id: str,
    request_body: ReopenRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyImprovementService = Depends(get_safety_improvement_service),
) -> StandardSuccessResponse[SafetyImprovementRecord]:
    req_id = _req_id(http_request)
    actor_id = str(getattr(current_user, "id", "unknown"))
    actor_role = str(getattr(current_user, "role", "SAFETY_OFFICER"))

    rec = service.reopen_improvement(
        improvement_id=improvement_id,
        reason=request_body.reason,
        actor_id=actor_id,
        actor_role=actor_role,
    )
    return StandardSuccessResponse(data=rec, request_id=req_id)


@router.post(
    "/{improvement_id}/close",
    response_model=StandardSuccessResponse[SafetyImprovementRecord],
    status_code=status.HTTP_200_OK,
    summary="Close Safety Improvement Opportunity",
)
async def close_improvement(
    http_request: Request,
    improvement_id: str,
    request_body: CloseRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyImprovementService = Depends(get_safety_improvement_service),
) -> StandardSuccessResponse[SafetyImprovementRecord]:
    req_id = _req_id(http_request)
    actor_id = str(getattr(current_user, "id", "unknown"))
    actor_role = str(getattr(current_user, "role", "SAFETY_OFFICER"))

    rec = service.close_improvement(
        improvement_id=improvement_id,
        rationale=request_body.rationale,
        actor_id=actor_id,
        actor_role=actor_role,
    )
    return StandardSuccessResponse(data=rec, request_id=req_id)
