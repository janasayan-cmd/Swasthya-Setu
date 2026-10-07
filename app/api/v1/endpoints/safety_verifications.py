"""Phase 58: Clinical Safety Change Verification, Release Evidence & Controlled Post-Rollout Closure APIs.

TRD Section 33 Endpoints:
  POST /safety-verifications
  GET  /safety-verifications/pending
  GET  /safety-verifications/review-required
  GET  /safety-verifications/closure-pending
  GET  /safety-verifications/reopened
  POST /safety-verifications/reanalysis
  GET  /safety-verifications
  GET  /safety-verifications/{verification_id}
  GET  /safety-verifications/{verification_id}/status
  GET  /safety-verifications/{verification_id}/evidence
  GET  /safety-verifications/{verification_id}/history
  POST /safety-verifications/{verification_id}/collect-evidence
  POST /safety-verifications/{verification_id}/verify
  POST /safety-verifications/{verification_id}/review
  POST /safety-verifications/{verification_id}/finalize
  POST /safety-verifications/{verification_id}/close
  POST /safety-verifications/{verification_id}/reopen
  POST /safety-verifications/{verification_id}/reassess
  GET  /safety-verifications/{verification_id}/closure-eligibility
  GET  /safety-verifications/{verification_id}/assurance
  GET  /safety-verifications/{verification_id}/effectiveness
"""

from typing import Annotated, Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query, Request, status

from app.api.deps import get_current_user
from app.core.exceptions import AppException, ErrorCode
from app.core.logging import request_id_ctx_var
from app.schemas.response import StandardSuccessResponse
from app.schemas.safety_verification import (
    ClosureEligibilityResponse,
    CollectEvidenceRequest,
    ControlledClosureRequest,
    CreateVerificationRequest,
    EvidenceReference,
    FinalizeVerificationRequest,
    HumanVerificationReviewRecord,
    ReanalysisVerificationRequest,
    ReassessmentVerificationRequest,
    ReopenVerificationRequest,
    RunVerificationRequest,
    SafetyVerificationRecord,
    SubmitReviewRequest,
    VerificationAssuranceResponse,
    VerificationEffectivenessResponse,
    VerificationHistoryEntry,
    VerificationLifecycleState,
    VerificationStatusResponse,
)
from app.schemas.user import AuthenticatedUserContext
from app.services.safety_verification_service import (
    SafetyVerificationService,
    get_safety_verification_service,
)

router = APIRouter(
    prefix="/safety-verifications",
    tags=["Clinical Safety Change Verification, Release Evidence & Controlled Post-Rollout Closure"],
)


def _req_id(request: Request) -> str:
    return getattr(request.state, "request_id", None) or request_id_ctx_var.get() or "req-unknown"


def _check_tenant(current_user: AuthenticatedUserContext, record: SafetyVerificationRecord) -> None:
    user_org = getattr(current_user, "organization_id", None)
    user_role = getattr(current_user, "role", "")
    if user_org and record.scope.organization_id != user_org and str(user_role).upper() not in {"SUPER_ADMIN", "ADMIN"}:
        raise AppException(
            code=ErrorCode.ACCESS_DENIED,
            message="Access denied to cross-tenant verification record",
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
    response_model=StandardSuccessResponse[SafetyVerificationRecord],
    status_code=status.HTTP_201_CREATED,
    summary="Create Change Verification Workflow",
)
async def create_verification(
    http_request: Request,
    request_body: CreateVerificationRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyVerificationService = Depends(get_safety_verification_service),
) -> StandardSuccessResponse[SafetyVerificationRecord]:
    req_id = _req_id(http_request)
    actor_id, actor_role = _actor_info(current_user)

    record = service.create_verification(
        request=request_body,
        actor_id=actor_id,
        actor_role=actor_role,
    )
    return StandardSuccessResponse(data=record, request_id=req_id)


@router.get(
    "/pending",
    response_model=StandardSuccessResponse[List[SafetyVerificationRecord]],
    status_code=status.HTTP_200_OK,
    summary="List Pending Safety Verifications",
)
async def list_pending_verifications(
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    organization_id: Optional[str] = Query(None),
    service: SafetyVerificationService = Depends(get_safety_verification_service),
) -> StandardSuccessResponse[List[SafetyVerificationRecord]]:
    req_id = _req_id(http_request)
    user_org = getattr(current_user, "organization_id", None)
    target_org = organization_id or user_org
    records = service.list_pending(organization_id=target_org)
    return StandardSuccessResponse(data=records, request_id=req_id)


@router.get(
    "/review-required",
    response_model=StandardSuccessResponse[List[SafetyVerificationRecord]],
    status_code=status.HTTP_200_OK,
    summary="List Verifications Requiring Human Review",
)
async def list_review_required_verifications(
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    organization_id: Optional[str] = Query(None),
    service: SafetyVerificationService = Depends(get_safety_verification_service),
) -> StandardSuccessResponse[List[SafetyVerificationRecord]]:
    req_id = _req_id(http_request)
    user_org = getattr(current_user, "organization_id", None)
    target_org = organization_id or user_org
    records = service.list_review_required(organization_id=target_org)
    return StandardSuccessResponse(data=records, request_id=req_id)


@router.get(
    "/closure-pending",
    response_model=StandardSuccessResponse[List[SafetyVerificationRecord]],
    status_code=status.HTTP_200_OK,
    summary="List Verifications Pending Controlled Closure",
)
async def list_closure_pending_verifications(
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    organization_id: Optional[str] = Query(None),
    service: SafetyVerificationService = Depends(get_safety_verification_service),
) -> StandardSuccessResponse[List[SafetyVerificationRecord]]:
    req_id = _req_id(http_request)
    user_org = getattr(current_user, "organization_id", None)
    target_org = organization_id or user_org
    records = service.list_closure_pending(organization_id=target_org)
    return StandardSuccessResponse(data=records, request_id=req_id)


@router.get(
    "/reopened",
    response_model=StandardSuccessResponse[List[SafetyVerificationRecord]],
    status_code=status.HTTP_200_OK,
    summary="List Reopened Verifications",
)
async def list_reopened_verifications(
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    organization_id: Optional[str] = Query(None),
    service: SafetyVerificationService = Depends(get_safety_verification_service),
) -> StandardSuccessResponse[List[SafetyVerificationRecord]]:
    req_id = _req_id(http_request)
    user_org = getattr(current_user, "organization_id", None)
    target_org = organization_id or user_org
    records = service.list_reopened(organization_id=target_org)
    return StandardSuccessResponse(data=records, request_id=req_id)


@router.post(
    "/reanalysis",
    response_model=StandardSuccessResponse[List[VerificationStatusResponse]],
    status_code=status.HTTP_200_OK,
    summary="Batch Reanalysis of Verifications",
)
async def batch_reanalysis(
    http_request: Request,
    request_body: ReanalysisVerificationRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyVerificationService = Depends(get_safety_verification_service),
) -> StandardSuccessResponse[List[VerificationStatusResponse]]:
    req_id = _req_id(http_request)
    actor_id, actor_role = _actor_info(current_user)

    results = service.reanalysis(
        request=request_body,
        actor_id=actor_id,
        actor_role=actor_role,
    )
    return StandardSuccessResponse(data=results, request_id=req_id)


@router.get(
    "",
    response_model=StandardSuccessResponse[List[SafetyVerificationRecord]],
    status_code=status.HTTP_200_OK,
    summary="List Controlled Safety Verifications",
)
async def list_verifications(
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    organization_id: Optional[str] = Query(None),
    facility_id: Optional[str] = Query(None),
    verification_status: Optional[VerificationLifecycleState] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    service: SafetyVerificationService = Depends(get_safety_verification_service),
) -> StandardSuccessResponse[List[SafetyVerificationRecord]]:
    req_id = _req_id(http_request)
    user_org = getattr(current_user, "organization_id", None)
    target_org = organization_id or user_org

    records = service.list_verifications(
        organization_id=target_org,
        facility_id=facility_id,
        verification_status=verification_status,
        limit=limit,
        offset=offset,
    )
    return StandardSuccessResponse(data=records, request_id=req_id)


# ---------------------------------------------------------------------------
# Item Subpaths
# ---------------------------------------------------------------------------


@router.get(
    "/{verification_id}",
    response_model=StandardSuccessResponse[SafetyVerificationRecord],
    status_code=status.HTTP_200_OK,
    summary="Get Safety Verification Record",
)
async def get_verification(
    http_request: Request,
    verification_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyVerificationService = Depends(get_safety_verification_service),
) -> StandardSuccessResponse[SafetyVerificationRecord]:
    req_id = _req_id(http_request)
    record = service.get_verification(verification_id)
    _check_tenant(current_user, record)
    return StandardSuccessResponse(data=record, request_id=req_id)


@router.get(
    "/{verification_id}/status",
    response_model=StandardSuccessResponse[VerificationStatusResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Verification Status",
)
async def get_verification_status(
    http_request: Request,
    verification_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyVerificationService = Depends(get_safety_verification_service),
) -> StandardSuccessResponse[VerificationStatusResponse]:
    req_id = _req_id(http_request)
    record = service.get_verification(verification_id)
    _check_tenant(current_user, record)
    status_resp = service.get_status(verification_id)
    return StandardSuccessResponse(data=status_resp, request_id=req_id)


@router.get(
    "/{verification_id}/evidence",
    response_model=StandardSuccessResponse[List[EvidenceReference]],
    status_code=status.HTTP_200_OK,
    summary="Get Linked Verification Evidence",
)
async def get_verification_evidence(
    http_request: Request,
    verification_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyVerificationService = Depends(get_safety_verification_service),
) -> StandardSuccessResponse[List[EvidenceReference]]:
    req_id = _req_id(http_request)
    record = service.get_verification(verification_id)
    _check_tenant(current_user, record)
    evidence = service.get_evidence(verification_id)
    return StandardSuccessResponse(data=evidence, request_id=req_id)


@router.get(
    "/{verification_id}/history",
    response_model=StandardSuccessResponse[List[VerificationHistoryEntry]],
    status_code=status.HTTP_200_OK,
    summary="Get Verification History",
)
async def get_verification_history(
    http_request: Request,
    verification_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyVerificationService = Depends(get_safety_verification_service),
) -> StandardSuccessResponse[List[VerificationHistoryEntry]]:
    req_id = _req_id(http_request)
    record = service.get_verification(verification_id)
    _check_tenant(current_user, record)
    history = service.get_history(verification_id)
    return StandardSuccessResponse(data=history, request_id=req_id)


@router.post(
    "/{verification_id}/collect-evidence",
    response_model=StandardSuccessResponse[List[EvidenceReference]],
    status_code=status.HTTP_200_OK,
    summary="Trigger Authoritative Evidence Harvesting",
)
async def collect_evidence(
    http_request: Request,
    verification_id: str,
    request_body: CollectEvidenceRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyVerificationService = Depends(get_safety_verification_service),
) -> StandardSuccessResponse[List[EvidenceReference]]:
    req_id = _req_id(http_request)
    record = service.get_verification(verification_id)
    _check_tenant(current_user, record)
    actor_id, actor_role = _actor_info(current_user)

    items = service.collect_evidence(
        verification_id=verification_id,
        request=request_body,
        actor_id=actor_id,
        actor_role=actor_role,
    )
    return StandardSuccessResponse(data=items, request_id=req_id)


@router.post(
    "/{verification_id}/verify",
    response_model=StandardSuccessResponse[SafetyVerificationRecord],
    status_code=status.HTTP_200_OK,
    summary="Run Verification Evaluation",
)
async def run_verification(
    http_request: Request,
    verification_id: str,
    request_body: RunVerificationRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyVerificationService = Depends(get_safety_verification_service),
) -> StandardSuccessResponse[SafetyVerificationRecord]:
    req_id = _req_id(http_request)
    record = service.get_verification(verification_id)
    _check_tenant(current_user, record)
    actor_id, actor_role = _actor_info(current_user)

    verified = service.verify(
        verification_id=verification_id,
        request=request_body,
        actor_id=actor_id,
        actor_role=actor_role,
    )
    return StandardSuccessResponse(data=verified, request_id=req_id)


@router.post(
    "/{verification_id}/review",
    response_model=StandardSuccessResponse[HumanVerificationReviewRecord],
    status_code=status.HTTP_200_OK,
    summary="Submit Human Supervisor Review Decision",
)
async def submit_review(
    http_request: Request,
    verification_id: str,
    request_body: SubmitReviewRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyVerificationService = Depends(get_safety_verification_service),
) -> StandardSuccessResponse[HumanVerificationReviewRecord]:
    req_id = _req_id(http_request)
    record = service.get_verification(verification_id)
    _check_tenant(current_user, record)
    actor_id, actor_role = _actor_info(current_user)

    review_rec = service.review(
        verification_id=verification_id,
        request=request_body,
        actor_id=actor_id,
        actor_role=actor_role,
    )
    return StandardSuccessResponse(data=review_rec, request_id=req_id)


@router.post(
    "/{verification_id}/finalize",
    response_model=StandardSuccessResponse[SafetyVerificationRecord],
    status_code=status.HTTP_200_OK,
    summary="Finalize Verification Result",
)
async def finalize_verification(
    http_request: Request,
    verification_id: str,
    request_body: FinalizeVerificationRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyVerificationService = Depends(get_safety_verification_service),
) -> StandardSuccessResponse[SafetyVerificationRecord]:
    req_id = _req_id(http_request)
    record = service.get_verification(verification_id)
    _check_tenant(current_user, record)
    actor_id, actor_role = _actor_info(current_user)

    finalized = service.finalize(
        verification_id=verification_id,
        request=request_body,
        actor_id=actor_id,
        actor_role=actor_role,
    )
    return StandardSuccessResponse(data=finalized, request_id=req_id)


@router.post(
    "/{verification_id}/close",
    response_model=StandardSuccessResponse[SafetyVerificationRecord],
    status_code=status.HTTP_200_OK,
    summary="Execute Controlled Change Closure",
)
async def close_verification(
    http_request: Request,
    verification_id: str,
    request_body: ControlledClosureRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyVerificationService = Depends(get_safety_verification_service),
) -> StandardSuccessResponse[SafetyVerificationRecord]:
    req_id = _req_id(http_request)
    record = service.get_verification(verification_id)
    _check_tenant(current_user, record)
    actor_id, actor_role = _actor_info(current_user)

    closed = service.close(
        verification_id=verification_id,
        request=request_body,
        actor_id=actor_id,
        actor_role=actor_role,
    )
    return StandardSuccessResponse(data=closed, request_id=req_id)


@router.post(
    "/{verification_id}/reopen",
    response_model=StandardSuccessResponse[SafetyVerificationRecord],
    status_code=status.HTTP_200_OK,
    summary="Execute Controlled Change Reopening",
)
async def reopen_verification(
    http_request: Request,
    verification_id: str,
    request_body: ReopenVerificationRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyVerificationService = Depends(get_safety_verification_service),
) -> StandardSuccessResponse[SafetyVerificationRecord]:
    req_id = _req_id(http_request)
    record = service.get_verification(verification_id)
    _check_tenant(current_user, record)
    actor_id, actor_role = _actor_info(current_user)

    reopened = service.reopen(
        verification_id=verification_id,
        request=request_body,
        actor_id=actor_id,
        actor_role=actor_role,
    )
    return StandardSuccessResponse(data=reopened, request_id=req_id)


@router.post(
    "/{verification_id}/reassess",
    response_model=StandardSuccessResponse[SafetyVerificationRecord],
    status_code=status.HTTP_200_OK,
    summary="Request Change Reassessment",
)
async def reassess_verification(
    http_request: Request,
    verification_id: str,
    request_body: ReassessmentVerificationRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyVerificationService = Depends(get_safety_verification_service),
) -> StandardSuccessResponse[SafetyVerificationRecord]:
    req_id = _req_id(http_request)
    record = service.get_verification(verification_id)
    _check_tenant(current_user, record)
    actor_id, actor_role = _actor_info(current_user)

    reassessed = service.reassess(
        verification_id=verification_id,
        request=request_body,
        actor_id=actor_id,
        actor_role=actor_role,
    )
    return StandardSuccessResponse(data=reassessed, request_id=req_id)


@router.get(
    "/{verification_id}/closure-eligibility",
    response_model=StandardSuccessResponse[ClosureEligibilityResponse],
    status_code=status.HTTP_200_OK,
    summary="Evaluate Closure Eligibility",
)
async def get_closure_eligibility(
    http_request: Request,
    verification_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyVerificationService = Depends(get_safety_verification_service),
) -> StandardSuccessResponse[ClosureEligibilityResponse]:
    req_id = _req_id(http_request)
    record = service.get_verification(verification_id)
    _check_tenant(current_user, record)
    eligibility = service.evaluate_closure_eligibility(verification_id)
    return StandardSuccessResponse(data=eligibility, request_id=req_id)


@router.get(
    "/{verification_id}/assurance",
    response_model=StandardSuccessResponse[VerificationAssuranceResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Linked Phase 52 Assurance Status",
)
async def get_verification_assurance(
    http_request: Request,
    verification_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyVerificationService = Depends(get_safety_verification_service),
) -> StandardSuccessResponse[VerificationAssuranceResponse]:
    req_id = _req_id(http_request)
    record = service.get_verification(verification_id)
    _check_tenant(current_user, record)
    resp = service.get_assurance(verification_id)
    return StandardSuccessResponse(data=resp, request_id=req_id)


@router.get(
    "/{verification_id}/effectiveness",
    response_model=StandardSuccessResponse[VerificationEffectivenessResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Linked Phase 55 Effectiveness Status",
)
async def get_verification_effectiveness(
    http_request: Request,
    verification_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyVerificationService = Depends(get_safety_verification_service),
) -> StandardSuccessResponse[VerificationEffectivenessResponse]:
    req_id = _req_id(http_request)
    record = service.get_verification(verification_id)
    _check_tenant(current_user, record)
    resp = service.get_effectiveness(verification_id)
    return StandardSuccessResponse(data=resp, request_id=req_id)
