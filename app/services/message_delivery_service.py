"""Message Delivery Orchestration and Webhook Handling Service (Phase 41).

CRITICAL NON-NEGOTIABLE SAFETY BOUNDARIES:
- SENT != DELIVERED
- DELIVERED != READ
- READ != ACKNOWLEDGED
- PROVIDER ACCEPTANCE != READ BY PATIENT
- UNKNOWN STATUS != SUCCESS
- PROVIDER FAILURE != SUCCESS
- PROVIDER FAILURES NEVER SILENTLY BECOME SUCCESSFUL DELIVERY
- WEBHOOK PAYLOADS ARE UNTRUSTED INPUTS WITH MANDATORY HMAC SIGNATURE CHECKS
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from app.core.exceptions import (
    CommunicationProviderTimeoutException,
    CommunicationProviderUnavailableException,
    CommunicationWebhookInvalidException,
    CommunicationWebhookReplayException,
    MessageNotFoundException,
)
from app.integrations.communication.base import CommunicationProvider
from app.repositories.message_repository import MessageRepository
from app.schemas.audit import AuditEventRecord, AuditEventType
from app.schemas.communication import ProviderState, WebhookPayload
from app.schemas.message import (
    MessageDeliveryHistoryRecord,
    MessageRecord,
    MessageStatus,
)
from app.services.audit_service import AuditService


class MessageDeliveryService:
    """Manages outbound provider dispatch, delivery state machines, and inbound webhooks."""

    def __init__(
        self,
        message_repository: MessageRepository,
        provider: CommunicationProvider,
        audit_service: AuditService,
        webhook_secret: str = "dev-comm-webhook-secret-32-bytes-minimum!",
        max_retries: int = 3,
        enabled: bool = True,
    ) -> None:
        self._message_repo = message_repository
        self._provider = provider
        self._audit = audit_service
        self._webhook_secret = webhook_secret
        self._max_retries = max_retries
        self._enabled = enabled

    async def dispatch_message(
        self,
        message: MessageRecord,
        recipient_ids: List[str],
    ) -> MessageRecord:
        """Dispatch message via communication provider and update authoritative state."""
        if not self._enabled:
            message.status = MessageStatus.SENT
            message.sent_at = datetime.now(timezone.utc)
            return self._message_repo.save(message)

        now = datetime.now(timezone.utc)
        prev_status = message.status
        message.provider = self._provider.provider_name

        try:
            result = await self._provider.send_message(
                message_id=message.id,
                recipient_ids=recipient_ids,
                content=message.content,
                sender_role=message.sender_role,
                metadata=message.metadata,
            )

            if result.success:
                message.status = MessageStatus.SENT
                message.sent_at = now
                message.provider_message_id = result.provider_message_id
                message.failure_reason = None

                self._record_transition(
                    message_id=message.id,
                    previous_status=prev_status,
                    new_status=MessageStatus.SENT,
                    reason=f"Provider accepted: {result.provider_status}",
                )

                await self._audit.log_event(
                    AuditEventRecord(
                        event_type=AuditEventType.MESSAGE_SENT,
                        actor_id=message.sender_id,
                        target_id=message.id,
                        metadata={
                            "provider": self._provider.provider_name,
                            "provider_message_id": result.provider_message_id,
                        },
                    )
                )
            elif result.provider_status == "TIMEOUT":
                # Indeterminate delivery status: Remain PROCESSING, never convert to DELIVERED
                message.status = MessageStatus.PROCESSING
                message.failure_reason = "Provider request timed out; status unknown"

                self._record_transition(
                    message_id=message.id,
                    previous_status=prev_status,
                    new_status=MessageStatus.PROCESSING,
                    reason="Provider timeout; delivery status unknown",
                )
            else:
                # Explicit failure
                message.retry_count += 1
                message.status = (
                    MessageStatus.RETRY_PENDING
                    if message.retry_count <= self._max_retries
                    else MessageStatus.FAILED
                )
                message.failure_reason = result.error_message or "Provider rejected message"

                self._record_transition(
                    message_id=message.id,
                    previous_status=prev_status,
                    new_status=message.status,
                    reason=message.failure_reason,
                )

                await self._audit.log_event(
                    AuditEventRecord(
                        event_type=AuditEventType.MESSAGE_FAILED,
                        actor_id=message.sender_id,
                        target_id=message.id,
                        metadata={"reason": message.failure_reason},
                    )
                )

        except Exception as exc:
            message.retry_count += 1
            message.status = (
                MessageStatus.RETRY_PENDING
                if message.retry_count <= self._max_retries
                else MessageStatus.FAILED
            )
            message.failure_reason = str(exc)

            self._record_transition(
                message_id=message.id,
                previous_status=prev_status,
                new_status=message.status,
                reason=f"Exception during dispatch: {exc}",
            )

        return self._message_repo.save(message)

    async def process_webhook(
        self,
        payload_bytes: bytes,
        signature: str,
        payload_dict: Dict[str, Any],
    ) -> WebhookPayload:
        """Verify HMAC signature, prevent replay, and apply authoritative delivery status."""
        # 1. Verify HMAC signature
        is_valid = self._provider.verify_webhook_signature(
            payload_bytes=payload_bytes,
            signature=signature,
            secret=self._webhook_secret,
        )
        if not is_valid:
            raise CommunicationWebhookInvalidException("Invalid webhook HMAC signature.")

        # 2. Parse payload
        webhook = await self._provider.parse_webhook(payload_dict)

        # 3. Replay protection
        if self._message_repo.is_event_seen(webhook.event_id):
            raise CommunicationWebhookReplayException(
                f"Webhook event '{webhook.event_id}' has already been processed."
            )
        self._message_repo.mark_event_seen(webhook.event_id)

        # 4. Resolve internal message
        message = self._message_repo.get_by_id(webhook.message_id)
        if not message:
            raise MessageNotFoundException(f"Message '{webhook.message_id}' referenced in webhook not found.")

        # 5. Apply status transition
        prev_status = message.status
        now = datetime.now(timezone.utc)

        if webhook.delivery_status == "DELIVERED":
            # Note: Provider DELIVERED does NOT mean READ by patient
            message.status = MessageStatus.DELIVERED
            message.delivered_at = now
            self._record_transition(
                message_id=message.id,
                previous_status=prev_status,
                new_status=MessageStatus.DELIVERED,
                reason="Provider confirmed delivery to recipient device",
                event_id=webhook.event_id,
            )
            await self._audit.log_event(
                AuditEventRecord(
                    event_type=AuditEventType.MESSAGE_DELIVERED,
                    actor_id="SYSTEM",
                    target_id=message.id,
                    metadata={"provider": webhook.provider, "event_id": webhook.event_id},
                )
            )
        elif webhook.delivery_status in ("FAILED", "BOUNCED", "UNDELIVERED"):
            message.status = MessageStatus.FAILED
            message.failure_reason = webhook.reason or "Provider reported delivery failure"
            self._record_transition(
                message_id=message.id,
                previous_status=prev_status,
                new_status=MessageStatus.FAILED,
                reason=message.failure_reason,
                event_id=webhook.event_id,
            )
            await self._audit.log_event(
                AuditEventRecord(
                    event_type=AuditEventType.MESSAGE_FAILED,
                    actor_id="SYSTEM",
                    target_id=message.id,
                    metadata={"reason": message.failure_reason, "event_id": webhook.event_id},
                )
            )

        self._message_repo.save(message)

        await self._audit.log_event(
            AuditEventRecord(
                event_type=AuditEventType.COMMUNICATION_WEBHOOK_RECEIVED,
                actor_id="SYSTEM",
                target_id=message.id,
                metadata={"provider": webhook.provider, "event_id": webhook.event_id},
            )
        )

        return webhook

    def _record_transition(
        self,
        message_id: str,
        previous_status: Optional[MessageStatus],
        new_status: MessageStatus,
        reason: Optional[str] = None,
        event_id: Optional[str] = None,
    ) -> None:
        """Helper to append a delivery history record."""
        self._message_repo.record_delivery_history(
            MessageDeliveryHistoryRecord(
                id=f"del-{uuid.uuid4().hex[:8]}",
                message_id=message_id,
                provider=self._provider.provider_name,
                previous_status=previous_status,
                new_status=new_status,
                reason=reason,
                event_id=event_id,
            )
        )
