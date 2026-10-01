"""Analytics Repository (Phase 28).

Thread-safe in-memory repository for analytics events, operational aggregates,
and usage anomalies. Follows the HealthSetu database dependency model where
backend repositories encapsulate persistence and provide clear database team contracts.

CRITICAL INVARIANTS:
- Event deduplication by `event_id` (idempotent recording)
- Zero PHI storage
- Failure isolation: database/repository errors must never crash caller
- Pure operational metrics; no clinical evaluation
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from app.schemas.analytics import AnalyticsEvent, AnalyticsFilterParams
from app.schemas.anomaly import AnomalyStatus, UsageAnomaly

logger = logging.getLogger(__name__)


class AnalyticsRepository:
    """Thread-safe repository for storing and querying operational analytics data."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._events: Dict[str, AnalyticsEvent] = {}
        self._anomalies: Dict[str, UsageAnomaly] = {}

    def record_event(self, event: AnalyticsEvent) -> AnalyticsEvent:
        """Record an operational analytics event idempotently by event_id.

        If event_id already exists, it is treated as a duplicate and ignored or updated.
        """
        with self._lock:
            if event.event_id in self._events:
                logger.debug("Duplicate analytics event ignored: %s", event.event_id)
                return self._events[event.event_id]

            self._events[event.event_id] = event
            return event

    def get_event(self, event_id: str) -> Optional[AnalyticsEvent]:
        """Fetch a single event by event_id."""
        with self._lock:
            return self._events.get(event_id)

    def list_events(self, filters: Optional[AnalyticsFilterParams] = None) -> List[AnalyticsEvent]:
        """List events filtered by the given filter parameters."""
        with self._lock:
            events = list(self._events.values())

        if not filters:
            return sorted(events, key=lambda e: e.timestamp, reverse=True)

        filtered: List[AnalyticsEvent] = []
        for ev in events:
            # Time range
            if filters.start_time and ev.timestamp < filters.start_time:
                continue
            if filters.end_time and ev.timestamp > filters.end_time:
                continue

            # Environment
            if filters.environment and ev.environment != filters.environment:
                continue

            # API Version
            if filters.api_version and ev.api_version != filters.api_version:
                continue

            # Endpoint (route pattern)
            if filters.endpoint and ev.endpoint != filters.endpoint:
                continue

            # Status code
            if filters.status and ev.status != filters.status:
                continue

            # Feature
            if filters.feature and ev.feature_name != filters.feature:
                continue

            # Provider
            if filters.provider and ev.provider_name != filters.provider:
                continue

            # Job Type
            if filters.job_type and ev.job_type != filters.job_type:
                continue

            # Organization
            if filters.organization_id and ev.organization_id != filters.organization_id:
                continue

            # Facility
            if filters.facility_id and ev.facility_id != filters.facility_id:
                continue

            # Event type
            if filters.event_type and ev.event_type != filters.event_type:
                continue

            filtered.append(ev)

        # Sort descending by timestamp
        filtered.sort(key=lambda e: e.timestamp, reverse=True)

        # Pagination
        offset = filters.offset
        limit = filters.limit
        return filtered[offset : offset + limit]

    def count_events(self, filters: Optional[AnalyticsFilterParams] = None) -> int:
        """Count total events matching the filter parameters."""
        with self._lock:
            if not filters:
                return len(self._events)

            # Return count matching filters without slice
            count = 0
            for ev in self._events.values():
                if filters.start_time and ev.timestamp < filters.start_time:
                    continue
                if filters.end_time and ev.timestamp > filters.end_time:
                    continue
                if filters.environment and ev.environment != filters.environment:
                    continue
                if filters.api_version and ev.api_version != filters.api_version:
                    continue
                if filters.endpoint and ev.endpoint != filters.endpoint:
                    continue
                if filters.status and ev.status != filters.status:
                    continue
                if filters.feature and ev.feature_name != filters.feature:
                    continue
                if filters.provider and ev.provider_name != filters.provider:
                    continue
                if filters.job_type and ev.job_type != filters.job_type:
                    continue
                if filters.organization_id and ev.organization_id != filters.organization_id:
                    continue
                if filters.facility_id and ev.facility_id != filters.facility_id:
                    continue
                if filters.event_type and ev.event_type != filters.event_type:
                    continue
                count += 1
            return count

    def record_anomaly(self, anomaly: UsageAnomaly) -> UsageAnomaly:
        """Record an operational anomaly."""
        with self._lock:
            self._anomalies[anomaly.anomaly_id] = anomaly
            return anomaly

    def get_anomaly(self, anomaly_id: str) -> Optional[UsageAnomaly]:
        """Fetch an anomaly by anomaly_id."""
        with self._lock:
            return self._anomalies.get(anomaly_id)

    def update_anomaly(
        self,
        anomaly_id: str,
        status: AnomalyStatus,
        acknowledged_by: Optional[str] = None,
        resolution_notes: Optional[str] = None,
    ) -> Optional[UsageAnomaly]:
        """Update an anomaly status (acknowledge or resolve)."""
        with self._lock:
            anomaly = self._anomalies.get(anomaly_id)
            if not anomaly:
                return None

            anomaly.status = status
            now = datetime.now(timezone.utc)
            if status == AnomalyStatus.ACKNOWLEDGED:
                anomaly.acknowledged_at = now
                anomaly.acknowledged_by = acknowledged_by
            elif status == AnomalyStatus.RESOLVED:
                anomaly.resolved_at = now
                anomaly.resolution_notes = resolution_notes

            return anomaly

    def list_anomalies(
        self,
        status: Optional[AnomalyStatus] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        offset: int = 0,
        limit: int = 50,
    ) -> List[UsageAnomaly]:
        """List recorded anomalies matching query criteria."""
        with self._lock:
            anomalies = list(self._anomalies.values())

        filtered: List[UsageAnomaly] = []
        for an in anomalies:
            if status and an.status != status:
                continue
            if start_time and an.detected_at < start_time:
                continue
            if end_time and an.detected_at > end_time:
                continue
            filtered.append(an)

        filtered.sort(key=lambda a: a.detected_at, reverse=True)
        return filtered[offset : offset + limit]

    def count_anomalies(self, status: Optional[AnomalyStatus] = None) -> int:
        """Count anomalies by status."""
        with self._lock:
            if not status:
                return len(self._anomalies)
            return sum(1 for a in self._anomalies.values() if a.status == status)

    def prune_retention(self, retention_days: int) -> int:
        """Prune events older than the specified retention days.

        Returns number of deleted events.
        """
        if retention_days <= 0:
            return 0

        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        deleted_count = 0
        with self._lock:
            keys_to_remove = [
                eid for eid, ev in self._events.items() if ev.timestamp < cutoff
            ]
            for eid in keys_to_remove:
                del self._events[eid]
                deleted_count += 1

        logger.info("Pruned %d analytics events older than %d days", deleted_count, retention_days)
        return deleted_count

    def clear(self) -> None:
        """Clear all in-memory events and anomalies (used in testing)."""
        with self._lock:
            self._events.clear()
            self._anomalies.clear()
