"""Diagnostic Webhook Repository (Phase 34).

Thread-safe event deduplication and replay protection repository for external laboratory webhooks.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.schemas.diagnostic_webhook import DiagnosticWebhookPayload


class DiagnosticWebhookRepository:
    """Thread-safe storage for received webhooks preventing replay attacks."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._events: Dict[str, DiagnosticWebhookPayload] = {}  # event_key -> payload
        self._timestamps: Dict[str, datetime] = {}

    def _make_key(self, provider_id: str, event_id: str) -> str:
        return f"{provider_id}:{event_id}"

    def has_event(self, provider_id: str, event_id: str) -> bool:
        with self._lock:
            key = self._make_key(provider_id, event_id)
            return key in self._events

    def record_event(self, payload: DiagnosticWebhookPayload) -> bool:
        """Record event if not already present. Returns True if recorded, False if duplicate."""
        with self._lock:
            key = self._make_key(payload.provider_id, payload.event_id)
            if key in self._events:
                return False
            self._events[key] = payload
            self._timestamps[key] = datetime.now(timezone.utc)
            return True

    def get_event(self, provider_id: str, event_id: str) -> Optional[DiagnosticWebhookPayload]:
        with self._lock:
            key = self._make_key(provider_id, event_id)
            return self._events.get(key)
