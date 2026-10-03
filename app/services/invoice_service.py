"""Invoice Service (Phase 32).

Deterministic invoice creation, itemization, state transitions,
and financial balance management.

SAFETY INVARIANTS:
- INVOICE ≠ MEDICAL RECORD
- BILLING ≠ CLINICAL DECISION
- No floating-point math; all balances computed in integer minor units.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import settings
from app.core.exceptions import (
    BillingDisabledException,
    InvoiceAlreadyPaidException,
    InvoiceNotFoundException,
)
from app.repositories.billing_repository import BillingRepository
from app.repositories.invoice_repository import InvoiceRepository
from app.schemas.audit import AuditEventType
from app.schemas.invoice import (
    InvoiceCancelRequest,
    InvoiceCreateRequest,
    InvoiceRecord,
    InvoiceResponse,
    InvoiceStatus,
)
from app.schemas.notification import NotificationType
from app.schemas.user import AuthenticatedUserContext
from app.services.billing_authorization_service import BillingAuthorizationService
from app.services.billing_validation_service import BillingValidationService

logger = logging.getLogger(__name__)


class InvoiceService:
    """Core domain service for invoice lifecycle and ledger tracking."""

    def __init__(
        self,
        invoice_repo: InvoiceRepository,
        billing_repo: BillingRepository,
        auth_service: BillingAuthorizationService,
        audit_service: Optional[Any] = None,
        notification_service: Optional[Any] = None,
        analytics_service: Optional[Any] = None,
    ) -> None:
        self.invoice_repo = invoice_repo
        self.billing_repo = billing_repo
        self.auth_service = auth_service
        self.audit_service = audit_service
        self.notification_service = notification_service
        self.analytics_service = analytics_service

    def _ensure_enabled(self) -> None:
        if not settings.BILLING_ENABLED or not settings.INVOICING_ENABLED:
            raise BillingDisabledException("Billing/Invoicing capability is currently disabled.")

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
                    resource_type="invoice",
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
                        resource_type="invoice",
                        resource_id=resource_id,
                    )
                    self.notification_service.create_notification(notif)
            except Exception as e:
                logger.warning(f"Notification dispatch error: {e}")

    def create_invoice(
        self,
        user: AuthenticatedUserContext,
        request: InvoiceCreateRequest,
    ) -> InvoiceRecord:
        """Create a new draft invoice with deterministic integer totals."""
        self._ensure_enabled()
        self.auth_service.check_can_create_invoice(
            user,
            request.patient_id,
            request.organization_id,
            request.facility_id,
        )

        currency = (request.currency or settings.PAYMENT_DEFAULT_CURRENCY).upper()
        item_records, subtotal, tax, discount, total = BillingValidationService.calculate_invoice_totals(
            request.items,
            default_currency=currency,
        )

        invoice = InvoiceRecord(
            invoice_number="",  # Populated sequentially by repo
            patient_id=request.patient_id,
            organization_id=request.organization_id,
            facility_id=request.facility_id,
            status=InvoiceStatus.DRAFT,
            currency=currency,
            subtotal_in_minor_units=subtotal,
            tax_in_minor_units=tax,
            discount_in_minor_units=discount,
            total_in_minor_units=total,
            amount_paid_in_minor_units=0,
            amount_refunded_in_minor_units=0,
            outstanding_amount_in_minor_units=total,
            items=[],
            notes=request.notes,
            due_at=request.due_at,
            metadata=request.metadata,
        )

        # Bind items with invoice_id
        bound_items = []
        for it in item_records:
            it.invoice_id = invoice.id
            bound_items.append(it)
            if it.billable_event_id:
                self.billing_repo.mark_event_billed(it.billable_event_id, invoice.id)
        invoice.items = bound_items

        created = self.invoice_repo.create(invoice)
        self._record_audit(
            AuditEventType.INVOICE_CREATED,
            user.user_id,
            created.id,
            created.patient_id,
            {"total": total, "currency": currency, "invoice_number": created.invoice_number},
        )
        self._record_analytics("billing.invoice.created", 1.0, {"currency": currency})
        return created

    def get_invoice(
        self,
        user: AuthenticatedUserContext,
        invoice_id: str,
    ) -> InvoiceRecord:
        """Retrieve an invoice by ID with strict authorization verification."""
        self._ensure_enabled()
        invoice = self.invoice_repo.get(invoice_id)
        if not invoice:
            raise InvoiceNotFoundException(f"Invoice with ID {invoice_id} not found")

        self.auth_service.check_can_view_invoice(user, invoice)
        self._record_audit(AuditEventType.INVOICE_VIEWED, user.user_id, invoice.id, invoice.patient_id)
        return invoice

    def issue_invoice(
        self,
        user: AuthenticatedUserContext,
        invoice_id: str,
    ) -> InvoiceRecord:
        """Formally issue a draft invoice, making it payable."""
        self._ensure_enabled()
        invoice = self.invoice_repo.get(invoice_id)
        if not invoice:
            raise InvoiceNotFoundException(f"Invoice with ID {invoice_id} not found")

        self.auth_service.check_can_issue_invoice(user, invoice)
        BillingValidationService.validate_invoice_transition(invoice.status, InvoiceStatus.ISSUED)

        invoice.status = InvoiceStatus.ISSUED
        invoice.issued_at = datetime.now(timezone.utc)
        updated = self.invoice_repo.update(invoice)

        self._record_audit(AuditEventType.INVOICE_ISSUED, user.user_id, updated.id, updated.patient_id)
        self._dispatch_notification(
            updated.patient_id,
            NotificationType.INVOICE_ISSUED,
            {
                "invoice_number": updated.invoice_number,
                "amount": updated.total_in_minor_units / 100.0,
                "currency": updated.currency,
            },
            updated.id,
        )
        return updated

    def cancel_invoice(
        self,
        user: AuthenticatedUserContext,
        invoice_id: str,
        request: InvoiceCancelRequest,
    ) -> InvoiceRecord:
        """Cancel an invoice with mandatory audit reason."""
        self._ensure_enabled()
        invoice = self.invoice_repo.get(invoice_id)
        if not invoice:
            raise InvoiceNotFoundException(f"Invoice with ID {invoice_id} not found")

        if invoice.amount_paid_in_minor_units > 0:
            raise InvoiceAlreadyPaidException(
                "Cannot cancel invoice that has already received payments. Process a refund instead."
            )

        self.auth_service.check_can_cancel_invoice(user, invoice)
        BillingValidationService.validate_invoice_transition(invoice.status, InvoiceStatus.CANCELLED)

        invoice.status = InvoiceStatus.CANCELLED
        invoice.cancelled_at = datetime.now(timezone.utc)
        invoice.cancellation_reason = request.reason
        updated = self.invoice_repo.update(invoice)

        self._record_audit(
            AuditEventType.INVOICE_CANCELLED,
            user.user_id,
            updated.id,
            updated.patient_id,
            {"reason": request.reason},
        )
        return updated

    def apply_payment_delta(
        self,
        invoice_id: str,
        amount_paid_delta: int = 0,
        amount_refunded_delta: int = 0,
    ) -> InvoiceRecord:
        """Atomically update invoice balances and advance status accordingly."""
        invoice = self.invoice_repo.get(invoice_id)
        if not invoice:
            raise InvoiceNotFoundException(f"Invoice with ID {invoice_id} not found")

        invoice.amount_paid_in_minor_units += amount_paid_delta
        invoice.amount_refunded_in_minor_units += amount_refunded_delta
        invoice.outstanding_amount_in_minor_units = (
            invoice.total_in_minor_units
            - invoice.amount_paid_in_minor_units
            + invoice.amount_refunded_in_minor_units
        )

        old_status = invoice.status
        # Determine status transitions based on balances
        if invoice.amount_refunded_in_minor_units >= invoice.total_in_minor_units:
            invoice.status = InvoiceStatus.REFUNDED
        elif invoice.amount_refunded_in_minor_units > 0:
            invoice.status = InvoiceStatus.PARTIALLY_REFUNDED
        elif invoice.outstanding_amount_in_minor_units == 0:
            invoice.status = InvoiceStatus.PAID
            invoice.paid_at = datetime.now(timezone.utc)
        elif invoice.amount_paid_in_minor_units > 0:
            invoice.status = InvoiceStatus.PARTIALLY_PAID

        updated = self.invoice_repo.update(invoice)

        if updated.status != old_status:
            if updated.status == InvoiceStatus.PAID:
                self._record_audit(AuditEventType.INVOICE_PAID, "SYSTEM", updated.id, updated.patient_id)
                self._dispatch_notification(
                    updated.patient_id,
                    NotificationType.INVOICE_PAID,
                    {"invoice_number": updated.invoice_number},
                    updated.id,
                )
            elif updated.status in (InvoiceStatus.REFUNDED, InvoiceStatus.PARTIALLY_REFUNDED):
                self._record_audit(AuditEventType.INVOICE_REFUNDED, "SYSTEM", updated.id, updated.patient_id)

        return updated

    def list_by_patient(
        self,
        user: AuthenticatedUserContext,
        patient_id: str,
        status: Optional[InvoiceStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[InvoiceRecord], int]:
        """List invoices for patient."""
        self._ensure_enabled()
        role_str = user.role.value if hasattr(user.role, "value") else str(user.role)
        if role_str == "PATIENT":
            own_pid = self.auth_service.resolve_patient_id(user)
            if patient_id != own_pid:
                raise InvoiceNotFoundException("Access denied")
        return self.invoice_repo.list_by_patient(patient_id, status=status, limit=limit, offset=offset)

    def list_by_organization(
        self,
        user: AuthenticatedUserContext,
        organization_id: str,
        status: Optional[InvoiceStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[InvoiceRecord], int]:
        """List invoices for an organization."""
        self._ensure_enabled()
        self.auth_service.check_admin_billing_access(user)
        return self.invoice_repo.list_by_organization(organization_id, status=status, limit=limit, offset=offset)

    def list_by_facility(
        self,
        user: AuthenticatedUserContext,
        facility_id: str,
        status: Optional[InvoiceStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[InvoiceRecord], int]:
        """List invoices for a facility."""
        self._ensure_enabled()
        self.auth_service.check_admin_billing_access(user)
        return self.invoice_repo.list_by_facility(facility_id, status=status, limit=limit, offset=offset)

    def list_all(
        self,
        user: AuthenticatedUserContext,
        status: Optional[InvoiceStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[InvoiceRecord], int]:
        """Administrative invoice listing."""
        self._ensure_enabled()
        self.auth_service.check_admin_billing_access(user)
        return self.invoice_repo.list_all(status=status, limit=limit, offset=offset)
