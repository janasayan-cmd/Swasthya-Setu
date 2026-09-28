"""Idempotency Repository (Phase 22).

DATABASE TEAM DEPENDENCY — PHASE 22
===================================
In-memory repository implementing the data contract for operation idempotency.

Expected PostgreSQL table:
- idempotency_records (key, operation_type, resource_id, state, created_at,
                       completed_at, expires_at, result_payload, error_message)
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.repositories.base import BaseRepository
from app.schemas.idempotency import IdempotencyRecord, IdempotencyState


class IdempotencyRepository(BaseRepository[Any]):
    """Thread-safe repository managing idempotency keys and cached outputs."""

    def __init__(self, session: Any = None) -> None:
        super().__init__(session=session)
        self._records: Dict[str, IdempotencyRecord] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[IdempotencyRecord]:
        """Fetch idempotency record by key."""
        async with self._lock:
            record = self._records.get(key)
            if record and record.expires_at:
                if datetime.now(timezone.utc) > record.expires_at:
                    del self._records[key]
                    return None
            return record

    async def create(self, record: IdempotencyRecord) -> IdempotencyRecord:
        """Persist a new in-progress idempotency record."""
        async with self._lock:
            self._records[record.key] = record
            return record

    async def update(self, record: IdempotencyRecord) -> IdempotencyRecord:
        """Update idempotency state and result payload."""
        async with self._lock:
            self._records[record.key] = record
            return record
