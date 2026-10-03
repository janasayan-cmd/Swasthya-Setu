"""Claim Repository (Phase 33).

Thread-safe repository for medical claims, line items, and lifecycle states.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from app.schemas.claim import ClaimRecord, ClaimStatus

logger = logging.getLogger(__name__)


class ClaimRepository:
    """Thread-safe repository for insurance claims."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._claims: Dict[str, ClaimRecord] = {}
        self._sequence: int = 1000

    def _next_claim_number(self) -> str:
        self._sequence += 1
        today = datetime.now(timezone.utc).strftime("%Y%m%d")
        return f"CLM-{today}-{self._sequence:04d}"

    def create(self, claim: ClaimRecord) -> ClaimRecord:
        """Persist a new claim record."""
        with self._lock:
            if not claim.claim_number:
                claim.claim_number = self._next_claim_number()
            self._claims[claim.id] = claim
            return claim

    def get(self, claim_id: str) -> Optional[ClaimRecord]:
        """Fetch claim by primary ID."""
        with self._lock:
            return self._claims.get(claim_id)

    def get_by_number(self, claim_number: str) -> Optional[ClaimRecord]:
        """Fetch claim by sequential claim number."""
        with self._lock:
            for c in self._claims.values():
                if c.claim_number == claim_number:
                    return c
            return None

    def get_by_provider_reference(self, provider_claim_reference: str) -> Optional[ClaimRecord]:
        """Fetch claim by external payer clearinghouse reference."""
        with self._lock:
            for c in self._claims.values():
                if c.provider_claim_reference == provider_claim_reference:
                    return c
            return None

    def get_by_idempotency_key(self, idempotency_key: str) -> Optional[ClaimRecord]:
        """Fetch claim by submission idempotency key."""
        with self._lock:
            for c in self._claims.values():
                if c.idempotency_key == idempotency_key:
                    return c
            return None

    def update(self, claim: ClaimRecord) -> ClaimRecord:
        """Update existing claim record."""
        with self._lock:
            claim.updated_at = datetime.now(timezone.utc)
            self._claims[claim.id] = claim
            return claim

    def list_by_patient(
        self,
        patient_id: str,
        status: Optional[ClaimStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[ClaimRecord], int]:
        """List claims filed for a patient with optional status filtering."""
        with self._lock:
            records = [
                c for c in self._claims.values()
                if c.patient_id == patient_id
                and (status is None or c.status == status)
            ]
            records.sort(key=lambda r: r.created_at, reverse=True)
            total = len(records)
            return records[offset : offset + limit], total

    def list_by_invoice(self, invoice_id: str) -> List[ClaimRecord]:
        """List claims linked to a Phase 32 invoice."""
        with self._lock:
            return [c for c in self._claims.values() if c.invoice_id == invoice_id]

    def list_all(
        self,
        facility_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        status: Optional[ClaimStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[ClaimRecord], int]:
        """Administrative search across all claims."""
        with self._lock:
            records = [
                c for c in self._claims.values()
                if (facility_id is None or c.facility_id == facility_id)
                and (organization_id is None or c.organization_id == organization_id)
                and (status is None or c.status == status)
            ]
            records.sort(key=lambda r: r.created_at, reverse=True)
            total = len(records)
            return records[offset : offset + limit], total
