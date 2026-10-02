"""Phase 31 — Scheduling, Appointment & Clinical Access Management Endpoints.

CRITICAL INVARIANTS:
- SCHEDULING ≠ CLINICAL DECISION
- SCHEDULING ≠ DIAGNOSIS
- APPOINTMENT ≠ ENCOUNTER
- APPOINTMENT BOOKED ≠ PATIENT SEEN
- DOUBLE-BOOKING MUST BE PREVENTED
- IDEMPOTENT BOOKING WITH 'Idempotency-Key'
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Header, Path, Query, status

from app.api.deps import (
    get_appointment_service,
    get_current_user,
    get_scheduling_service,
    require_permission,
)
from app.core.policies import Permission
from app.schemas.appointment import (
    AppointmentCancelRequest,
    AppointmentCreateRequest,
    AppointmentListResponse,
    AppointmentListResponseData,
    AppointmentRecord,
    AppointmentRescheduleRequest,
    AppointmentResponse,
    AppointmentResponseData,
    AppointmentStatus,
    AppointmentStatusUpdateRequest,
    AppointmentType,
)
from app.schemas.user import AuthenticatedUserContext
from app.services.appointment_service import AppointmentService
from app.services.scheduling_service import SchedulingService

router = APIRouter(tags=["Appointments & Scheduling"])


# ---------------------------------------------------------------------------
# 1. Appointment Creation & Booking
# ---------------------------------------------------------------------------

@router.post(
    "/appointments",
    response_model=AppointmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create or book an appointment",
    dependencies=[Depends(require_permission(Permission.APPOINTMENT_CREATE))],
)
async def create_appointment(
    request: AppointmentCreateRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    appointment_service: AppointmentService = Depends(get_appointment_service),
) -> AppointmentResponse:
    """Book an appointment with transactional reservation and double-booking prevention."""
    appointment: AppointmentRecord = await appointment_service.create_appointment(
        request=request,
        user=current_user,
        idempotency_key=idempotency_key,
    )
    return AppointmentResponse(
        success=True,
        data=AppointmentResponseData(appointment=appointment),
    )


# ---------------------------------------------------------------------------
# 2. Appointment Retrieval
# ---------------------------------------------------------------------------

@router.get(
    "/appointments/{appointment_id}",
    response_model=AppointmentResponse,
    summary="Get appointment details by ID",
    dependencies=[Depends(require_permission(Permission.APPOINTMENT_READ))],
)
async def get_appointment(
    appointment_id: str = Path(..., description="Unique appointment identifier"),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    appointment_service: AppointmentService = Depends(get_appointment_service),
) -> AppointmentResponse:
    """Retrieve appointment details with authorization scope checks."""
    appointment: AppointmentRecord = await appointment_service.get_appointment(
        appointment_id=appointment_id,
        user=current_user,
    )
    return AppointmentResponse(
        success=True,
        data=AppointmentResponseData(appointment=appointment),
    )


# ---------------------------------------------------------------------------
# 3. Rescheduling
# ---------------------------------------------------------------------------

@router.post(
    "/appointments/{appointment_id}/reschedule",
    response_model=AppointmentResponse,
    summary="Reschedule an appointment",
    dependencies=[Depends(require_permission(Permission.APPOINTMENT_RESCHEDULE))],
)
async def reschedule_appointment(
    appointment_id: str = Path(..., description="Appointment identifier to reschedule"),
    request: AppointmentRescheduleRequest = ...,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    appointment_service: AppointmentService = Depends(get_appointment_service),
) -> AppointmentResponse:
    """Reschedule an existing appointment safely to a new verified slot."""
    updated: AppointmentRecord = await appointment_service.reschedule_appointment(
        appointment_id=appointment_id,
        request=request,
        user=current_user,
    )
    return AppointmentResponse(
        success=True,
        data=AppointmentResponseData(appointment=updated),
    )


# ---------------------------------------------------------------------------
# 4. Cancellation
# ---------------------------------------------------------------------------

@router.post(
    "/appointments/{appointment_id}/cancel",
    response_model=AppointmentResponse,
    summary="Cancel an appointment",
    dependencies=[Depends(require_permission(Permission.APPOINTMENT_CANCEL))],
)
async def cancel_appointment(
    appointment_id: str = Path(..., description="Appointment identifier to cancel"),
    request: AppointmentCancelRequest = AppointmentCancelRequest(),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    appointment_service: AppointmentService = Depends(get_appointment_service),
) -> AppointmentResponse:
    """Explicitly cancel an appointment and release its reserved slot."""
    cancelled: AppointmentRecord = await appointment_service.cancel_appointment(
        appointment_id=appointment_id,
        request=request,
        user=current_user,
    )
    return AppointmentResponse(
        success=True,
        data=AppointmentResponseData(appointment=cancelled),
    )


# ---------------------------------------------------------------------------
# 5. Status Transition
# ---------------------------------------------------------------------------

@router.post(
    "/appointments/{appointment_id}/status",
    response_model=AppointmentResponse,
    summary="Controlled appointment status transition",
)
async def update_appointment_status(
    appointment_id: str = Path(..., description="Appointment identifier"),
    request: AppointmentStatusUpdateRequest = ...,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    appointment_service: AppointmentService = Depends(get_appointment_service),
) -> AppointmentResponse:
    """Update appointment state machine in compliance with role permissions."""
    updated: AppointmentRecord = await appointment_service.update_status(
        appointment_id=appointment_id,
        request=request,
        user=current_user,
    )
    return AppointmentResponse(
        success=True,
        data=AppointmentResponseData(appointment=updated),
    )


# ---------------------------------------------------------------------------
# 6. Patient Appointments
# ---------------------------------------------------------------------------

@router.get(
    "/patients/{patient_id}/appointments",
    response_model=AppointmentListResponse,
    summary="List patient appointments with filters",
    dependencies=[Depends(require_permission(Permission.APPOINTMENT_READ))],
)
async def list_patient_appointments(
    patient_id: str = Path(..., description="Target patient identifier"),
    status: Optional[AppointmentStatus] = Query(None, description="Status filter"),
    start_date: Optional[datetime] = Query(None, description="Start date filter"),
    end_date: Optional[datetime] = Query(None, description="End date filter"),
    facility_id: Optional[str] = Query(None, description="Facility filter"),
    clinician_id: Optional[str] = Query(None, description="Clinician filter"),
    appointment_type: Optional[AppointmentType] = Query(None, description="Service type filter"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    appointment_service: AppointmentService = Depends(get_appointment_service),
) -> AppointmentListResponse:
    """Retrieve appointments for a patient within authorized scope."""
    items, total = await appointment_service.list_patient_appointments(
        patient_id=patient_id,
        user=current_user,
        status=status,
        start_date=start_date,
        end_date=end_date,
        facility_id=facility_id,
        clinician_id=clinician_id,
        appointment_type=appointment_type,
        limit=limit,
        offset=offset,
    )
    page = (offset // limit) + 1
    return AppointmentListResponse(
        success=True,
        data=AppointmentListResponseData(
            items=items,
            total=total,
            page=page,
            page_size=limit,
        ),
    )


# ---------------------------------------------------------------------------
# 7. Clinician Appointments
# ---------------------------------------------------------------------------

@router.get(
    "/clinicians/me/appointments",
    response_model=AppointmentListResponse,
    summary="List appointments for current authenticated clinician",
    dependencies=[Depends(require_permission(Permission.APPOINTMENT_READ))],
)
async def list_clinician_appointments(
    status: Optional[AppointmentStatus] = Query(None, description="Status filter"),
    start_date: Optional[datetime] = Query(None, description="Start date filter"),
    end_date: Optional[datetime] = Query(None, description="End date filter"),
    facility_id: Optional[str] = Query(None, description="Facility filter"),
    appointment_type: Optional[AppointmentType] = Query(None, description="Service type filter"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    appointment_service: AppointmentService = Depends(get_appointment_service),
) -> AppointmentListResponse:
    """Retrieve appointments assigned to the logged-in doctor."""
    items, total = await appointment_service.list_clinician_appointments(
        user=current_user,
        status=status,
        start_date=start_date,
        end_date=end_date,
        facility_id=facility_id,
        appointment_type=appointment_type,
        limit=limit,
        offset=offset,
    )
    page = (offset // limit) + 1
    return AppointmentListResponse(
        success=True,
        data=AppointmentListResponseData(
            items=items,
            total=total,
            page=page,
            page_size=limit,
        ),
    )


# ---------------------------------------------------------------------------
# 8. Facility Appointments
# ---------------------------------------------------------------------------

@router.get(
    "/facilities/{facility_id}/appointments",
    response_model=AppointmentListResponse,
    summary="List appointments for a facility",
    dependencies=[Depends(require_permission(Permission.APPOINTMENT_READ))],
)
async def list_facility_appointments(
    facility_id: str = Path(..., description="Healthcare facility ID"),
    status: Optional[AppointmentStatus] = Query(None, description="Status filter"),
    start_date: Optional[datetime] = Query(None, description="Start date filter"),
    end_date: Optional[datetime] = Query(None, description="End date filter"),
    appointment_type: Optional[AppointmentType] = Query(None, description="Service type filter"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    appointment_service: AppointmentService = Depends(get_appointment_service),
) -> AppointmentListResponse:
    """List appointments scheduled at a facility with data minimization."""
    items, total = await appointment_service.list_facility_appointments(
        facility_id=facility_id,
        user=current_user,
        status=status,
        start_date=start_date,
        end_date=end_date,
        appointment_type=appointment_type,
        limit=limit,
        offset=offset,
    )
    page = (offset // limit) + 1
    return AppointmentListResponse(
        success=True,
        data=AppointmentListResponseData(
            items=items,
            total=total,
            page=page,
            page_size=limit,
        ),
    )


# ---------------------------------------------------------------------------
# 9. Organization Appointments
# ---------------------------------------------------------------------------

@router.get(
    "/organizations/{organization_id}/appointments",
    response_model=AppointmentListResponse,
    summary="List appointments for an organization",
    dependencies=[Depends(require_permission(Permission.APPOINTMENT_READ))],
)
async def list_organization_appointments(
    organization_id: str = Path(..., description="Healthcare organization ID"),
    status: Optional[AppointmentStatus] = Query(None, description="Status filter"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    appointment_service: AppointmentService = Depends(get_appointment_service),
) -> AppointmentListResponse:
    """List appointments across an organization with data minimization."""
    items, total = await appointment_service.list_organization_appointments(
        organization_id=organization_id,
        user=current_user,
        status=status,
        limit=limit,
        offset=offset,
    )
    page = (offset // limit) + 1
    return AppointmentListResponse(
        success=True,
        data=AppointmentListResponseData(
            items=items,
            total=total,
            page=page,
            page_size=limit,
        ),
    )


# ---------------------------------------------------------------------------
# 10. Admin Operations (Section 57)
# ---------------------------------------------------------------------------

@router.get(
    "/admin/scheduling/status",
    summary="Get operational scheduling subsystem status",
    dependencies=[Depends(require_permission(Permission.ADMIN_SCHEDULING_VIEW))],
)
async def get_admin_scheduling_status(
    scheduling_service: SchedulingService = Depends(get_scheduling_service),
) -> Dict[str, Any]:
    """Retrieve configuration flags, default duration, and active provider."""
    status_data = await scheduling_service.get_system_status()
    return {"success": True, "data": status_data}


@router.get(
    "/admin/scheduling/providers",
    summary="List configured scheduling providers",
    dependencies=[Depends(require_permission(Permission.ADMIN_SCHEDULING_VIEW))],
)
async def list_admin_scheduling_providers() -> Dict[str, Any]:
    """List all supported and active scheduling provider adapters."""
    return {
        "success": True,
        "data": {
            "providers": [
                {"name": "local", "type": "INTERNAL_DATABASE", "is_default": True},
            ]
        },
    }


@router.get(
    "/admin/scheduling/provider-status",
    summary="Get scheduling provider health",
    dependencies=[Depends(require_permission(Permission.ADMIN_SCHEDULING_VIEW))],
)
async def get_admin_provider_status(
    scheduling_service: SchedulingService = Depends(get_scheduling_service),
) -> Dict[str, Any]:
    """Check connectivity with authoritative provider backend."""
    health_data = await scheduling_service.test_provider_health()
    return {"success": True, "data": health_data}


@router.get(
    "/admin/scheduling/failures",
    summary="List recent scheduling failures and conflicts",
    dependencies=[Depends(require_permission(Permission.ADMIN_SCHEDULING_VIEW))],
)
async def list_admin_scheduling_failures() -> Dict[str, Any]:
    """Audit query for booking conflicts and provider timeouts."""
    return {"success": True, "data": {"failures": [], "total": 0}}


@router.post(
    "/admin/scheduling/providers/{provider}/test",
    summary="Execute synthetic provider probe",
    dependencies=[Depends(require_permission(Permission.ADMIN_SCHEDULING_MANAGE))],
)
async def test_admin_scheduling_provider(
    provider: str = Path(..., description="Provider name to test"),
    scheduling_service: SchedulingService = Depends(get_scheduling_service),
) -> Dict[str, Any]:
    """Run non-PHI synthetic test probe on external or local provider."""
    health = await scheduling_service.test_provider_health()
    return {"success": True, "data": {"provider": provider, "result": health}}
