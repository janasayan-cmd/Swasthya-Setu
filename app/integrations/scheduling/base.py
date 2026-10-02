"""Scheduling Provider Base Interface (Phase 31).

Defines the pluggable adapter interface for authoritative scheduling backends.
Ensures external vendor decoupling and safe failure boundaries.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.schemas.appointment import (
    AppointmentCreateRequest,
    AppointmentRecord,
    AppointmentStatus,
)
from app.schemas.availability import AvailabilitySlotRecord


class SchedulingProvider(ABC):
    """Abstract interface for authoritative scheduling providers."""

    @abstractmethod
    async def get_availability(
        self,
        facility_id: Optional[str] = None,
        clinician_id: Optional[str] = None,
        appointment_type: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[AvailabilitySlotRecord]:
        """Fetch verified availability slots from authoritative provider."""
        pass

    @abstractmethod
    async def create_appointment(
        self,
        request: AppointmentCreateRequest,
        created_by: str,
        idempotency_key: Optional[str] = None,
    ) -> AppointmentRecord:
        """Create or book an appointment with the authoritative provider."""
        pass

    @abstractmethod
    async def get_appointment(self, appointment_id: str) -> Optional[AppointmentRecord]:
        """Retrieve an appointment by ID from the authoritative provider."""
        pass

    @abstractmethod
    async def reschedule_appointment(
        self,
        appointment_id: str,
        new_slot_id: Optional[str],
        new_start_time: Optional[datetime],
        new_end_time: Optional[datetime],
        reason: Optional[str],
    ) -> AppointmentRecord:
        """Reschedule an existing appointment."""
        pass

    @abstractmethod
    async def cancel_appointment(
        self,
        appointment_id: str,
        reason: Optional[str],
    ) -> AppointmentRecord:
        """Cancel an existing appointment."""
        pass

    @abstractmethod
    async def get_appointment_status(self, appointment_id: str) -> Optional[AppointmentStatus]:
        """Get latest verified appointment status."""
        pass

    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Perform synthetic health check on the scheduling provider."""
        pass
