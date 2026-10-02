"""Appointment Validation Service (Phase 31).

Pure validation service enforcing scheduling constraints, timeframe boundaries,
state transitions, and clinical safety invariants.

SAFETY INVARIANTS:
- SCHEDULING ≠ DIAGNOSIS: appointment reason is free-text non-diagnostic context.
- APPOINTMENT ≠ ENCOUNTER: scheduling does not fabricate clinical encounters.
- Timeframes must be strictly ordered with positive duration.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.core.config import settings
from app.core.exceptions import (
    AppointmentInvalidStateException,
    InvalidAppointmentTimeException,
    InvalidAppointmentTypeException,
    InvalidTimezoneException,
)
from app.schemas.appointment import (
    AppointmentCreateRequest,
    AppointmentStatus,
    AppointmentType,
    VALID_APPOINTMENT_TRANSITIONS,
)

logger = logging.getLogger(__name__)


class AppointmentValidationService:
    """Deterministic validation logic for appointment operations."""

    def validate_create_request(self, request: AppointmentCreateRequest) -> None:
        """Validate an appointment creation request."""
        # 1. Validate start and end time order
        if request.start_time >= request.end_time:
            raise InvalidAppointmentTimeException(
                "Appointment start time must be strictly before end time."
            )

        duration_minutes = (request.end_time - request.start_time).total_seconds() / 60
        if duration_minutes < 5:
            raise InvalidAppointmentTimeException(
                "Appointment duration must be at least 5 minutes."
            )
        if duration_minutes > 480:
            raise InvalidAppointmentTimeException(
                "Appointment duration cannot exceed 8 hours (480 minutes)."
            )

        # 2. Validate lookahead window
        now_utc = datetime.now(timezone.utc)
        req_start_utc = request.start_time if request.start_time.tzinfo else request.start_time.replace(tzinfo=timezone.utc)
        
        # Prevent booking in the past (allow 5-minute skew)
        if (req_start_utc - now_utc).total_seconds() < -300:
            raise InvalidAppointmentTimeException(
                "Cannot book an appointment in the past."
            )

        if settings.APPOINTMENT_MAX_LOOKAHEAD_DAYS > 0:
            max_future_seconds = settings.APPOINTMENT_MAX_LOOKAHEAD_DAYS * 86400
            if (req_start_utc - now_utc).total_seconds() > max_future_seconds:
                raise InvalidAppointmentTimeException(
                    f"Appointments cannot be scheduled more than {settings.APPOINTMENT_MAX_LOOKAHEAD_DAYS} days in advance."
                )

        # 3. Validate appointment type
        if not isinstance(request.appointment_type, AppointmentType):
            try:
                AppointmentType(request.appointment_type)
            except ValueError:
                raise InvalidAppointmentTypeException(
                    f"Appointment type '{request.appointment_type}' is not recognized."
                )

    def validate_transition(
        self,
        current_status: AppointmentStatus,
        target_status: AppointmentStatus,
    ) -> None:
        """Validate state transition against the database-approved state machine."""
        if current_status == target_status:
            return  # No-op transition

        allowed = VALID_APPOINTMENT_TRANSITIONS.get(current_status, set())
        if target_status not in allowed:
            logger.warning(
                f"Invalid appointment state transition: {current_status.value} -> {target_status.value}"
            )
            raise AppointmentInvalidStateException(
                f"Transition from '{current_status.value}' to '{target_status.value}' is not permitted."
            )

    def validate_timezone(self, tz_str: Optional[str]) -> None:
        """Validate that a timezone string is a valid IANA identifier."""
        if not tz_str:
            return
        try:
            ZoneInfo(tz_str)
        except (ZoneInfoNotFoundError, ValueError):
            raise InvalidTimezoneException(
                f"Invalid or unsupported timezone identifier: '{tz_str}'."
            )
