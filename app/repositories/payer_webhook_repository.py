"""Payer Webhook Event Repository (Phase 33).

Thread-safe repository for deduplicating, verifying, and logging inbound payer webhook events.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from app.schemas.payer_webhook import PayerWebhookEventRecord, PayerWebhookEventStatus

logger = logging.getLogger(__name__)


class PayerWebhookRepository:
    """Thread-safe repository tracking received payer gateway webhook events."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._events: Dict[str, PayerWebhookEventRecord] = {}

    def get_by_provider_event(self, provider_name: str, event_id: str) -> Optional[PayerWebhookEventRecord]:
        """Fetch previously ingested event to detect duplicates and replay attacks."""
        with self._lock:
            key = f"{provider_name.upper()}:{event_id}"
            return self._events.get(key)

    def record_event(self, record: PayerWebhookEventRecord) -> PayerWebhookEventRecord:
        """Persist a new webhook event log."""
        with self._lock:
            key = f"{record.provider_name.upper()}:{record.event_id}"
            self._events[key] = record
            return record

    def list_recent(
        self,
        provider_name: Optional[str] = None,
        limit: int = 50,
    ) -> List[PayerWebhookEventRecord]:
        """Retrieve recent webhook logs for operational audit."""
        with self._lock:
            records = [
                ev for ev in self._events.values()
                if provider_name is None or ev.provider_name.upper() == provider_name.upper()
            ]
            records.sort(key=lambda r: r.created_at, reverse=True)
            return records[:limit]
