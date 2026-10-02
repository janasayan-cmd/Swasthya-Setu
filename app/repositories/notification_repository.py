"""Notification Repository (Phase 29).

Thread-safe repository for notification entities, lifecycle states,
and recipient inbox operations. Adheres to the database dependency contract.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from app.schemas.notification import (
    NotificationCategory,
    NotificationRead,
    NotificationStatus,
)

logger = logging.getLogger(__name__)


class NotificationRepository:
    """Thread-safe repository for persisting and querying notifications."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._notifications: Dict[str, NotificationRead] = {}
        self._idempotency_index: Dict[str, str] = {}  # idempotency_key -> notification_id

    def create(self, notification: NotificationRead) -> NotificationRead:
        """Persist a notification entity."""
        with self._lock:
            self._notifications[notification.id] = notification
            if notification.idempotency_key:
                self._idempotency_index[notification.idempotency_key] = notification.id
            return notification

    def get(self, notification_id: str) -> Optional[NotificationRead]:
        """Fetch notification by primary ID."""
        with self._lock:
            return self._notifications.get(notification_id)

    def get_by_idempotency_key(self, idempotency_key: str) -> Optional[NotificationRead]:
        """Fetch notification by deterministic idempotency key."""
        with self._lock:
            notification_id = self._idempotency_index.get(idempotency_key)
            if notification_id:
                return self._notifications.get(notification_id)
            return None

    def list_for_recipient(
        self,
        recipient_id: str,
        unread_only: bool = False,
        limit: int = 50,
        offset: int = 0,
        category: Optional[NotificationCategory] = None,
    ) -> Tuple[List[NotificationRead], int, int]:
        """List notifications for recipient with pagination and filtering.

        Returns (items, total_count, unread_count).
        """
        with self._lock:
            recipient_items = [
                n for n in self._notifications.values()
                if n.recipient_id == recipient_id and n.dismissed_at is None
            ]

        # Calculate unread count across all active items for recipient
        unread_count = sum(1 for n in recipient_items if n.read_at is None)

        # Filter
        filtered = recipient_items
        if unread_only:
            filtered = [n for n in filtered if n.read_at is None]
        if category:
            filtered = [n for n in filtered if n.category == category]

        # Sort newest first
        sorted_items = sorted(filtered, key=lambda n: n.created_at, reverse=True)
        total_count = len(sorted_items)
        paginated_items = sorted_items[offset : offset + limit]

        return paginated_items, total_count, unread_count

    def mark_as_read(self, notification_id: str, recipient_id: str) -> Optional[NotificationRead]:
        """Mark notification as read by recipient."""
        with self._lock:
            n = self._notifications.get(notification_id)
            if not n or n.recipient_id != recipient_id:
                return None

            now = datetime.now(timezone.utc)
            updated = n.model_copy(
                update={
                    "read_at": now,
                    "status": NotificationStatus.READ if n.status == NotificationStatus.DELIVERED else n.status,
                }
            )
            self._notifications[notification_id] = updated
            return updated

    def mark_as_dismissed(self, notification_id: str, recipient_id: str) -> Optional[NotificationRead]:
        """Dismiss notification from recipient inbox."""
        with self._lock:
            n = self._notifications.get(notification_id)
            if not n or n.recipient_id != recipient_id:
                return None

            now = datetime.now(timezone.utc)
            updated = n.model_copy(
                update={
                    "dismissed_at": now,
                }
            )
            self._notifications[notification_id] = updated
            return updated

    def update_status(self, notification_id: str, status: NotificationStatus) -> Optional[NotificationRead]:
        """Update notification lifecycle state."""
        with self._lock:
            n = self._notifications.get(notification_id)
            if not n:
                return None
            updated = n.model_copy(update={"status": status})
            self._notifications[notification_id] = updated
            return updated

    def list_admin(
        self,
        limit: int = 50,
        offset: int = 0,
        status: Optional[NotificationStatus] = None,
        recipient_id: Optional[str] = None,
    ) -> Tuple[List[NotificationRead], int]:
        """Administrative query over notifications."""
        with self._lock:
            items = list(self._notifications.values())

        if status:
            items = [n for n in items if n.status == status]
        if recipient_id:
            items = [n for n in items if n.recipient_id == recipient_id]

        sorted_items = sorted(items, key=lambda n: n.created_at, reverse=True)
        total = len(sorted_items)
        return sorted_items[offset : offset + limit], total

    def delete_older_than(self, cutoff: datetime) -> int:
        """Purge notifications older than cutoff (retention cleanup job)."""
        with self._lock:
            to_remove = [
                n_id for n_id, n in self._notifications.items()
                if n.created_at < cutoff
            ]
            for n_id in to_remove:
                n = self._notifications.pop(n_id, None)
                if n and n.idempotency_key:
                    self._idempotency_index.pop(n.idempotency_key, None)
            return len(to_remove)
