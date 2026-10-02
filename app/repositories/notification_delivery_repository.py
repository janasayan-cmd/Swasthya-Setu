"""Notification Delivery Repository (Phase 29).

Tracks channel-specific delivery attempts, normalized statuses, provider references,
and failure categories. Thread-safe in-memory store adhering to DB contracts.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from app.schemas.notification_delivery import DeliveryStatus, NotificationDelivery

logger = logging.getLogger(__name__)


class NotificationDeliveryRepository:
    """Thread-safe repository for persisting and querying delivery attempts."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._deliveries: Dict[str, NotificationDelivery] = {}
        self._by_notification: Dict[str, List[str]] = {}  # notification_id -> [delivery_id, ...]

    def create_delivery(self, delivery: NotificationDelivery) -> NotificationDelivery:
        """Persist a new delivery attempt."""
        with self._lock:
            self._deliveries[delivery.id] = delivery
            self._by_notification.setdefault(delivery.notification_id, []).append(delivery.id)
            return delivery

    def get_delivery(self, delivery_id: str) -> Optional[NotificationDelivery]:
        """Fetch delivery attempt by ID."""
        with self._lock:
            return self._deliveries.get(delivery_id)

    def list_by_notification(self, notification_id: str) -> List[NotificationDelivery]:
        """Fetch all delivery attempts for a given notification."""
        with self._lock:
            delivery_ids = self._by_notification.get(notification_id, [])
            return [self._deliveries[d_id] for d_id in delivery_ids if d_id in self._deliveries]

    def update_status(
        self,
        delivery_id: str,
        status: DeliveryStatus,
        error_message: Optional[str] = None,
        error_category: Optional[str] = None,
        provider_message_id: Optional[str] = None,
        delivered_at: Optional[datetime] = None,
        sent_at: Optional[datetime] = None,
    ) -> Optional[NotificationDelivery]:
        """Update delivery status and provider receipt info."""
        with self._lock:
            d = self._deliveries.get(delivery_id)
            if not d:
                return None

            now = datetime.now(timezone.utc)
            updates: Dict[str, Any] = {
                "status": status,
                "updated_at": now,
            }
            if error_message is not None:
                updates["last_error"] = error_message
            if error_category is not None:
                updates["error_category"] = error_category
            if provider_message_id is not None:
                updates["provider_message_id"] = provider_message_id
            if delivered_at is not None:
                updates["delivered_at"] = delivered_at
            if sent_at is not None:
                updates["sent_at"] = sent_at
            if status == DeliveryStatus.FAILED and d.failed_at is None:
                updates["failed_at"] = now

            updated = d.model_copy(update=updates)
            self._deliveries[delivery_id] = updated
            return updated

    def increment_retry(
        self,
        delivery_id: str,
        error_message: Optional[str] = None,
        error_category: Optional[str] = None,
    ) -> Optional[NotificationDelivery]:
        """Record a retry attempt increment."""
        with self._lock:
            d = self._deliveries.get(delivery_id)
            if not d:
                return None

            now = datetime.now(timezone.utc)
            updated = d.model_copy(
                update={
                    "retry_count": d.retry_count + 1,
                    "last_error": error_message or d.last_error,
                    "error_category": error_category or d.error_category,
                    "updated_at": now,
                }
            )
            self._deliveries[delivery_id] = updated
            return updated

    def list_failures(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[NotificationDelivery], int]:
        """List failed delivery attempts for administrator diagnostic visibility."""
        with self._lock:
            failed = [
                d for d in self._deliveries.values()
                if d.status == DeliveryStatus.FAILED
            ]

        sorted_failed = sorted(failed, key=lambda d: d.updated_at, reverse=True)
        total = len(sorted_failed)
        return sorted_failed[offset : offset + limit], total

    def delete_older_than(self, cutoff: datetime) -> int:
        """Purge delivery records older than cutoff date."""
        with self._lock:
            to_remove = [
                d_id for d_id, d in self._deliveries.items()
                if d.created_at < cutoff
            ]
            for d_id in to_remove:
                d = self._deliveries.pop(d_id, None)
                if d and d.notification_id in self._by_notification:
                    self._by_notification[d.notification_id] = [
                        x for x in self._by_notification[d.notification_id] if x != d_id
                    ]
            return len(to_remove)
