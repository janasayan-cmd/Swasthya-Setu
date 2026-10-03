"""Insurance Eligibility Verification Endpoints (Phase 33).

Provides REST APIs for:
- Requesting point-in-time eligibility verification from external payers
- Inspecting eligibility check history for a patient
"""

from __future__ import annotations

import logging
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import (
    get_current_user,
    get_eligibility_service,
)
from app.schemas.eligibility import (
    EligibilityCheckRequest,
    EligibilityCheckResponse,
)
from app.schemas.user import AuthenticatedUserContext
from app.services.eligibility_service import EligibilityService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Insurance & Eligibility"])


@router.post(
    "/patients/{patient_id}/insurance/eligibility-check",
    response_model=EligibilityCheckResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify Patient Insurance Eligibility",
    description="Performs a real-time point-in-time eligibility check via the configured payer clearinghouse.",
)
async def check_patient_eligibility(
    patient_id: str,
    request: EligibilityCheckRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: Annotated[EligibilityService, Depends(get_eligibility_service)],
) -> EligibilityCheckResponse:
    return await service.verify_eligibility(current_user, request)


@router.get(
    "/patients/{patient_id}/insurance/eligibility",
    response_model=List[EligibilityCheckResponse],
    summary="List Patient Eligibility Checks",
    description="Returns historical eligibility verification outcomes for the patient.",
)
async def list_patient_eligibility(
    patient_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: Annotated[EligibilityService, Depends(get_eligibility_service)],
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> List[EligibilityCheckResponse]:
    records, _ = service.list_patient_eligibility_checks(current_user, patient_id, limit=limit, offset=offset)
    return records


@router.get(
    "/patients/{patient_id}/insurance/eligibility/{check_id}",
    response_model=EligibilityCheckResponse,
    summary="Get Eligibility Check Details",
    description="Fetches detailed outcome of a specific historical eligibility check.",
)
async def get_eligibility_check_detail(
    patient_id: str,
    check_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: Annotated[EligibilityService, Depends(get_eligibility_service)],
) -> EligibilityCheckResponse:
    return service.get_eligibility_check(current_user, check_id)
