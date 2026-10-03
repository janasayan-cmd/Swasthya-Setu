"""Payment Repository (Phase 32).

Thread-safe repository for payment transactions, idempotency indexing,
and webhook event deduplication.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from app.schemas.payment import PaymentRecord, PaymentStatus
from app.schemas.payment_webhook import WebhookEventRecord

logger = logging.getLogger(__name__)


class PaymentRepository:
    """Thread-safe repository managing payment transactions and idempotency."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._payments: Dict[str, PaymentRecord] = {}
        self._idempotency_index: Dict[str, str] = {}  # idempotency_key -> payment_id
        self._provider_tx_index: Dict[str, str] = {}  # provider_transaction_id -> payment_id
        self._webhook_events: Dict[str, WebhookEventRecord] = {}
        self._webhook_dedup_index: Dict[str, str] = {}  # f"{provider}:{event_id}" -> event_record_id
        self._sequence: int = 1000

    def _next_payment_number(self) -> str:
        """Generate human-readable payment reference."""
        self._sequence += 1
        today = datetime.now(timezone.utc).strftime("%Y%m%d")
        return f"PAY-{today}-{self._sequence:04d}"

    def create(self, payment: PaymentRecord) -> PaymentRecord:
        """Persist a new payment record and index idempotency/provider keys."""
        with self._lock:
            if not payment.payment_number:
                payment.payment_number = self._next_payment_number()
            self._payments[payment.id] = payment
            if payment.idempotency_key:
                self._idempotency_index[payment.idempotency_key] = payment.id
            if payment.provider_transaction_id:
                self._provider_tx_index[payment.provider_transaction_id] = payment.id
            return payment

    def get(self, payment_id: str) -> Optional[PaymentRecord]:
        """Fetch payment by ID."""
        with self._lock:
            return self._payments.get(payment_id)

    def get_by_idempotency_key(self, idempotency_key: str) -> Optional[PaymentRecord]:
        """Fetch payment by idempotency key."""
        with self._lock:
            payment_id = self._idempotency_index.get(idempotency_key)
            if payment_id:
                return self._payments.get(payment_id)
            return None

    def get_by_provider_transaction_id(self, provider_tx_id: str) -> Optional[PaymentRecord]:
        """Fetch payment by provider transaction ID."""
        with self._lock:
            payment_id = self._provider_tx_index.get(provider_tx_id)
            if payment_id:
                return self._payments.get(payment_id)
            return None

    def update(self, payment: PaymentRecord) -> PaymentRecord:
        """Update existing payment record."""
        with self._lock:
            payment.updated_at = datetime.now(timezone.utc)
            self._payments[payment.id] = payment
            if payment.provider_transaction_id:
                self._provider_tx_index[payment.provider_transaction_id] = payment.id
            return payment

    def list_by_invoice(self, invoice_id: str) -> List[PaymentRecord]:
        """List all payment attempts/transactions for an invoice."""
        with self._lock:
            matching = [p for p in self._payments.values() if p.invoice_id == invoice_id]
            matching.sort(key=lambda x: x.created_at, reverse=True)
            return matching

    def list_by_patient(
        self,
        patient_id: str,
        status: Optional[PaymentStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[PaymentRecord], int]:
        """List payments for a patient."""
        with self._lock:
            matching = [
                p for p in self._payments.values()
                if p.patient_id == patient_id
                and (status is None or p.status == status)
            ]
            matching.sort(key=lambda x: x.created_at, reverse=True)
            total = len(matching)
            return matching[offset : offset + limit], total

    def list_by_organization(
        self,
        organization_id: str,
        status: Optional[PaymentStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[PaymentRecord], int]:
        """List payments for an organization."""
        with self._lock:
            matching = [
                p for p in self._payments.values()
                if p.organization_id == organization_id
                and (status is None or p.status == status)
            ]
            matching.sort(key=lambda x: x.created_at, reverse=True)
            total = len(matching)
            return matching[offset : offset + limit], total

    def list_by_facility(
        self,
        facility_id: str,
        status: Optional[PaymentStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[PaymentRecord], int]:
        """List payments for a facility."""
        with self._lock:
            matching = [
                p for p in self._payments.values()
                if p.facility_id == facility_id
                and (status is None or p.status == status)
            ]
            matching.sort(key=lambda x: x.created_at, reverse=True)
            total = len(matching)
            return matching[offset : offset + limit], total

    def list_all(
        self,
        status: Optional[PaymentStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[PaymentRecord], int]:
        """Admin listing of all payments."""
        with self._lock:
            matching = [
                p for p in self._payments.values()
                if (status is None or p.status == status)
            ]
            matching.sort(key=lambda x: x.created_at, reverse=True)
            total = len(matching)
            return matching[offset : offset + limit], total

    # Webhook event persistence & deduplication
    def save_webhook_event(self, event: WebhookEventRecord) -> WebhookEventRecord:
        """Persist inbound webhook event and index provider:event_id."""
        with self._lock:
            self._webhook_events[event.id] = event
            key = f"{event.provider}:{event.event_id}"
            self._webhook_dedup_index[key] = event.id
            return event

    def get_webhook_event(self, provider: str, event_id: str) -> Optional[WebhookEventRecord]:
        """Check if provider event was already received."""
        with self._lock:
            key = f"{provider}:{event_id}"
            rec_id = self._webhook_dedup_index.get(key)
            if rec_id:
                return self._webhook_events.get(rec_id)
            return None

    def update_webhook_event(self, event: WebhookEventRecord) -> WebhookEventRecord:
        """Update webhook event status."""
        with self._lock:
            self._webhook_events[event.id] = event
            return event
