"""Consent management API endpoints.

All endpoints are protected and require authentication.
Authorization within each endpoint is enforced by ConsentService business rules:
  - Only the patient subject can create their own consent.
  - Only the patient subject can revoke their own consent.
  - Only the patient subject, grantee, or ADMIN can read a consent.

HTTP semantics:
  201 Created      — consent created
  200 OK           — read/revoke success
  401 Unauthorized — missing or invalid authentication
  403 Forbidden    — authenticated but not authorized for the operation
  404 Not Found    — consent not found (also used to prevent existence leakage)
  422              — validation error (invalid purpose, scope, expiry, etc.)
"""

from typing import Annotated
from fastapi import APIRouter, Depends, Request, status

from app.api.deps import (
    get_audit_service,
    get_consent_service,
    get_current_user,
)
from app.core.logging import request_id_ctx_var
from app.schemas.authorization import (
    ConsentCreateRequest,
    ConsentListResponse,
    ConsentResponse,
    ConsentRevokeRequest,
    ConsentStatus,
)
from app.schemas.consent import (
    ConsentDenyAction,
    ConsentGrantAction,
    ConsentHistoryResponse,
    ConsentRenewAction,
    ConsentWithdrawAction,
)
from app.schemas.response import StandardErrorResponse, StandardSuccessResponse
from app.schemas.user import AuthenticatedUserContext
from app.services.audit_service import AuditService
from app.services.consent_service import ConsentService

router = APIRouter(prefix="/consents", tags=["Consent"])


def _req_id(request: Request) -> str:
    return getattr(request.state, "request_id", None) or request_id_ctx_var.get() or "unknown"


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=StandardSuccessResponse[ConsentResponse],
    summary="Create consent grant",
    description=(
        "Creates a new consent grant from the authenticated patient to a specified recipient "
        "for a defined purpose and resource scope. Only PATIENT accounts may create consent. "
        "Purpose and scope must be from the supported sets. "
        "Consent cannot be granted to oneself."
    ),
    responses={
        401: {"model": StandardErrorResponse, "description": "Authentication required"},
        403: {"model": StandardErrorResponse, "description": "Only patients may create consent on their own behalf"},
        422: {"model": StandardErrorResponse, "description": "Invalid purpose, scope, or expiry"},
    },
)
async def create_consent(
    request: Request,
    body: ConsentCreateRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    consent_service: Annotated[ConsentService, Depends(get_consent_service)],
    audit_service: Annotated[AuditService, Depends(get_audit_service)],
) -> StandardSuccessResponse[ConsentResponse]:
    """Create a new consent grant for the authenticated patient."""
    consent = await consent_service.create_consent(
        requester_id=current_user.user_id,
        requester_role=current_user.role.value,
        request=body,
    )
    await audit_service.record_consent_created(
        actor_id=current_user.user_id,
        consent_id=consent.id,
        patient_id=consent.patient_id,
        grantee_id=consent.grantee_id,
        purpose=consent.purpose,
        scope=consent.scope,
    )
    return StandardSuccessResponse(data=consent, request_id=_req_id(request))


@router.get(
    "",
    response_model=StandardSuccessResponse[ConsentListResponse],
    summary="List my consents",
    description=(
        "Returns all consent grants where the authenticated user is the patient subject. "
        "Optionally filter by status."
    ),
    responses={
        401: {"model": StandardErrorResponse, "description": "Authentication required"},
    },
)
async def list_my_consents(
    request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    consent_service: Annotated[ConsentService, Depends(get_consent_service)],
    status_filter: ConsentStatus | None = None,
) -> StandardSuccessResponse[ConsentListResponse]:
    """List all consents for the authenticated patient."""
    consents = await consent_service.list_my_consents(
        requester_id=current_user.user_id,
        status_filter=status_filter,
    )
    return StandardSuccessResponse(
        data=ConsentListResponse(items=consents, total=len(consents)),
        request_id=_req_id(request),
    )


@router.get(
    "/{consent_id}",
    response_model=StandardSuccessResponse[ConsentResponse],
    summary="Get consent by ID",
    description=(
        "Retrieves a specific consent by its ID. "
        "Accessible by the patient subject, the grantee, or an ADMIN. "
        "Returns 404 to avoid leaking consent existence to unauthorized callers."
    ),
    responses={
        401: {"model": StandardErrorResponse, "description": "Authentication required"},
        404: {"model": StandardErrorResponse, "description": "Consent not found or access not permitted"},
    },
)
async def get_consent(
    request: Request,
    consent_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    consent_service: Annotated[ConsentService, Depends(get_consent_service)],
) -> StandardSuccessResponse[ConsentResponse]:
    """Retrieve a specific consent record."""
    consent = await consent_service.get_consent(
        requester_id=current_user.user_id,
        requester_role=current_user.role.value,
        consent_id=consent_id,
    )
    return StandardSuccessResponse(data=consent, request_id=_req_id(request))


@router.post(
    "/{consent_id}/revoke",
    response_model=StandardSuccessResponse[ConsentResponse],
    summary="Revoke consent",
    description=(
        "Revokes an existing consent grant. Only the patient subject may revoke their own consent. "
        "Revocation is effective immediately for all future authorization checks. "
        "Historical audit records are not deleted."
    ),
    responses={
        401: {"model": StandardErrorResponse, "description": "Authentication required"},
        403: {"model": StandardErrorResponse, "description": "Only the patient subject may revoke this consent"},
        404: {"model": StandardErrorResponse, "description": "Consent not found"},
        422: {"model": StandardErrorResponse, "description": "Consent is already revoked"},
    },
)
async def revoke_consent(
    request: Request,
    consent_id: str,
    body: ConsentRevokeRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    consent_service: Annotated[ConsentService, Depends(get_consent_service)],
    audit_service: Annotated[AuditService, Depends(get_audit_service)],
) -> StandardSuccessResponse[ConsentResponse]:
    """Revoke a specific consent grant."""
    consent = await consent_service.revoke_consent(
        requester_id=current_user.user_id,
        requester_role=current_user.role.value,
        consent_id=consent_id,
        reason=body.reason,
    )
    await audit_service.record_consent_revoked(
        actor_id=current_user.user_id,
        consent_id=consent_id,
        reason=body.reason,
    )
    return StandardSuccessResponse(data=consent, request_id=_req_id(request))


@router.post(
    "/{consent_id}/grant",
    response_model=StandardSuccessResponse[ConsentResponse],
    summary="Explicitly grant consent",
    description="Explicitly activates a draft or requested consent. Only the patient subject can grant consent.",
)
async def grant_consent(
    request: Request,
    consent_id: str,
    body: ConsentGrantAction,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    consent_service: Annotated[ConsentService, Depends(get_consent_service)],
    audit_service: Annotated[AuditService, Depends(get_audit_service)],
) -> StandardSuccessResponse[ConsentResponse]:
    """Explicitly grant consent."""
    consent = await consent_service.grant_consent(
        actor_id=current_user.user_id,
        actor_role=current_user.role.value,
        consent_id=consent_id,
        action=body,
    )
    await audit_service.log_event(
        action="CONSENT_GRANTED",
        actor_id=current_user.user_id,
        resource_id=consent.id,
        patient_id=consent.patient_id,
        metadata={"grantee_id": consent.grantee_id, "evidence": body.evidence},
    )
    return StandardSuccessResponse(data=consent, request_id=_req_id(request))


@router.post(
    "/{consent_id}/deny",
    response_model=StandardSuccessResponse[ConsentResponse],
    summary="Deny consent",
    description="Explicitly marks consent as DENIED. Only the patient subject can deny consent.",
)
async def deny_consent(
    request: Request,
    consent_id: str,
    body: ConsentDenyAction,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    consent_service: Annotated[ConsentService, Depends(get_consent_service)],
    audit_service: Annotated[AuditService, Depends(get_audit_service)],
) -> StandardSuccessResponse[ConsentResponse]:
    """Explicitly deny consent."""
    consent = await consent_service.deny_consent(
        actor_id=current_user.user_id,
        actor_role=current_user.role.value,
        consent_id=consent_id,
        action=body,
    )
    await audit_service.log_event(
        action="CONSENT_DENIED",
        actor_id=current_user.user_id,
        resource_id=consent.id,
        patient_id=consent.patient_id,
        metadata={"reason": body.reason},
    )
    return StandardSuccessResponse(data=consent, request_id=_req_id(request))


@router.post(
    "/{consent_id}/withdraw",
    response_model=StandardSuccessResponse[ConsentResponse],
    summary="Withdraw consent",
    description=(
        "Explicitly withdraws an active consent grant. Immediately halts all future access. "
        "Historical audit records and underlying medical records are retained per Phase 24 policy."
    ),
)
async def withdraw_consent(
    request: Request,
    consent_id: str,
    body: ConsentWithdrawAction,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    consent_service: Annotated[ConsentService, Depends(get_consent_service)],
    audit_service: Annotated[AuditService, Depends(get_audit_service)],
) -> StandardSuccessResponse[ConsentResponse]:
    """Withdraw an active consent grant."""
    consent = await consent_service.withdraw_consent(
        actor_id=current_user.user_id,
        actor_role=current_user.role.value,
        consent_id=consent_id,
        action=body,
    )
    await audit_service.log_event(
        action="CONSENT_WITHDRAWN",
        actor_id=current_user.user_id,
        resource_id=consent.id,
        patient_id=consent.patient_id,
        metadata={"reason": body.reason},
    )
    return StandardSuccessResponse(data=consent, request_id=_req_id(request))


@router.post(
    "/{consent_id}/renew",
    response_model=StandardSuccessResponse[ConsentResponse],
    summary="Renew expired consent",
    description="Explicitly renews an expired consent grant. Creates a new version with updated validity period.",
)
async def renew_consent(
    request: Request,
    consent_id: str,
    body: ConsentRenewAction,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    consent_service: Annotated[ConsentService, Depends(get_consent_service)],
    audit_service: Annotated[AuditService, Depends(get_audit_service)],
) -> StandardSuccessResponse[ConsentResponse]:
    """Renew an expired consent grant."""
    consent = await consent_service.renew_consent(
        actor_id=current_user.user_id,
        actor_role=current_user.role.value,
        consent_id=consent_id,
        action=body,
    )
    await audit_service.log_event(
        action="CONSENT_RENEWED",
        actor_id=current_user.user_id,
        resource_id=consent.id,
        patient_id=consent.patient_id,
        metadata={"version": consent.version, "expires_at": str(consent.expires_at)},
    )
    return StandardSuccessResponse(data=consent, request_id=_req_id(request))


@router.get(
    "/{consent_id}/history",
    response_model=StandardSuccessResponse[ConsentHistoryResponse],
    summary="Get consent provenance and history",
    description="Retrieves the complete audit history, versioning, and provenance records for a consent grant.",
)
async def get_consent_history(
    request: Request,
    consent_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    consent_service: Annotated[ConsentService, Depends(get_consent_service)],
) -> StandardSuccessResponse[ConsentHistoryResponse]:
    """Retrieve history and audit provenance for a specific consent record."""
    history = await consent_service.get_consent_history(
        actor_id=current_user.user_id,
        actor_role=current_user.role.value,
        consent_id=consent_id,
    )
    return StandardSuccessResponse(data=history, request_id=_req_id(request))


@router.get(
    "/patient/{patient_id}",
    response_model=StandardSuccessResponse[ConsentListResponse],
    summary="List patient consents",
    description="Returns all consents for a patient. Patient can list own consents; clinicians/admins subject to authorization.",
)
async def list_patient_consents(
    request: Request,
    patient_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    consent_service: Annotated[ConsentService, Depends(get_consent_service)],
    status_filter: ConsentStatus | None = None,
) -> StandardSuccessResponse[ConsentListResponse]:
    """List all consents for a given patient."""
    items = await consent_service.list_patient_consents(
        actor_id=current_user.user_id,
        actor_role=current_user.role.value,
        patient_id=patient_id,
        status_filter=status_filter,
    )
    return StandardSuccessResponse(
        data=ConsentListResponse(items=items, total=len(items)),
        request_id=_req_id(request),
    )
