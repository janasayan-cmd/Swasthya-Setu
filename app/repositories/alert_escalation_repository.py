"""Repository for Alert Escalation Records (Phase 35)."""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional
from app.schemas.alert_escalation import EscalationRecord


class AlertEscalationRepository:
    """Thread-safe storage for alert escalation audit records."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._records: Dict[str, EscalationRecord] = {}
        self._by_alert: Dict[str, List[str]] = {}
        self._counter: int = 1

    def _generate_id(self) -> str:
        today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        record_id = f"ESC-{today_str}-{self._counter:04d}"
        self._counter += 1
        return record_id

    def save(self, record: EscalationRecord) -> EscalationRecord:
        """Save an escalation execution record."""
        with self._lock:
            if not record.id:
                record = record.model_copy(update={"id": self._generate_id()})
            self._records[record.id] = record
            if record.alert_id not in self._by_alert:
                self._by_alert[record.alert_id] = []
            if record.id not in self._by_alert[record.alert_id]:
                self._by_alert[record.alert_id].append(record.id)
            return record

    def get_by_id(self, escalation_id: str) -> Optional[EscalationRecord]:
        """Fetch escalation record by ID."""
        with self._lock:
            return self._records.get(escalation_id)

    def list_by_alert_id(self, alert_id: str) -> List[EscalationRecord]:
        """List all escalations that occurred for an alert."""
        with self._lock:
            ids = self._by_alert.get(alert_id, [])
            return [self._records[rec_id] for rec_id in ids if rec_id in self._records]

    def clear(self) -> None:
        """Clear state for test isolation."""
        with self._lock:
            self._records.clear()
            self._by_alert.clear()
            self._counter = 1
