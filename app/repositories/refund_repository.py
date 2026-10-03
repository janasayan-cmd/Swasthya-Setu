"""Refund Repository (Phase 32).

Thread-safe repository for refund transactions, idempotency tracking,
and refund state persistence.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from app.schemas.refund import RefundRecord, RefundStatus

logger = logging.getLogger(__name__)


class RefundRepository:
    """Thread-safe repository managing refund transactions."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._refunds: Dict[str, RefundRecord] = {}
        self._idempotency_index: Dict[str, str] = {}  # idempotency_key -> refund_id
        self._sequence: int = 1000

    def _next_refund_number(self) -> str:
        """Generate human-readable refund reference."""
        self._sequence += 1
        today = datetime.now(timezone.utc).strftime("%Y%m%d")
        return f"REF-{today}-{self._sequence:04d}"

    def create(self, refund: RefundRecord) -> RefundRecord:
        """Persist a new refund record and index idempotency."""
        with self._lock:
            if not refund.refund_number:
                refund.refund_number = self._next_refund_number()
            self._refunds[refund.id] = refund
            if refund.idempotency_key:
                self._idempotency_index[refund.idempotency_key] = refund.id
            return refund

    def get(self, refund_id: str) -> Optional[RefundRecord]:
        """Fetch refund by ID."""
        with self._lock:
            return self._refunds.get(refund_id)

    def get_by_idempotency_key(self, idempotency_key: str) -> Optional[RefundRecord]:
        """Fetch refund by idempotency key."""
        with self._lock:
            refund_id = self._idempotency_index.get(idempotency_key)
            if refund_id:
                return self._refunds.get(refund_id)
            return None

    def update(self, refund: RefundRecord) -> RefundRecord:
        """Update existing refund record."""
        with self._lock:
            refund.updated_at = datetime.now(timezone.utc)
            self._refunds[refund.id] = refund
            return refund

    def list_by_payment(self, payment_id: str) -> List[RefundRecord]:
        """List all refunds associated with a payment."""
        with self._lock:
            matching = [r for r in self._refunds.values() if r.payment_id == payment_id]
            matching.sort(key=lambda x: x.created_at, reverse=True)
            return matching

    def list_by_patient(
        self,
        patient_id: str,
        status: Optional[RefundStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[RefundRecord], int]:
        """List refunds for a patient."""
        with self._lock:
            matching = [
                r for r in self._refunds.values()
                if r.patient_id == patient_id
                and (status is None or r.status == status)
            ]
            matching.sort(key=lambda x: x.created_at, reverse=True)
            total = len(matching)
            return matching[offset : offset + limit], total

    def list_all(
        self,
        status: Optional[RefundStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[RefundRecord], int]:
        """Admin listing of all refunds."""
        with self._lock:
            matching = [
                r for r in self._refunds.values()
                if (status is None or r.status == status)
            ]
            matching.sort(key=lambda x: x.created_at, reverse=True)
            total = len(matching)
            return matching[offset : offset + limit], total
