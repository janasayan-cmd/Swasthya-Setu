"""Scheduling Service (Phase 31).

Coordinates schedule template parsing, synthetic slot generation, provider operational checks,
and administrative status reporting.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.integrations.scheduling.base import SchedulingProvider
from app.repositories.availability_repository import AvailabilityRepository
from app.repositories.schedule_repository import ScheduleRepository
from app.schemas.appointment import AppointmentType
from app.schemas.availability import AvailabilitySlotRecord, SlotStatus
from app.schemas.schedule import ScheduleRecord

logger = logging.getLogger(__name__)


class SchedulingService:
    """Coordinates schedule templates, slot generation, and administrative diagnostic endpoints."""

    def __init__(
        self,
        schedule_repo: ScheduleRepository,
        availability_repo: AvailabilityRepository,
        provider: SchedulingProvider,
    ) -> None:
        self.schedule_repo = schedule_repo
        self.availability_repo = availability_repo
        self.provider = provider

    def generate_slots_for_schedule(
        self,
        schedule: ScheduleRecord,
        start_date: date,
        end_date: date,
        appointment_type: AppointmentType = AppointmentType.CONSULTATION,
        capacity: int = 1,
    ) -> List[AvailabilitySlotRecord]:
        """Generate authoritative discrete availability slots from a recurring schedule rule."""
        tz = ZoneInfo(schedule.timezone)
        generated: List[AvailabilitySlotRecord] = []

        curr = start_date
        while curr <= end_date:
            date_str = curr.isoformat()
            if date_str in schedule.blocked_dates:
                curr += timedelta(days=1)
                continue

            day_of_week = curr.weekday()  # 0=Monday, 6=Sunday
            matching_rules = [r for r in schedule.working_hours if r.day_of_week == day_of_week]

            for rule in matching_rules:
                sh, sm = map(int, rule.start_time.split(":"))
                eh, em = map(int, rule.end_time.split(":"))
                slot_duration = timedelta(minutes=rule.slot_duration_minutes)

                start_dt = datetime.combine(curr, time(sh, sm), tzinfo=tz)
                end_dt = datetime.combine(curr, time(eh, em), tzinfo=tz)

                slot_start = start_dt
                while slot_start + slot_duration <= end_dt:
                    slot_end = slot_start + slot_duration
                    slot_id = f"slot-{uuid.uuid4().hex[:10]}"
                    slot = AvailabilitySlotRecord(
                        slot_id=slot_id,
                        facility_id=schedule.facility_id,
                        clinician_id=schedule.clinician_id,
                        appointment_type=appointment_type,
                        start_time=slot_start,
                        end_time=slot_end,
                        status=SlotStatus.AVAILABLE,
                        capacity=capacity,
                        booked_count=0,
                        metadata={"schedule_id": schedule.id},
                    )
                    self.availability_repo.create_slot(slot)
                    generated.append(slot)
                    slot_start = slot_end

            curr += timedelta(days=1)

        return generated

    async def get_system_status(self) -> Dict[str, Any]:
        """Retrieve operational scheduling health and capability state."""
        return {
            "appointments_enabled": settings.APPOINTMENTS_ENABLED,
            "availability_enabled": settings.AVAILABILITY_ENABLED,
            "booking_enabled": settings.APPOINTMENT_BOOKING_ENABLED,
            "rescheduling_enabled": settings.APPOINTMENT_RESCHEDULING_ENABLED,
            "cancellation_enabled": settings.APPOINTMENT_CANCELLATION_ENABLED,
            "reminders_enabled": settings.APPOINTMENT_REMINDERS_ENABLED,
            "provider": settings.SCHEDULING_PROVIDER,
            "default_duration_minutes": settings.APPOINTMENT_DEFAULT_DURATION_MINUTES,
            "max_lookahead_days": settings.APPOINTMENT_MAX_LOOKAHEAD_DAYS,
        }

    async def test_provider_health(self) -> Dict[str, Any]:
        """Run diagnostic health check against configured provider."""
        return await self.provider.health_check()
