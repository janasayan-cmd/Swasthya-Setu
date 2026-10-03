"""Insurance Benefit Repository (Phase 33).

Thread-safe repository for benefit breakdown records and caching.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from app.schemas.benefits import BenefitRecord

logger = logging.getLogger(__name__)


class BenefitRepository:
    """Thread-safe repository for persisting and querying benefit inquiry results."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._benefits: Dict[str, BenefitRecord] = {}

    def create(self, record: BenefitRecord) -> BenefitRecord:
        """Persist a new benefit record."""
        with self._lock:
            self._benefits[record.id] = record
            return record

    def get(self, benefit_id: str) -> Optional[BenefitRecord]:
        """Fetch benefit record by ID."""
        with self._lock:
            return self._benefits.get(benefit_id)

    def get_latest_for_coverage(self, coverage_id: str) -> Optional[BenefitRecord]:
        """Retrieve most recent benefit schedule returned for a policy."""
        with self._lock:
            records = [b for b in self._benefits.values() if b.coverage_id == coverage_id]
            if not records:
                return None
            records.sort(key=lambda r: r.response_timestamp, reverse=True)
            return records[0]

    def list_by_patient(
        self,
        patient_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[BenefitRecord], int]:
        """List benefit inquiries for a patient."""
        with self._lock:
            records = [b for b in self._benefits.values() if b.patient_id == patient_id]
            records.sort(key=lambda r: r.response_timestamp, reverse=True)
            total = len(records)
            return records[offset : offset + limit], total
