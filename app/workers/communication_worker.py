"""Asynchronous Communication Worker and Task Handlers (Phase 41).

Integrates with Phase 22 async job orchestration to process:
- Outbound message delivery
- Recipient notifications
- Bounded delivery retries
- Communication retention lifecycle

ARCHITECTURAL INVARIANTS:
- Background jobs receive minimal identifiers, never raw PHI bodies.
- Worker re-validates authorized resource state from repository before execution.
- Retries are bounded by maximum attempt policies.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from app.schemas.message import MessageStatus
from app.services.message_delivery_service import MessageDeliveryService

logger = logging.getLogger("app.workers.communication")


class CommunicationWorker:
    """Async background worker for communication tasks."""

    def __init__(
        self,
        delivery_service: MessageDeliveryService,
        max_retries: int = 3,
    ) -> None:
        self._delivery = delivery_service
        self._max_retries = max_retries

    async def handle_delivery_job(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process an async message delivery dispatch job."""
        message_id = job_data.get("message_id")
        recipient_ids = job_data.get("recipient_ids", [])

        if not message_id:
            return {"status": "FAILED", "reason": "Missing message_id"}

        msg = self._delivery._message_repo.get_by_id(message_id)
        if not msg:
            return {"status": "FAILED", "reason": "Message not found"}

        # State check: If already delivered or cancelled, do not resend
        if msg.status in (MessageStatus.DELIVERED, MessageStatus.READ, MessageStatus.ACKNOWLEDGED, MessageStatus.CANCELLED):
            return {"status": "SKIPPED", "current_status": msg.status.value}

        dispatched = await self._delivery.dispatch_message(msg, recipient_ids)
        return {
            "status": "COMPLETED",
            "message_id": message_id,
            "final_status": dispatched.status.value,
        }

    async def handle_retry_job(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute scheduled delivery retry."""
        message_id = job_data.get("message_id")
        if not message_id:
            return {"status": "FAILED", "reason": "Missing message_id"}

        msg = self._delivery._message_repo.get_by_id(message_id)
        if not msg:
            return {"status": "FAILED", "reason": "Message not found"}

        if msg.retry_count >= self._max_retries:
            msg.status = MessageStatus.FAILED
            msg.failure_reason = f"Exceeded max delivery retries ({self._max_retries})"
            self._delivery._message_repo.save(msg)
            return {"status": "EXHAUSTED", "message_id": message_id}

        conv = self._delivery._message_repo._conversation_messages.get(msg.conversation_id, [])
        dispatched = await self._delivery.dispatch_message(msg, [])
        return {
            "status": "RETRIED",
            "message_id": message_id,
            "final_status": dispatched.status.value,
        }
