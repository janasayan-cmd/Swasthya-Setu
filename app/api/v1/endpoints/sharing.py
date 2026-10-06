"""Clinical Data Sharing API Endpoints (Phase 44).

Enforces:
- DATA SHARING != CLINICAL DECISION
- READ ACCESS != EXPORT ACCESS != SHARE ACCESS
- AI != SHARING AUTHORITY
- QUEUED AUTHORIZATION != CURRENT AUTHORIZATION
"""

from __future__ import annotations

from typing import Annotated, Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, Request, status

from app.api.deps import (
    get_audit_service,
    get_current_user,
    get_sharing_policy_service,
    get_sharing_service,
)
from app.core.logging import request_id_ctx_var
from app.schemas.response import StandardErrorResponse, StandardSuccessResponse
from app.schemas.sharing import (
    SharedDataSummaryResponse,
    SharingApproveAction,
    SharingCancelAction,
    SharingDenyAction,
    SharingEvaluationRequest,
    SharingEvaluationResponse,
    SharingExecuteAction,
    SharingRequestCreate,
    SharingRequestListResponse,
    SharingRequestResponse,
    SharingStatus,
)
from app.schemas.user import AuthenticatedUserContext
from app.services.audit_service import AuditService
from app.services.sharing_policy_service import SharingPolicyService
from app.services.sharing_service import SharingService

router = APIRouter(tags=["Clinical Data Sharing"])


def _req_id(request: Request) -> str:
    return getattr(request.state, "request_id", None) or request_id_ctx_var.get() or "unknown"


# ============================================================================
# SHARING REQUESTS ENDPOINTS
# ============================================================================

@router.post(
    "/sharing-requests",
    status_code=status.HTTP_201_CREATED,
    response_model=StandardSuccessResponse[SharingRequestResponse],
    summary="Create a clinical data sharing request",
    description="Initiates a controlled clinical data sharing request.",
    responses={
        401: {"model": StandardErrorResponse, "description": "Authentication required"},
        403: {"model": StandardErrorResponse, "description": "Unauthorized or AI attempted sharing"},
        422: {"model": StandardErrorResponse, "description": "Validation error or invalid scopes"},
    },
)
async def create_sharing_request(
    request: Request,
    body: SharingRequestCreate,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    sharing_service: Annotated[SharingService, Depends(get_sharing_service)],
) -> StandardSuccessResponse[SharingRequestResponse]:
    """Create a new clinical data sharing request."""
    result = await sharing_service.create_sharing_request(
        request=body,
        requester_id=current_user.user_id,
        requester_role=current_user.role.value,
    )
    return StandardSuccessResponse(
        data=result,
        request_id=_req_id(request),
        message="Sharing request created successfully.",
    )


@router.get(
    "/sharing-requests",
    response_model=StandardSuccessResponse[SharingRequestListResponse],
    summary="List sharing requests",
    description="List sharing requests accessible to the authenticated user.",
)
async def list_sharing_requests(
    request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    sharing_service: Annotated[SharingService, Depends(get_sharing_service)],
    patient_id: Optional[str] = Query(None, description="Filter by patient ID"),
    status_filter: Optional[SharingStatus] = Query(None, alias="status", description="Filter by sharing status"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Page size"),
) -> StandardSuccessResponse[SharingRequestListResponse]:
    """List clinical data sharing requests."""
    result = await sharing_service.list_sharing_requests(
        actor_id=current_user.user_id,
        actor_role=current_user.role.value,
        patient_id=patient_id,
        status=status_filter,
        page=page,
        size=size,
    )
    return StandardSuccessResponse(
        data=result,
        request_id=_req_id(request),
    )


@router.get(
    "/sharing-requests/{sharing_request_id}",
    response_model=StandardSuccessResponse[SharingRequestResponse],
    summary="Get sharing request by ID",
    description="Retrieve details of a specific sharing request.",
)
async def get_sharing_request(
    request: Request,
    sharing_request_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    sharing_service: Annotated[SharingService, Depends(get_sharing_service)],
) -> StandardSuccessResponse[SharingRequestResponse]:
    """Retrieve details of a sharing request."""
    result = await sharing_service.get_sharing_request(
        sharing_id=sharing_request_id,
        actor_id=current_user.user_id,
        actor_role=current_user.role.value,
    )
    return StandardSuccessResponse(
        data=result,
        request_id=_req_id(request),
    )


@router.post(
    "/sharing-requests/{sharing_request_id}/approve",
    response_model=StandardSuccessResponse[SharingRequestResponse],
    summary="Approve a sharing request",
    description="Patient approves a pending clinical data sharing request.",
)
async def approve_sharing_request(
    request: Request,
    sharing_request_id: str,
    body: SharingApproveAction,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    sharing_service: Annotated[SharingService, Depends(get_sharing_service)],
) -> StandardSuccessResponse[SharingRequestResponse]:
    """Approve a pending sharing request."""
    result = await sharing_service.approve_sharing_request(
        sharing_id=sharing_request_id,
        actor_id=current_user.user_id,
        actor_role=current_user.role.value,
        action=body,
    )
    return StandardSuccessResponse(
        data=result,
        request_id=_req_id(request),
        message="Sharing request approved.",
    )


@router.post(
    "/sharing-requests/{sharing_request_id}/deny",
    response_model=StandardSuccessResponse[SharingRequestResponse],
    summary="Deny a sharing request",
    description="Deny a pending clinical data sharing request.",
)
async def deny_sharing_request(
    request: Request,
    sharing_request_id: str,
    body: SharingDenyAction,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    sharing_service: Annotated[SharingService, Depends(get_sharing_service)],
) -> StandardSuccessResponse[SharingRequestResponse]:
    """Deny a sharing request."""
    result = await sharing_service.deny_sharing_request(
        sharing_id=sharing_request_id,
        actor_id=current_user.user_id,
        actor_role=current_user.role.value,
        action=body,
    )
    return StandardSuccessResponse(
        data=result,
        request_id=_req_id(request),
        message="Sharing request denied.",
    )


@router.post(
    "/sharing-requests/{sharing_request_id}/cancel",
    response_model=StandardSuccessResponse[SharingRequestResponse],
    summary="Cancel a sharing request",
    description="Cancel a sharing request before or during processing.",
)
async def cancel_sharing_request(
    request: Request,
    sharing_request_id: str,
    body: SharingCancelAction,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    sharing_service: Annotated[SharingService, Depends(get_sharing_service)],
) -> StandardSuccessResponse[SharingRequestResponse]:
    """Cancel a sharing request."""
    result = await sharing_service.cancel_sharing_request(
        sharing_id=sharing_request_id,
        actor_id=current_user.user_id,
        actor_role=current_user.role.value,
        action=body,
    )
    return StandardSuccessResponse(
        data=result,
        request_id=_req_id(request),
        message="Sharing request cancelled.",
    )


@router.post(
    "/sharing-requests/{sharing_request_id}/execute",
    response_model=StandardSuccessResponse[SharingRequestResponse],
    summary="Execute sharing dispatch",
    description="Execute the data exchange with mandatory JIT consent verification.",
)
async def execute_sharing(
    request: Request,
    sharing_request_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    sharing_service: Annotated[SharingService, Depends(get_sharing_service)],
    body: Optional[SharingExecuteAction] = None,
) -> StandardSuccessResponse[SharingRequestResponse]:
    """Execute sharing transmission to recipient or external destination."""
    result = await sharing_service.execute_sharing(
        sharing_id=sharing_request_id,
        actor_id=current_user.user_id,
        actor_role=current_user.role.value,
        action=body,
    )
    return StandardSuccessResponse(
        data=result,
        request_id=_req_id(request),
        message="Sharing executed successfully.",
    )


@router.get(
    "/sharing-requests/{sharing_request_id}/status",
    response_model=StandardSuccessResponse[Dict[str, Any]],
    summary="Get sharing request status",
    description="Retrieve delivery and execution status of a sharing request.",
)
async def get_sharing_status(
    request: Request,
    sharing_request_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    sharing_service: Annotated[SharingService, Depends(get_sharing_service)],
) -> StandardSuccessResponse[Dict[str, Any]]:
    """Poll status of a sharing request."""
    record = await sharing_service.get_sharing_request(
        sharing_id=sharing_request_id,
        actor_id=current_user.user_id,
        actor_role=current_user.role.value,
    )
    return StandardSuccessResponse(
        data={
            "id": record.id,
            "status": record.status.value,
            "delivery_status": record.delivery_status,
            "provider_reference": record.provider_reference,
            "delivered_at": record.delivered_at,
            "retry_count": record.retry_count,
        },
        request_id=_req_id(request),
    )


@router.get(
    "/sharing-requests/{sharing_request_id}/history",
    response_model=StandardSuccessResponse[List[Dict[str, Any]]],
    summary="Get sharing request lifecycle history",
    description="Retrieve state transition history for a sharing request.",
)
async def get_sharing_history(
    request: Request,
    sharing_request_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    sharing_service: Annotated[SharingService, Depends(get_sharing_service)],
) -> StandardSuccessResponse[List[Dict[str, Any]]]:
    """Retrieve history log for a sharing request."""
    record = await sharing_service.sharing_repo.get_by_id(sharing_request_id)
    if not record:
        from app.core.exceptions import SharingNotFoundException
        raise SharingNotFoundException("Sharing request not found.")
    return StandardSuccessResponse(
        data=record.history,
        request_id=_req_id(request),
    )


# ============================================================================
# PATIENT-CENTRIC SHARING ENDPOINTS
# ============================================================================

@router.get(
    "/patients/{patient_id}/sharing-requests",
    response_model=StandardSuccessResponse[SharingRequestListResponse],
    summary="Get patient sharing requests",
    description="List all sharing requests involving a specific patient.",
)
async def get_patient_sharing_requests(
    request: Request,
    patient_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    sharing_service: Annotated[SharingService, Depends(get_sharing_service)],
    status_filter: Optional[SharingStatus] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
) -> StandardSuccessResponse[SharingRequestListResponse]:
    """Retrieve sharing requests for a patient."""
    result = await sharing_service.list_sharing_requests(
        actor_id=current_user.user_id,
        actor_role=current_user.role.value,
        patient_id=patient_id,
        status=status_filter,
        page=page,
        size=size,
    )
    return StandardSuccessResponse(
        data=result,
        request_id=_req_id(request),
    )


@router.get(
    "/patients/{patient_id}/shared-data",
    response_model=StandardSuccessResponse[SharedDataSummaryResponse],
    summary="Get patient shared data summary",
    description="Retrieve an overview of clinical data currently shared with external parties.",
)
async def get_patient_shared_data(
    request: Request,
    patient_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    sharing_service: Annotated[SharingService, Depends(get_sharing_service)],
) -> StandardSuccessResponse[SharedDataSummaryResponse]:
    """Retrieve summary of data shared for a patient."""
    result = await sharing_service.get_patient_shared_data(
        patient_id=patient_id,
        actor_id=current_user.user_id,
        actor_role=current_user.role.value,
    )
    return StandardSuccessResponse(
        data=result,
        request_id=_req_id(request),
    )


# ============================================================================
# INTERNAL POLICY EVALUATION ENDPOINT
# ============================================================================

@router.post(
    "/internal/sharing/evaluate",
    response_model=StandardSuccessResponse[SharingEvaluationResponse],
    summary="Evaluate sharing policy eligibility",
    description="Internal policy check evaluating if a sharing operation is permissible.",
)
async def evaluate_sharing_policy(
    request: Request,
    body: SharingEvaluationRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    policy_service: Annotated[SharingPolicyService, Depends(get_sharing_policy_service)],
) -> StandardSuccessResponse[SharingEvaluationResponse]:
    """Evaluate sharing policy eligibility without executing transmission."""
    result = await policy_service.evaluate_sharing_policy(body)
    return StandardSuccessResponse(
        data=result,
        request_id=_req_id(request),
    )
