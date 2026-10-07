"""Phase 59: Clinical Safety Post-Closure Surveillance, Reopen Triggers & Longitudinal Control Monitoring APIs.

TRD Section 38 Endpoints:
  POST /safety-monitoring
  GET  /safety-monitoring/active
  GET  /safety-monitoring/review-required
  GET  /safety-monitoring/reopen-required
  GET  /safety-monitoring/escalation-required
  POST /safety-monitoring/reanalysis
  GET  /safety-monitoring
  GET  /safety-monitoring/{monitoring_id}
  GET  /safety-monitoring/{monitoring_id}/status
  GET  /safety-monitoring/{monitoring_id}/signals
  GET  /safety-monitoring/{monitoring_id}/history
  GET  /safety-monitoring/{monitoring_id}/checkpoints
  GET  /safety-monitoring/{monitoring_id}/triggers
  POST /safety-monitoring/{monitoring_id}/start
  POST /safety-monitoring/{monitoring_id}/pause
  POST /safety-monitoring/{monitoring_id}/resume
  POST /safety-monitoring/{monitoring_id}/collect
  POST /safety-monitoring/{monitoring_id}/evaluate
  POST /safety-monitoring/{monitoring_id}/checkpoint
  POST /safety-monitoring/{monitoring_id}/review
  POST /safety-monitoring/{monitoring_id}/reopen-review
  POST /safety-monitoring/{monitoring_id}/reassess
  POST /safety-monitoring/{monitoring_id}/complete
"""

from typing import Annotated, Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query, Request, Response, status

from app.api.deps import get_current_user
from app.core.exceptions import AppException, ErrorCode
from app.core.logging import request_id_ctx_var
from app.schemas.response import StandardSuccessResponse
from app.schemas.safety_monitoring import (
    CompleteMonitoringRequest,
    CreateMonitoringRequest,
    CreateReopenReviewRequest,
    EvaluateSurveillanceRequest,
    IngestSignalRequest,
    MonitoringCheckpoint,
    MonitoringHistoryEntry,
    MonitoringLifecycleState,
    MonitoringReviewRecord,
    MonitoringStatusResponse,
    MonitoringTriggerRecord,
    PauseMonitoringRequest,
    ReanalysisSurveillanceRequest,
    RequestReassessmentRequest,
    ResumeMonitoringRequest,
    RunCheckpointRequest,
    SafetyMonitoringRecord,
    SubmitSurveillanceReviewRequest,
    SurveillanceEvaluationResponse,
    SurveillanceSignalRecord,
)
from app.schemas.user import AuthenticatedUserContext
from app.services.safety_monitoring_service import (
    SafetyMonitoringService,
    get_safety_monitoring_service,
)

router = APIRouter(
    prefix="/safety-monitoring",
    tags=["Clinical Safety Post-Closure Surveillance, Reopen Triggers & Longitudinal Control Monitoring"],
)


def _req_id(request: Request) -> str:
    return getattr(request.state, "request_id", None) or request_id_ctx_var.get() or "req-unknown"


def _check_tenant(current_user: AuthenticatedUserContext, record: SafetyMonitoringRecord) -> None:
    user_org = getattr(current_user, "organization_id", None)
    record_org = record.organization_id or getattr(record.scope, "organization_id", None)
    if user_org and record_org and record_org != user_org:
        raise AppException(
            code=ErrorCode.ACCESS_DENIED,
            message="Access denied to cross-tenant surveillance record",
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
    response_model=StandardSuccessResponse[SafetyMonitoringRecord],
    status_code=status.HTTP_201_CREATED,
    summary="Create Post-Closure Surveillance Context",
)
async def create_monitoring(
    http_request: Request,
    request_body: CreateMonitoringRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyMonitoringService = Depends(get_safety_monitoring_service),
) -> StandardSuccessResponse[SafetyMonitoringRecord]:
    req_id = _req_id(http_request)
    actor_id, actor_role = _actor_info(current_user)
    user_org = getattr(current_user, "organization_id", None)

    idem_key = http_request.headers.get("X-Idempotency-Key") or request_body.idempotency_key
    if idem_key and not request_body.idempotency_key:
        request_body.idempotency_key = idem_key

    record = service.create_monitoring(
        request=request_body,
        actor_id=actor_id,
        actor_role=actor_role,
        actor_organization_id=user_org,
    )
    return StandardSuccessResponse(data=record, request_id=req_id)


@router.get(
    "/active",
    response_model=StandardSuccessResponse[List[SafetyMonitoringRecord]],
    status_code=status.HTTP_200_OK,
    summary="List Active Surveillance Contexts",
)
async def list_active_monitoring(
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    organization_id: Optional[str] = Query(None),
    service: SafetyMonitoringService = Depends(get_safety_monitoring_service),
) -> StandardSuccessResponse[List[SafetyMonitoringRecord]]:
    req_id = _req_id(http_request)
    user_org = getattr(current_user, "organization_id", None)
    target_org = organization_id or user_org
    records = service.list_active(organization_id=target_org)
    return StandardSuccessResponse(data=records, request_id=req_id)


@router.get(
    "/review-required",
    response_model=StandardSuccessResponse[List[SafetyMonitoringRecord]],
    status_code=status.HTTP_200_OK,
    summary="List Surveillance Contexts Requiring Human Review",
)
async def list_review_required_monitoring(
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    organization_id: Optional[str] = Query(None),
    service: SafetyMonitoringService = Depends(get_safety_monitoring_service),
) -> StandardSuccessResponse[List[SafetyMonitoringRecord]]:
    req_id = _req_id(http_request)
    user_org = getattr(current_user, "organization_id", None)
    target_org = organization_id or user_org
    records = service.list_review_required(organization_id=target_org)
    return StandardSuccessResponse(data=records, request_id=req_id)


@router.get(
    "/reopen-required",
    response_model=StandardSuccessResponse[List[SafetyMonitoringRecord]],
    status_code=status.HTTP_200_OK,
    summary="List Surveillance Contexts with Reopen Triggers",
)
async def list_reopen_required_monitoring(
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    organization_id: Optional[str] = Query(None),
    service: SafetyMonitoringService = Depends(get_safety_monitoring_service),
) -> StandardSuccessResponse[List[SafetyMonitoringRecord]]:
    req_id = _req_id(http_request)
    user_org = getattr(current_user, "organization_id", None)
    target_org = organization_id or user_org
    records = service.list_reopen_required(organization_id=target_org)
    return StandardSuccessResponse(data=records, request_id=req_id)


@router.get(
    "/escalation-required",
    response_model=StandardSuccessResponse[List[SafetyMonitoringRecord]],
    status_code=status.HTTP_200_OK,
    summary="List Surveillance Contexts Requiring Escalation",
)
async def list_escalation_required_monitoring(
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    organization_id: Optional[str] = Query(None),
    service: SafetyMonitoringService = Depends(get_safety_monitoring_service),
) -> StandardSuccessResponse[List[SafetyMonitoringRecord]]:
    req_id = _req_id(http_request)
    user_org = getattr(current_user, "organization_id", None)
    target_org = organization_id or user_org
    records = service.list_escalation_required(organization_id=target_org)
    return StandardSuccessResponse(data=records, request_id=req_id)


@router.post(
    "/reanalysis",
    response_model=StandardSuccessResponse[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Batch Reanalysis of Surveillance Contexts",
)
async def batch_reanalysis(
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    request_body: Optional[ReanalysisSurveillanceRequest] = None,
    service: SafetyMonitoringService = Depends(get_safety_monitoring_service),
) -> StandardSuccessResponse[Dict[str, Any]]:
    req_id = _req_id(http_request)
    actor_id, actor_role = _actor_info(current_user)

    req = request_body or ReanalysisSurveillanceRequest(reason="Periodic surveillance reanalysis")
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
    response_model=StandardSuccessResponse[List[SafetyMonitoringRecord]],
    status_code=status.HTTP_200_OK,
    summary="List Controlled Safety Surveillance Contexts",
)
async def list_monitoring(
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    organization_id: Optional[str] = Query(None),
    facility_id: Optional[str] = Query(None),
    lifecycle_state: Optional[MonitoringLifecycleState] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    service: SafetyMonitoringService = Depends(get_safety_monitoring_service),
) -> StandardSuccessResponse[List[SafetyMonitoringRecord]]:
    req_id = _req_id(http_request)
    user_org = getattr(current_user, "organization_id", None)
    target_org = organization_id or user_org

    records = service.list_monitoring(
        organization_id=target_org,
        facility_id=facility_id,
        lifecycle_state=lifecycle_state,
        limit=limit,
        offset=offset,
    )
    return StandardSuccessResponse(data=records, request_id=req_id)


# ---------------------------------------------------------------------------
# Item Subpaths
# ---------------------------------------------------------------------------


@router.get(
    "/{monitoring_id}",
    response_model=StandardSuccessResponse[SafetyMonitoringRecord],
    status_code=status.HTTP_200_OK,
    summary="Get Safety Surveillance Context",
)
async def get_monitoring(
    http_request: Request,
    monitoring_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyMonitoringService = Depends(get_safety_monitoring_service),
) -> StandardSuccessResponse[SafetyMonitoringRecord]:
    req_id = _req_id(http_request)
    record = service.get_monitoring(monitoring_id)
    _check_tenant(current_user, record)
    return StandardSuccessResponse(data=record, request_id=req_id)


@router.get(
    "/{monitoring_id}/status",
    response_model=StandardSuccessResponse[MonitoringStatusResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Surveillance Status",
)
async def get_monitoring_status(
    http_request: Request,
    monitoring_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyMonitoringService = Depends(get_safety_monitoring_service),
) -> StandardSuccessResponse[MonitoringStatusResponse]:
    req_id = _req_id(http_request)
    record = service.get_monitoring(monitoring_id)
    _check_tenant(current_user, record)
    status_resp = service.get_status(monitoring_id)
    return StandardSuccessResponse(data=status_resp, request_id=req_id)


@router.get(
    "/{monitoring_id}/signals",
    response_model=StandardSuccessResponse[List[SurveillanceSignalRecord]],
    status_code=status.HTTP_200_OK,
    summary="Get Surveillance Signals",
)
async def get_monitoring_signals(
    http_request: Request,
    monitoring_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyMonitoringService = Depends(get_safety_monitoring_service),
) -> StandardSuccessResponse[List[SurveillanceSignalRecord]]:
    req_id = _req_id(http_request)
    record = service.get_monitoring(monitoring_id)
    _check_tenant(current_user, record)
    signals = service.get_signals(monitoring_id)
    return StandardSuccessResponse(data=signals, request_id=req_id)


@router.post(
    "/{monitoring_id}/signals",
    response_model=StandardSuccessResponse[SurveillanceSignalRecord],
    status_code=status.HTTP_201_CREATED,
    summary="Ingest Surveillance Signal",
)
async def ingest_signal(
    http_request: Request,
    monitoring_id: str,
    request_body: IngestSignalRequest,
    response: Response,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyMonitoringService = Depends(get_safety_monitoring_service),
) -> StandardSuccessResponse[SurveillanceSignalRecord]:
    req_id = _req_id(http_request)
    record = service.get_monitoring(monitoring_id)
    _check_tenant(current_user, record)
    actor_id, actor_role = _actor_info(current_user)

    is_new, signal = service.ingest_signal_with_status(
        monitoring_id=monitoring_id,
        request=request_body,
        actor_id=actor_id,
        actor_role=actor_role,
    )
    if not is_new or signal.is_duplicate:
        response.status_code = status.HTTP_200_OK
    return StandardSuccessResponse(data=signal, request_id=req_id)


@router.get(
    "/{monitoring_id}/history",
    response_model=StandardSuccessResponse[List[MonitoringHistoryEntry]],
    status_code=status.HTTP_200_OK,
    summary="Get Surveillance History",
)
async def get_monitoring_history(
    http_request: Request,
    monitoring_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyMonitoringService = Depends(get_safety_monitoring_service),
) -> StandardSuccessResponse[List[MonitoringHistoryEntry]]:
    req_id = _req_id(http_request)
    record = service.get_monitoring(monitoring_id)
    _check_tenant(current_user, record)
    history = service.get_history(monitoring_id)
    return StandardSuccessResponse(data=history, request_id=req_id)


@router.get(
    "/{monitoring_id}/checkpoints",
    response_model=StandardSuccessResponse[List[MonitoringCheckpoint]],
    status_code=status.HTTP_200_OK,
    summary="Get Surveillance Checkpoints",
)
async def get_monitoring_checkpoints(
    http_request: Request,
    monitoring_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyMonitoringService = Depends(get_safety_monitoring_service),
) -> StandardSuccessResponse[List[MonitoringCheckpoint]]:
    req_id = _req_id(http_request)
    record = service.get_monitoring(monitoring_id)
    _check_tenant(current_user, record)
    checkpoints = service.get_checkpoints(monitoring_id)
    return StandardSuccessResponse(data=checkpoints, request_id=req_id)


@router.get(
    "/{monitoring_id}/triggers",
    response_model=StandardSuccessResponse[List[MonitoringTriggerRecord]],
    status_code=status.HTTP_200_OK,
    summary="Get Reopen and Escalation Triggers",
)
async def get_monitoring_triggers(
    http_request: Request,
    monitoring_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyMonitoringService = Depends(get_safety_monitoring_service),
) -> StandardSuccessResponse[List[MonitoringTriggerRecord]]:
    req_id = _req_id(http_request)
    record = service.get_monitoring(monitoring_id)
    _check_tenant(current_user, record)
    triggers = service.get_triggers(monitoring_id)
    return StandardSuccessResponse(data=triggers, request_id=req_id)


@router.post(
    "/{monitoring_id}/start",
    response_model=StandardSuccessResponse[SafetyMonitoringRecord],
    status_code=status.HTTP_200_OK,
    summary="Start Surveillance Observing Sources",
)
async def start_monitoring(
    http_request: Request,
    monitoring_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyMonitoringService = Depends(get_safety_monitoring_service),
) -> StandardSuccessResponse[SafetyMonitoringRecord]:
    req_id = _req_id(http_request)
    record = service.get_monitoring(monitoring_id)
    _check_tenant(current_user, record)
    actor_id, actor_role = _actor_info(current_user)

    started = service.start(
        monitoring_id=monitoring_id,
        actor_id=actor_id,
        actor_role=actor_role,
    )
    return StandardSuccessResponse(data=started, request_id=req_id)


@router.post(
    "/{monitoring_id}/pause",
    response_model=StandardSuccessResponse[SafetyMonitoringRecord],
    status_code=status.HTTP_200_OK,
    summary="Pause Surveillance",
)
async def pause_monitoring(
    http_request: Request,
    monitoring_id: str,
    request_body: PauseMonitoringRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyMonitoringService = Depends(get_safety_monitoring_service),
) -> StandardSuccessResponse[SafetyMonitoringRecord]:
    req_id = _req_id(http_request)
    record = service.get_monitoring(monitoring_id)
    _check_tenant(current_user, record)
    actor_id, actor_role = _actor_info(current_user)

    paused = service.pause(
        monitoring_id=monitoring_id,
        request=request_body,
        actor_id=actor_id,
        actor_role=actor_role,
    )
    return StandardSuccessResponse(data=paused, request_id=req_id)


@router.post(
    "/{monitoring_id}/resume",
    response_model=StandardSuccessResponse[SafetyMonitoringRecord],
    status_code=status.HTTP_200_OK,
    summary="Resume Paused Surveillance",
)
async def resume_monitoring(
    http_request: Request,
    monitoring_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    request_body: Optional[ResumeMonitoringRequest] = None,
    service: SafetyMonitoringService = Depends(get_safety_monitoring_service),
) -> StandardSuccessResponse[SafetyMonitoringRecord]:
    req_id = _req_id(http_request)
    record = service.get_monitoring(monitoring_id)
    _check_tenant(current_user, record)
    actor_id, actor_role = _actor_info(current_user)

    req = request_body or ResumeMonitoringRequest(rationale="Surveillance resumed following pause")
    resumed = service.resume(
        monitoring_id=monitoring_id,
        request=req,
        actor_id=actor_id,
        actor_role=actor_role,
    )
    return StandardSuccessResponse(data=resumed, request_id=req_id)


@router.post(
    "/{monitoring_id}/collect",
    response_model=StandardSuccessResponse[List[SurveillanceSignalRecord]],
    status_code=status.HTTP_200_OK,
    summary="Collect Surveillance Signals and Evaluate Thresholds",
)
async def collect_signals(
    http_request: Request,
    monitoring_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyMonitoringService = Depends(get_safety_monitoring_service),
) -> StandardSuccessResponse[List[SurveillanceSignalRecord]]:
    req_id = _req_id(http_request)
    record = service.get_monitoring(monitoring_id)
    _check_tenant(current_user, record)
    actor_id, actor_role = _actor_info(current_user)

    signals = service.collect(
        monitoring_id=monitoring_id,
        actor_id=actor_id,
        actor_role=actor_role,
    )
    return StandardSuccessResponse(data=signals, request_id=req_id)


@router.post(
    "/{monitoring_id}/evaluate",
    response_model=StandardSuccessResponse[SurveillanceEvaluationResponse],
    status_code=status.HTTP_200_OK,
    summary="Evaluate Surveillance State Against Thresholds",
)
async def evaluate_surveillance(
    http_request: Request,
    monitoring_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    request_body: Optional[EvaluateSurveillanceRequest] = None,
    service: SafetyMonitoringService = Depends(get_safety_monitoring_service),
) -> StandardSuccessResponse[SurveillanceEvaluationResponse]:
    req_id = _req_id(http_request)
    record = service.get_monitoring(monitoring_id)
    _check_tenant(current_user, record)
    actor_id, actor_role = _actor_info(current_user)

    req = request_body or EvaluateSurveillanceRequest(force_reevaluation=True)
    resp = service.evaluate(
        monitoring_id=monitoring_id,
        request=req,
        actor_id=actor_id,
        actor_role=actor_role,
    )
    return StandardSuccessResponse(data=resp, request_id=req_id)


@router.post(
    "/{monitoring_id}/checkpoint",
    response_model=StandardSuccessResponse[MonitoringCheckpoint],
    status_code=status.HTTP_200_OK,
    summary="Run Surveillance Checkpoint",
)
async def run_checkpoint(
    http_request: Request,
    monitoring_id: str,
    request_body: RunCheckpointRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyMonitoringService = Depends(get_safety_monitoring_service),
) -> StandardSuccessResponse[MonitoringCheckpoint]:
    req_id = _req_id(http_request)
    record = service.get_monitoring(monitoring_id)
    _check_tenant(current_user, record)
    actor_id, actor_role = _actor_info(current_user)

    cp = service.run_checkpoint(
        monitoring_id=monitoring_id,
        request=request_body,
        actor_id=actor_id,
        actor_role=actor_role,
    )
    return StandardSuccessResponse(data=cp, request_id=req_id)


@router.post(
    "/{monitoring_id}/review",
    response_model=StandardSuccessResponse[MonitoringReviewRecord],
    status_code=status.HTTP_200_OK,
    summary="Submit Human Surveillance Review Decision",
)
async def submit_review(
    http_request: Request,
    monitoring_id: str,
    request_body: SubmitSurveillanceReviewRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyMonitoringService = Depends(get_safety_monitoring_service),
) -> StandardSuccessResponse[MonitoringReviewRecord]:
    req_id = _req_id(http_request)
    record = service.get_monitoring(monitoring_id)
    _check_tenant(current_user, record)
    actor_id, actor_role = _actor_info(current_user)

    rev = service.review(
        monitoring_id=monitoring_id,
        request=request_body,
        actor_id=actor_id,
        actor_role=actor_role,
    )
    return StandardSuccessResponse(data=rev, request_id=req_id)


@router.post(
    "/{monitoring_id}/reopen-review",
    response_model=StandardSuccessResponse[MonitoringTriggerRecord],
    status_code=status.HTTP_200_OK,
    summary="Create Governed Reopen Review Trigger for Phase 58",
)
async def create_reopen_review(
    http_request: Request,
    monitoring_id: str,
    request_body: CreateReopenReviewRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyMonitoringService = Depends(get_safety_monitoring_service),
) -> StandardSuccessResponse[MonitoringTriggerRecord]:
    req_id = _req_id(http_request)
    record = service.get_monitoring(monitoring_id)
    _check_tenant(current_user, record)
    actor_id, actor_role = _actor_info(current_user)

    trg = service.create_reopen_review(
        monitoring_id=monitoring_id,
        request=request_body,
        actor_id=actor_id,
        actor_role=actor_role,
    )
    return StandardSuccessResponse(data=trg, request_id=req_id)


@router.post(
    "/{monitoring_id}/reassess",
    response_model=StandardSuccessResponse[MonitoringTriggerRecord],
    status_code=status.HTTP_200_OK,
    summary="Request Reassessment Trigger for Phase 51 Governance",
)
async def request_reassessment(
    http_request: Request,
    monitoring_id: str,
    request_body: RequestReassessmentRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyMonitoringService = Depends(get_safety_monitoring_service),
) -> StandardSuccessResponse[MonitoringTriggerRecord]:
    req_id = _req_id(http_request)
    record = service.get_monitoring(monitoring_id)
    _check_tenant(current_user, record)
    actor_id, actor_role = _actor_info(current_user)

    trg = service.request_reassessment(
        monitoring_id=monitoring_id,
        request=request_body,
        actor_id=actor_id,
        actor_role=actor_role,
    )
    return StandardSuccessResponse(data=trg, request_id=req_id)


@router.post(
    "/{monitoring_id}/complete",
    response_model=StandardSuccessResponse[SafetyMonitoringRecord],
    status_code=status.HTTP_200_OK,
    summary="Complete Post-Closure Surveillance Context",
)
async def complete_monitoring(
    http_request: Request,
    monitoring_id: str,
    request_body: CompleteMonitoringRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: SafetyMonitoringService = Depends(get_safety_monitoring_service),
) -> StandardSuccessResponse[SafetyMonitoringRecord]:
    req_id = _req_id(http_request)
    record = service.get_monitoring(monitoring_id)
    _check_tenant(current_user, record)
    actor_id, actor_role = _actor_info(current_user)

    completed = service.complete(
        monitoring_id=monitoring_id,
        request=request_body,
        actor_id=actor_id,
        actor_role=actor_role,
    )
    return StandardSuccessResponse(data=completed, request_id=req_id)
