"""Payment Service (Phase 32).

Orchestrates payment intent creation, external provider gateway communication,
idempotent transaction tracking, and balance reconciliation with invoices.

CRITICAL PAYMENT SAFETY INVARIANTS:
- CLIENT PAYMENT STATUS ≠ AUTHORITATIVE PAYMENT STATUS
- PAYMENT SUCCESS MUST BE VERIFIED
- UNKNOWN PAYMENT ≠ FAILED PAYMENT
- UNKNOWN PAYMENT ≠ SUCCESSFUL PAYMENT
- PROVIDER FAILURE ≠ PAYMENT SUCCESS
- NO duplicate transactions on idempotent retries.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import settings
from app.core.exceptions import (
    InvoiceAlreadyPaidException,
    InvoiceInvalidStateException,
    InvoiceNotFoundException,
    PaymentAlreadyProcessedException,
    PaymentIdempotencyConflictException,
    PaymentNotFoundException,
    PaymentProviderTimeoutException,
    PaymentProviderUnavailableException,
    PaymentsDisabledException,
)
from app.integrations.payments.base import PaymentProvider
from app.repositories.invoice_repository import InvoiceRepository
from app.repositories.payment_repository import PaymentRepository
from app.schemas.audit import AuditEventType
from app.schemas.invoice import InvoiceStatus
from app.schemas.notification import NotificationType
from app.schemas.payment import (
    PaymentCreateRequest,
    PaymentRecord,
    PaymentStatus,
    PaymentVerificationRequest,
)
from app.schemas.user import AuthenticatedUserContext
from app.services.billing_authorization_service import BillingAuthorizationService
from app.services.billing_validation_service import BillingValidationService
from app.services.invoice_service import InvoiceService

logger = logging.getLogger(__name__)


class PaymentService:
    """Core domain service for payment transactions, gateway mediation, and idempotency."""

    def __init__(
        self,
        payment_repo: PaymentRepository,
        invoice_repo: InvoiceRepository,
        invoice_service: InvoiceService,
        auth_service: BillingAuthorizationService,
        provider: PaymentProvider,
        audit_service: Optional[Any] = None,
        notification_service: Optional[Any] = None,
        analytics_service: Optional[Any] = None,
    ) -> None:
        self.payment_repo = payment_repo
        self.invoice_repo = invoice_repo
        self.invoice_service = invoice_service
        self.auth_service = auth_service
        self.provider = provider
        self.audit_service = audit_service
        self.notification_service = notification_service
        self.analytics_service = analytics_service

    def _ensure_enabled(self) -> None:
        if not settings.PAYMENTS_ENABLED:
            raise PaymentsDisabledException("Payments capability is currently disabled.")

    def _record_audit(
        self,
        event_type: AuditEventType,
        actor_id: str,
        resource_id: str,
        patient_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not self.audit_service:
            return
        try:
            meta = {**(details or {})}
            if patient_id:
                meta["patient_id"] = patient_id
            if hasattr(self.audit_service, "record"):
                import asyncio
                coro = self.audit_service.record(
                    event_type=event_type,
                    outcome="SUCCESS",
                    actor_id=actor_id,
                    resource_type="payment",
                    resource_id=resource_id,
                    metadata=meta,
                )
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(coro)
                except RuntimeError:
                    pass
        except Exception as e:
            logger.warning(f"Audit log error: {e}")

    def _record_analytics(self, metric: str, value: float = 1.0, tags: Optional[Dict[str, str]] = None) -> None:
        if settings.BILLING_ANALYTICS_ENABLED and self.analytics_service:
            try:
                if hasattr(self.analytics_service, "record_metric"):
                    self.analytics_service.record_metric(metric, value, tags or {})
            except Exception as e:
                logger.warning(f"Analytics logging error: {e}")

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
                logger.warning(f"Notification dispatch error: {e}")

    async def create_payment_intent(
        self,
        user: AuthenticatedUserContext,
        request: PaymentCreateRequest,
    ) -> PaymentRecord:
        """Initiate payment transaction with idempotency and gateway integration."""
        self._ensure_enabled()

        # Idempotency check
        if request.idempotency_key:
            existing = self.payment_repo.get_by_idempotency_key(request.idempotency_key)
            if existing:
                if (
                    existing.invoice_id != request.invoice_id
                    or existing.amount_in_minor_units != request.amount_in_minor_units
                    or existing.currency != request.currency.upper()
                ):
                    raise PaymentIdempotencyConflictException(
                        f"Idempotency key {request.idempotency_key} reused with mismatched parameters"
                    )
                return existing

        invoice = self.invoice_repo.get(request.invoice_id)
        if not invoice:
            raise InvoiceNotFoundException(f"Invoice {request.invoice_id} not found")

        # Invoice state check
        if invoice.status == InvoiceStatus.PAID:
            raise InvoiceAlreadyPaidException(f"Invoice {invoice.invoice_number} is already fully paid")
        if invoice.status not in (InvoiceStatus.ISSUED, InvoiceStatus.PARTIALLY_PAID):
            raise InvoiceInvalidStateException(
                f"Invoice {invoice.invoice_number} is in state {invoice.status.value}, which is not payable"
            )

        # Authorization check
        self.auth_service.check_can_create_payment(user, invoice)

        # Monetary and currency validation
        BillingValidationService.validate_currencies(invoice.currency, request.currency)
        BillingValidationService.validate_payment_amount(
            request.amount_in_minor_units,
            invoice.outstanding_amount_in_minor_units,
        )

        payment = PaymentRecord(
            payment_number="",  # Generated by repo
            invoice_id=invoice.id,
            patient_id=invoice.patient_id,
            organization_id=invoice.organization_id,
            facility_id=invoice.facility_id,
            amount_in_minor_units=request.amount_in_minor_units,
            currency=request.currency.upper(),
            status=PaymentStatus.PENDING,
            payment_method=request.payment_method,
            provider_name=self.provider.name,
            idempotency_key=request.idempotency_key,
            metadata=request.metadata,
        )

        # Invoke provider
        try:
            intent_res = await self.provider.create_payment_intent(payment)
        except Exception as e:
            logger.error(f"Provider call failed: {e}")
            payment.status = PaymentStatus.UNKNOWN
            payment.error_message = str(e)
            saved = self.payment_repo.create(payment)
            self._record_audit(AuditEventType.PAYMENT_UNKNOWN, user.user_id, saved.id, saved.patient_id)
            raise PaymentProviderUnavailableException("Payment gateway could not be reached")

        if intent_res.success:
            payment.provider_transaction_id = intent_res.provider_transaction_id
            payment.provider_order_id = intent_res.provider_order_id
            payment.provider_status = intent_res.provider_status
            payment.status = PaymentStatus.PROCESSING
        elif intent_res.provider_status == "TIMEOUT":
            payment.status = PaymentStatus.UNKNOWN
            payment.error_code = intent_res.error_code
            payment.error_message = intent_res.error_message
        elif intent_res.provider_status == "UNKNOWN":
            payment.status = PaymentStatus.RECONCILIATION_REQUIRED
            payment.provider_transaction_id = intent_res.provider_transaction_id
            payment.error_code = intent_res.error_code
            payment.error_message = intent_res.error_message
        else:
            payment.status = PaymentStatus.FAILED
            payment.failed_at = datetime.now(timezone.utc)
            payment.error_code = intent_res.error_code
            payment.error_message = intent_res.error_message

        saved = self.payment_repo.create(payment)
        self._record_audit(
            AuditEventType.PAYMENT_CREATED,
            user.user_id,
            saved.id,
            saved.patient_id,
            {
                "amount": saved.amount_in_minor_units,
                "currency": saved.currency,
                "provider_tx_id": saved.provider_transaction_id,
                "status": saved.status.value,
            },
        )
        self._record_analytics("billing.payment.attempt", 1.0, {"status": saved.status.value})
        return saved

    async def verify_and_capture(
        self,
        user: AuthenticatedUserContext,
        payment_id: str,
        verification: PaymentVerificationRequest,
    ) -> PaymentRecord:
        """Verify transaction outcome with payment gateway before committing success."""
        self._ensure_enabled()
        payment = self.payment_repo.get(payment_id)
        if not payment:
            raise PaymentNotFoundException(f"Payment with ID {payment_id} not found")

        self.auth_service.check_can_view_payment(user, payment)

        if payment.status == PaymentStatus.SUCCEEDED:
            return payment
        if payment.status in (PaymentStatus.FAILED, PaymentStatus.CANCELLED):
            raise PaymentAlreadyProcessedException(f"Payment is in terminal state {payment.status.value}")

        # Authoritatively query external provider
        provider_tx_id = verification.provider_transaction_id or payment.provider_transaction_id
        if not provider_tx_id:
            raise PaymentNotFoundException("No provider transaction reference available for verification")

        try:
            status_res = await self.provider.get_payment_status(provider_tx_id)
            if status_res.success and status_res.status in ("AUTHORIZED", "CREATED"):
                capture_res = await self.provider.capture_payment(provider_tx_id, payment.amount_in_minor_units)
                if capture_res.success:
                    status_res = capture_res
        except Exception as e:
            logger.error(f"Error querying provider status: {e}")
            payment.status = PaymentStatus.RECONCILIATION_REQUIRED
            payment.error_message = str(e)
            self.payment_repo.update(payment)
            self._record_audit(AuditEventType.PAYMENT_UNKNOWN, user.user_id, payment.id, payment.patient_id)
            raise PaymentProviderTimeoutException("External gateway timed out during verification")

        if not status_res.success:
            if status_res.status == "TIMEOUT":
                payment.status = PaymentStatus.RECONCILIATION_REQUIRED
                self.payment_repo.update(payment)
                raise PaymentProviderTimeoutException("Provider inquiry timed out; reconciliation required")
            payment.status = PaymentStatus.FAILED
            payment.failed_at = datetime.now(timezone.utc)
            payment.error_message = status_res.error_message
            updated = self.payment_repo.update(payment)
            self._record_audit(AuditEventType.PAYMENT_FAILED, user.user_id, updated.id, updated.patient_id)
            return updated

        # Validate verified transaction details
        if (
            status_res.status in ("CAPTURED", "SUCCESS", "PAID")
            and status_res.amount_in_minor_units == payment.amount_in_minor_units
            and status_res.currency.upper() == payment.currency.upper()
        ):
            payment.status = PaymentStatus.SUCCEEDED
            payment.completed_at = datetime.now(timezone.utc)
            payment.provider_transaction_id = status_res.provider_transaction_id
            payment.provider_status = status_res.status
            updated = self.payment_repo.update(payment)

            # Apply payment delta to invoice
            self.invoice_service.apply_payment_delta(
                updated.invoice_id,
                amount_paid_delta=updated.amount_in_minor_units,
            )

            self._record_audit(AuditEventType.PAYMENT_SUCCEEDED, user.user_id, updated.id, updated.patient_id)
            self._record_analytics("billing.payment.succeeded", 1.0, {"currency": updated.currency})
            self._dispatch_notification(
                updated.patient_id,
                NotificationType.PAYMENT_SUCCEEDED,
                {
                    "amount": updated.amount_in_minor_units / 100.0,
                    "currency": updated.currency,
                    "payment_number": updated.payment_number,
                },
                updated.id,
            )
            return updated

        # Amount or currency mismatch
        if status_res.amount_in_minor_units != payment.amount_in_minor_units:
            logger.error(
                f"Amount mismatch on verification! System expected {payment.amount_in_minor_units}, provider got {status_res.amount_in_minor_units}"
            )
            payment.status = PaymentStatus.RECONCILIATION_REQUIRED
            payment.error_code = "AMOUNT_MISMATCH"
            payment.error_message = f"Provider captured {status_res.amount_in_minor_units} vs expected {payment.amount_in_minor_units}"
            updated = self.payment_repo.update(payment)
            self._record_audit(AuditEventType.PAYMENT_UNKNOWN, user.user_id, updated.id, updated.patient_id)
            return updated

        payment.status = PaymentStatus.RECONCILIATION_REQUIRED
        payment.error_code = "UNKNOWN_PROVIDER_STATE"
        updated = self.payment_repo.update(payment)
        return updated

    def get_payment(
        self,
        user: AuthenticatedUserContext,
        payment_id: str,
    ) -> PaymentRecord:
        """Retrieve payment record with strict access authorization."""
        self._ensure_enabled()
        payment = self.payment_repo.get(payment_id)
        if not payment:
            raise PaymentNotFoundException(f"Payment with ID {payment_id} not found")

        self.auth_service.check_can_view_payment(user, payment)
        return payment

    def list_by_patient(
        self,
        user: AuthenticatedUserContext,
        patient_id: str,
        status: Optional[PaymentStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[PaymentRecord], int]:
        """List payments for a specific patient."""
        self._ensure_enabled()
        role_str = user.role.value if hasattr(user.role, "value") else str(user.role)
        if role_str == "PATIENT":
            own_pid = self.auth_service.resolve_patient_id(user)
            if patient_id != own_pid:
                raise PaymentNotFoundException("Access denied")
        return self.payment_repo.list_by_patient(patient_id, status=status, limit=limit, offset=offset)

    def list_by_invoice(
        self,
        user: AuthenticatedUserContext,
        invoice_id: str,
    ) -> List[PaymentRecord]:
        """List payment attempts for a given invoice."""
        self._ensure_enabled()
        invoice = self.invoice_repo.get(invoice_id)
        if not invoice:
            raise InvoiceNotFoundException(f"Invoice {invoice_id} not found")
        self.auth_service.check_can_view_invoice(user, invoice)
        return self.payment_repo.list_by_invoice(invoice_id)

    def list_all(
        self,
        user: AuthenticatedUserContext,
        status: Optional[PaymentStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[PaymentRecord], int]:
        """Administrative payment listing."""
        self._ensure_enabled()
        self.auth_service.check_admin_billing_access(user)
        return self.payment_repo.list_all(status=status, limit=limit, offset=offset)
