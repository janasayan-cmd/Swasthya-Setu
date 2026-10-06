"""Clinical Record Versioning & History API Endpoints (Phase 46).

Provides:
- Current record state retrieval (GET /{resource_type}/{resource_id})
- Authorized historical version list (GET /{resource_type}/{resource_id}/history and /versions)
- Specific historical revision detail (GET /{resource_type}/{resource_id}/versions/{version_number})
- Version difference comparison (GET /{resource_type}/{resource_id}/diff)
- Concurrency-controlled updates (PATCH /{resource_type}/{resource_id})
- Clinical state corrections preserving history (POST /{resource_type}/{resource_id}/correct)
- Clinical state supersession (POST /{resource_type}/{resource_id}/supersede)
- Controlled historical state restoration (POST /{resource_type}/{resource_id}/restore)
"""

from typing import Annotated, Optional
from fastapi import APIRouter, Depends, Query, Request, status

from app.api.deps import (
    get_current_user,
    get_history_service,
    get_versioning_service,
)
from app.core.exceptions import ResourceVersionNotFoundException
from app.core.logging import request_id_ctx_var
from app.schemas.history import (
    HistoryQueryResponse,
    VersionDiffResponse,
)
from app.schemas.response import (
    StandardErrorResponse,
    StandardSuccessResponse,
)
from app.schemas.user import AuthenticatedUserContext
from app.schemas.versioning import (
    ClinicalVersionRecord,
    VersionCorrectionRequest,
    VersionRestoreRequest,
    VersionSupersedeRequest,
    VersionUpdateRequest,
)
from app.services.history_service import HistoryService
from app.services.versioning_service import VersioningService

router = APIRouter(prefix="/records", tags=["Clinical Record Versioning & History"])


def _req_id(request: Request) -> str:
    return getattr(request.state, "request_id", None) or request_id_ctx_var.get() or "req-unknown"


@router.get(
    "/{resource_type}/{resource_id}",
    response_model=StandardSuccessResponse[ClinicalVersionRecord],
    summary="Get current clinical record state",
    description="Retrieve the current active version of a clinical resource.",
    responses={
        404: {"model": StandardErrorResponse, "description": "Resource not found"},
    },
)
async def get_current_record(
    request: Request,
    resource_type: str,
    resource_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    versioning_service: Annotated[VersioningService, Depends(get_versioning_service)],
) -> StandardSuccessResponse[ClinicalVersionRecord]:
    """Retrieve current active clinical version."""
    record = versioning_service.get_current_version(resource_type=resource_type, resource_id=resource_id)
    if not record:
        raise ResourceVersionNotFoundException(f"Clinical record {resource_type}:{resource_id} not found.")

    return StandardSuccessResponse(
        success=True,
        data=record,
        request_id=_req_id(request),
    )


@router.get(
    "/{resource_type}/{resource_id}/history",
    response_model=StandardSuccessResponse[HistoryQueryResponse],
    summary="Get clinical record version history",
    description="Retrieve authorized chronological version history with pagination.",
    responses={
        403: {"model": StandardErrorResponse, "description": "Historical access denied"},
        404: {"model": StandardErrorResponse, "description": "Resource not found"},
    },
)
async def get_record_history(
    request: Request,
    resource_type: str,
    resource_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    history_service: Annotated[HistoryService, Depends(get_history_service)],
    limit: int = Query(default=50, ge=1, le=100),
    cursor: Optional[str] = Query(default=None),
    reverse: bool = Query(default=True, description="True for newest version first"),
) -> StandardSuccessResponse[HistoryQueryResponse]:
    """Retrieve paginated version history for an authorized caller."""
    actor_role_str = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    has_history_scope = actor_role_str.upper() in {"DOCTOR", "ADMIN", "SYSTEM_ADMIN"}

    history = await history_service.get_history(
        resource_type=resource_type,
        resource_id=resource_id,
        actor_id=current_user.user_id,
        actor_role=actor_role_str,
        limit=limit,
        cursor=cursor,
        reverse=reverse,
        history_scope_granted=has_history_scope,
    )
    return StandardSuccessResponse(
        success=True,
        data=history,
        request_id=_req_id(request),
    )


@router.get(
    "/{resource_type}/{resource_id}/versions",
    response_model=StandardSuccessResponse[HistoryQueryResponse],
    summary="List resource versions (alias)",
    description="Alias route for resource version history retrieval.",
)
async def list_record_versions(
    request: Request,
    resource_type: str,
    resource_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    history_service: Annotated[HistoryService, Depends(get_history_service)],
    limit: int = Query(default=50, ge=1, le=100),
    cursor: Optional[str] = Query(default=None),
    reverse: bool = Query(default=True),
) -> StandardSuccessResponse[HistoryQueryResponse]:
    """Alias for version history retrieval."""
    return await get_record_history(
        request=request,
        resource_type=resource_type,
        resource_id=resource_id,
        current_user=current_user,
        history_service=history_service,
        limit=limit,
        cursor=cursor,
        reverse=reverse,
    )


@router.get(
    "/{resource_type}/{resource_id}/versions/{version_number}",
    response_model=StandardSuccessResponse[ClinicalVersionRecord],
    summary="Get specific historical version detail",
    description="Retrieve a specific historical version snapshot.",
    responses={
        403: {"model": StandardErrorResponse, "description": "Historical access denied"},
        404: {"model": StandardErrorResponse, "description": "Version not found"},
    },
)
async def get_version_detail(
    request: Request,
    resource_type: str,
    resource_id: str,
    version_number: int,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    history_service: Annotated[HistoryService, Depends(get_history_service)],
) -> StandardSuccessResponse[ClinicalVersionRecord]:
    """Retrieve a specific version snapshot."""
    actor_role_str = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    has_history_scope = actor_role_str.upper() in {"DOCTOR", "ADMIN", "SYSTEM_ADMIN"}

    record = await history_service.get_version_detail(
        resource_type=resource_type,
        resource_id=resource_id,
        version_number=version_number,
        actor_id=current_user.user_id,
        actor_role=actor_role_str,
        history_scope_granted=has_history_scope,
    )
    return StandardSuccessResponse(
        success=True,
        data=record,
        request_id=_req_id(request),
    )


@router.get(
    "/{resource_type}/{resource_id}/diff",
    response_model=StandardSuccessResponse[VersionDiffResponse],
    summary="Compare two versions of a clinical resource",
    description="Generate field-level difference between two versions.",
    responses={
        404: {"model": StandardErrorResponse, "description": "Version not found"},
    },
)
async def diff_record_versions(
    request: Request,
    resource_type: str,
    resource_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    history_service: Annotated[HistoryService, Depends(get_history_service)],
    base_version: int = Query(ge=1, description="Base version number"),
    compared_version: int = Query(ge=1, description="Target version number to compare"),
) -> StandardSuccessResponse[VersionDiffResponse]:
    """Compare two versions."""
    diff = history_service.diff_versions(
        resource_type=resource_type,
        resource_id=resource_id,
        base_version_number=base_version,
        compared_version_number=compared_version,
    )
    return StandardSuccessResponse(
        success=True,
        data=diff,
        request_id=_req_id(request),
    )


@router.patch(
    "/{resource_type}/{resource_id}",
    response_model=StandardSuccessResponse[ClinicalVersionRecord],
    summary="Update clinical record with optimistic concurrency",
    description="Apply field-level changes guarded by expected_version concurrency check.",
    responses={
        400: {"model": StandardErrorResponse, "description": "Invalid modification"},
        403: {"model": StandardErrorResponse, "description": "Forbidden or AI prohibited"},
        404: {"model": StandardErrorResponse, "description": "Resource not found"},
        409: {"model": StandardErrorResponse, "description": "Version conflict / Stale write"},
        422: {"model": StandardErrorResponse, "description": "Validation error or missing reason"},
    },
)
async def update_record(
    request: Request,
    resource_type: str,
    resource_id: str,
    body: VersionUpdateRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    versioning_service: Annotated[VersioningService, Depends(get_versioning_service)],
) -> StandardSuccessResponse[ClinicalVersionRecord]:
    """Concurrency-controlled update."""
    updated = await versioning_service.update_version(
        resource_type=resource_type,
        resource_id=resource_id,
        request=body,
        actor_id=current_user.user_id,
        actor_role=current_user.role,
        actor_type="CLINICIAN",
    )
    return StandardSuccessResponse(
        success=True,
        data=updated,
        request_id=_req_id(request),
    )


@router.post(
    "/{resource_type}/{resource_id}/correct",
    response_model=StandardSuccessResponse[ClinicalVersionRecord],
    summary="Correct clinical record preserving historical version",
    description="Apply clinical correction without overwriting history.",
    responses={
        409: {"model": StandardErrorResponse, "description": "Version conflict"},
        422: {"model": StandardErrorResponse, "description": "Reason required"},
    },
)
async def correct_record(
    request: Request,
    resource_type: str,
    resource_id: str,
    body: VersionCorrectionRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    versioning_service: Annotated[VersioningService, Depends(get_versioning_service)],
) -> StandardSuccessResponse[ClinicalVersionRecord]:
    """Correct record preserving history."""
    corrected = await versioning_service.correct_version(
        resource_type=resource_type,
        resource_id=resource_id,
        request=body,
        actor_id=current_user.user_id,
        actor_role=current_user.role,
        actor_type="CLINICIAN",
    )
    return StandardSuccessResponse(
        success=True,
        data=corrected,
        request_id=_req_id(request),
    )


@router.post(
    "/{resource_type}/{resource_id}/supersede",
    response_model=StandardSuccessResponse[ClinicalVersionRecord],
    summary="Supersede clinical record",
    description="Mark current record as superseded by replacement state.",
    responses={
        409: {"model": StandardErrorResponse, "description": "Version conflict"},
    },
)
async def supersede_record(
    request: Request,
    resource_type: str,
    resource_id: str,
    body: VersionSupersedeRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    versioning_service: Annotated[VersioningService, Depends(get_versioning_service)],
) -> StandardSuccessResponse[ClinicalVersionRecord]:
    """Supersede record."""
    superseded = await versioning_service.supersede_version(
        resource_type=resource_type,
        resource_id=resource_id,
        request=body,
        actor_id=current_user.user_id,
        actor_role=current_user.role,
        actor_type="CLINICIAN",
    )
    return StandardSuccessResponse(
        success=True,
        data=superseded,
        request_id=_req_id(request),
    )


@router.post(
    "/{resource_type}/{resource_id}/restore",
    response_model=StandardSuccessResponse[ClinicalVersionRecord],
    summary="Restore historical version state",
    description="Appends a new version from target historical state without deleting intervening versions.",
    responses={
        404: {"model": StandardErrorResponse, "description": "Target version not found"},
        409: {"model": StandardErrorResponse, "description": "Version conflict"},
    },
)
async def restore_record(
    request: Request,
    resource_type: str,
    resource_id: str,
    body: VersionRestoreRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    versioning_service: Annotated[VersioningService, Depends(get_versioning_service)],
) -> StandardSuccessResponse[ClinicalVersionRecord]:
    """Restore historical version."""
    restored = await versioning_service.restore_version(
        resource_type=resource_type,
        resource_id=resource_id,
        request=body,
        actor_id=current_user.user_id,
        actor_role=current_user.role,
        actor_type="CLINICIAN",
    )
    return StandardSuccessResponse(
        success=True,
        data=restored,
        request_id=_req_id(request),
    )
