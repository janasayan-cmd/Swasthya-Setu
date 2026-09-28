"""Event Outbox and Consumer Repository (Phase 22).

DATABASE TEAM DEPENDENCY — PHASE 22
===================================
In-memory repository implementing the transactional outbox pattern and
consumer deduplication.

Expected PostgreSQL tables:
- event_outbox (id, event_id, event_type, payload, status, attempts, created_at, published_at, last_error)
- consumed_events (event_id, event_type, consumer_name, consumed_at)
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from app.repositories.base import BaseRepository
from app.schemas.event import OutboxEventRecord, OutboxStatus


class EventRepository(BaseRepository[Any]):
    """Thread-safe repository managing transactional outbox and consumed events."""

    def __init__(self, session: Any = None) -> None:
        super().__init__(session=session)
        self._outbox: Dict[str, OutboxEventRecord] = {}
        self._consumed: Set[str] = set()  # format: f"{event_id}:{consumer_name}"
        self._lock = asyncio.Lock()

    async def create_outbox_event(self, record: OutboxEventRecord) -> OutboxEventRecord:
        """Persist an event to the transactional outbox."""
        async with self._lock:
            self._outbox[record.id] = record
            return record

    async def get_pending_outbox_events(self, limit: int = 50) -> List[OutboxEventRecord]:
        """Fetch pending outbox events awaiting publication."""
        async with self._lock:
            pending = [
                rec for rec in self._outbox.values()
                if rec.status == OutboxStatus.PENDING and rec.attempts < rec.max_attempts
            ]
            pending.sort(key=lambda r: r.created_at)
            return pending[:limit]

    async def update_outbox_event(self, record: OutboxEventRecord) -> OutboxEventRecord:
        """Update outbox event status or retry count."""
        async with self._lock:
            self._outbox[record.id] = record
            return record

    async def mark_event_consumed(self, event_id: str, consumer_name: str) -> bool:
        """Record that an event has been processed by a consumer.

        Returns True if first time consumed, False if it was already processed (duplicate).
        """
        key = f"{event_id}:{consumer_name}"
        async with self._lock:
            if key in self._consumed:
                return False
            self._consumed.add(key)
            return True

    async def is_event_consumed(self, event_id: str, consumer_name: str) -> bool:
        """Check if an event was already processed by this consumer."""
        key = f"{event_id}:{consumer_name}"
        async with self._lock:
            return key in self._consumed
