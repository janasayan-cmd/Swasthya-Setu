"""Access Evaluation & Break-Glass Emergency Endpoints.

Provides centralized clinical data access evaluation according to:
- Deny-by-default
- Identity & Role validation
- Relationship verification
- Consent state (Active, not Expired/Withdrawn)
- Resource scope matching
- Action scope matching (READ ≠ UPDATE ≠ SHARE ≠ EXPORT)
- Purpose limitation
- Emergency Break-Glass token issuance and validation

RESTRICTION:
Access evaluation is restricted to authenticated clinicians, internal services, and authorized administrators.
"""

from typing import Annotated
from fastapi import APIRouter, Depends, Request, status

from app.api.deps import (
    get_audit_service,
    get_consent_access_service,
    get_current_user,
)
from app.core.exceptions import ForbiddenException
from app.core.logging import request_id_ctx_var
from app.schemas.access_decision import (
    AccessEvaluationRequest,
    AccessEvaluationResponse,
)
from app.schemas.auth import UserRole
from app.schemas.consent import (
    BreakGlassRequest,
    BreakGlassResponse,
)
from app.schemas.response import StandardErrorResponse, StandardSuccessResponse
from app.schemas.user import AuthenticatedUserContext
from app.services.audit_service import AuditService
from app.services.consent_access_service import ConsentAccessService

router = APIRouter(prefix="/access", tags=["Access Evaluation & Access Control"])


def _req_id(request: Request) -> str:
    return getattr(request.state, "request_id", None) or request_id_ctx_var.get() or "unknown"


@router.post(
    "/evaluate",
    response_model=StandardSuccessResponse[AccessEvaluationResponse],
    summary="Evaluate clinical data access authorization",
    description=(
        "Centralized policy and consent evaluation engine. "
        "Enforces deny-by-default, resource category scoping, action differentiation, "
        "and time-bound consent validity. Accessible by authenticated users/internal services."
    ),
    responses={
        401: {"model": StandardErrorResponse, "description": "Authentication required"},
        403: {"model": StandardErrorResponse, "description": "Forbidden"},
    },
)
async def evaluate_access(
    request: Request,
    body: AccessEvaluationRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    access_service: Annotated[ConsentAccessService, Depends(get_consent_access_service)],
) -> StandardSuccessResponse[AccessEvaluationResponse]:
    """Evaluate whether an actor is authorized to perform an action on a clinical resource."""
    # Ensure actor_id matches caller unless admin or caller is authorized service
    actor_id = body.actor_id or current_user.user_id
    if current_user.role != UserRole.ADMIN and actor_id != current_user.user_id:
        # Non-admins cannot query access on behalf of arbitrary actors
        raise ForbiddenException("Cannot evaluate access on behalf of a different actor.")

    eval_request = AccessEvaluationRequest(
        actor_id=actor_id,
        patient_id=body.patient_id,
        resource_type=body.resource_type,
        resource_id=body.resource_id,
        action=body.action,
        purpose=body.purpose,
        actor_role=body.actor_role or current_user.role.value,
        organization_id=body.organization_id or current_user.organization_id,
        facility_id=body.facility_id,
        break_glass_token=body.break_glass_token,
    )

    decision = await access_service.evaluate_access(eval_request)
    return StandardSuccessResponse(data=decision, request_id=_req_id(request))


@router.post(
    "/break-glass",
    status_code=status.HTTP_201_CREATED,
    response_model=StandardSuccessResponse[BreakGlassResponse],
    summary="Issue emergency break-glass access token",
    description=(
        "Exceptional clinical emergency override. "
        "Requires explicit justification (>= 10 chars) by an authorized clinician. "
        "Generates enhanced audit records and a time-bound override token. "
        "AI or arbitrary user messages CANNOT declare break-glass emergencies."
    ),
    responses={
        401: {"model": StandardErrorResponse, "description": "Authentication required"},
        403: {"model": StandardErrorResponse, "description": "Only clinicians or emergency staff may request break-glass"},
        422: {"model": StandardErrorResponse, "description": "Invalid justification or emergency context"},
    },
)
async def request_break_glass(
    request: Request,
    body: BreakGlassRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    access_service: Annotated[ConsentAccessService, Depends(get_consent_access_service)],
    audit_service: Annotated[AuditService, Depends(get_audit_service)],
) -> StandardSuccessResponse[BreakGlassResponse]:
    """Request exceptional emergency break-glass access."""
    # Only clinicians, doctors, nurses, or admins can initiate emergency break-glass
    allowed_roles = {UserRole.DOCTOR, UserRole.CLINICIAN, UserRole.NURSE, UserRole.ADMIN}
    if current_user.role not in allowed_roles:
        raise ForbiddenException("Only clinical practitioners or emergency administrators may invoke break-glass access.")

    token_resp = await access_service.issue_break_glass(
        actor_id=current_user.user_id,
        actor_role=current_user.role.value,
        request=body,
    )
    await audit_service.log_event(
        action="BREAK_GLASS_GRANTED",
        actor_id=current_user.user_id,
        resource_id=body.patient_id,
        patient_id=body.patient_id,
        metadata={
            "justification": body.reason,
            "expires_at": str(token_resp.expires_at),
        },
    )
    return StandardSuccessResponse(data=token_resp, request_id=_req_id(request))
