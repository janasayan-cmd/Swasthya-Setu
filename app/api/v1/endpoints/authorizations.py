"""Pre-Authorization (Prior Auth) Endpoints (Phase 33).

Provides REST APIs for:
- Initiating pre-authorization requests with linked clinical and appointment references
- Submitting pre-authorizations to external payers
- Inspecting status, approved amounts, denial reasons, and validity windows
"""

from __future__ import annotations

import logging
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import (
    get_current_user,
    get_preauthorization_service,
)
from app.schemas.authorization import (
    PreAuthorizationCreate,
    PreAuthorizationResponse,
    PreAuthorizationStatus,
    PreAuthorizationSubmitRequest,
)
from app.schemas.user import AuthenticatedUserContext
from app.services.preauthorization_service import PreAuthorizationService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Pre-Authorization & Prior Auth"])


@router.post(
    "/patients/{patient_id}/authorizations",
    response_model=PreAuthorizationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Pre-Authorization Request",
    description="Drafts a new prior authorization request with linked clinical and appointment references.",
)
async def create_preauthorization(
    patient_id: str,
    request: PreAuthorizationCreate,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: Annotated[PreAuthorizationService, Depends(get_preauthorization_service)],
) -> PreAuthorizationResponse:
    request.patient_id = patient_id
    return service.create_preauthorization(current_user, request)


@router.get(
    "/patients/{patient_id}/authorizations",
    response_model=List[PreAuthorizationResponse],
    summary="List Patient Pre-Authorizations",
    description="Lists all prior authorizations filed for a patient.",
)
async def list_patient_authorizations(
    patient_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: Annotated[PreAuthorizationService, Depends(get_preauthorization_service)],
    status: Optional[PreAuthorizationStatus] = Query(None, description="Filter by authorization status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> List[PreAuthorizationResponse]:
    records, _ = service.list_patient_preauthorizations(current_user, patient_id, status=status, limit=limit, offset=offset)
    return records


@router.get(
    "/patients/{patient_id}/authorizations/{authorization_id}",
    response_model=PreAuthorizationResponse,
    summary="Get Pre-Authorization Details",
    description="Retrieves details and approved limits of a prior authorization request.",
)
async def get_authorization_detail(
    patient_id: str,
    authorization_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: Annotated[PreAuthorizationService, Depends(get_preauthorization_service)],
) -> PreAuthorizationResponse:
    return service.get_preauthorization(current_user, authorization_id)


@router.post(
    "/patients/{patient_id}/authorizations/{authorization_id}/submit",
    response_model=PreAuthorizationResponse,
    summary="Submit Pre-Authorization to Payer",
    description="Submits the draft prior authorization request to the configured payer clearinghouse.",
)
async def submit_authorization_to_payer(
    patient_id: str,
    authorization_id: str,
    request: Optional[PreAuthorizationSubmitRequest],
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: Annotated[PreAuthorizationService, Depends(get_preauthorization_service)],
) -> PreAuthorizationResponse:
    return await service.submit_preauthorization(current_user, authorization_id, request)


@router.get(
    "/patients/{patient_id}/authorizations/{authorization_id}/status",
    response_model=PreAuthorizationResponse,
    summary="Sync Pre-Authorization Status",
    description="Queries the external payer gateway for the latest adjudication status.",
)
async def sync_authorization_status_endpoint(
    patient_id: str,
    authorization_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: Annotated[PreAuthorizationService, Depends(get_preauthorization_service)],
) -> PreAuthorizationResponse:
    return await service.sync_authorization_status(current_user, authorization_id)
