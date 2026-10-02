"""Availability Repository (Phase 31).

Thread-safe repository for slot storage, reservation, release, and querying.
Enforces double-booking prevention at the slot level with transactional locking.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.schemas.appointment import AppointmentType
from app.schemas.availability import AvailabilitySlotRecord, SlotStatus

logger = logging.getLogger(__name__)


class AvailabilityRepository:
    """Thread-safe repository managing availability slots and reservation invariants."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._slots: Dict[str, AvailabilitySlotRecord] = {}

    def create_slot(self, slot: AvailabilitySlotRecord) -> AvailabilitySlotRecord:
        """Store or update a schedulable slot."""
        with self._lock:
            self._slots[slot.slot_id] = slot
            return slot

    def get_slot(self, slot_id: str) -> Optional[AvailabilitySlotRecord]:
        """Fetch slot by unique identifier."""
        with self._lock:
            return self._slots.get(slot_id)

    def query_slots(
        self,
        facility_id: Optional[str] = None,
        clinician_id: Optional[str] = None,
        appointment_type: Optional[AppointmentType] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        status: Optional[SlotStatus] = None,
    ) -> List[AvailabilitySlotRecord]:
        """Query slots matching filters in authoritative storage."""
        with self._lock:
            results: List[AvailabilitySlotRecord] = []
            for slot in self._slots.values():
                if facility_id and slot.facility_id != facility_id:
                    continue
                if clinician_id and slot.clinician_id != clinician_id:
                    continue
                if appointment_type and slot.appointment_type != appointment_type:
                    continue
                if status and slot.status != status:
                    continue
                if start_time and slot.end_time < start_time:
                    continue
                if end_time and slot.start_time > end_time:
                    continue
                results.append(slot)

            results.sort(key=lambda s: s.start_time)
            return results

    def reserve_slot(self, slot_id: str) -> bool:
        """Atomically reserve a slot, preventing double booking.
        
        Returns True if reservation succeeded, False if already fully booked or unavailable.
        """
        with self._lock:
            slot = self._slots.get(slot_id)
            if not slot:
                return False
            if slot.status != SlotStatus.AVAILABLE:
                return False
            if slot.booked_count >= slot.capacity:
                return False

            new_booked_count = slot.booked_count + 1
            new_status = SlotStatus.BOOKED if new_booked_count >= slot.capacity else SlotStatus.AVAILABLE
            updated_slot = slot.model_copy(
                update={
                    "booked_count": new_booked_count,
                    "status": new_status,
                }
            )
            self._slots[slot_id] = updated_slot
            return True

    def release_slot(self, slot_id: str) -> bool:
        """Atomically release a previously reserved slot."""
        with self._lock:
            slot = self._slots.get(slot_id)
            if not slot:
                return False

            new_booked_count = max(0, slot.booked_count - 1)
            new_status = SlotStatus.AVAILABLE if new_booked_count < slot.capacity else slot.status
            updated_slot = slot.model_copy(
                update={
                    "booked_count": new_booked_count,
                    "status": new_status,
                }
            )
            self._slots[slot_id] = updated_slot
            return True

    def clear(self) -> None:
        """Clear all slots (for testing)."""
        with self._lock:
            self._slots.clear()
