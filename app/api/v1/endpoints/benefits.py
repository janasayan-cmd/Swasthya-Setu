"""Insurance Benefit Breakdown Endpoints (Phase 33).

Provides REST APIs for:
- Querying covered medical benefits, copays, coinsurance, and deductibles
- Listing historical benefit breakdowns for a patient
"""

from __future__ import annotations

import logging
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import (
    get_benefit_service,
    get_current_user,
)
from app.schemas.benefits import (
    BenefitRequest,
    BenefitResponse,
)
from app.schemas.user import AuthenticatedUserContext
from app.services.benefit_service import BenefitService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Insurance & Benefits"])


@router.post(
    "/patients/{patient_id}/insurance/benefits",
    response_model=BenefitResponse,
    status_code=status.HTTP_200_OK,
    summary="Query Policy Covered Benefits",
    description="Fetches live covered medical benefits, copays, coinsurance, and deductible balances from payer.",
)
async def query_patient_benefits(
    patient_id: str,
    request: BenefitRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: Annotated[BenefitService, Depends(get_benefit_service)],
) -> BenefitResponse:
    return await service.get_benefits(current_user, request)


@router.get(
    "/patients/{patient_id}/insurance/benefits",
    response_model=List[BenefitResponse],
    summary="List Patient Benefit Inquiries",
    description="Returns historical benefit inquiry records for the patient.",
)
async def list_patient_benefits(
    patient_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    service: Annotated[BenefitService, Depends(get_benefit_service)],
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> List[BenefitResponse]:
    records, _ = service.list_patient_benefits(current_user, patient_id, limit=limit, offset=offset)
    return records
