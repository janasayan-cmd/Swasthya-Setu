"""Phase 54: Clinical Safety Oversight Decision Support, Escalation & Controlled Action Orchestration APIs.

Endpoints follow TRD Section 44:
  POST /safety-actions                           — Create safety action candidate
  GET  /safety-actions                           — List actions with filters
  GET  /safety-actions/pending                   — List pending actions
  GET  /safety-actions/escalated                 — List escalated actions
  GET  /safety-actions/overdue                   — List overdue actions
  GET  /safety-actions/reassessment-required     — List actions requiring reassessment
  GET  /safety-actions/{action_id}               — Get action details
  GET  /safety-actions/{action_id}/status        — Lightweight async polling status
  GET  /safety-actions/{action_id}/history       — Immutable history trail
  GET  /safety-actions/{action_id}/evidence      — Evidence and source finding references
  POST /safety-actions/{action_id}/approve       — Submit human approval
  POST /safety-actions/{action_id}/reject        — Reject proposed action
  POST /safety-actions/{action_id}/assign        — Assign operational owner
  POST /safety-actions/{action_id}/start         — Execution gate & subsystem trigger
  POST /safety-actions/{action_id}/complete      — Complete action
  POST /safety-actions/{action_id}/verify        — Independent verification
  POST /safety-actions/{action_id}/fail          — Record action failure
  POST /safety-actions/{action_id}/retry         — Bounded retry
  POST /safety-actions/{action_id}/rollback      — Rollback execution
  POST /safety-actions/{action_id}/escalate      — Policy escalation
  POST /safety-actions/{action_id}/close         — Close verified action
  POST /safety-actions/{action_id}/reopen        — Reopen action
"""

from typing import Annotated, Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query, Request, status

from app.api.deps import get_current_user
from app.core.exceptions import AppException, ErrorCode
from app.core.logging import request_id_ctx_var
from app.repositories.safety_action_repository import safety_action_repository
from app.schemas.response import StandardSuccessResponse
from app.schemas.safety_action import (
    ActionApprovalDecision,
    ActionHistoryEntry,
    ActionLifecycleState,
    ActionPriority,
    ActionType,
    SafetyActionApproveRequest,
    SafetyActionAssignRequest,
    SafetyActionCloseRequest,
    SafetyActionCompleteRequest,
    SafetyActionCreateRequest,
    SafetyActionEscalateRequest,
    SafetyActionExecuteRequest,
    SafetyActionRecord,
    SafetyActionReopenRequest,
    SafetyActionRetryRequest,
    SafetyActionRollbackRequest,
    SafetyActionVerifyRequest,
)
from app.schemas.user import AuthenticatedUserContext
from app.services.safety_action_service import safety_action_service

router = APIRouter(
    prefix="/safety-actions",
    tags=["Clinical Safety Oversight Decision Support & Controlled Action Orchestration"],
)


def _req_id(request: Request) -> str:
    return getattr(request.state, "request_id", None) or request_id_ctx_var.get() or "req-unknown"


@router.post(
    "",
    response_model=StandardSuccessResponse[SafetyActionRecord],
    status_code=status.HTTP_202_ACCEPTED,
    summary="Create Safety Action Candidate",
)
async def create_safety_action(
    http_request: Request,
    request_body: SafetyActionCreateRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
) -> StandardSuccessResponse[SafetyActionRecord]:
    req_id = _req_id(http_request)
    actor_id = str(getattr(current_user, "id", "unknown"))
    actor_role = str(getattr(current_user, "role", "SAFETY_OFFICER"))
    actor_org_id = getattr(current_user, "organization_id", None)
    actor_fac_id = getattr(current_user, "facility_id", None)

    action = safety_action_service.create_action(
        request=request_body,
        actor_id=actor_id,
        actor_role=actor_role,
        actor_organization_id=actor_org_id,
        actor_facility_id=actor_fac_id,
    )

    return StandardSuccessResponse(
        success=True,
        data=action,
        request_id=req_id,
    )


@router.get(
    "",
    response_model=StandardSuccessResponse[List[SafetyActionRecord]],
    summary="List Safety Actions",
)
async def list_safety_actions(
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    lifecycle_state: Optional[ActionLifecycleState] = Query(None),
    action_type: Optional[ActionType] = Query(None),
    priority: Optional[ActionPriority] = Query(None),
    owner_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> StandardSuccessResponse[List[SafetyActionRecord]]:
    req_id = _req_id(http_request)
    actor_org_id = getattr(current_user, "organization_id", None)
    actor_fac_id = getattr(current_user, "facility_id", None)

    actions = safety_action_repository.list_actions(
        organization_id=actor_org_id,
        facility_id=actor_fac_id,
        lifecycle_state=lifecycle_state,
        action_type=action_type,
        priority=priority,
        owner_id=owner_id,
        limit=limit,
        offset=offset,
    )

    return StandardSuccessResponse(
        success=True,
        data=actions,
        request_id=req_id,
    )


@router.get(
    "/pending",
    response_model=StandardSuccessResponse[List[SafetyActionRecord]],
    summary="List Pending Safety Actions",
)
async def list_pending_actions(
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> StandardSuccessResponse[List[SafetyActionRecord]]:
    req_id = _req_id(http_request)
    actor_org_id = getattr(current_user, "organization_id", None)
    actor_fac_id = getattr(current_user, "facility_id", None)

    actions = safety_action_repository.list_actions(
        organization_id=actor_org_id,
        facility_id=actor_fac_id,
        pending_only=True,
        limit=limit,
        offset=offset,
    )

    return StandardSuccessResponse(
        success=True,
        data=actions,
        request_id=req_id,
    )


@router.get(
    "/escalated",
    response_model=StandardSuccessResponse[List[SafetyActionRecord]],
    summary="List Escalated Safety Actions",
)
async def list_escalated_actions(
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> StandardSuccessResponse[List[SafetyActionRecord]]:
    req_id = _req_id(http_request)
    actor_org_id = getattr(current_user, "organization_id", None)
    actor_fac_id = getattr(current_user, "facility_id", None)

    actions = safety_action_repository.list_actions(
        organization_id=actor_org_id,
        facility_id=actor_fac_id,
        escalated_only=True,
        limit=limit,
        offset=offset,
    )

    return StandardSuccessResponse(
        success=True,
        data=actions,
        request_id=req_id,
    )


@router.get(
    "/overdue",
    response_model=StandardSuccessResponse[List[SafetyActionRecord]],
    summary="List Overdue Safety Actions",
)
async def list_overdue_actions(
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> StandardSuccessResponse[List[SafetyActionRecord]]:
    req_id = _req_id(http_request)
    actor_org_id = getattr(current_user, "organization_id", None)
    actor_fac_id = getattr(current_user, "facility_id", None)

    actions = safety_action_repository.list_actions(
        organization_id=actor_org_id,
        facility_id=actor_fac_id,
        overdue_only=True,
        limit=limit,
        offset=offset,
    )

    return StandardSuccessResponse(
        success=True,
        data=actions,
        request_id=req_id,
    )


@router.get(
    "/reassessment-required",
    response_model=StandardSuccessResponse[List[SafetyActionRecord]],
    summary="List Actions Requiring Reassessment",
)
async def list_reassessment_actions(
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> StandardSuccessResponse[List[SafetyActionRecord]]:
    req_id = _req_id(http_request)
    actor_org_id = getattr(current_user, "organization_id", None)
    actor_fac_id = getattr(current_user, "facility_id", None)

    actions = safety_action_repository.list_actions(
        organization_id=actor_org_id,
        facility_id=actor_fac_id,
        reassessment_only=True,
        limit=limit,
        offset=offset,
    )

    return StandardSuccessResponse(
        success=True,
        data=actions,
        request_id=req_id,
    )


@router.get(
    "/{action_id}",
    response_model=StandardSuccessResponse[SafetyActionRecord],
    summary="Get Safety Action Details",
)
async def get_safety_action(
    action_id: str,
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
) -> StandardSuccessResponse[SafetyActionRecord]:
    req_id = _req_id(http_request)
    actor_org_id = getattr(current_user, "organization_id", None)

    action = safety_action_service.get_action(action_id, actor_org_id)

    return StandardSuccessResponse(
        success=True,
        data=action,
        request_id=req_id,
    )


@router.get(
    "/{action_id}/status",
    response_model=StandardSuccessResponse[Dict[str, Any]],
    summary="Get Lightweight Action Status",
)
async def get_action_status(
    action_id: str,
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
) -> StandardSuccessResponse[Dict[str, Any]]:
    req_id = _req_id(http_request)
    actor_org_id = getattr(current_user, "organization_id", None)

    action = safety_action_service.get_action(action_id, actor_org_id)
    status_data = {
        "action_id": action.action_id,
        "version": action.version,
        "lifecycle_state": action.lifecycle_state.value,
        "actionability": action.actionability.value,
        "priority": action.priority.value,
        "is_urgent": action.is_urgent,
        "is_rolled_back": action.is_rolled_back,
    }

    return StandardSuccessResponse(
        success=True,
        data=status_data,
        request_id=req_id,
    )


@router.get(
    "/{action_id}/history",
    response_model=StandardSuccessResponse[List[ActionHistoryEntry]],
    summary="Get Action History Trail",
)
async def get_action_history(
    action_id: str,
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
) -> StandardSuccessResponse[List[ActionHistoryEntry]]:
    req_id = _req_id(http_request)
    actor_org_id = getattr(current_user, "organization_id", None)

    # Validate access
    safety_action_service.get_action(action_id, actor_org_id)
    history = safety_action_repository.get_history(action_id)

    return StandardSuccessResponse(
        success=True,
        data=history,
        request_id=req_id,
    )


@router.get(
    "/{action_id}/evidence",
    response_model=StandardSuccessResponse[Dict[str, Any]],
    summary="Get Action Evidence and Finding Reference",
)
async def get_action_evidence(
    action_id: str,
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
) -> StandardSuccessResponse[Dict[str, Any]]:
    req_id = _req_id(http_request)
    actor_org_id = getattr(current_user, "organization_id", None)

    action = safety_action_service.get_action(action_id, actor_org_id)
    evidence_data = {
        "finding": action.finding.model_dump(),
        "effectiveness": action.effectiveness.model_dump() if action.effectiveness else None,
        "external_task_id": action.external_task_id,
        "external_workflow_id": action.external_workflow_id,
        "external_change_id": action.external_change_id,
        "external_incident_id": action.external_incident_id,
    }

    return StandardSuccessResponse(
        success=True,
        data=evidence_data,
        request_id=req_id,
    )


@router.post(
    "/{action_id}/approve",
    response_model=StandardSuccessResponse[SafetyActionRecord],
    summary="Submit Human Governance Approval",
)
async def approve_safety_action(
    action_id: str,
    http_request: Request,
    request_body: SafetyActionApproveRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
) -> StandardSuccessResponse[SafetyActionRecord]:
    req_id = _req_id(http_request)
    actor_id = str(getattr(current_user, "id", "unknown"))
    actor_role = str(getattr(current_user, "role", "SAFETY_OFFICER"))
    actor_org_id = getattr(current_user, "organization_id", None)

    action = safety_action_service.approve_action(
        action_id=action_id,
        request=request_body,
        actor_id=actor_id,
        actor_role=actor_role,
        actor_organization_id=actor_org_id,
    )

    return StandardSuccessResponse(
        success=True,
        data=action,
        request_id=req_id,
    )


@router.post(
    "/{action_id}/reject",
    response_model=StandardSuccessResponse[SafetyActionRecord],
    summary="Reject Proposed Action",
)
async def reject_safety_action(
    action_id: str,
    http_request: Request,
    request_body: SafetyActionApproveRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
) -> StandardSuccessResponse[SafetyActionRecord]:
    req_id = _req_id(http_request)
    actor_id = str(getattr(current_user, "id", "unknown"))
    actor_role = str(getattr(current_user, "role", "SAFETY_OFFICER"))
    actor_org_id = getattr(current_user, "organization_id", None)

    # Force reject decision
    request_body.decision = ActionApprovalDecision.REJECT
    action = safety_action_service.approve_action(
        action_id=action_id,
        request=request_body,
        actor_id=actor_id,
        actor_role=actor_role,
        actor_organization_id=actor_org_id,
    )

    return StandardSuccessResponse(
        success=True,
        data=action,
        request_id=req_id,
    )


@router.post(
    "/{action_id}/assign",
    response_model=StandardSuccessResponse[SafetyActionRecord],
    summary="Assign Operational Owner",
)
async def assign_safety_action(
    action_id: str,
    http_request: Request,
    request_body: SafetyActionAssignRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
) -> StandardSuccessResponse[SafetyActionRecord]:
    req_id = _req_id(http_request)
    actor_id = str(getattr(current_user, "id", "unknown"))
    actor_role = str(getattr(current_user, "role", "SAFETY_OFFICER"))
    actor_org_id = getattr(current_user, "organization_id", None)

    action = safety_action_service.assign_action(
        action_id=action_id,
        request=request_body,
        actor_id=actor_id,
        actor_role=actor_role,
        actor_organization_id=actor_org_id,
    )

    return StandardSuccessResponse(
        success=True,
        data=action,
        request_id=req_id,
    )


@router.post(
    "/{action_id}/start",
    response_model=StandardSuccessResponse[SafetyActionRecord],
    summary="Execution Gate & Subsystem Trigger",
)
async def start_safety_action(
    action_id: str,
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    request_body: Optional[SafetyActionExecuteRequest] = None,
) -> StandardSuccessResponse[SafetyActionRecord]:
    req_id = _req_id(http_request)
    actor_id = str(getattr(current_user, "id", "unknown"))
    actor_role = str(getattr(current_user, "role", "SAFETY_OFFICER"))
    actor_org_id = getattr(current_user, "organization_id", None)

    action = safety_action_service.start_action(
        action_id=action_id,
        request=request_body,
        actor_id=actor_id,
        actor_role=actor_role,
        actor_organization_id=actor_org_id,
    )

    return StandardSuccessResponse(
        success=True,
        data=action,
        request_id=req_id,
    )


@router.post(
    "/{action_id}/complete",
    response_model=StandardSuccessResponse[SafetyActionRecord],
    summary="Complete Safety Action",
)
async def complete_safety_action(
    action_id: str,
    http_request: Request,
    request_body: SafetyActionCompleteRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
) -> StandardSuccessResponse[SafetyActionRecord]:
    req_id = _req_id(http_request)
    actor_id = str(getattr(current_user, "id", "unknown"))
    actor_role = str(getattr(current_user, "role", "SAFETY_OFFICER"))
    actor_org_id = getattr(current_user, "organization_id", None)

    action = safety_action_service.complete_action(
        action_id=action_id,
        request=request_body,
        actor_id=actor_id,
        actor_role=actor_role,
        actor_organization_id=actor_org_id,
    )

    return StandardSuccessResponse(
        success=True,
        data=action,
        request_id=req_id,
    )


@router.post(
    "/{action_id}/verify",
    response_model=StandardSuccessResponse[SafetyActionRecord],
    summary="Independent Verification of Action",
)
async def verify_safety_action(
    action_id: str,
    http_request: Request,
    request_body: SafetyActionVerifyRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
) -> StandardSuccessResponse[SafetyActionRecord]:
    req_id = _req_id(http_request)
    actor_id = str(getattr(current_user, "id", "unknown"))
    actor_role = str(getattr(current_user, "role", "SAFETY_OFFICER"))
    actor_org_id = getattr(current_user, "organization_id", None)

    action = safety_action_service.verify_action(
        action_id=action_id,
        request=request_body,
        actor_id=actor_id,
        actor_role=actor_role,
        actor_organization_id=actor_org_id,
    )

    return StandardSuccessResponse(
        success=True,
        data=action,
        request_id=req_id,
    )


@router.post(
    "/{action_id}/fail",
    response_model=StandardSuccessResponse[SafetyActionRecord],
    summary="Mark Action Failed",
)
async def fail_safety_action(
    action_id: str,
    http_request: Request,
    reason: str = Query("Action execution failed"),
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)] = None,
) -> StandardSuccessResponse[SafetyActionRecord]:
    req_id = _req_id(http_request)
    actor_id = str(getattr(current_user, "id", "unknown"))
    actor_role = str(getattr(current_user, "role", "SAFETY_OFFICER"))
    actor_org_id = getattr(current_user, "organization_id", None)

    action = safety_action_service.fail_action(
        action_id=action_id,
        reason=reason,
        actor_id=actor_id,
        actor_role=actor_role,
        actor_organization_id=actor_org_id,
    )

    return StandardSuccessResponse(
        success=True,
        data=action,
        request_id=req_id,
    )


@router.post(
    "/{action_id}/retry",
    response_model=StandardSuccessResponse[SafetyActionRecord],
    summary="Retry Failed Action",
)
async def retry_safety_action(
    action_id: str,
    http_request: Request,
    request_body: SafetyActionRetryRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
) -> StandardSuccessResponse[SafetyActionRecord]:
    req_id = _req_id(http_request)
    actor_id = str(getattr(current_user, "id", "unknown"))
    actor_role = str(getattr(current_user, "role", "SAFETY_OFFICER"))
    actor_org_id = getattr(current_user, "organization_id", None)

    action = safety_action_service.retry_action(
        action_id=action_id,
        request=request_body,
        actor_id=actor_id,
        actor_role=actor_role,
        actor_organization_id=actor_org_id,
    )

    return StandardSuccessResponse(
        success=True,
        data=action,
        request_id=req_id,
    )


@router.post(
    "/{action_id}/rollback",
    response_model=StandardSuccessResponse[SafetyActionRecord],
    summary="Rollback Executed Action",
)
async def rollback_safety_action(
    action_id: str,
    http_request: Request,
    request_body: SafetyActionRollbackRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
) -> StandardSuccessResponse[SafetyActionRecord]:
    req_id = _req_id(http_request)
    actor_id = str(getattr(current_user, "id", "unknown"))
    actor_role = str(getattr(current_user, "role", "SAFETY_OFFICER"))
    actor_org_id = getattr(current_user, "organization_id", None)

    action = safety_action_service.rollback_action(
        action_id=action_id,
        request=request_body,
        actor_id=actor_id,
        actor_role=actor_role,
        actor_organization_id=actor_org_id,
    )

    return StandardSuccessResponse(
        success=True,
        data=action,
        request_id=req_id,
    )


@router.post(
    "/{action_id}/escalate",
    response_model=StandardSuccessResponse[SafetyActionRecord],
    summary="Escalate Action",
)
async def escalate_safety_action(
    action_id: str,
    http_request: Request,
    request_body: SafetyActionEscalateRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
) -> StandardSuccessResponse[SafetyActionRecord]:
    req_id = _req_id(http_request)
    actor_id = str(getattr(current_user, "id", "unknown"))
    actor_role = str(getattr(current_user, "role", "SAFETY_OFFICER"))
    actor_org_id = getattr(current_user, "organization_id", None)

    action = safety_action_service.escalate_action(
        action_id=action_id,
        request=request_body,
        actor_id=actor_id,
        actor_role=actor_role,
        actor_organization_id=actor_org_id,
    )

    return StandardSuccessResponse(
        success=True,
        data=action,
        request_id=req_id,
    )


@router.post(
    "/{action_id}/close",
    response_model=StandardSuccessResponse[SafetyActionRecord],
    summary="Close Verified Action",
)
async def close_safety_action(
    action_id: str,
    http_request: Request,
    request_body: SafetyActionCloseRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
) -> StandardSuccessResponse[SafetyActionRecord]:
    req_id = _req_id(http_request)
    actor_id = str(getattr(current_user, "id", "unknown"))
    actor_role = str(getattr(current_user, "role", "SAFETY_OFFICER"))
    actor_org_id = getattr(current_user, "organization_id", None)

    action = safety_action_service.close_action(
        action_id=action_id,
        request=request_body,
        actor_id=actor_id,
        actor_role=actor_role,
        actor_organization_id=actor_org_id,
    )

    return StandardSuccessResponse(
        success=True,
        data=action,
        request_id=req_id,
    )


@router.post(
    "/{action_id}/reopen",
    response_model=StandardSuccessResponse[SafetyActionRecord],
    summary="Reopen Closed Action",
)
async def reopen_safety_action(
    action_id: str,
    http_request: Request,
    request_body: SafetyActionReopenRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
) -> StandardSuccessResponse[SafetyActionRecord]:
    req_id = _req_id(http_request)
    actor_id = str(getattr(current_user, "id", "unknown"))
    actor_role = str(getattr(current_user, "role", "SAFETY_OFFICER"))
    actor_org_id = getattr(current_user, "organization_id", None)

    action = safety_action_service.reopen_action(
        action_id=action_id,
        request=request_body,
        actor_id=actor_id,
        actor_role=actor_role,
        actor_organization_id=actor_org_id,
    )

    return StandardSuccessResponse(
        success=True,
        data=action,
        request_id=req_id,
    )
