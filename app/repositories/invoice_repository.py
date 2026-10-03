"""Invoice Repository (Phase 32).

Thread-safe repository for invoices, items, and state persistence.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from app.schemas.invoice import InvoiceRecord, InvoiceStatus

logger = logging.getLogger(__name__)


class InvoiceRepository:
    """Thread-safe repository managing invoice persistence and querying."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._invoices: Dict[str, InvoiceRecord] = {}
        self._sequence: int = 1000

    def _next_invoice_number(self) -> str:
        """Generate human-readable sequential invoice number."""
        self._sequence += 1
        today = datetime.now(timezone.utc).strftime("%Y%m%d")
        return f"INV-{today}-{self._sequence:04d}"

    def create(self, invoice: InvoiceRecord) -> InvoiceRecord:
        """Persist a new invoice record."""
        with self._lock:
            if not invoice.invoice_number:
                invoice.invoice_number = self._next_invoice_number()
            self._invoices[invoice.id] = invoice
            return invoice

    def get(self, invoice_id: str) -> Optional[InvoiceRecord]:
        """Fetch invoice by primary ID."""
        with self._lock:
            return self._invoices.get(invoice_id)

    def get_by_number(self, invoice_number: str) -> Optional[InvoiceRecord]:
        """Fetch invoice by human-readable invoice number."""
        with self._lock:
            for inv in self._invoices.values():
                if inv.invoice_number == invoice_number:
                    return inv
            return None

    def update(self, invoice: InvoiceRecord) -> InvoiceRecord:
        """Update an existing invoice record."""
        with self._lock:
            invoice.updated_at = datetime.now(timezone.utc)
            self._invoices[invoice.id] = invoice
            return invoice

    def list_by_patient(
        self,
        patient_id: str,
        status: Optional[InvoiceStatus] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[InvoiceRecord], int]:
        """List invoices for a given patient."""
        with self._lock:
            matching = [
                inv for inv in self._invoices.values()
                if inv.patient_id == patient_id
                and (status is None or inv.status == status)
                and (from_date is None or inv.created_at >= from_date)
                and (to_date is None or inv.created_at <= to_date)
            ]
            matching.sort(key=lambda x: x.created_at, reverse=True)
            total = len(matching)
            return matching[offset : offset + limit], total

    def list_by_organization(
        self,
        organization_id: str,
        status: Optional[InvoiceStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[InvoiceRecord], int]:
        """List invoices for a given organization."""
        with self._lock:
            matching = [
                inv for inv in self._invoices.values()
                if inv.organization_id == organization_id
                and (status is None or inv.status == status)
            ]
            matching.sort(key=lambda x: x.created_at, reverse=True)
            total = len(matching)
            return matching[offset : offset + limit], total

    def list_by_facility(
        self,
        facility_id: str,
        status: Optional[InvoiceStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[InvoiceRecord], int]:
        """List invoices for a given facility."""
        with self._lock:
            matching = [
                inv for inv in self._invoices.values()
                if inv.facility_id == facility_id
                and (status is None or inv.status == status)
            ]
            matching.sort(key=lambda x: x.created_at, reverse=True)
            total = len(matching)
            return matching[offset : offset + limit], total

    def list_all(
        self,
        status: Optional[InvoiceStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[InvoiceRecord], int]:
        """Administrative invoice listing."""
        with self._lock:
            matching = [
                inv for inv in self._invoices.values()
                if (status is None or inv.status == status)
            ]
            matching.sort(key=lambda x: x.created_at, reverse=True)
            total = len(matching)
            return matching[offset : offset + limit], total
