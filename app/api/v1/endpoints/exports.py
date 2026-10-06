"""Controlled Clinical Export API Endpoints (Phase 44).

Enforces:
- EXPORT != LIVE RECORD (point-in-time snapshot only)
- READ ACCESS != EXPORT ACCESS
- AI cannot request exports
- Secret / credential / audit log / unrelated PHI masking
"""

from __future__ import annotations

from typing import Annotated, Any, Dict, Optional
from fastapi import APIRouter, Depends, Request, status

from app.api.deps import (
    get_current_user,
    get_sharing_service,
)
from app.core.logging import request_id_ctx_var
from app.schemas.export import (
    ExportRequestCreate,
    ExportResponse,
    ExportStatusResponse,
)
from app.schemas.response import StandardErrorResponse, StandardSuccessResponse
from app.schemas.user import AuthenticatedUserContext
from app.services.sharing_service import SharingService

router = APIRouter(tags=["Controlled Clinical Exports"])


def _req_id(request: Request) -> str:
    return getattr(request.state, "request_id", None) or request_id_ctx_var.get() or "unknown"


@router.post(
    "/patients/{patient_id}/exports",
    status_code=status.HTTP_201_CREATED,
    response_model=StandardSuccessResponse[ExportResponse],
    summary="Create a controlled patient data export",
    description="Initiates an authorized snapshot export of clinical data for a patient.",
    responses={
        401: {"model": StandardErrorResponse, "description": "Authentication required"},
        403: {"model": StandardErrorResponse, "description": "Export not authorized or AI attempted export"},
        422: {"model": StandardErrorResponse, "description": "Invalid format or scope"},
    },
)
async def create_export(
    request: Request,
    patient_id: str,
    body: ExportRequestCreate,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    sharing_service: Annotated[SharingService, Depends(get_sharing_service)],
) -> StandardSuccessResponse[ExportResponse]:
    """Generate a controlled snapshot export."""
    result = await sharing_service.create_export(
        patient_id=patient_id,
        requester_id=current_user.user_id,
        requester_role=current_user.role.value,
        request=body,
    )
    return StandardSuccessResponse(
        data=result,
        request_id=_req_id(request),
        message="Export snapshot generated successfully.",
    )


@router.get(
    "/exports/{export_id}",
    response_model=StandardSuccessResponse[ExportResponse],
    summary="Get export details",
    description="Retrieve metadata and payload reference for an authorized clinical export.",
)
async def get_export(
    request: Request,
    export_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    sharing_service: Annotated[SharingService, Depends(get_sharing_service)],
) -> StandardSuccessResponse[ExportResponse]:
    """Retrieve details of an export."""
    result = await sharing_service.get_export(
        export_id=export_id,
        actor_id=current_user.user_id,
        actor_role=current_user.role.value,
    )
    return StandardSuccessResponse(
        data=result,
        request_id=_req_id(request),
    )


@router.get(
    "/exports/{export_id}/status",
    response_model=StandardSuccessResponse[ExportStatusResponse],
    summary="Get export status",
    description="Poll generation status and download link for an export.",
)
async def get_export_status(
    request: Request,
    export_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    sharing_service: Annotated[SharingService, Depends(get_sharing_service)],
) -> StandardSuccessResponse[ExportStatusResponse]:
    """Poll status of an export."""
    record = await sharing_service.get_export(
        export_id=export_id,
        actor_id=current_user.user_id,
        actor_role=current_user.role.value,
    )
    return StandardSuccessResponse(
        data=ExportStatusResponse(
            export_id=record.id,
            status=record.status,
            progress_percentage=100 if record.status.value == "READY" else 0,
            expires_at=record.expires_at,
            download_url=record.download_url,
            error_message=record.error_message,
        ),
        request_id=_req_id(request),
    )


@router.post(
    "/exports/{export_id}/cancel",
    response_model=StandardSuccessResponse[ExportResponse],
    summary="Cancel an export",
    description="Cancel and invalidate a clinical data export.",
)
async def cancel_export(
    request: Request,
    export_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    sharing_service: Annotated[SharingService, Depends(get_sharing_service)],
) -> StandardSuccessResponse[ExportResponse]:
    """Cancel an export."""
    result = await sharing_service.cancel_export(
        export_id=export_id,
        actor_id=current_user.user_id,
        actor_role=current_user.role.value,
    )
    return StandardSuccessResponse(
        data=result,
        request_id=_req_id(request),
        message="Export cancelled successfully.",
    )
