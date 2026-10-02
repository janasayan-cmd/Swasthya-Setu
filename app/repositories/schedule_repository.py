"""Schedule Repository (Phase 31).

Repository for clinician and facility schedule configurations, working hours,
and blocked dates.
"""

from __future__ import annotations

import logging
import threading
from typing import Dict, List, Optional

from app.schemas.schedule import ScheduleRecord

logger = logging.getLogger(__name__)


class ScheduleRepository:
    """Thread-safe repository for persisting schedule configurations."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._schedules: Dict[str, ScheduleRecord] = {}

    def create_or_update(self, schedule: ScheduleRecord) -> ScheduleRecord:
        """Store or update schedule configuration."""
        with self._lock:
            self._schedules[schedule.id] = schedule
            return schedule

    def get(self, schedule_id: str) -> Optional[ScheduleRecord]:
        """Fetch schedule by primary ID."""
        with self._lock:
            return self._schedules.get(schedule_id)

    def get_by_clinician(self, clinician_id: str) -> Optional[ScheduleRecord]:
        """Fetch schedule defined specifically for a clinician."""
        with self._lock:
            for sched in self._schedules.values():
                if sched.clinician_id == clinician_id and sched.is_active:
                    return sched
            return None

    def get_by_facility(self, facility_id: str) -> List[ScheduleRecord]:
        """Fetch all active schedules associated with a facility."""
        with self._lock:
            return [s for s in self._schedules.values() if s.facility_id == facility_id and s.is_active]

    def clear(self) -> None:
        """Clear all schedules (for testing)."""
        with self._lock:
            self._schedules.clear()
