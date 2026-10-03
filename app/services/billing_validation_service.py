"""Billing & Financial Validation Service (Phase 32).

CRITICAL FINANCIAL SAFETY INVARIANTS:
- All monetary amounts MUST be integer minor units (paise/cents).
- Never use floating point or LLMs for calculating prices, taxes, totals, or refunds.
- Currencies must match explicitly (never infer or silently convert).
- State transitions must strictly follow approved lifecycles.
"""

from __future__ import annotations

import logging
from typing import List, Tuple

from app.core.exceptions import (
    InvoiceAmountMismatchException,
    InvoiceCurrencyMismatchException,
    InvoiceInvalidStateException,
    PaymentAmountInvalidException,
    PaymentAmountMismatchException,
    PaymentCurrencyMismatchException,
    PaymentInvalidStateException,
    RefundInvalidAmountException,
)
from app.schemas.billing_item import BillingItemCreate, BillingItemRecord
from app.schemas.invoice import InvoiceStatus
from app.schemas.payment import PaymentStatus
from app.schemas.refund import RefundStatus

logger = logging.getLogger(__name__)

# Allowed state transition graphs
ALLOWED_INVOICE_TRANSITIONS = {
    InvoiceStatus.DRAFT: {InvoiceStatus.ISSUED, InvoiceStatus.CANCELLED, InvoiceStatus.VOID},
    InvoiceStatus.ISSUED: {
        InvoiceStatus.PARTIALLY_PAID,
        InvoiceStatus.PAID,
        InvoiceStatus.OVERDUE,
        InvoiceStatus.CANCELLED,
        InvoiceStatus.VOID,
    },
    InvoiceStatus.PARTIALLY_PAID: {
        InvoiceStatus.PAID,
        InvoiceStatus.OVERDUE,
        InvoiceStatus.PARTIALLY_REFUNDED,
    },
    InvoiceStatus.PAID: {InvoiceStatus.PARTIALLY_REFUNDED, InvoiceStatus.REFUNDED},
    InvoiceStatus.OVERDUE: {InvoiceStatus.PARTIALLY_PAID, InvoiceStatus.PAID, InvoiceStatus.CANCELLED},
    InvoiceStatus.PARTIALLY_REFUNDED: {InvoiceStatus.REFUNDED},
    InvoiceStatus.CANCELLED: set(),
    InvoiceStatus.VOID: set(),
    InvoiceStatus.REFUNDED: set(),
    InvoiceStatus.FAILED: set(),
}

ALLOWED_PAYMENT_TRANSITIONS = {
    PaymentStatus.PENDING: {
        PaymentStatus.PROCESSING,
        PaymentStatus.CANCELLED,
        PaymentStatus.FAILED,
    },
    PaymentStatus.PROCESSING: {
        PaymentStatus.SUCCEEDED,
        PaymentStatus.FAILED,
        PaymentStatus.CANCELLED,
        PaymentStatus.UNKNOWN,
        PaymentStatus.RECONCILIATION_REQUIRED,
    },
    PaymentStatus.UNKNOWN: {
        PaymentStatus.RECONCILIATION_REQUIRED,
        PaymentStatus.SUCCEEDED,
        PaymentStatus.FAILED,
    },
    PaymentStatus.RECONCILIATION_REQUIRED: {
        PaymentStatus.SUCCEEDED,
        PaymentStatus.FAILED,
        PaymentStatus.REFUNDED,
    },
    PaymentStatus.SUCCEEDED: {PaymentStatus.REFUNDED},
    PaymentStatus.FAILED: set(),
    PaymentStatus.CANCELLED: set(),
    PaymentStatus.REFUNDED: set(),
}

ALLOWED_REFUND_TRANSITIONS = {
    RefundStatus.REQUESTED: {RefundStatus.PROCESSING, RefundStatus.REJECTED, RefundStatus.FAILED},
    RefundStatus.PROCESSING: {RefundStatus.COMPLETED, RefundStatus.FAILED, RefundStatus.REJECTED},
    RefundStatus.COMPLETED: set(),
    RefundStatus.FAILED: set(),
    RefundStatus.REJECTED: set(),
}


class BillingValidationService:
    """Deterministic validator for billing arithmetic, currencies, and state machines."""

    @staticmethod
    def calculate_item_total(item: BillingItemCreate) -> int:
        """Calculate line item total using integer minor units: (price * qty) + tax - discount."""
        if item.unit_price_in_minor_units <= 0:
            raise PaymentAmountInvalidException("Line item unit price must be greater than zero")
        if item.quantity <= 0:
            raise PaymentAmountInvalidException("Line item quantity must be at least 1")
        if item.tax_in_minor_units < 0:
            raise PaymentAmountInvalidException("Tax amount cannot be negative")
        if item.discount_in_minor_units < 0:
            raise PaymentAmountInvalidException("Discount amount cannot be negative")

        subtotal = item.unit_price_in_minor_units * item.quantity
        if item.discount_in_minor_units > (subtotal + item.tax_in_minor_units):
            raise PaymentAmountInvalidException("Discount cannot exceed item gross total")

        return subtotal + item.tax_in_minor_units - item.discount_in_minor_units

    @classmethod
    def calculate_invoice_totals(
        cls,
        items: List[BillingItemCreate],
        default_currency: str = "INR",
    ) -> Tuple[List[BillingItemRecord], int, int, int, int]:
        """Deterministically calculate subtotal, tax, discount, and total for an invoice.

        Returns: (records, subtotal, tax, discount, total)
        """
        if not items:
            raise PaymentAmountInvalidException("Invoice must contain at least one line item")

        subtotal = 0
        total_tax = 0
        total_discount = 0
        total = 0
        records: List[BillingItemRecord] = []

        for item in items:
            if item.currency.upper() != default_currency.upper():
                raise InvoiceCurrencyMismatchException(
                    f"Line item currency {item.currency} does not match invoice currency {default_currency}"
                )
            item_tot = cls.calculate_item_total(item)
            subtotal += item.unit_price_in_minor_units * item.quantity
            total_tax += item.tax_in_minor_units
            total_discount += item.discount_in_minor_units
            total += item_tot

            record = BillingItemRecord(
                invoice_id="",  # Bound by caller
                description=item.description,
                category=item.category,
                unit_price_in_minor_units=item.unit_price_in_minor_units,
                quantity=item.quantity,
                tax_in_minor_units=item.tax_in_minor_units,
                discount_in_minor_units=item.discount_in_minor_units,
                total_in_minor_units=item_tot,
                currency=default_currency.upper(),
                billable_event_id=item.billable_event_id,
                appointment_id=item.appointment_id,
                metadata=item.metadata,
            )
            records.append(record)

        expected_total = subtotal + total_tax - total_discount
        if total != expected_total or total <= 0:
            raise InvoiceAmountMismatchException(
                f"Computed invoice total ({total}) does not match items sum ({expected_total}) or is non-positive"
            )

        return records, subtotal, total_tax, total_discount, total

    @staticmethod
    def validate_currencies(expected: str, actual: str) -> None:
        """Ensure currency codes match strictly without conversion."""
        if expected.strip().upper() != actual.strip().upper():
            raise PaymentCurrencyMismatchException(
                f"Currency mismatch: expected {expected.upper()}, received {actual.upper()}"
            )

    @staticmethod
    def validate_payment_amount(
        requested_amount: int,
        outstanding_amount: int,
    ) -> None:
        """Ensure payment amount is valid and does not exceed invoice balance."""
        if requested_amount <= 0:
            raise PaymentAmountInvalidException("Payment amount must be greater than zero")
        if requested_amount > outstanding_amount:
            raise PaymentAmountMismatchException(
                f"Requested payment ({requested_amount}) exceeds outstanding invoice amount ({outstanding_amount})"
            )

    @staticmethod
    def validate_refund_amount(
        requested_refund: int,
        paid_amount: int,
        already_refunded: int,
    ) -> None:
        """Ensure refund does not exceed refundable balance."""
        if requested_refund <= 0:
            raise RefundInvalidAmountException("Refund amount must be greater than zero")
        refundable = paid_amount - already_refunded
        if requested_refund > refundable:
            raise RefundInvalidAmountException(
                f"Requested refund ({requested_refund}) exceeds refundable amount ({refundable})"
            )

    @staticmethod
    def validate_invoice_transition(current: InvoiceStatus, target: InvoiceStatus) -> None:
        """Enforce strict invoice lifecycle state machine."""
        allowed = ALLOWED_INVOICE_TRANSITIONS.get(current, set())
        if target not in allowed:
            raise InvoiceInvalidStateException(
                f"Illegal invoice transition from {current.value} to {target.value}"
            )

    @staticmethod
    def validate_payment_transition(current: PaymentStatus, target: PaymentStatus) -> None:
        """Enforce strict payment transaction state machine."""
        allowed = ALLOWED_PAYMENT_TRANSITIONS.get(current, set())
        if target not in allowed:
            raise PaymentInvalidStateException(
                f"Illegal payment transition from {current.value} to {target.value}"
            )

    @staticmethod
    def validate_refund_transition(current: RefundStatus, target: RefundStatus) -> None:
        """Enforce strict refund transaction state machine."""
        allowed = ALLOWED_REFUND_TRANSITIONS.get(current, set())
        if target not in allowed:
            raise PaymentInvalidStateException(
                f"Illegal refund transition from {current.value} to {target.value}"
            )
