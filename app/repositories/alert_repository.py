"""In-memory thread-safe repository for Clinical Alerts and Alert History (Phase 35).

Consumes existing database contracts; does not create competing database schemas or migrations.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple
from app.schemas.alert import AlertFilter, AlertRecord, AlertStatus
from app.schemas.alert_history import AlertHistoryEntry


class AlertRepository:
    """Thread-safe storage for alerts and immutable lifecycle transitions."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._alerts: Dict[str, AlertRecord] = {}
        # Index: (source_event_type, source_event_id) -> alert_id (for idempotency)
        self._source_event_index: Dict[Tuple[str, str], str] = {}
        # History index: alert_id -> list of AlertHistoryEntry
        self._history: Dict[str, List[AlertHistoryEntry]] = {}
        self._counter: int = 1

    def _generate_alert_id(self) -> str:
        today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        alert_id = f"ALT-{today_str}-{self._counter:04d}"
        self._counter += 1
        return alert_id

    def save(self, alert: AlertRecord) -> AlertRecord:
        """Create or update an alert record."""
        with self._lock:
            if not alert.id:
                alert = alert.model_copy(update={"id": self._generate_alert_id()})
            self._alerts[alert.id] = alert
            if alert.provenance and alert.provenance.source_event_type and alert.provenance.source_event_id:
                key = (alert.provenance.source_event_type, alert.provenance.source_event_id)
                self._source_event_index[key] = alert.id
            return alert

    def get_by_id(self, alert_id: str) -> Optional[AlertRecord]:
        """Fetch alert by unique ID."""
        with self._lock:
            return self._alerts.get(alert_id)

    def get_by_source_event(self, source_event_type: str, source_event_id: str) -> Optional[AlertRecord]:
        """Retrieve existing alert by authoritative source event identity for idempotency."""
        with self._lock:
            alert_id = self._source_event_index.get((source_event_type, source_event_id))
            if alert_id:
                return self._alerts.get(alert_id)
            return None

    def list_alerts(
        self,
        filters: AlertFilter,
        allowed_patient_ids: Optional[Set[str]] = None,
        recipient_user_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        facility_id: Optional[str] = None,
    ) -> Tuple[List[AlertRecord], int]:
        """List alerts with filtering, multi-tenant boundaries, and pagination."""
        with self._lock:
            results = list(self._alerts.values())

            # Multi-tenant boundary
            if organization_id:
                results = [a for a in results if a.organization_id == organization_id or a.organization_id is None]
            if facility_id:
                results = [a for a in results if a.facility_id == facility_id or a.facility_id is None]

            # Patient-level authorization boundary
            if allowed_patient_ids is not None:
                results = [a for a in results if a.patient_id in allowed_patient_ids]

            # Recipient matching (clinician or user inbox)
            if recipient_user_id:
                results = [
                    a for a in results
                    if any(r.recipient_id == recipient_user_id for r in a.recipients)
                ]

            # Query filters
            if filters.status:
                results = [a for a in results if a.status == filters.status]
            if filters.severity:
                results = [a for a in results if a.severity == filters.severity]
            if filters.category:
                results = [a for a in results if a.category == filters.category]
            if filters.patient_id:
                results = [a for a in results if a.patient_id == filters.patient_id]
            if filters.source_resource_type:
                results = [a for a in results if a.provenance.source_resource_type == filters.source_resource_type]
            if filters.source_resource_id:
                results = [a for a in results if a.provenance.source_resource_id == filters.source_resource_id]
            if filters.requires_acknowledgement is not None:
                results = [a for a in results if a.requires_acknowledgement == filters.requires_acknowledgement]
            if filters.created_from:
                results = [a for a in results if a.created_at >= filters.created_from]
            if filters.created_to:
                results = [a for a in results if a.created_at <= filters.created_to]

            # Sort descending by created_at
            results.sort(key=lambda a: a.created_at, reverse=True)

            total = len(results)
            start_idx = (filters.page - 1) * filters.page_size
            end_idx = start_idx + filters.page_size
            paged_items = results[start_idx:end_idx]

            return paged_items, total

    def add_history(self, entry: AlertHistoryEntry) -> AlertHistoryEntry:
        """Append an immutable audit/history entry."""
        with self._lock:
            if not entry.id:
                hist_id = f"ALH-{len(self._history.get(entry.alert_id, [])) + 1:04d}"
                entry = entry.model_copy(update={"id": hist_id})
            if entry.alert_id not in self._history:
                self._history[entry.alert_id] = []
            self._history[entry.alert_id].append(entry)
            return entry

    def get_history(self, alert_id: str) -> List[AlertHistoryEntry]:
        """Fetch chronological history transitions for an alert."""
        with self._lock:
            return list(self._history.get(alert_id, []))

    def clear(self) -> None:
        """Clear state for test isolation."""
        with self._lock:
            self._alerts.clear()
            self._source_event_index.clear()
            self._history.clear()
            self._counter = 1
