"""Idempotency Service (Phase 22).

Enforces:
- Deterministic operation key calculation (SHA-256).
- Race-condition detection (concurrent identical executions).
- Safe replay of completed operations without re-executing clinical mutations.
- Transient failure retry support.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from typing import Any, Dict, Optional, Tuple

from app.core.exceptions import IdempotencyConflictException
from app.core.logging import get_logger
from app.repositories.idempotency_repository import IdempotencyRepository
from app.schemas.idempotency import IdempotencyRecord, IdempotencyState
from app.services.base import BaseService

logger = get_logger("app.services.idempotency")


class IdempotencyService(BaseService[IdempotencyRepository]):
    """Service governing execution idempotency and duplicate elimination."""

    def __init__(self, repository: IdempotencyRepository) -> None:
        super().__init__(repository=repository)
        self.repo = repository

    @staticmethod
    def generate_key(operation_type: str, resource_id: str, *discriminators: Any) -> str:
        """Derive a deterministic SHA-256 idempotency key."""
        raw_parts = [operation_type, resource_id]
        for d in discriminators:
            if isinstance(d, (dict, list)):
                raw_parts.append(json.dumps(d, sort_keys=True))
            else:
                raw_parts.append(str(d))
        encoded = ":".join(raw_parts).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    async def acquire_or_replay(
        self,
        key: str,
        operation_type: str,
        resource_id: str,
        ttl_seconds: int = 86400,
    ) -> Tuple[bool, Optional[IdempotencyRecord]]:
        """Attempt to acquire execution lease under key.

        Returns:
            (True, record) if caller should execute operation (first execution or retry of failed).
            (False, record) if operation ALREADY COMPLETED (caller should safely replay record.result_payload).
        Raises:
            IdempotencyConflictException if identical operation is currently PROCESSING.
        """
        existing = await self.repo.get(key)
        now = datetime.now(timezone.utc)

        if existing:
            if existing.state == IdempotencyState.PROCESSING:
                # Concurrent request in progress
                logger.warning(f"Concurrent request collision on idempotency key '{key}' for {operation_type}:{resource_id}.")
                raise IdempotencyConflictException(idempotency_key=key)

            if existing.state == IdempotencyState.COMPLETED:
                # Safe replay
                logger.info(f"Idempotency cache hit on '{key}'. Replaying cached result without re-execution.")
                return False, existing

            if existing.state == IdempotencyState.FAILED:
                # Previous attempt failed; allow retry by marking PROCESSING
                existing.state = IdempotencyState.PROCESSING
                existing.created_at = now
                existing.expires_at = now + timedelta(seconds=ttl_seconds)
                existing.error_message = None
                await self.repo.update(existing)
                return True, existing

        # First time seen
        expires_at = now + timedelta(seconds=ttl_seconds)
        new_record = IdempotencyRecord(
            key=key,
            operation_type=operation_type,
            resource_id=resource_id,
            state=IdempotencyState.PROCESSING,
            created_at=now,
            expires_at=expires_at,
        )
        saved = await self.repo.create(new_record)
        return True, saved

    async def mark_completed(self, key: str, result_payload: Dict[str, Any]) -> IdempotencyRecord:
        """Mark idempotency record COMPLETED and attach validated output."""
        rec = await self.repo.get(key)
        if not rec:
            rec = IdempotencyRecord(
                key=key,
                operation_type="unknown",
                resource_id="unknown",
                state=IdempotencyState.COMPLETED,
            )
            await self.repo.create(rec)
        rec.state = IdempotencyState.COMPLETED
        rec.completed_at = datetime.now(timezone.utc)
        rec.result_payload = result_payload
        return await self.repo.update(rec)

    async def mark_failed(self, key: str, error_message: str) -> IdempotencyRecord:
        """Mark idempotency record FAILED so future calls may re-attempt."""
        rec = await self.repo.get(key)
        if not rec:
            rec = IdempotencyRecord(
                key=key,
                operation_type="unknown",
                resource_id="unknown",
                state=IdempotencyState.FAILED,
            )
            await self.repo.create(rec)
        rec.state = IdempotencyState.FAILED
        rec.error_message = error_message
        return await self.repo.update(rec)
