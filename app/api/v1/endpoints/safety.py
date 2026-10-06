"""Clinical Decision Safety Controls, Guardrails & Fail-Safe Enforcement API Endpoints (Phase 48).

Provides:
- Safety gate evaluation for operations and decisions
- Inspection of historical safety checks
- Decision-scoped and resource-scoped safety status checks
- Safety policy registry introspection
"""

from typing import Annotated, Any, List, Optional
from fastapi import APIRouter, Depends, Query, Request, status

from app.api.deps import (
    get_current_user,
    get_safety_gate_service,
    get_safety_policy_service,
)
from app.core.exceptions import (
    ErrorCode,
    SafetyCheckFailedException,
    SafetyPolicyBlockedException,
)
from app.core.logging import request_id_ctx_var
from app.schemas.response import StandardSuccessResponse
from app.schemas.safety import (
    ResourceSafetyStatusResponse,
    SafetyEvaluationRequest,
    SafetyGateResult,
)
from app.schemas.safety_policy import SafetyPolicyRecord
from app.schemas.safety_result import SafetyCheckRecord, SafetyStatus
from app.schemas.user import AuthenticatedUserContext
from app.services.safety_gate_service import SafetyGateService, safety_gate_service
from app.services.safety_policy_service import SafetyPolicyService, safety_policy_service


router = APIRouter(tags=["Clinical Safety Controls & Fail-Safe Enforcement"])


def _req_id(request: Request) -> str:
    return getattr(request.state, "request_id", None) or request_id_ctx_var.get() or "req-unknown"


@router.post(
    "/safety/evaluate",
    response_model=StandardSuccessResponse[SafetyGateResult],
    summary="Evaluate Clinical Safety Gate",
    description="Run safety controls, policy checks, input validation, and guardrails for a proposed operation.",
)
async def evaluate_safety_gate(
    http_request: Request,
    request_body: SafetyEvaluationRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    gate_service: Annotated[SafetyGateService, Depends(get_safety_gate_service)] = None,
) -> StandardSuccessResponse[SafetyGateResult]:
    """Evaluate safety prerequisites for a clinical action or decision."""
    svc = gate_service or safety_gate_service
    req_id = _req_id(http_request)

    result = await svc.evaluate_safety(
        request=request_body,
        actor_id=current_user.user_id,
        actor_role=str(current_user.role),
        request_id=req_id,
    )
    return StandardSuccessResponse(
        success=True,
        data=result,
        request_id=req_id,
    )


@router.get(
    "/safety/checks/{check_id}",
    response_model=StandardSuccessResponse[SafetyCheckRecord],
    summary="Get Safety Check Details",
    description="Retrieve historical safety gate check execution record by ID.",
)
async def get_safety_check(
    http_request: Request,
    check_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    gate_service: Annotated[SafetyGateService, Depends(get_safety_gate_service)] = None,
) -> StandardSuccessResponse[SafetyCheckRecord]:
    """Retrieve historical safety check record."""
    svc = gate_service or safety_gate_service
    record = svc.get_check(check_id)
    if not record:
        raise SafetyCheckFailedException(f"Safety check '{check_id}' not found.")
    return StandardSuccessResponse(
        success=True,
        data=record,
        request_id=_req_id(http_request),
    )


@router.get(
    "/decisions/{decision_id}/safety",
    response_model=StandardSuccessResponse[List[SafetyCheckRecord]],
    summary="Get Decision Safety Checks",
    description="Retrieve all safety evaluations executed for a specific decision.",
)
async def get_decision_safety(
    http_request: Request,
    decision_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    gate_service: Annotated[SafetyGateService, Depends(get_safety_gate_service)] = None,
) -> StandardSuccessResponse[List[SafetyCheckRecord]]:
    """Retrieve safety checks associated with a decision."""
    svc = gate_service or safety_gate_service
    checks = svc.list_decision_safety_checks(decision_id)
    return StandardSuccessResponse(
        success=True,
        data=checks,
        request_id=_req_id(http_request),
    )


@router.get(
    "/resources/{resource_type}/{resource_id}/safety-status",
    response_model=StandardSuccessResponse[ResourceSafetyStatusResponse],
    summary="Get Resource Safety Status",
    description="Retrieve safety evaluation status and active guardrail state for a clinical resource.",
)
async def get_resource_safety_status(
    http_request: Request,
    resource_type: str,
    resource_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    gate_service: Annotated[SafetyGateService, Depends(get_safety_gate_service)] = None,
) -> StandardSuccessResponse[ResourceSafetyStatusResponse]:
    """Retrieve clinical safety status for a resource."""
    svc = gate_service or safety_gate_service
    checks = svc.list_resource_safety_checks(resource_type, resource_id)

    is_safe = True
    status_val = SafetyStatus.ALLOWED
    active_conflicts: list[str] = []
    latest_ts = None

    if checks:
        latest = checks[-1]
        is_safe = latest.allowed
        status_val = latest.status
        latest_ts = latest.timestamp
        if latest.status == SafetyStatus.CONFLICTED:
            active_conflicts.extend(latest.reason_codes)

    response = ResourceSafetyStatusResponse(
        resource_type=resource_type,
        resource_id=resource_id,
        is_safe_for_action=is_safe,
        safety_status=status_val,
        active_conflicts=active_conflicts,
        last_evaluated_at=latest_ts,
    )
    return StandardSuccessResponse(
        success=True,
        data=response,
        request_id=_req_id(http_request),
    )


@router.get(
    "/safety/policies",
    response_model=StandardSuccessResponse[List[SafetyPolicyRecord]],
    summary="List Safety Policies",
    description="Retrieve active registered clinical safety policies and version metadata.",
)
async def list_safety_policies(
    http_request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    policy_svc: Annotated[SafetyPolicyService, Depends(get_safety_policy_service)] = None,
) -> StandardSuccessResponse[List[SafetyPolicyRecord]]:
    """List registered safety policies."""
    svc = policy_svc or safety_policy_service
    policies = svc.list_policies()
    return StandardSuccessResponse(
        success=True,
        data=policies,
        request_id=_req_id(http_request),
    )

