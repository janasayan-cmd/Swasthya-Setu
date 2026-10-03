"""Insurance Coverage Repository (Phase 33).

Thread-safe repository managing patient insurance coverage persistence and lookup.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from app.schemas.insurance import CoverageStatus, InsuranceCoverageRecord

logger = logging.getLogger(__name__)


class InsuranceRepository:
    """Thread-safe in-memory/cache repository for patient insurance policies."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._coverages: Dict[str, InsuranceCoverageRecord] = {}

    def create(self, coverage: InsuranceCoverageRecord) -> InsuranceCoverageRecord:
        """Persist a new insurance coverage record."""
        with self._lock:
            # If marked as primary, demote existing primary policies for same patient
            if coverage.is_primary:
                for existing in self._coverages.values():
                    if existing.patient_id == coverage.patient_id and existing.id != coverage.id:
                        existing.is_primary = False
                        existing.updated_at = datetime.now(timezone.utc)
            self._coverages[coverage.id] = coverage
            return coverage

    def get(self, coverage_id: str) -> Optional[InsuranceCoverageRecord]:
        """Fetch coverage record by primary ID."""
        with self._lock:
            return self._coverages.get(coverage_id)

    def update(self, coverage: InsuranceCoverageRecord) -> InsuranceCoverageRecord:
        """Update existing insurance coverage record."""
        with self._lock:
            coverage.updated_at = datetime.now(timezone.utc)
            if coverage.is_primary:
                for existing in self._coverages.values():
                    if existing.patient_id == coverage.patient_id and existing.id != coverage.id:
                        existing.is_primary = False
                        existing.updated_at = datetime.now(timezone.utc)
            self._coverages[coverage.id] = coverage
            return coverage

    def delete(self, coverage_id: str) -> bool:
        """Delete coverage record."""
        with self._lock:
            if coverage_id in self._coverages:
                del self._coverages[coverage_id]
                return True
            return False

    def list_by_patient(
        self,
        patient_id: str,
        status: Optional[CoverageStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[InsuranceCoverageRecord], int]:
        """List coverage policies registered for a patient with optional status filtering."""
        with self._lock:
            records = [
                cov for cov in self._coverages.values()
                if cov.patient_id == patient_id
                and (status is None or cov.status == status)
            ]
            # Primary policies first, then newest
            records.sort(key=lambda r: (not r.is_primary, r.created_at), reverse=False)
            total = len(records)
            return records[offset : offset + limit], total

    def get_primary(self, patient_id: str) -> Optional[InsuranceCoverageRecord]:
        """Fetch patient's primary active policy if available."""
        with self._lock:
            for cov in self._coverages.values():
                if cov.patient_id == patient_id and cov.is_primary:
                    return cov
            # Fallback to any active policy
            for cov in self._coverages.values():
                if cov.patient_id == patient_id and cov.status == CoverageStatus.ACTIVE:
                    return cov
            return None

    def list_all(
        self,
        payer_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[InsuranceCoverageRecord], int]:
        """Admin query listing coverage across all patients."""
        with self._lock:
            records = [
                cov for cov in self._coverages.values()
                if payer_id is None or cov.payer_id == payer_id
            ]
            records.sort(key=lambda r: r.created_at, reverse=True)
            total = len(records)
            return records[offset : offset + limit], total
