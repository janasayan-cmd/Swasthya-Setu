"""Claim Reconciliation Repository (Phase 33).

Thread-safe repository for claim reconciliation findings and discrepancies.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from app.schemas.claim_reconciliation import (
    ClaimDiscrepancyType,
    ClaimReconciliationRecord,
    ClaimReconciliationStatus,
)

logger = logging.getLogger(__name__)


class ClaimReconciliationRepository:
    """Thread-safe repository for persisting and resolving claim reconciliation records."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._records: Dict[str, ClaimReconciliationRecord] = {}

    def create(self, record: ClaimReconciliationRecord) -> ClaimReconciliationRecord:
        """Persist a new reconciliation finding."""
        with self._lock:
            self._records[record.id] = record
            return record

    def get(self, rec_id: str) -> Optional[ClaimReconciliationRecord]:
        """Fetch reconciliation record by ID."""
        with self._lock:
            return self._records.get(rec_id)

    def get_by_claim(self, claim_id: str) -> Optional[ClaimReconciliationRecord]:
        """Fetch latest reconciliation record for a claim."""
        with self._lock:
            matches = [r for r in self._records.values() if r.claim_id == claim_id]
            if not matches:
                return None
            matches.sort(key=lambda r: r.created_at, reverse=True)
            return matches[0]

    def update(self, record: ClaimReconciliationRecord) -> ClaimReconciliationRecord:
        """Update existing reconciliation record."""
        with self._lock:
            self._records[record.id] = record
            return record

    def list_all(
        self,
        status: Optional[ClaimReconciliationStatus] = None,
        discrepancy_type: Optional[ClaimDiscrepancyType] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[ClaimReconciliationRecord], int]:
        """List reconciliation records with optional status/discrepancy filtering."""
        with self._lock:
            records = [
                r for r in self._records.values()
                if (status is None or r.status == status)
                and (discrepancy_type is None or r.discrepancy_type == discrepancy_type)
            ]
            records.sort(key=lambda r: r.created_at, reverse=True)
            total = len(records)
            return records[offset : offset + limit], total
