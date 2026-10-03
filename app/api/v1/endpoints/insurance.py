"""Patient Insurance Coverage Endpoints (Phase 33).

Provides REST APIs for:
- Registering patient insurance policies
- Listing patient policies with status filtering
- Viewing policy details (sensitive identifiers masked in standard views)
- Updating and deactivating coverage
"""

from __future__ import annotations

import logging
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import (
    get_current_user,
    get_insurance_service,
)
from app.schemas.insurance import (
    CoverageStatus,
    InsuranceCoverageCreate,
    InsuranceCoverageResponse,
    InsuranceCoverageUpdate,
)
from app.schemas.user import AuthenticatedUserContext
from app.services.insurance_service import InsuranceService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Insurance & Coverage"])


@router.post(
    "/patients/{patient_id}/insurance",
    response_model=InsuranceCoverageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register Patient Insurance Coverage",
    description="Registers an active or unverified insurance policy for a patient.",
)
async def create_patient_insurance(
    patient_id: str,
    request: InsuranceCoverageCreate,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: Annotated[InsuranceService, Depends(get_insurance_service)],
) -> InsuranceCoverageResponse:
    request.patient_id = patient_id
    return service.create_coverage(current_user, request)


@router.get(
    "/patients/{patient_id}/insurance",
    response_model=List[InsuranceCoverageResponse],
    summary="List Patient Insurance Policies",
    description="Returns all insurance policies registered for the patient.",
)
async def list_patient_insurance(
    patient_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: Annotated[InsuranceService, Depends(get_insurance_service)],
    status: Optional[CoverageStatus] = Query(None, description="Filter by coverage status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> List[InsuranceCoverageResponse]:
    records, _ = service.list_patient_coverages(current_user, patient_id, status=status, limit=limit, offset=offset)
    return records


@router.get(
    "/patients/{patient_id}/insurance/{coverage_id}",
    response_model=InsuranceCoverageResponse,
    summary="Get Insurance Coverage Details",
    description="Fetches full details of a specific patient coverage policy.",
)
async def get_patient_coverage(
    patient_id: str,
    coverage_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: Annotated[InsuranceService, Depends(get_insurance_service)],
) -> InsuranceCoverageResponse:
    return service.get_coverage(current_user, coverage_id)


@router.patch(
    "/patients/{patient_id}/insurance/{coverage_id}",
    response_model=InsuranceCoverageResponse,
    summary="Update Insurance Coverage",
    description="Updates policy status or metadata.",
)
async def update_patient_coverage(
    patient_id: str,
    coverage_id: str,
    request: InsuranceCoverageUpdate,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: Annotated[InsuranceService, Depends(get_insurance_service)],
) -> InsuranceCoverageResponse:
    return service.update_coverage(current_user, coverage_id, request)


@router.delete(
    "/patients/{patient_id}/insurance/{coverage_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Insurance Coverage",
    description="Deletes or de-registers an insurance coverage record.",
)
async def delete_patient_coverage(
    patient_id: str,
    coverage_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: Annotated[InsuranceService, Depends(get_insurance_service)],
) -> None:
    service.delete_coverage(current_user, coverage_id)
