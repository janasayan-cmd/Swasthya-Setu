"""Phase 31 — Slot Availability Retrieval Endpoints.

CRITICAL INVARIANTS:
- AVAILABLE SLOT ≠ CLINICAL RECOMMENDATION
- NO VERIFIED AVAILABILITY → DO NOT SHOW SLOT AS AVAILABLE
- FACILITY DISCOVERY ≠ APPOINTMENT AVAILABILITY
- CLINICIAN PROFILE ≠ CLINICIAN AVAILABILITY
"""

from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, Query, status

from app.api.deps import (
    get_availability_service,
    get_current_user,
    require_permission,
)
from app.core.policies import Permission
from app.schemas.appointment import AppointmentType
from app.schemas.availability import (
    AvailabilityQuery,
    AvailabilityResponse,
    AvailabilityResponseData,
)
from app.schemas.user import AuthenticatedUserContext
from app.services.availability_service import AvailabilityService

router = APIRouter(prefix="/availability", tags=["Availability & Scheduling"])


@router.get(
    "",
    response_model=AvailabilityResponse,
    summary="Query verified appointment slot availability",
    dependencies=[Depends(require_permission(Permission.AVAILABILITY_READ))],
)
async def get_availability(
    facility_id: Optional[str] = Query(None, description="Target healthcare facility identifier"),
    clinician_id: Optional[str] = Query(None, description="Target clinician identifier"),
    appointment_type: Optional[AppointmentType] = Query(None, description="Clinical appointment service type"),
    date: Optional[str] = Query(None, description="Exact date in YYYY-MM-DD"),
    start_date: Optional[str] = Query(None, description="Start date window in YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="End date window in YYYY-MM-DD"),
    duration: Optional[int] = Query(None, ge=5, le=480, description="Minimum slot duration in minutes"),
    timezone: Optional[str] = Query("UTC", description="Operating timezone identifier (e.g. UTC, Asia/Kolkata)"),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    availability_service: AvailabilityService = Depends(get_availability_service),
) -> AvailabilityResponse:
    """Retrieve authoritative available appointment slots matching the query."""
    query = AvailabilityQuery(
        facility_id=facility_id,
        clinician_id=clinician_id,
        appointment_type=appointment_type,
        date=date,
        start_date=start_date,
        end_date=end_date,
        duration=duration,
        timezone=timezone,
    )
    result_data: AvailabilityResponseData = await availability_service.get_availability(query)
    return AvailabilityResponse(success=True, data=result_data)
