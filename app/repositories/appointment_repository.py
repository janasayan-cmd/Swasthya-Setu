"""Appointment Repository (Phase 31).

Thread-safe repository for appointment entities, lifecycle state persistence,
idempotent lookup, and controlled access queries.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from app.schemas.appointment import (
    AppointmentRecord,
    AppointmentStatus,
    AppointmentType,
)

logger = logging.getLogger(__name__)


class AppointmentRepository:
    """Thread-safe repository managing appointment lifecycle persistence and queries."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._appointments: Dict[str, AppointmentRecord] = {}
        self._idempotency_index: Dict[str, str] = {}  # idempotency_key -> appointment_id

    def create(self, appointment: AppointmentRecord) -> AppointmentRecord:
        """Persist a new appointment record and register idempotency mapping."""
        with self._lock:
            self._appointments[appointment.id] = appointment
            if appointment.idempotency_key:
                self._idempotency_index[appointment.idempotency_key] = appointment.id
            return appointment

    def get(self, appointment_id: str) -> Optional[AppointmentRecord]:
        """Retrieve an appointment by ID."""
        with self._lock:
            return self._appointments.get(appointment_id)

    def get_by_idempotency_key(self, idempotency_key: str) -> Optional[AppointmentRecord]:
        """Fetch appointment associated with a unique idempotency key."""
        with self._lock:
            appointment_id = self._idempotency_index.get(idempotency_key)
            if appointment_id:
                return self._appointments.get(appointment_id)
            return None

    def update(self, appointment: AppointmentRecord) -> AppointmentRecord:
        """Update an existing appointment record."""
        with self._lock:
            self._appointments[appointment.id] = appointment
            return appointment

    def check_clinician_conflict(
        self,
        clinician_id: str,
        start_time: datetime,
        end_time: datetime,
        exclude_id: Optional[str] = None,
    ) -> bool:
        """Check if clinician has active overlapping appointments."""
        with self._lock:
            active_statuses = {
                AppointmentStatus.REQUESTED,
                AppointmentStatus.PENDING,
                AppointmentStatus.CONFIRMED,
                AppointmentStatus.RESCHEDULED,
                AppointmentStatus.CHECKED_IN,
                AppointmentStatus.IN_PROGRESS,
            }
            for appt in self._appointments.values():
                if exclude_id and appt.id == exclude_id:
                    continue
                if appt.clinician_id != clinician_id:
                    continue
                if appt.status not in active_statuses:
                    continue
                # Overlap check: start1 < end2 and start2 < end1
                if appt.start_time < end_time and start_time < appt.end_time:
                    return True
            return False

    def list_by_patient(
        self,
        patient_id: str,
        status: Optional[AppointmentStatus] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        facility_id: Optional[str] = None,
        clinician_id: Optional[str] = None,
        appointment_type: Optional[AppointmentType] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[AppointmentRecord], int]:
        """List appointments for a patient with controlled filters."""
        with self._lock:
            matches: List[AppointmentRecord] = []
            for appt in self._appointments.values():
                if appt.patient_id != patient_id:
                    continue
                if status and appt.status != status:
                    continue
                if facility_id and appt.facility_id != facility_id:
                    continue
                if clinician_id and appt.clinician_id != clinician_id:
                    continue
                if appointment_type and appt.appointment_type != appointment_type:
                    continue
                if start_date and appt.end_time < start_date:
                    continue
                if end_date and appt.start_time > end_date:
                    continue
                matches.append(appt)

            matches.sort(key=lambda a: a.start_time, reverse=True)
            total = len(matches)
            return matches[offset : offset + limit], total

    def list_by_clinician(
        self,
        clinician_id: str,
        status: Optional[AppointmentStatus] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        facility_id: Optional[str] = None,
        appointment_type: Optional[AppointmentType] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[AppointmentRecord], int]:
        """List appointments assigned to a clinician."""
        with self._lock:
            matches: List[AppointmentRecord] = []
            for appt in self._appointments.values():
                if appt.clinician_id != clinician_id:
                    continue
                if status and appt.status != status:
                    continue
                if facility_id and appt.facility_id != facility_id:
                    continue
                if appointment_type and appt.appointment_type != appointment_type:
                    continue
                if start_date and appt.end_time < start_date:
                    continue
                if end_date and appt.start_time > end_date:
                    continue
                matches.append(appt)

            matches.sort(key=lambda a: a.start_time)
            total = len(matches)
            return matches[offset : offset + limit], total

    def list_by_facility(
        self,
        facility_id: str,
        status: Optional[AppointmentStatus] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        appointment_type: Optional[AppointmentType] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[AppointmentRecord], int]:
        """List appointments hosted at a specific facility."""
        with self._lock:
            matches: List[AppointmentRecord] = []
            for appt in self._appointments.values():
                if appt.facility_id != facility_id:
                    continue
                if status and appt.status != status:
                    continue
                if appointment_type and appt.appointment_type != appointment_type:
                    continue
                if start_date and appt.end_time < start_date:
                    continue
                if end_date and appt.start_time > end_date:
                    continue
                matches.append(appt)

            matches.sort(key=lambda a: a.start_time)
            total = len(matches)
            return matches[offset : offset + limit], total

    def list_by_organization(
        self,
        organization_id: str,
        status: Optional[AppointmentStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[AppointmentRecord], int]:
        """List appointments for a healthcare organization."""
        with self._lock:
            matches: List[AppointmentRecord] = []
            for appt in self._appointments.values():
                if appt.organization_id != organization_id:
                    continue
                if status and appt.status != status:
                    continue
                matches.append(appt)

            matches.sort(key=lambda a: a.start_time)
            total = len(matches)
            return matches[offset : offset + limit], total

    def clear(self) -> None:
        """Clear store (for testing)."""
        with self._lock:
            self._appointments.clear()
            self._idempotency_index.clear()
