"""Billing Authorization Service (Phase 32).

Enforces role-based, identity-scoped, and multi-tenant access control for
billing, invoices, payments, refunds, and reconciliation.
Prevents cross-patient financial data exposure (BOLA/IDOR).
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from app.core.exceptions import (
    BillingAccessDeniedException,
    FacilityBillingAccessDeniedException,
    InvoiceNotAuthorizedException,
    OrganizationBillingAccessDeniedException,
    PaymentNotAuthorizedException,
    RefundNotAuthorizedException,
)
from app.core.policies import Permission, role_has_permission
from app.schemas.invoice import InvoiceRecord
from app.schemas.payment import PaymentRecord
from app.schemas.user import AuthenticatedUserContext

logger = logging.getLogger(__name__)


class BillingAuthorizationService:
    """Authorization evaluation for billing and payment operations."""

    def __init__(self, patient_repo: Optional[Any] = None) -> None:
        self.patient_repo = patient_repo

    def resolve_patient_id(self, user: AuthenticatedUserContext) -> str:
        """Resolve canonical patient identifier from user context."""
        pid = getattr(user, "patient_id", None)
        if pid:
            return pid
        if self.patient_repo:
            user_to_patient = getattr(self.patient_repo, "_user_to_patient", {})
            p_rec = user_to_patient.get(user.user_id)
            if p_rec:
                return p_rec
        return user.user_id

    def check_can_view_invoice(
        self,
        user: AuthenticatedUserContext,
        invoice: InvoiceRecord,
    ) -> None:
        """Verify actor has authority to view target invoice."""
        role_str = user.role.value if hasattr(user.role, "value") else str(user.role)

        if not role_has_permission(role_str, Permission.INVOICE_READ):
            raise InvoiceNotAuthorizedException("User lacks INVOICE_READ permission")

        # Patient scope check
        if role_str == "PATIENT":
            own_patient_id = self.resolve_patient_id(user)
            if invoice.patient_id != own_patient_id and invoice.patient_id != user.user_id:
                logger.warning(
                    f"Cross-patient invoice read denied: User {user.user_id} tried accessing invoice {invoice.id} of {invoice.patient_id}"
                )
                raise InvoiceNotAuthorizedException("Patients can only view their own invoices")
            return

        # Organization / facility scope check for org staff
        user_org = getattr(user, "organization_id", None)
        if user_org and invoice.organization_id and user_org != invoice.organization_id:
            raise OrganizationBillingAccessDeniedException(
                "Access denied: invoice belongs to a different organization"
            )

        user_fac = getattr(user, "facility_id", None)
        if user_fac and invoice.facility_id and user_fac != invoice.facility_id:
            raise FacilityBillingAccessDeniedException(
                "Access denied: invoice belongs to a different facility"
            )

    def check_can_create_invoice(
        self,
        user: AuthenticatedUserContext,
        target_patient_id: str,
        organization_id: Optional[str] = None,
        facility_id: Optional[str] = None,
    ) -> None:
        """Verify actor can create or draft invoices."""
        role_str = user.role.value if hasattr(user.role, "value") else str(user.role)

        if not role_has_permission(role_str, Permission.INVOICE_CREATE):
            raise InvoiceNotAuthorizedException("User lacks INVOICE_CREATE permission")

        if role_str == "PATIENT":
            own_patient_id = self.resolve_patient_id(user)
            if target_patient_id != own_patient_id and target_patient_id != user.user_id:
                raise InvoiceNotAuthorizedException("Patients can only create invoices for themselves")

        user_org = getattr(user, "organization_id", None)
        if user_org and organization_id and user_org != organization_id:
            raise OrganizationBillingAccessDeniedException("Cannot create invoice for external organization")

        user_fac = getattr(user, "facility_id", None)
        if user_fac and facility_id and user_fac != facility_id:
            raise FacilityBillingAccessDeniedException("Cannot create invoice for external facility")

    def check_can_issue_invoice(
        self,
        user: AuthenticatedUserContext,
        invoice: InvoiceRecord,
    ) -> None:
        """Verify actor can issue invoice."""
        role_str = user.role.value if hasattr(user.role, "value") else str(user.role)

        if not role_has_permission(role_str, Permission.INVOICE_ISSUE):
            raise InvoiceNotAuthorizedException("User lacks INVOICE_ISSUE permission")

    def check_can_cancel_invoice(
        self,
        user: AuthenticatedUserContext,
        invoice: InvoiceRecord,
    ) -> None:
        """Verify actor can cancel invoice."""
        role_str = user.role.value if hasattr(user.role, "value") else str(user.role)

        if not role_has_permission(role_str, Permission.INVOICE_CANCEL):
            raise InvoiceNotAuthorizedException("User lacks INVOICE_CANCEL permission")

    def check_can_create_payment(
        self,
        user: AuthenticatedUserContext,
        invoice: InvoiceRecord,
    ) -> None:
        """Verify actor can initiate payment for an invoice."""
        role_str = user.role.value if hasattr(user.role, "value") else str(user.role)

        if not role_has_permission(role_str, Permission.PAYMENT_CREATE):
            raise PaymentNotAuthorizedException("User lacks PAYMENT_CREATE permission")

        if role_str == "PATIENT":
            own_patient_id = self.resolve_patient_id(user)
            if invoice.patient_id != own_patient_id and invoice.patient_id != user.user_id:
                raise PaymentNotAuthorizedException("Patients can only pay their own invoices")

    def check_can_view_payment(
        self,
        user: AuthenticatedUserContext,
        payment: PaymentRecord,
    ) -> None:
        """Verify actor can view payment details."""
        role_str = user.role.value if hasattr(user.role, "value") else str(user.role)

        if not role_has_permission(role_str, Permission.PAYMENT_READ):
            raise PaymentNotAuthorizedException("User lacks PAYMENT_READ permission")

        if role_str == "PATIENT":
            own_patient_id = self.resolve_patient_id(user)
            if payment.patient_id != own_patient_id and payment.patient_id != user.user_id:
                raise PaymentNotAuthorizedException("Patients can only view their own payments")

    def check_can_refund_payment(
        self,
        user: AuthenticatedUserContext,
        payment: PaymentRecord,
    ) -> None:
        """Verify actor can initiate a refund."""
        role_str = user.role.value if hasattr(user.role, "value") else str(user.role)

        if not role_has_permission(role_str, Permission.PAYMENT_REFUND):
            raise RefundNotAuthorizedException("User lacks PAYMENT_REFUND permission")

        if role_str == "PATIENT":
            raise RefundNotAuthorizedException("Patients cannot initiate administrative refunds directly")

    def check_admin_billing_access(
        self,
        user: AuthenticatedUserContext,
        required_permission: Permission = Permission.ADMIN_BILLING_VIEW,
    ) -> None:
        """Verify administrative billing access."""
        role_str = user.role.value if hasattr(user.role, "value") else str(user.role)

        if not role_has_permission(role_str, required_permission):
            raise BillingAccessDeniedException(
                f"Administrative billing access denied. Required: {required_permission.value}"
            )
