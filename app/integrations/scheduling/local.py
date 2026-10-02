"""Local Database-backed Scheduling Provider (Phase 31).

Authoritative internal implementation of SchedulingProvider using HealthSetu
repositories with strict double-booking and concurrency prevention.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.exceptions import (
    AppointmentBookingConflictException,
    AppointmentDoubleBookingException,
    AppointmentInvalidStateException,
    AppointmentNotFoundException,
    AppointmentRescheduleFailedException,
    AppointmentSlotNotFoundException,
    AppointmentSlotUnavailableException,
)
from app.integrations.scheduling.base import SchedulingProvider
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.availability_repository import AvailabilityRepository
from app.schemas.appointment import (
    AppointmentCreateRequest,
    AppointmentRecord,
    AppointmentStatus,
    AppointmentType,
    VALID_APPOINTMENT_TRANSITIONS,
)
from app.schemas.availability import AvailabilitySlotRecord, SlotStatus

logger = logging.getLogger(__name__)


class LocalSchedulingProvider(SchedulingProvider):
    """Local repository-backed scheduling provider."""

    def __init__(
        self,
        appointment_repo: AppointmentRepository,
        availability_repo: AvailabilityRepository,
    ) -> None:
        self.appointment_repo = appointment_repo
        self.availability_repo = availability_repo

    async def get_availability(
        self,
        facility_id: Optional[str] = None,
        clinician_id: Optional[str] = None,
        appointment_type: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[AvailabilitySlotRecord]:
        """Fetch available slots matching criteria from authoritative local repository."""
        app_type = None
        if appointment_type:
            try:
                app_type = AppointmentType(appointment_type)
            except ValueError:
                pass

        return self.availability_repo.query_slots(
            facility_id=facility_id,
            clinician_id=clinician_id,
            appointment_type=app_type,
            start_time=start_time,
            end_time=end_time,
            status=SlotStatus.AVAILABLE,
        )

    async def create_appointment(
        self,
        request: AppointmentCreateRequest,
        created_by: str,
        idempotency_key: Optional[str] = None,
    ) -> AppointmentRecord:
        """Create appointment with transactional slot reservation and conflict checks."""
        # 1. Check idempotency if key provided
        if idempotency_key:
            existing = self.appointment_repo.get_by_idempotency_key(idempotency_key)
            if existing:
                logger.info(f"Returning idempotent appointment: {existing.id}")
                return existing

        # 2. If slot_id is supplied, reserve it atomically
        if request.slot_id:
            slot = self.availability_repo.get_slot(request.slot_id)
            if not slot:
                raise AppointmentSlotNotFoundException(f"Slot '{request.slot_id}' not found.")
            if not self.availability_repo.reserve_slot(request.slot_id):
                raise AppointmentSlotUnavailableException(
                    "The selected appointment slot is no longer available."
                )

        # 3. Check for clinician booking conflict
        if request.clinician_id:
            conflict = self.appointment_repo.check_clinician_conflict(
                clinician_id=request.clinician_id,
                start_time=request.start_time,
                end_time=request.end_time,
            )
            if conflict:
                # If slot was reserved, release it before failing
                if request.slot_id:
                    self.availability_repo.release_slot(request.slot_id)
                raise AppointmentBookingConflictException(
                    "Clinician already has an overlapping appointment scheduled."
                )

        # 4. Construct appointment record
        now = datetime.now(timezone.utc)
        appointment_id = f"appt-{uuid.uuid4().hex[:12]}"
        record = AppointmentRecord(
            id=appointment_id,
            patient_id=request.patient_id,
            facility_id=request.facility_id,
            clinician_id=request.clinician_id,
            organization_id=request.organization_id,
            appointment_type=request.appointment_type,
            slot_id=request.slot_id,
            start_time=request.start_time,
            end_time=request.end_time,
            status=AppointmentStatus.CONFIRMED,
            reason=request.reason,
            encounter_id=request.encounter_id,
            idempotency_key=idempotency_key,
            created_by=created_by,
            created_at=now,
            updated_at=now,
        )

        return self.appointment_repo.create(record)

    async def get_appointment(self, appointment_id: str) -> Optional[AppointmentRecord]:
        """Fetch appointment from local store."""
        return self.appointment_repo.get(appointment_id)

    async def reschedule_appointment(
        self,
        appointment_id: str,
        new_slot_id: Optional[str],
        new_start_time: Optional[datetime],
        new_end_time: Optional[datetime],
        reason: Optional[str],
    ) -> AppointmentRecord:
        """Reschedule appointment: reserve new slot first, then release old slot."""
        appt = self.appointment_repo.get(appointment_id)
        if not appt:
            raise AppointmentNotFoundException(f"Appointment '{appointment_id}' not found.")

        if appt.status not in (AppointmentStatus.CONFIRMED, AppointmentStatus.REQUESTED, AppointmentStatus.RESCHEDULED):
            raise AppointmentInvalidStateException(
                f"Cannot reschedule appointment currently in '{appt.status.value}' state."
            )

        old_slot_id = appt.slot_id
        target_start = new_start_time or appt.start_time
        target_end = new_end_time or appt.end_time

        # If new slot provided, attempt to reserve it
        if new_slot_id:
            new_slot = self.availability_repo.get_slot(new_slot_id)
            if not new_slot:
                raise AppointmentSlotNotFoundException(f"Target slot '{new_slot_id}' not found.")
            target_start = new_slot.start_time
            target_end = new_slot.end_time

            reserved = self.availability_repo.reserve_slot(new_slot_id)
            if not reserved:
                raise AppointmentSlotUnavailableException(
                    "Target rescheduling slot is no longer available."
                )

        # Check clinician conflict for new timeframe
        if appt.clinician_id:
            conflict = self.appointment_repo.check_clinician_conflict(
                clinician_id=appt.clinician_id,
                start_time=target_start,
                end_time=target_end,
                exclude_id=appt.id,
            )
            if conflict:
                if new_slot_id:
                    self.availability_repo.release_slot(new_slot_id)
                raise AppointmentBookingConflictException(
                    "Clinician has an overlapping appointment during the new requested timeframe."
                )

        # Release old slot if previously reserved
        if old_slot_id:
            self.availability_repo.release_slot(old_slot_id)

        now = datetime.now(timezone.utc)
        updated_appt = appt.model_copy(
            update={
                "slot_id": new_slot_id or appt.slot_id,
                "start_time": target_start,
                "end_time": target_end,
                "status": AppointmentStatus.RESCHEDULED,
                "updated_at": now,
                "metadata": {
                    **appt.metadata,
                    "rescheduled_at": now.isoformat(),
                    "reschedule_reason": reason,
                },
            }
        )
        return self.appointment_repo.update(updated_appt)

    async def cancel_appointment(
        self,
        appointment_id: str,
        reason: Optional[str],
    ) -> AppointmentRecord:
        """Cancel an appointment and release its slot."""
        appt = self.appointment_repo.get(appointment_id)
        if not appt:
            raise AppointmentNotFoundException(f"Appointment '{appointment_id}' not found.")

        if appt.status in (AppointmentStatus.CANCELLED, AppointmentStatus.COMPLETED, AppointmentStatus.NO_SHOW):
            raise AppointmentInvalidStateException(
                f"Appointment in terminal '{appt.status.value}' state cannot be cancelled."
            )

        # Release slot
        if appt.slot_id:
            self.availability_repo.release_slot(appt.slot_id)

        now = datetime.now(timezone.utc)
        updated_appt = appt.model_copy(
            update={
                "status": AppointmentStatus.CANCELLED,
                "cancelled_at": now,
                "cancellation_reason": reason,
                "updated_at": now,
            }
        )
        return self.appointment_repo.update(updated_appt)

    async def get_appointment_status(self, appointment_id: str) -> Optional[AppointmentStatus]:
        """Retrieve verified status from repository."""
        appt = self.appointment_repo.get(appointment_id)
        return appt.status if appt else None

    async def health_check(self) -> Dict[str, Any]:
        """Check provider health."""
        return {
            "status": "healthy",
            "provider": "local",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
