"""Eligibility Verification Repository (Phase 33).

Thread-safe repository for eligibility check histories and results.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from app.schemas.eligibility import EligibilityCheckRecord, EligibilityStatus

logger = logging.getLogger(__name__)


class EligibilityRepository:
    """Thread-safe repository managing eligibility verification records."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._checks: Dict[str, EligibilityCheckRecord] = {}

    def create(self, record: EligibilityCheckRecord) -> EligibilityCheckRecord:
        """Persist a new eligibility verification record."""
        with self._lock:
            self._checks[record.id] = record
            return record

    def get(self, check_id: str) -> Optional[EligibilityCheckRecord]:
        """Fetch eligibility check record by ID."""
        with self._lock:
            return self._checks.get(check_id)

    def list_by_patient(
        self,
        patient_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[EligibilityCheckRecord], int]:
        """List eligibility checks performed for a patient."""
        with self._lock:
            records = [c for c in self._checks.values() if c.patient_id == patient_id]
            records.sort(key=lambda r: r.verification_timestamp, reverse=True)
            total = len(records)
            return records[offset : offset + limit], total

    def list_by_coverage(
        self,
        coverage_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[EligibilityCheckRecord], int]:
        """List eligibility inquiries conducted under a coverage ID."""
        with self._lock:
            records = [c for c in self._checks.values() if c.coverage_id == coverage_id]
            records.sort(key=lambda r: r.verification_timestamp, reverse=True)
            total = len(records)
            return records[offset : offset + limit], total

    def get_latest_for_coverage(self, coverage_id: str) -> Optional[EligibilityCheckRecord]:
        """Retrieve most recent point-in-time check for coverage."""
        with self._lock:
            records = [c for c in self._checks.values() if c.coverage_id == coverage_id]
            if not records:
                return None
            records.sort(key=lambda r: r.verification_timestamp, reverse=True)
            return records[0]
