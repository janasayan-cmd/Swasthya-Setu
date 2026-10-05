"""Clinical Message, Threading, and Delivery Repository (Phase 41).

Thread-safe repository for messages, delivery states, read/acknowledgement tracking,
and webhook replay prevention.

ARCHITECTURAL INVARIANTS:
- Consumes existing database contract without duplicating tables.
- Thread-safe via threading.Lock.
- Idempotent creation prevents duplicate messages across retries.
- Webhook event IDs are tracked to eliminate replay attacks.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple

from app.schemas.message import (
    MessageDeliveryHistoryRecord,
    MessageRecord,
    MessageStatus,
)


class MessageRepository:
    """Thread-safe in-memory repository for clinical messages and delivery states."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._messages: Dict[str, MessageRecord] = {}
        self._idempotency_map: Dict[str, str] = {}  # idempotency_key -> message_id
        self._conversation_messages: Dict[str, List[str]] = {}  # conversation_id -> list of message_ids
        self._delivery_history: Dict[str, List[MessageDeliveryHistoryRecord]] = {}
        self._seen_webhook_events: Set[str] = set()

    def save(self, message: MessageRecord) -> MessageRecord:
        """Persist or update a message record."""
        with self._lock:
            message.updated_at = datetime.now(timezone.utc)
            self._messages[message.id] = message

            if message.idempotency_key:
                self._idempotency_map[message.idempotency_key] = message.id

            conv_list = self._conversation_messages.setdefault(message.conversation_id, [])
            if message.id not in conv_list:
                conv_list.append(message.id)

            return message.model_copy(deep=True)

    def get_by_id(self, message_id: str) -> Optional[MessageRecord]:
        """Retrieve message by ID."""
        with self._lock:
            msg = self._messages.get(message_id)
            return msg.model_copy(deep=True) if msg else None

    def get_by_idempotency_key(self, idempotency_key: str) -> Optional[MessageRecord]:
        """Retrieve message by idempotency key."""
        with self._lock:
            msg_id = self._idempotency_map.get(idempotency_key)
            if msg_id:
                msg = self._messages.get(msg_id)
                return msg.model_copy(deep=True) if msg else None
            return None

    def list_messages(
        self,
        conversation_id: str,
        limit: int = 50,
        cursor: Optional[str] = None,
    ) -> Tuple[List[MessageRecord], int, Optional[str], bool]:
        """Bounded, cursor-based message listing in chronological order."""
        with self._lock:
            msg_ids = self._conversation_messages.get(conversation_id, [])
            all_messages = [self._messages[mid] for mid in msg_ids if mid in self._messages]

        # Sort chronologically by created_at
        all_messages.sort(key=lambda m: m.created_at)

        # Apply cursor pagination if cursor provided
        start_idx = 0
        if cursor:
            for idx, msg in enumerate(all_messages):
                if msg.id == cursor:
                    start_idx = idx + 1
                    break

        page = all_messages[start_idx : start_idx + limit]
        has_more = (start_idx + limit) < len(all_messages)
        next_cursor = page[-1].id if (has_more and page) else None

        return (
            [m.model_copy(deep=True) for m in page],
            len(all_messages),
            next_cursor,
            has_more,
        )

    def get_unread_messages(
        self,
        user_id: str,
        conversation_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[MessageRecord]:
        """Retrieve messages not yet read by user where user is not the sender."""
        with self._lock:
            if conversation_id:
                msg_ids = self._conversation_messages.get(conversation_id, [])
                candidates = [self._messages[mid] for mid in msg_ids if mid in self._messages]
            else:
                candidates = list(self._messages.values())

        unread: List[MessageRecord] = []
        for m in candidates:
            if m.sender_id != user_id and user_id not in m.read_by:
                unread.append(m)
            if len(unread) >= limit:
                break

        return [m.model_copy(deep=True) for m in unread]

    def mark_as_read(self, message_id: str, user_id: str) -> Optional[MessageRecord]:
        """Mark message as read by a specific user."""
        with self._lock:
            msg = self._messages.get(message_id)
            if not msg:
                return None

            if user_id not in msg.read_by:
                msg.read_by.append(user_id)
                msg.read_at = datetime.now(timezone.utc)
                if msg.status in (MessageStatus.SENT, MessageStatus.DELIVERED):
                    msg.status = MessageStatus.READ
                msg.updated_at = datetime.now(timezone.utc)

            return msg.model_copy(deep=True)

    def mark_as_acknowledged(
        self,
        message_id: str,
        user_id: str,
        note: Optional[str] = None,
    ) -> Optional[MessageRecord]:
        """Record explicit clinical acknowledgment of a message."""
        with self._lock:
            msg = self._messages.get(message_id)
            if not msg:
                return None

            msg.status = MessageStatus.ACKNOWLEDGED
            msg.acknowledged_at = datetime.now(timezone.utc)
            msg.acknowledged_by = user_id
            msg.acknowledgment_note = note
            msg.updated_at = datetime.now(timezone.utc)
            return msg.model_copy(deep=True)

    def record_delivery_history(self, entry: MessageDeliveryHistoryRecord) -> None:
        """Record a delivery lifecycle transition."""
        with self._lock:
            self._delivery_history.setdefault(entry.message_id, []).append(entry)

    def get_delivery_history(self, message_id: str) -> List[MessageDeliveryHistoryRecord]:
        """Get delivery transition history for a message."""
        with self._lock:
            entries = self._delivery_history.get(message_id, [])
            return [e.model_copy(deep=True) for e in entries]

    def is_event_seen(self, event_id: str) -> bool:
        """Check if webhook event has already been processed (replay check)."""
        with self._lock:
            return event_id in self._seen_webhook_events

    def mark_event_seen(self, event_id: str) -> None:
        """Register seen webhook event ID."""
        with self._lock:
            self._seen_webhook_events.add(event_id)

    def count_total(self) -> int:
        """Total message count."""
        with self._lock:
            return len(self._messages)

    def count_by_status(self, status: MessageStatus) -> int:
        """Count messages in a given status."""
        with self._lock:
            return sum(1 for m in self._messages.values() if m.status == status)
