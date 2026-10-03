"""Refund Service (Phase 32).

Orchestrates refund processing, refund safety boundaries, provider integration,
and invoice/payment balance reversals.

CRITICAL REFUND INVARIANTS:
- REFUND ≠ CLINICAL REVERSAL (Does not cancel appointments or care)
- Refund amount must NEVER exceed refundable amount.
- Duplicate refunds are strictly blocked.
- Refunds can only be processed against SUCCEEDED payments.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import settings
from app.core.exceptions import (
    PaymentNotFoundException,
    RefundAlreadyProcessedException,
    RefundInvalidAmountException,
    RefundNotAllowedException,
    RefundNotFoundException,
    RefundProviderFailedException,
    RefundsDisabledException,
)
from app.integrations.payments.base import PaymentProvider
from app.repositories.payment_repository import PaymentRepository
from app.repositories.refund_repository import RefundRepository
from app.schemas.audit import AuditEventType
from app.schemas.notification import NotificationType
from app.schemas.payment import PaymentStatus
from app.schemas.refund import RefundCreateRequest, RefundRecord, RefundStatus
from app.schemas.user import AuthenticatedUserContext
from app.services.billing_authorization_service import BillingAuthorizationService
from app.services.billing_validation_service import BillingValidationService
from app.services.invoice_service import InvoiceService

logger = logging.getLogger(__name__)


class RefundService:
    """Core domain service for refunds, balance adjustments, and audit."""

    def __init__(
        self,
        refund_repo: RefundRepository,
        payment_repo: PaymentRepository,
        invoice_service: InvoiceService,
        auth_service: BillingAuthorizationService,
        provider: PaymentProvider,
        audit_service: Optional[Any] = None,
        notification_service: Optional[Any] = None,
        analytics_service: Optional[Any] = None,
    ) -> None:
        self.refund_repo = refund_repo
        self.payment_repo = payment_repo
        self.invoice_service = invoice_service
        self.auth_service = auth_service
        self.provider = provider
        self.audit_service = audit_service
        self.notification_service = notification_service
        self.analytics_service = analytics_service

    def _ensure_enabled(self) -> None:
        if not settings.REFUNDS_ENABLED:
            raise RefundsDisabledException("Refunds capability is currently disabled.")

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
                    resource_type="refund",
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
                        resource_type="refund",
                        resource_id=resource_id,
                    )
                    self.notification_service.create_notification(notif)
            except Exception as e:
                logger.warning(f"Notification dispatch error: {e}")

    async def process_refund(
        self,
        user: AuthenticatedUserContext,
        request: RefundCreateRequest,
    ) -> RefundRecord:
        """Execute a refund against a successful payment with strict validation and audit."""
        self._ensure_enabled()

        # Idempotency check
        if request.idempotency_key:
            existing = self.refund_repo.get_by_idempotency_key(request.idempotency_key)
            if existing:
                if (
                    existing.payment_id != request.payment_id
                    or existing.amount_in_minor_units != request.amount_in_minor_units
                ):
                    raise RefundAlreadyProcessedException(
                        f"Idempotency key {request.idempotency_key} reused with mismatched parameters"
                    )
                return existing

        payment = self.payment_repo.get(request.payment_id)
        if not payment:
            raise PaymentNotFoundException(f"Payment {request.payment_id} not found")

        # Authorization check
        self.auth_service.check_can_refund_payment(user, payment)

        # Payment status verification
        if payment.status != PaymentStatus.SUCCEEDED:
            raise RefundNotAllowedException(
                f"Cannot refund payment in state {payment.status.value}. Only SUCCEEDED payments are refundable."
            )

        # Amount validation
        BillingValidationService.validate_refund_amount(
            request.amount_in_minor_units,
            payment.amount_in_minor_units,
            payment.amount_refunded_in_minor_units,
        )

        refund = RefundRecord(
            refund_number="",  # Populated by repo
            payment_id=payment.id,
            invoice_id=payment.invoice_id,
            patient_id=payment.patient_id,
            organization_id=payment.organization_id,
            facility_id=payment.facility_id,
            amount_in_minor_units=request.amount_in_minor_units,
            currency=payment.currency,
            status=RefundStatus.REQUESTED,
            reason=request.reason,
            provider_name=payment.provider_name,
            idempotency_key=request.idempotency_key,
            metadata=request.metadata,
        )
        saved = self.refund_repo.create(refund)
        self._record_audit(
            AuditEventType.REFUND_CREATED,
            user.user_id,
            saved.id,
            saved.patient_id,
            {"amount": saved.amount_in_minor_units, "reason": request.reason},
        )

        # Call provider adapter
        try:
            saved.status = RefundStatus.PROCESSING
            self.refund_repo.update(saved)
            prov_res = await self.provider.refund_payment(saved)
        except Exception as e:
            logger.error(f"Provider refund failed: {e}")
            saved.status = RefundStatus.FAILED
            saved.failed_at = datetime.now(timezone.utc)
            saved.error_message = str(e)
            self.refund_repo.update(saved)
            self._record_audit(AuditEventType.REFUND_FAILED, user.user_id, saved.id, saved.patient_id)
            raise RefundProviderFailedException(f"Gateway error during refund: {e}")

        if prov_res.success:
            saved.status = RefundStatus.COMPLETED
            saved.completed_at = datetime.now(timezone.utc)
            saved.provider_refund_id = prov_res.provider_refund_id
            saved.provider_status = prov_res.provider_status
            updated = self.refund_repo.update(saved)

            # Update parent payment refunded amount
            payment.amount_refunded_in_minor_units += saved.amount_in_minor_units
            if payment.amount_refunded_in_minor_units >= payment.amount_in_minor_units:
                payment.status = PaymentStatus.REFUNDED
            self.payment_repo.update(payment)

            # Update invoice balance and status
            self.invoice_service.apply_payment_delta(
                payment.invoice_id,
                amount_refunded_delta=saved.amount_in_minor_units,
            )

            self._record_audit(AuditEventType.REFUND_SUCCEEDED, user.user_id, updated.id, updated.patient_id)
            self._record_analytics("billing.refund.succeeded", 1.0, {"currency": updated.currency})
            self._dispatch_notification(
                updated.patient_id,
                NotificationType.REFUND_SUCCEEDED,
                {
                    "amount": updated.amount_in_minor_units / 100.0,
                    "currency": updated.currency,
                    "refund_number": updated.refund_number,
                },
                updated.id,
            )
            return updated
        else:
            saved.status = RefundStatus.FAILED
            saved.failed_at = datetime.now(timezone.utc)
            saved.error_code = prov_res.error_code
            saved.error_message = prov_res.error_message
            updated = self.refund_repo.update(saved)
            self._record_audit(AuditEventType.REFUND_FAILED, user.user_id, updated.id, updated.patient_id)
            raise RefundProviderFailedException(f"Gateway declined refund: {prov_res.error_message}")

    def get_refund(
        self,
        user: AuthenticatedUserContext,
        refund_id: str,
    ) -> RefundRecord:
        """Fetch refund by ID."""
        self._ensure_enabled()
        refund = self.refund_repo.get(refund_id)
        if not refund:
            raise RefundNotFoundException(f"Refund with ID {refund_id} not found")

        role_str = user.role.value if hasattr(user.role, "value") else str(user.role)
        if role_str == "PATIENT":
            own_pid = self.auth_service.resolve_patient_id(user)
            if refund.patient_id != own_pid:
                raise RefundNotFoundException("Access denied")
        return refund

    def list_by_payment(
        self,
        user: AuthenticatedUserContext,
        payment_id: str,
    ) -> List[RefundRecord]:
        """List refunds for a specific payment."""
        self._ensure_enabled()
        payment = self.payment_repo.get(payment_id)
        if not payment:
            raise PaymentNotFoundException(f"Payment {payment_id} not found")
        self.auth_service.check_can_view_payment(user, payment)
        return self.refund_repo.list_by_payment(payment_id)

    def list_by_patient(
        self,
        user: AuthenticatedUserContext,
        patient_id: str,
        status: Optional[RefundStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[RefundRecord], int]:
        """List refunds for a patient."""
        self._ensure_enabled()
        role_str = user.role.value if hasattr(user.role, "value") else str(user.role)
        if role_str == "PATIENT":
            own_pid = self.auth_service.resolve_patient_id(user)
            if patient_id != own_pid:
                raise RefundNotFoundException("Access denied")
        return self.refund_repo.list_by_patient(patient_id, status=status, limit=limit, offset=offset)

    def list_all(
        self,
        user: AuthenticatedUserContext,
        status: Optional[RefundStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[RefundRecord], int]:
        """Administrative refund listing."""
        self._ensure_enabled()
        self.auth_service.check_admin_billing_access(user)
        return self.refund_repo.list_all(status=status, limit=limit, offset=offset)
