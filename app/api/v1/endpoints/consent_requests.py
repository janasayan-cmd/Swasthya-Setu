"""Consent Request API Endpoints.

Allows clinicians, care teams, facilities, and organizations to request patient data access permissions.
Enforces:
- Consent requested ≠ Consent granted.
- AI cannot create, approve, or deny requests.
- Only the target patient can approve or deny requests.
"""

from typing import Annotated, Optional
from fastapi import APIRouter, Depends, Request, status

from app.api.deps import (
    get_audit_service,
    get_consent_request_service,
    get_current_user,
)
from app.core.logging import request_id_ctx_var
from app.schemas.consent import (
    ConsentDenyAction,
    ConsentGrantAction,
    ConsentRequestCreate,
    ConsentRequestListResponse,
    ConsentRequestResponse,
    ConsentRequestStatus,
)
from app.schemas.response import StandardErrorResponse, StandardSuccessResponse
from app.schemas.user import AuthenticatedUserContext
from app.services.audit_service import AuditService
from app.services.consent_request_service import ConsentRequestService

router = APIRouter(prefix="/consent-requests", tags=["Consent Requests"])


def _req_id(request: Request) -> str:
    return getattr(request.state, "request_id", None) or request_id_ctx_var.get() or "unknown"


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=StandardSuccessResponse[ConsentRequestResponse],
    summary="Create a consent request",
    description="Allows authorized clinicians/care-teams to request scoped data access from a patient.",
    responses={
        401: {"model": StandardErrorResponse, "description": "Authentication required"},
        403: {"model": StandardErrorResponse, "description": "AI or unauthorized roles cannot request consent"},
        422: {"model": StandardErrorResponse, "description": "Validation error in request scope"},
    },
)
async def create_consent_request(
    request: Request,
    body: ConsentRequestCreate,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    request_service: Annotated[ConsentRequestService, Depends(get_consent_request_service)],
    audit_service: Annotated[AuditService, Depends(get_audit_service)],
) -> StandardSuccessResponse[ConsentRequestResponse]:
    """Create a scoped consent request to a patient."""
    result = await request_service.create_request(
        requester_id=current_user.user_id,
        requester_role=current_user.role.value,
        payload=body,
    )
    await audit_service.log_event(
        action="CONSENT_REQUESTED",
        actor_id=current_user.user_id,
        resource_id=result.id,
        patient_id=result.patient_id,
        metadata={"grantee_id": result.grantee_id, "purpose": result.purpose},
    )
    return StandardSuccessResponse(data=result, request_id=_req_id(request))


@router.get(
    "",
    response_model=StandardSuccessResponse[ConsentRequestListResponse],
    summary="List consent requests for current user",
    description="Returns pending or all consent requests where user is either the patient or the requester.",
)
async def list_consent_requests(
    request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    request_service: Annotated[ConsentRequestService, Depends(get_consent_request_service)],
    status_filter: Optional[ConsentRequestStatus] = None,
) -> StandardSuccessResponse[ConsentRequestListResponse]:
    """List consent requests relevant to current user."""
    items = await request_service.list_requests(
        actor_id=current_user.user_id,
        actor_role=current_user.role.value,
        status_filter=status_filter,
    )
    return StandardSuccessResponse(
        data=ConsentRequestListResponse(items=items, total=len(items)),
        request_id=_req_id(request),
    )


@router.get(
    "/{request_id}",
    response_model=StandardSuccessResponse[ConsentRequestResponse],
    summary="Get consent request by ID",
    description="Retrieves a consent request. Accessible only by patient, requester, or authorized admin.",
)
async def get_consent_request(
    request: Request,
    request_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    request_service: Annotated[ConsentRequestService, Depends(get_consent_request_service)],
) -> StandardSuccessResponse[ConsentRequestResponse]:
    """Retrieve details of a consent request."""
    result = await request_service.get_request(
        actor_id=current_user.user_id,
        actor_role=current_user.role.value,
        request_id=request_id,
    )
    return StandardSuccessResponse(data=result, request_id=_req_id(request))


@router.post(
    "/{request_id}/approve",
    response_model=StandardSuccessResponse[ConsentRequestResponse],
    summary="Approve consent request",
    description="Patient approves the request, creating an explicit active consent record.",
)
async def approve_consent_request(
    request: Request,
    request_id: str,
    body: ConsentGrantAction,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    request_service: Annotated[ConsentRequestService, Depends(get_consent_request_service)],
    audit_service: Annotated[AuditService, Depends(get_audit_service)],
) -> StandardSuccessResponse[ConsentRequestResponse]:
    """Approve a consent request (patient-only)."""
    result = await request_service.approve_request(
        actor_id=current_user.user_id,
        actor_role=current_user.role.value,
        request_id=request_id,
        action=body,
    )
    await audit_service.log_event(
        action="CONSENT_GRANTED",
        actor_id=current_user.user_id,
        resource_id=result.id,
        patient_id=result.patient_id,
        metadata={"decision": "APPROVED", "evidence": body.evidence},
    )
    return StandardSuccessResponse(data=result, request_id=_req_id(request))


@router.post(
    "/{request_id}/deny",
    response_model=StandardSuccessResponse[ConsentRequestResponse],
    summary="Deny consent request",
    description="Patient denies the request. No consent record is activated.",
)
async def deny_consent_request(
    request: Request,
    request_id: str,
    body: ConsentDenyAction,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    request_service: Annotated[ConsentRequestService, Depends(get_consent_request_service)],
    audit_service: Annotated[AuditService, Depends(get_audit_service)],
) -> StandardSuccessResponse[ConsentRequestResponse]:
    """Deny a consent request (patient-only)."""
    result = await request_service.deny_request(
        actor_id=current_user.user_id,
        actor_role=current_user.role.value,
        request_id=request_id,
        action=body,
    )
    await audit_service.log_event(
        action="CONSENT_DENIED",
        actor_id=current_user.user_id,
        resource_id=result.id,
        patient_id=result.patient_id,
        metadata={"decision": "DENIED", "reason": body.reason},
    )
    return StandardSuccessResponse(data=result, request_id=_req_id(request))


@router.get(
    "/patient/{patient_id}",
    response_model=StandardSuccessResponse[ConsentRequestListResponse],
    summary="List patient consent requests",
    description="List requests targeted to a specific patient. Enforces patient isolation.",
)
async def list_patient_consent_requests(
    request: Request,
    patient_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    request_service: Annotated[ConsentRequestService, Depends(get_consent_request_service)],
    status_filter: Optional[ConsentRequestStatus] = None,
) -> StandardSuccessResponse[ConsentRequestListResponse]:
    """List requests for a specific patient."""
    items = await request_service.list_requests(
        actor_id=current_user.user_id,
        actor_role=current_user.role.value,
        patient_id=patient_id,
        status_filter=status_filter,
    )
    return StandardSuccessResponse(
        data=ConsentRequestListResponse(items=items, total=len(items)),
        request_id=_req_id(request),
    )
