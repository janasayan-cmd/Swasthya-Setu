"""Phase 57: Clinical Safety Change Validation, Controlled Rollout Governance & Post-Deployment Safety Verification APIs.

TRD Section 37 Endpoints:
  POST /safety-rollouts
  GET  /safety-rollouts/pending
  GET  /safety-rollouts/paused
  GET  /safety-rollouts/rollback-required
  GET  /safety-rollouts/validation-failed
  GET  /safety-rollouts/active
  POST /safety-rollouts/reanalysis
  GET  /safety-rollouts
  GET  /safety-rollouts/{rollout_id}
  GET  /safety-rollouts/{rollout_id}/status
  GET  /safety-rollouts/{rollout_id}/history
  GET  /safety-rollouts/{rollout_id}/readiness
  GET  /safety-rollouts/{rollout_id}/checkpoints
  GET  /safety-rollouts/{rollout_id}/evidence
  POST /safety-rollouts/{rollout_id}/validate-readiness
  POST /safety-rollouts/{rollout_id}/start
  POST /safety-rollouts/{rollout_id}/advance
  POST /safety-rollouts/{rollout_id}/validate-stage
  POST /safety-rollouts/{rollout_id}/pause
  POST /safety-rollouts/{rollout_id}/resume
  POST /safety-rollouts/{rollout_id}/rollback
  POST /safety-rollouts/{rollout_id}/validate-rollback
  POST /safety-rollouts/{rollout_id}/reassess
  POST /safety-rollouts/{rollout_id}/complete
  POST /safety-rollouts/{rollout_id}/reopen
"""

from typing import Annotated, Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query, Request, status

from app.api.deps import get_current_user
from app.core.exceptions import AppException, ErrorCode
from app.core.logging import request_id_ctx_var
from app.schemas.response import StandardSuccessResponse
from app.schemas.safety_rollout import (
    AdvanceStageRequest,
    CompleteRolloutRequest,
    CreateRolloutRequest,
    PauseRolloutRequest,
    ReanalysisRequest,
    ReassessmentRequest,
    ReopenRolloutRequest,
    ResumeRolloutRequest,
    RollbackRequest,
    RolloutCheckpointsResponse,
    RolloutEvidenceResponse,
    RolloutHistoryEntry,
    RolloutLifecycleState,
    RolloutReadinessResponse,
    RolloutStage,
    RolloutStatusResponse,
    SafetyRolloutRecord,
    StartRolloutRequest,
    ValidateReadinessRequest,
    ValidateRollbackRequest,
    ValidateStageRequest,
    ValidationCheckpoint,
)
from app.schemas.user import AuthenticatedUserContext
from app.services.safety_rollout_service import (
    SafetyRolloutService,
    get_safety_rollout_service,
)

router = APIRouter(
    prefix="/safety-rollouts",
    tags=["Clinical Safety Change Validation, Controlled Rollout Governance & Post-Deployment Verification"],
)


def _req_id(request: Request) -> str:
    return getattr(request.state, "request_id", None) or request_id_ctx_var.get() or "req-unknown"


def _check_tenant(current_user: AuthenticatedUserContext, record: SafetyRolloutRecord) -> None:
    user_org = getattr(current_user, "organization_id", None)
    user_role = getattr(current_user, "role", "")
    if user_org and record.scope.organization_id != user_org and str(user_role).upper() not in {"SUPER_ADMIN", "ADMIN"}:
        raise AppException(
            code=ErrorCode.ACCESS_DENIED,
            message="Access denied to cross-tenant rollout record",
            status_code=403,
        )


# ---------------------------------------------------------------------------
# Static Subpaths First (prevent parameter capture)
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=StandardSuccessResponse[SafetyRolloutRecord],
    status_code=status.HTTP_201_CREATED,
    summary="Create Controlled Safety Rollout",
)
async def create_rollout(
    http_request: Request,
    request_body: CreateRolloutRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyRolloutService = Depends(get_safety_rollout_service),
) -> StandardSuccessResponse[SafetyRolloutRecord]:
    req_id = _req_id(http_request)
    actor_id = str(getattr(current_user, "id", "unknown"))
    actor_role = str(getattr(current_user, "role", "SAFETY_OFFICER"))

    record = service.create_rollout(
        request=request_body,
        actor_id=actor_id,
        actor_role=actor_role,
    )
    return StandardSuccessResponse(data=record, request_id=req_id)


@router.get(
    "/pending",
    response_model=StandardSuccessResponse[List[SafetyRolloutRecord]],
    status_code=status.HTTP_200_OK,
    summary="List Pending Safety Rollouts",
)
async def list_pending_rollouts(
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    organization_id: Optional[str] = Query(None),
    service: SafetyRolloutService = Depends(get_safety_rollout_service),
) -> StandardSuccessResponse[List[SafetyRolloutRecord]]:
    req_id = _req_id(http_request)
    user_org = getattr(current_user, "organization_id", None)
    target_org = organization_id or user_org
    records = service.list_pending(organization_id=target_org)
    return StandardSuccessResponse(data=records, request_id=req_id)


@router.get(
    "/paused",
    response_model=StandardSuccessResponse[List[SafetyRolloutRecord]],
    status_code=status.HTTP_200_OK,
    summary="List Paused Safety Rollouts",
)
async def list_paused_rollouts(
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    organization_id: Optional[str] = Query(None),
    service: SafetyRolloutService = Depends(get_safety_rollout_service),
) -> StandardSuccessResponse[List[SafetyRolloutRecord]]:
    req_id = _req_id(http_request)
    user_org = getattr(current_user, "organization_id", None)
    target_org = organization_id or user_org
    records = service.list_paused(organization_id=target_org)
    return StandardSuccessResponse(data=records, request_id=req_id)


@router.get(
    "/rollback-required",
    response_model=StandardSuccessResponse[List[SafetyRolloutRecord]],
    status_code=status.HTTP_200_OK,
    summary="List Rollouts Requiring Rollback",
)
async def list_rollback_required_rollouts(
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    organization_id: Optional[str] = Query(None),
    service: SafetyRolloutService = Depends(get_safety_rollout_service),
) -> StandardSuccessResponse[List[SafetyRolloutRecord]]:
    req_id = _req_id(http_request)
    user_org = getattr(current_user, "organization_id", None)
    target_org = organization_id or user_org
    records = service.list_rollback_required(organization_id=target_org)
    return StandardSuccessResponse(data=records, request_id=req_id)


@router.get(
    "/validation-failed",
    response_model=StandardSuccessResponse[List[SafetyRolloutRecord]],
    status_code=status.HTTP_200_OK,
    summary="List Rollouts with Validation Failures",
)
async def list_validation_failed_rollouts(
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    organization_id: Optional[str] = Query(None),
    service: SafetyRolloutService = Depends(get_safety_rollout_service),
) -> StandardSuccessResponse[List[SafetyRolloutRecord]]:
    req_id = _req_id(http_request)
    user_org = getattr(current_user, "organization_id", None)
    target_org = organization_id or user_org
    records = service.list_validation_failed(organization_id=target_org)
    return StandardSuccessResponse(data=records, request_id=req_id)


@router.get(
    "/active",
    response_model=StandardSuccessResponse[List[SafetyRolloutRecord]],
    status_code=status.HTTP_200_OK,
    summary="List Active In-Flight Rollouts",
)
async def list_active_rollouts(
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    organization_id: Optional[str] = Query(None),
    service: SafetyRolloutService = Depends(get_safety_rollout_service),
) -> StandardSuccessResponse[List[SafetyRolloutRecord]]:
    req_id = _req_id(http_request)
    user_org = getattr(current_user, "organization_id", None)
    target_org = organization_id or user_org
    records = service.list_active(organization_id=target_org)
    return StandardSuccessResponse(data=records, request_id=req_id)


@router.post(
    "/reanalysis",
    response_model=StandardSuccessResponse[List[RolloutStatusResponse]],
    status_code=status.HTTP_200_OK,
    summary="Batch Reanalysis of Rollouts",
)
async def batch_reanalysis(
    http_request: Request,
    request_body: ReanalysisRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyRolloutService = Depends(get_safety_rollout_service),
) -> StandardSuccessResponse[List[RolloutStatusResponse]]:
    req_id = _req_id(http_request)
    actor_id = str(getattr(current_user, "id", "unknown"))
    actor_role = str(getattr(current_user, "role", "SAFETY_OFFICER"))

    results = service.reanalysis(
        request=request_body,
        actor_id=actor_id,
        actor_role=actor_role,
    )
    return StandardSuccessResponse(data=results, request_id=req_id)


@router.get(
    "",
    response_model=StandardSuccessResponse[List[SafetyRolloutRecord]],
    status_code=status.HTTP_200_OK,
    summary="List Controlled Safety Rollouts",
)
async def list_rollouts(
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    organization_id: Optional[str] = Query(None),
    facility_id: Optional[str] = Query(None),
    stage: Optional[RolloutStage] = Query(None),
    lifecycle_state: Optional[RolloutLifecycleState] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    service: SafetyRolloutService = Depends(get_safety_rollout_service),
) -> StandardSuccessResponse[List[SafetyRolloutRecord]]:
    req_id = _req_id(http_request)
    user_org = getattr(current_user, "organization_id", None)
    target_org = organization_id or user_org

    records = service.list_rollouts(
        organization_id=target_org,
        facility_id=facility_id,
        stage=stage,
        lifecycle_state=lifecycle_state,
        limit=limit,
        offset=offset,
    )
    return StandardSuccessResponse(data=records, request_id=req_id)


# ---------------------------------------------------------------------------
# Item Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/{rollout_id}",
    response_model=StandardSuccessResponse[SafetyRolloutRecord],
    status_code=status.HTTP_200_OK,
    summary="Get Controlled Safety Rollout Record",
)
async def get_rollout(
    http_request: Request,
    rollout_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyRolloutService = Depends(get_safety_rollout_service),
) -> StandardSuccessResponse[SafetyRolloutRecord]:
    req_id = _req_id(http_request)
    record = service.get_rollout(rollout_id)
    _check_tenant(current_user, record)
    return StandardSuccessResponse(data=record, request_id=req_id)


@router.get(
    "/{rollout_id}/status",
    response_model=StandardSuccessResponse[RolloutStatusResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Rollout Status",
)
async def get_rollout_status(
    http_request: Request,
    rollout_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyRolloutService = Depends(get_safety_rollout_service),
) -> StandardSuccessResponse[RolloutStatusResponse]:
    req_id = _req_id(http_request)
    record = service.get_rollout(rollout_id)
    _check_tenant(current_user, record)
    status_resp = service.get_status(rollout_id)
    return StandardSuccessResponse(data=status_resp, request_id=req_id)


@router.get(
    "/{rollout_id}/history",
    response_model=StandardSuccessResponse[List[RolloutHistoryEntry]],
    status_code=status.HTTP_200_OK,
    summary="Get Rollout History",
)
async def get_rollout_history(
    http_request: Request,
    rollout_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyRolloutService = Depends(get_safety_rollout_service),
) -> StandardSuccessResponse[List[RolloutHistoryEntry]]:
    req_id = _req_id(http_request)
    record = service.get_rollout(rollout_id)
    _check_tenant(current_user, record)
    history = service.get_history(rollout_id)
    return StandardSuccessResponse(data=history, request_id=req_id)


@router.get(
    "/{rollout_id}/readiness",
    response_model=StandardSuccessResponse[RolloutReadinessResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Rollout Readiness Audit",
)
async def get_rollout_readiness(
    http_request: Request,
    rollout_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyRolloutService = Depends(get_safety_rollout_service),
) -> StandardSuccessResponse[RolloutReadinessResponse]:
    req_id = _req_id(http_request)
    record = service.get_rollout(rollout_id)
    _check_tenant(current_user, record)
    readiness = service.get_readiness(rollout_id)
    return StandardSuccessResponse(data=readiness, request_id=req_id)


@router.get(
    "/{rollout_id}/checkpoints",
    response_model=StandardSuccessResponse[RolloutCheckpointsResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Rollout Checkpoints",
)
async def get_rollout_checkpoints(
    http_request: Request,
    rollout_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyRolloutService = Depends(get_safety_rollout_service),
) -> StandardSuccessResponse[RolloutCheckpointsResponse]:
    req_id = _req_id(http_request)
    record = service.get_rollout(rollout_id)
    _check_tenant(current_user, record)
    checkpoints = service.get_checkpoints(rollout_id)
    return StandardSuccessResponse(data=checkpoints, request_id=req_id)


@router.get(
    "/{rollout_id}/evidence",
    response_model=StandardSuccessResponse[RolloutEvidenceResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Rollout Evidence and Verified Controls",
)
async def get_rollout_evidence(
    http_request: Request,
    rollout_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyRolloutService = Depends(get_safety_rollout_service),
) -> StandardSuccessResponse[RolloutEvidenceResponse]:
    req_id = _req_id(http_request)
    record = service.get_rollout(rollout_id)
    _check_tenant(current_user, record)
    evidence = service.get_evidence(rollout_id)
    return StandardSuccessResponse(data=evidence, request_id=req_id)


@router.post(
    "/{rollout_id}/validate-readiness",
    response_model=StandardSuccessResponse[RolloutReadinessResponse],
    status_code=status.HTTP_200_OK,
    summary="Validate Readiness Gates",
)
async def validate_readiness(
    http_request: Request,
    rollout_id: str,
    request_body: ValidateReadinessRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyRolloutService = Depends(get_safety_rollout_service),
) -> StandardSuccessResponse[RolloutReadinessResponse]:
    req_id = _req_id(http_request)
    record = service.get_rollout(rollout_id)
    _check_tenant(current_user, record)
    actor_id = str(getattr(current_user, "id", "unknown"))
    actor_role = str(getattr(current_user, "role", "SAFETY_OFFICER"))

    resp = service.validate_readiness(
        rollout_id=rollout_id,
        request=request_body,
        actor_id=actor_id,
        actor_role=actor_role,
    )
    return StandardSuccessResponse(data=resp, request_id=req_id)


@router.post(
    "/{rollout_id}/start",
    response_model=StandardSuccessResponse[SafetyRolloutRecord],
    status_code=status.HTTP_200_OK,
    summary="Start Controlled Rollout (Enter Canary Stage)",
)
async def start_rollout(
    http_request: Request,
    rollout_id: str,
    request_body: StartRolloutRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyRolloutService = Depends(get_safety_rollout_service),
) -> StandardSuccessResponse[SafetyRolloutRecord]:
    req_id = _req_id(http_request)
    record = service.get_rollout(rollout_id)
    _check_tenant(current_user, record)
    actor_id = str(getattr(current_user, "id", "unknown"))
    actor_role = str(getattr(current_user, "role", "SAFETY_OFFICER"))

    started = service.start_rollout(
        rollout_id=rollout_id,
        request=request_body,
        actor_id=actor_id,
        actor_role=actor_role,
    )
    return StandardSuccessResponse(data=started, request_id=req_id)


@router.post(
    "/{rollout_id}/advance",
    response_model=StandardSuccessResponse[SafetyRolloutRecord],
    status_code=status.HTTP_200_OK,
    summary="Advance Rollout to Next Controlled Stage",
)
async def advance_stage(
    http_request: Request,
    rollout_id: str,
    request_body: AdvanceStageRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyRolloutService = Depends(get_safety_rollout_service),
) -> StandardSuccessResponse[SafetyRolloutRecord]:
    req_id = _req_id(http_request)
    record = service.get_rollout(rollout_id)
    _check_tenant(current_user, record)
    actor_id = str(getattr(current_user, "id", "unknown"))
    actor_role = str(getattr(current_user, "role", "SAFETY_OFFICER"))

    advanced = service.advance_stage(
        rollout_id=rollout_id,
        request=request_body,
        actor_id=actor_id,
        actor_role=actor_role,
    )
    return StandardSuccessResponse(data=advanced, request_id=req_id)


@router.post(
    "/{rollout_id}/validate-stage",
    response_model=StandardSuccessResponse[ValidationCheckpoint],
    status_code=status.HTTP_200_OK,
    summary="Submit Validation Evidence for Active Stage Checkpoint",
)
async def validate_stage(
    http_request: Request,
    rollout_id: str,
    request_body: ValidateStageRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyRolloutService = Depends(get_safety_rollout_service),
) -> StandardSuccessResponse[ValidationCheckpoint]:
    req_id = _req_id(http_request)
    record = service.get_rollout(rollout_id)
    _check_tenant(current_user, record)
    actor_id = str(getattr(current_user, "id", "unknown"))
    actor_role = str(getattr(current_user, "role", "SAFETY_OFFICER"))

    checkpoint = service.validate_stage(
        rollout_id=rollout_id,
        request=request_body,
        actor_id=actor_id,
        actor_role=actor_role,
    )
    return StandardSuccessResponse(data=checkpoint, request_id=req_id)


@router.post(
    "/{rollout_id}/pause",
    response_model=StandardSuccessResponse[SafetyRolloutRecord],
    status_code=status.HTTP_200_OK,
    summary="Pause Active Rollout",
)
async def pause_rollout(
    http_request: Request,
    rollout_id: str,
    request_body: PauseRolloutRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyRolloutService = Depends(get_safety_rollout_service),
) -> StandardSuccessResponse[SafetyRolloutRecord]:
    req_id = _req_id(http_request)
    record = service.get_rollout(rollout_id)
    _check_tenant(current_user, record)
    actor_id = str(getattr(current_user, "id", "unknown"))
    actor_role = str(getattr(current_user, "role", "SAFETY_OFFICER"))

    paused = service.pause(
        rollout_id=rollout_id,
        request=request_body,
        actor_id=actor_id,
        actor_role=actor_role,
    )
    return StandardSuccessResponse(data=paused, request_id=req_id)


@router.post(
    "/{rollout_id}/resume",
    response_model=StandardSuccessResponse[SafetyRolloutRecord],
    status_code=status.HTTP_200_OK,
    summary="Resume Paused Rollout",
)
async def resume_rollout(
    http_request: Request,
    rollout_id: str,
    request_body: ResumeRolloutRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyRolloutService = Depends(get_safety_rollout_service),
) -> StandardSuccessResponse[SafetyRolloutRecord]:
    req_id = _req_id(http_request)
    record = service.get_rollout(rollout_id)
    _check_tenant(current_user, record)
    actor_id = str(getattr(current_user, "id", "unknown"))
    actor_role = str(getattr(current_user, "role", "SAFETY_OFFICER"))

    resumed = service.resume(
        rollout_id=rollout_id,
        request=request_body,
        actor_id=actor_id,
        actor_role=actor_role,
    )
    return StandardSuccessResponse(data=resumed, request_id=req_id)


@router.post(
    "/{rollout_id}/rollback",
    response_model=StandardSuccessResponse[SafetyRolloutRecord],
    status_code=status.HTTP_200_OK,
    summary="Initiate Governed Rollback",
)
async def request_rollback(
    http_request: Request,
    rollout_id: str,
    request_body: RollbackRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyRolloutService = Depends(get_safety_rollout_service),
) -> StandardSuccessResponse[SafetyRolloutRecord]:
    req_id = _req_id(http_request)
    record = service.get_rollout(rollout_id)
    _check_tenant(current_user, record)
    actor_id = str(getattr(current_user, "id", "unknown"))
    actor_role = str(getattr(current_user, "role", "SAFETY_OFFICER"))

    rolled_back = service.rollback(
        rollout_id=rollout_id,
        request=request_body,
        actor_id=actor_id,
        actor_role=actor_role,
    )
    return StandardSuccessResponse(data=rolled_back, request_id=req_id)


@router.post(
    "/{rollout_id}/validate-rollback",
    response_model=StandardSuccessResponse[SafetyRolloutRecord],
    status_code=status.HTTP_200_OK,
    summary="Validate Rollback Completion and Safety Control Integrity",
)
async def validate_rollback(
    http_request: Request,
    rollout_id: str,
    request_body: ValidateRollbackRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyRolloutService = Depends(get_safety_rollout_service),
) -> StandardSuccessResponse[SafetyRolloutRecord]:
    req_id = _req_id(http_request)
    record = service.get_rollout(rollout_id)
    _check_tenant(current_user, record)
    actor_id = str(getattr(current_user, "id", "unknown"))
    actor_role = str(getattr(current_user, "role", "SAFETY_OFFICER"))

    validated = service.validate_rollback(
        rollout_id=rollout_id,
        request=request_body,
        actor_id=actor_id,
        actor_role=actor_role,
    )
    return StandardSuccessResponse(data=validated, request_id=req_id)


@router.post(
    "/{rollout_id}/reassess",
    response_model=StandardSuccessResponse[SafetyRolloutRecord],
    status_code=status.HTTP_200_OK,
    summary="Request Rollout Reassessment",
)
async def request_reassessment(
    http_request: Request,
    rollout_id: str,
    request_body: ReassessmentRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyRolloutService = Depends(get_safety_rollout_service),
) -> StandardSuccessResponse[SafetyRolloutRecord]:
    req_id = _req_id(http_request)
    record = service.get_rollout(rollout_id)
    _check_tenant(current_user, record)
    actor_id = str(getattr(current_user, "id", "unknown"))
    actor_role = str(getattr(current_user, "role", "SAFETY_OFFICER"))

    reassessed = service.reassess(
        rollout_id=rollout_id,
        request=request_body,
        actor_id=actor_id,
        actor_role=actor_role,
    )
    return StandardSuccessResponse(data=reassessed, request_id=req_id)


@router.post(
    "/{rollout_id}/complete",
    response_model=StandardSuccessResponse[SafetyRolloutRecord],
    status_code=status.HTTP_200_OK,
    summary="Mark Rollout Completed Following Observation",
)
async def complete_rollout(
    http_request: Request,
    rollout_id: str,
    request_body: CompleteRolloutRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyRolloutService = Depends(get_safety_rollout_service),
) -> StandardSuccessResponse[SafetyRolloutRecord]:
    req_id = _req_id(http_request)
    record = service.get_rollout(rollout_id)
    _check_tenant(current_user, record)
    actor_id = str(getattr(current_user, "id", "unknown"))
    actor_role = str(getattr(current_user, "role", "SAFETY_OFFICER"))

    completed = service.complete(
        rollout_id=rollout_id,
        request=request_body,
        actor_id=actor_id,
        actor_role=actor_role,
    )
    return StandardSuccessResponse(data=completed, request_id=req_id)


@router.post(
    "/{rollout_id}/reopen",
    response_model=StandardSuccessResponse[SafetyRolloutRecord],
    status_code=status.HTTP_200_OK,
    summary="Reopen Rollout for Investigation or Adaptation",
)
async def reopen_rollout(
    http_request: Request,
    rollout_id: str,
    request_body: ReopenRolloutRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyRolloutService = Depends(get_safety_rollout_service),
) -> StandardSuccessResponse[SafetyRolloutRecord]:
    req_id = _req_id(http_request)
    record = service.get_rollout(rollout_id)
    _check_tenant(current_user, record)
    actor_id = str(getattr(current_user, "id", "unknown"))
    actor_role = str(getattr(current_user, "role", "SAFETY_OFFICER"))

    reopened = service.reopen(
        rollout_id=rollout_id,
        request=request_body,
        actor_id=actor_id,
        actor_role=actor_role,
    )
    return StandardSuccessResponse(data=reopened, request_id=req_id)
