"""Availability Service (Phase 31).

Orchestrates retrieval of schedulable appointment slots from authoritative sources.
Enforces the safety principle: NO VERIFIED AVAILABILITY → DO NOT SHOW AS AVAILABLE.
"""

from __future__ import annotations

import logging
from datetime import datetime, time, timezone
from typing import Any, List, Optional
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.core.exceptions import (
    AppointmentsDisabledException,
    AvailabilityUnavailableException,
)
from app.integrations.scheduling.base import SchedulingProvider
from app.schemas.audit import AuditEventType
from app.schemas.availability import (
    AvailabilityQuery,
    AvailabilityResponseData,
    AvailabilitySlotRecord,
)
from app.services.appointment_validation_service import AppointmentValidationService

logger = logging.getLogger(__name__)


class AvailabilityService:
    """Service orchestrating slot availability lookups."""

    def __init__(
        self,
        provider: SchedulingProvider,
        validation_service: AppointmentValidationService,
        audit_service: Optional[Any] = None,
    ) -> None:
        self.provider = provider
        self.validation_service = validation_service
        self.audit_service = audit_service

    async def get_availability(
        self,
        query: AvailabilityQuery,
        request_id: Optional[str] = None,
    ) -> AvailabilityResponseData:
        """Retrieve verified availability slots from the authoritative provider."""
        # 1. Feature flag guard
        if not settings.APPOINTMENTS_ENABLED or not settings.AVAILABILITY_ENABLED:
            raise AppointmentsDisabledException("Availability search is currently disabled.")

        # 2. Timezone validation
        tz_name = query.timezone or "UTC"
        self.validation_service.validate_timezone(tz_name)
        tz = ZoneInfo(tz_name)

        # 3. Parse date window boundaries
        start_dt: Optional[datetime] = None
        end_dt: Optional[datetime] = None

        if query.date:
            try:
                d = datetime.strptime(query.date, "%Y-%m-%d").date()
                start_dt = datetime.combine(d, time.min, tzinfo=tz)
                end_dt = datetime.combine(d, time.max, tzinfo=tz)
            except ValueError:
                pass
        else:
            if query.start_date:
                try:
                    d = datetime.strptime(query.start_date, "%Y-%m-%d").date()
                    start_dt = datetime.combine(d, time.min, tzinfo=tz)
                except ValueError:
                    pass
            if query.end_date:
                try:
                    d = datetime.strptime(query.end_date, "%Y-%m-%d").date()
                    end_dt = datetime.combine(d, time.max, tzinfo=tz)
                except ValueError:
                    pass

        # 4. Fetch from provider
        slots: List[AvailabilitySlotRecord] = await self.provider.get_availability(
            facility_id=query.facility_id,
            clinician_id=query.clinician_id,
            appointment_type=query.appointment_type.value if query.appointment_type else None,
            start_time=start_dt,
            end_time=end_dt,
        )

        # 5. Filter by duration if specified
        if query.duration:
            slots = [
                s for s in slots
                if (s.end_time - s.start_time).total_seconds() / 60 >= query.duration
            ]

        # 6. Audit event logging (non-PHI)
        if self.audit_service:
            try:
                await self.audit_service.log_event(
                    event_type=AuditEventType.AVAILABILITY_SEARCH_EXECUTED,
                    actor_id="system",
                    resource_type="availability",
                    facility_id=query.facility_id,
                    metadata={
                        "facility_id": query.facility_id,
                        "clinician_id": query.clinician_id,
                        "slots_returned": len(slots),
                        "request_id": request_id,
                    },
                )
            except Exception as e:
                logger.warning(f"Failed to record availability search audit event: {e}")

        return AvailabilityResponseData(slots=slots, total=len(slots))
