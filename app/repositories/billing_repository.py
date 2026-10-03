"""Billing Repository (Phase 32).

Thread-safe repository for billable events and billing entities.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from app.schemas.billing_item import BillableEventRecord, BillingItemCategory

logger = logging.getLogger(__name__)


class BillingRepository:
    """Thread-safe repository managing billable event persistence and querying."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._billable_events: Dict[str, BillableEventRecord] = {}

    def create_event(self, event: BillableEventRecord) -> BillableEventRecord:
        """Persist a new billable event."""
        with self._lock:
            self._billable_events[event.id] = event
            return event

    def get_event(self, event_id: str) -> Optional[BillableEventRecord]:
        """Fetch a billable event by ID."""
        with self._lock:
            return self._billable_events.get(event_id)

    def get_by_source(self, source_type: str, source_id: str) -> Optional[BillableEventRecord]:
        """Lookup billable event linked to a specific domain source (e.g. appointment)."""
        with self._lock:
            for event in self._billable_events.values():
                if event.source_type == source_type and event.source_id == source_id:
                    return event
            return None

    def mark_event_billed(self, event_id: str, invoice_id: str) -> Optional[BillableEventRecord]:
        """Mark billable event as attached to an invoice."""
        with self._lock:
            event = self._billable_events.get(event_id)
            if not event:
                return None
            updated = event.model_copy(update={"is_billed": True, "invoice_id": invoice_id})
            self._billable_events[event_id] = updated
            return updated

    def list_by_patient(
        self,
        patient_id: str,
        is_billed: Optional[bool] = None,
        category: Optional[BillingItemCategory] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[BillableEventRecord], int]:
        """List billable events for a patient with optional billed filter."""
        with self._lock:
            matching = [
                e for e in self._billable_events.values()
                if e.patient_id == patient_id
                and (is_billed is None or e.is_billed == is_billed)
                and (category is None or e.category == category)
            ]
            matching.sort(key=lambda x: x.created_at, reverse=True)
            total = len(matching)
            return matching[offset : offset + limit], total
