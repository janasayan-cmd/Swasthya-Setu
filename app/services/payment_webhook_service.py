"""Payment Webhook Service (Phase 32).

Verifies, deduplicates, and processes inbound asynchronous webhook events from
external payment gateways.

SAFETY INVARIANTS:
- WEBHOOK ≠ TRUSTED UNTIL CRYPTOGRAPHICALLY VERIFIED
- DUPLICATE WEBHOOK ≠ DUPLICATE PAYMENT (Strict event idempotency)
- Replay protection and payload validation.
- Never log card details, CVVs, passwords, or secrets.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.core.config import settings
from app.core.exceptions import (
    PaymentWebhooksDisabledException,
    WebhookEventInvalidException,
    WebhookProviderUnknownException,
    WebhookSignatureInvalidException,
)
from app.integrations.payments.base import PaymentProvider
from app.repositories.payment_repository import PaymentRepository
from app.schemas.audit import AuditEventType
from app.schemas.notification import NotificationType
from app.schemas.payment import PaymentStatus
from app.schemas.payment_webhook import (
    WebhookEventRecord,
    WebhookProcessingStatus,
    WebhookProcessResult,
)
from app.services.invoice_service import InvoiceService

logger = logging.getLogger(__name__)


class PaymentWebhookService:
    """Service handling cryptographic signature check, event deduplication, and transaction updates."""

    def __init__(
        self,
        payment_repo: PaymentRepository,
        invoice_service: InvoiceService,
        providers: Dict[str, PaymentProvider],
        audit_service: Optional[Any] = None,
        notification_service: Optional[Any] = None,
        analytics_service: Optional[Any] = None,
    ) -> None:
        self.payment_repo = payment_repo
        self.invoice_service = invoice_service
        self.providers = providers
        self.audit_service = audit_service
        self.notification_service = notification_service
        self.analytics_service = analytics_service

    def _ensure_enabled(self) -> None:
        if not settings.PAYMENT_WEBHOOKS_ENABLED:
            raise PaymentWebhooksDisabledException("Payment webhook processing is disabled.")

    def _record_audit(
        self,
        event_type: AuditEventType,
        actor_id: str,
        resource_id: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not self.audit_service:
            return
        try:
            if hasattr(self.audit_service, "record"):
                import asyncio
                coro = self.audit_service.record(
                    event_type=event_type,
                    outcome="SUCCESS",
                    actor_id=actor_id,
                    resource_type="payment_webhook",
                    resource_id=resource_id,
                    metadata=details or {},
                )
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(coro)
                except RuntimeError:
                    pass
        except Exception as e:
            logger.warning(f"Audit log error: {e}")

    def _dispatch_notification(
        self,
        recipient_id: str,
        notification_type: NotificationType,
        variables: Dict[str, Any],
        resource_id: str,
    ) -> None:
        if settings.BILLING_NOTIFICATIONS_ENABLED and self.notification_service:
            try:
                if hasattr(self.notification_service, "create_notification"):
                    from app.schemas.notification import NotificationCreate
                    notif = NotificationCreate(
                        recipient_id=recipient_id,
                        notification_type=notification_type,
                        template_variables=variables,
                        resource_type="payment",
                        resource_id=resource_id,
                    )
                    self.notification_service.create_notification(notif)
            except Exception as e:
                logger.warning(f"Notification error: {e}")

    async def handle_webhook(
        self,
        provider_name: str,
        raw_body: bytes,
        headers: Dict[str, str],
        payload: Dict[str, Any],
    ) -> WebhookProcessResult:
        """Process verified provider webhook event with strict deduplication."""
        self._ensure_enabled()

        provider_key = provider_name.strip().upper()
        provider = self.providers.get(provider_key)
        if not provider:
            logger.error(f"Unknown payment provider: {provider_name}")
            raise WebhookProviderUnknownException(f"Unsupported payment provider: {provider_name}")

        # 1. Cryptographic signature verification
        is_valid = provider.verify_webhook(raw_body, headers)
        if not is_valid:
            self._record_audit(
                AuditEventType.PAYMENT_WEBHOOK_REJECTED,
                provider_key,
                "unknown",
                {"reason": "Invalid signature or forged webhook"},
            )
            raise WebhookSignatureInvalidException("Webhook signature verification failed")

        # 2. Parse standardized event
        parsed = provider.parse_webhook(payload)
        if not parsed.event_id:
            raise WebhookEventInvalidException("Missing event identifier in webhook payload")

        # 3. Deduplication check
        existing_event = self.payment_repo.get_webhook_event(provider_key, parsed.event_id)
        if existing_event and existing_event.processed:
            self._record_audit(
                AuditEventType.PAYMENT_WEBHOOK_DUPLICATE,
                provider_key,
                existing_event.id,
                {"event_id": parsed.event_id},
            )
            return WebhookProcessResult(
                status=WebhookProcessingStatus.DUPLICATE,
                event_id=parsed.event_id,
                provider=provider_key,
                transaction_id=parsed.provider_transaction_id,
                message="Duplicate event ignored",
            )

        # 4. Persist audit record of event
        event_record = WebhookEventRecord(
            provider=provider_key,
            event_id=parsed.event_id,
            event_type=parsed.event_type,
            transaction_id=parsed.provider_transaction_id,
            payload={k: v for k, v in payload.items() if k not in ("cvv", "card_number", "password")},
            signature=headers.get("x-mock-signature") or headers.get("X-Mock-Signature"),
            processing_status=WebhookProcessingStatus.PENDING,
        )
        self.payment_repo.save_webhook_event(event_record)
        self._record_audit(
            AuditEventType.PAYMENT_WEBHOOK_RECEIVED,
            provider_key,
            event_record.id,
            {"event_type": parsed.event_type, "event_id": parsed.event_id},
        )

        # 5. Resolve matching HealthSetu payment transaction
        payment = None
        if parsed.provider_transaction_id:
            payment = self.payment_repo.get_by_provider_transaction_id(parsed.provider_transaction_id)
        if not payment and parsed.provider_transaction_id:
            payment = self.payment_repo.get(parsed.provider_transaction_id)

        if not payment:
            event_record.processing_status = WebhookProcessingStatus.FAILED
            event_record.error_message = f"Payment transaction for {parsed.provider_transaction_id} not found"
            self.payment_repo.update_webhook_event(event_record)
            return WebhookProcessResult(
                status=WebhookProcessingStatus.FAILED,
                event_id=parsed.event_id,
                provider=provider_key,
                transaction_id=parsed.provider_transaction_id,
                message="Transaction not found in database",
            )

        # 6. Apply state transition
        event_type_lower = parsed.event_type.lower()
        if "captured" in event_type_lower or "succeeded" in event_type_lower or parsed.status == "SUCCESS":
            if (
                parsed.amount_in_minor_units is not None
                and parsed.amount_in_minor_units != payment.amount_in_minor_units
            ):
                logger.error("Webhook amount mismatch detected during processing")
                payment.status = PaymentStatus.RECONCILIATION_REQUIRED
                payment.error_code = "AMOUNT_MISMATCH"
                self.payment_repo.update(payment)
            elif payment.status != PaymentStatus.SUCCEEDED:
                payment.status = PaymentStatus.SUCCEEDED
                payment.completed_at = datetime.now(timezone.utc)
                self.payment_repo.update(payment)

                # Update invoice
                self.invoice_service.apply_payment_delta(
                    payment.invoice_id,
                    amount_paid_delta=payment.amount_in_minor_units,
                )
                self._record_audit(AuditEventType.PAYMENT_SUCCEEDED, provider_key, payment.id, payment.patient_id)
                self._dispatch_notification(
                    payment.patient_id,
                    NotificationType.PAYMENT_SUCCEEDED,
                    {"amount": payment.amount_in_minor_units / 100.0, "currency": payment.currency},
                    payment.id,
                )
        elif "failed" in event_type_lower or parsed.status == "FAILED":
            if payment.status not in (PaymentStatus.SUCCEEDED, PaymentStatus.REFUNDED):
                payment.status = PaymentStatus.FAILED
                payment.failed_at = datetime.now(timezone.utc)
                self.payment_repo.update(payment)
                self._record_audit(AuditEventType.PAYMENT_FAILED, provider_key, payment.id, payment.patient_id)
                self._dispatch_notification(
                    payment.patient_id,
                    NotificationType.PAYMENT_FAILED,
                    {"payment_number": payment.payment_number},
                    payment.id,
                )

        # 7. Finalize event record
        event_record.processed = True
        event_record.processing_status = WebhookProcessingStatus.ACCEPTED
        event_record.processed_at = datetime.now(timezone.utc)
        self.payment_repo.update_webhook_event(event_record)

        return WebhookProcessResult(
            status=WebhookProcessingStatus.ACCEPTED,
            event_id=parsed.event_id,
            provider=provider_key,
            transaction_id=payment.id,
            message="Webhook event processed successfully",
        )
