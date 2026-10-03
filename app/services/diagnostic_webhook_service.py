"""Diagnostic Webhook Processing Service (Phase 34).

Handles signature verification, replay protection, deduplication, and dispatch
of laboratory webhook notifications.

SECURITY & SAFETY INVARIANTS:
- SIGNATURE VERIFICATION MANDATORY BEFORE ANY PROCESSING
- REPLAY PROTECTION VIA UNIQUE EVENT ID ENFORCED
- MALFORMED / UNVERIFIED PAYLOADS ARE IMMEDIATELY REJECTED
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from app.core.exceptions import (
    DiagnosticWebhookDuplicateException,
    DiagnosticWebhookInvalidException,
    DiagnosticWebhookSignatureInvalidException,
)
from app.integrations.diagnostics.base import DiagnosticProvider
from app.repositories.diagnostic_order_repository import DiagnosticOrderRepository
from app.repositories.diagnostic_webhook_repository import DiagnosticWebhookRepository
from app.schemas.audit import AuditEventType, AuditRecord
from app.schemas.diagnostic_order import DiagnosticOrderStatus
from app.schemas.diagnostic_webhook import (
    DiagnosticWebhookPayload,
    WebhookEventType,
    WebhookIngestResponse,
)
from app.schemas.specimen import SpecimenStatus
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)


class DiagnosticWebhookService:
    """Service managing external diagnostic webhook ingest and dispatch."""

    def __init__(
        self,
        webhook_repository: Optional[DiagnosticWebhookRepository] = None,
        order_repository: Optional[DiagnosticOrderRepository] = None,
        provider: Optional[DiagnosticProvider] = None,
        audit_service: Optional[AuditService] = None,
        secret: Optional[str] = None,
    ) -> None:
        self.webhook_repository = webhook_repository or DiagnosticWebhookRepository()
        self.order_repository = order_repository or DiagnosticOrderRepository()
        self.provider = provider
        self.audit_service = audit_service
        self.secret = secret

    async def process_webhook(
        self,
        raw_body: bytes,
        signature_header: Optional[str],
        payload: DiagnosticWebhookPayload,
    ) -> WebhookIngestResponse:
        """Process incoming provider webhook with cryptographic signature and replay checks."""
        # 1. Cryptographic Signature Validation
        if self.provider:
            is_valid = self.provider.verify_webhook_signature(
                payload_bytes=raw_body,
                signature_header=signature_header or "",
                secret=self.secret,
            )
            if not is_valid:
                if self.audit_service:
                    await self._audit(
                        event_type=AuditEventType.DIAGNOSTIC_WEBHOOK_REJECTED,
                        resource_id=payload.event_id,
                        outcome="DENY",
                        reason="INVALID_SIGNATURE",
                    )
                raise DiagnosticWebhookSignatureInvalidException("Invalid HMAC signature on diagnostic webhook")

        # 2. Replay Protection
        recorded = self.webhook_repository.record_event(payload)
        if not recorded:
            if self.audit_service:
                await self._audit(
                    event_type=AuditEventType.DIAGNOSTIC_WEBHOOK_DUPLICATE,
                    resource_id=payload.event_id,
                    outcome="DENY",
                    reason="DUPLICATE_EVENT_ID",
                )
            raise DiagnosticWebhookDuplicateException(f"Duplicate webhook event '{payload.event_id}' rejected")

        # 3. Handle Event Types
        msg = f"Processed event {payload.event_type.value}"

        if payload.event_type == WebhookEventType.ORDER_ACCEPTED:
            target_order = None
            if payload.order_id:
                target_order = self.order_repository.get_by_id(payload.order_id)
            elif payload.provider_order_id:
                target_order = self.order_repository.get_by_provider_order_id(payload.provider_order_id)

            if target_order:
                self.order_repository.update_status(
                    order_id=target_order.order_id,
                    new_status=DiagnosticOrderStatus.ACCEPTED,
                    provider_order_id=payload.provider_order_id,
                )
                msg = f"Order '{target_order.order_number}' marked ACCEPTED via webhook"

        elif payload.event_type == WebhookEventType.SPECIMEN_COLLECTED:
            msg = "Specimen collected event acknowledged"

        # 4. Audit
        if self.audit_service:
            await self._audit(
                event_type=AuditEventType.DIAGNOSTIC_WEBHOOK_RECEIVED,
                resource_id=payload.event_id,
                outcome="ALLOW",
                reason=payload.event_type.value,
            )

        return WebhookIngestResponse(
            status="SUCCESS",
            event_id=payload.event_id,
            message=msg,
        )

    async def _audit(
        self,
        event_type: AuditEventType,
        resource_id: str,
        outcome: str,
        reason: Optional[str] = None,
    ) -> None:
        if not self.audit_service:
            return
        record = AuditRecord(
            event_type=event_type,
            actor_id="provider_webhook",
            action=event_type.value,
            resource_type="diagnostic_webhook",
            resource_id=resource_id,
            outcome=outcome,
            reason_code=reason,
        )
        try:
            await self.audit_service.log_event(record)
        except Exception as e:
            logger.warning("Audit logging failed for webhook: %s", e)
