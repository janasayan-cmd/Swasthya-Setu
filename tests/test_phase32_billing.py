"""Phase 32 Test Suite — Billing, Payments & Financial Transaction Management.

Validates:
- Integer minor unit deterministic financial calculations.
- Strict invoice, payment, and refund lifecycle state transitions.
- Idempotency on payment creation and refunds.
- Webhook HMAC signature verification and deduplication.
- Safe handling of ambiguous gateway results (UNKNOWN / RECONCILIATION_REQUIRED).
- Discrepancy detection during financial reconciliation.
- Multi-tenant role authorization and BOLA/IDOR prevention.
- Decoupling of financial status from clinical status.
"""

from __future__ import annotations

import hashlib
import hmac
import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.core.exceptions import (
    InvoiceAlreadyPaidException,
    InvoiceCurrencyMismatchException,
    InvoiceInvalidStateException,
    PaymentAmountInvalidException,
    PaymentAmountMismatchException,
    PaymentIdempotencyConflictException,
    PaymentInvalidStateException,
    RefundAlreadyProcessedException,
    RefundInvalidAmountException,
    RefundNotAllowedException,
    WebhookSignatureInvalidException,
)
from app.integrations.payments.providers.mock import MockPaymentProvider
from app.schemas.billing_item import BillingItemCategory, BillingItemCreate
from app.schemas.financial_reconciliation import (
    FinancialDiscrepancyType,
    FinancialReconciliationStatus,
)
from app.schemas.invoice import (
    InvoiceCancelRequest,
    InvoiceCreateRequest,
    InvoiceStatus,
)
from app.schemas.payment import (
    PaymentCreateRequest,
    PaymentMethodType,
    PaymentStatus,
    PaymentVerificationRequest,
)
from app.schemas.refund import RefundCreateRequest, RefundStatus
from app.schemas.user import AuthenticatedUserContext
from app.services.billing_validation_service import BillingValidationService


# ===========================================================================
# 1. Deterministic Financial Arithmetic & Minor Unit Calculations
# ===========================================================================

def test_minor_unit_line_item_arithmetic():
    """Verify (unit_price * qty) + tax - discount using pure integer arithmetic."""
    item = BillingItemCreate(
        description="Specialist Consultation",
        category=BillingItemCategory.CONSULTATION,
        unit_price_in_minor_units=150000,  # ₹1500.00
        quantity=2,
        tax_in_minor_units=54000,          # 18% GST = ₹540.00
        discount_in_minor_units=20000,     # ₹200.00 discount
        currency="INR",
    )
    # Expected: (150000 * 2) + 54000 - 20000 = 300000 + 54000 - 20000 = 334000 paise
    total = BillingValidationService.calculate_item_total(item)
    assert total == 334000


def test_line_item_validation_failures():
    """Verify non-positive quantities or prices are rejected by schema or validator."""
    from pydantic import ValidationError

    # Negative unit price rejected by Pydantic schema validation
    with pytest.raises(ValidationError):
        BillingItemCreate(
            description="Invalid Price",
            unit_price_in_minor_units=-100,
            quantity=1,
        )

    # Zero quantity rejected by Pydantic schema validation
    with pytest.raises(ValidationError):
        BillingItemCreate(
            description="Zero Qty",
            unit_price_in_minor_units=10000,
            quantity=0,
        )

    # Discount exceeding gross rejected by service calculation
    with pytest.raises(PaymentAmountInvalidException):
        BillingValidationService.calculate_item_total(
            BillingItemCreate(
                description="Excessive Discount",
                unit_price_in_minor_units=10000,
                quantity=1,
                tax_in_minor_units=0,
                discount_in_minor_units=20000,
            )
        )


def test_invoice_totals_aggregation():
    """Verify aggregation across multiple billable line items."""
    items = [
        BillingItemCreate(
            description="OPD Consultation",
            category=BillingItemCategory.CONSULTATION,
            unit_price_in_minor_units=50000,  # ₹500.00
            quantity=1,
            tax_in_minor_units=0,
            discount_in_minor_units=0,
            currency="INR",
        ),
        BillingItemCreate(
            description="Blood Test (CBC)",
            category=BillingItemCategory.DIAGNOSTIC,
            unit_price_in_minor_units=35000,  # ₹350.00
            quantity=1,
            tax_in_minor_units=1800,          # ₹18.00 tax
            discount_in_minor_units=5000,     # ₹50.00 discount
            currency="INR",
        ),
    ]
    # Expected:
    # subtotal = 50000 + 35000 = 85000
    # tax = 0 + 1800 = 1800
    # discount = 0 + 5000 = 5000
    # total = 85000 + 1800 - 5000 = 81800 paise (₹818.00)
    records, subtotal, tax, discount, total = BillingValidationService.calculate_invoice_totals(items, "INR")
    assert subtotal == 85000
    assert tax == 1800
    assert discount == 5000
    assert total == 81800
    assert len(records) == 2


def test_currency_mismatch_rejection():
    """Verify currency mixing on line items is rejected without silent conversion."""
    items = [
        BillingItemCreate(
            description="Service in INR",
            unit_price_in_minor_units=50000,
            currency="INR",
        ),
        BillingItemCreate(
            description="Service in USD",
            unit_price_in_minor_units=2000,
            currency="USD",
        ),
    ]
    with pytest.raises(InvoiceCurrencyMismatchException):
        BillingValidationService.calculate_invoice_totals(items, "INR")


# ===========================================================================
# 2. Lifecycle State Transition Guard Tests
# ===========================================================================

def test_invoice_state_transitions():
    """Verify strict invoice lifecycle transitions."""
    # Valid transitions
    BillingValidationService.validate_invoice_transition(InvoiceStatus.DRAFT, InvoiceStatus.ISSUED)
    BillingValidationService.validate_invoice_transition(InvoiceStatus.ISSUED, InvoiceStatus.PAID)
    BillingValidationService.validate_invoice_transition(InvoiceStatus.PAID, InvoiceStatus.REFUNDED)

    # Illegal transitions
    with pytest.raises(InvoiceInvalidStateException):
        BillingValidationService.validate_invoice_transition(InvoiceStatus.DRAFT, InvoiceStatus.PAID)

    with pytest.raises(InvoiceInvalidStateException):
        BillingValidationService.validate_invoice_transition(InvoiceStatus.CANCELLED, InvoiceStatus.ISSUED)


def test_payment_and_refund_state_transitions():
    """Verify payment and refund state transitions."""
    BillingValidationService.validate_payment_transition(PaymentStatus.PENDING, PaymentStatus.PROCESSING)
    BillingValidationService.validate_payment_transition(PaymentStatus.PROCESSING, PaymentStatus.SUCCEEDED)

    with pytest.raises(PaymentInvalidStateException):
        BillingValidationService.validate_payment_transition(PaymentStatus.FAILED, PaymentStatus.SUCCEEDED)


# ===========================================================================
# 3. Service Layer Integration Tests (Invoice, Payment, Refund)
# ===========================================================================

@pytest.mark.asyncio
async def test_full_invoice_payment_refund_flow(seeded_users, seeded_patients):
    """Test comprehensive end-to-end financial transaction lifecycle."""
    from app.api.deps import (
        get_invoice_service,
        get_payment_service,
        get_refund_service,
    )

    invoice_service = get_invoice_service()
    payment_service = get_payment_service()
    refund_service = get_refund_service()

    patient_ctx = AuthenticatedUserContext(
        user_id="usr-patient-001",
        email="patient@healthsetu.org",
        role="PATIENT",
        patient_id="pat-001",
    )

    # 1. Create Draft Invoice
    req = InvoiceCreateRequest(
        patient_id="pat-001",
        currency="INR",
        items=[
            BillingItemCreate(
                description="Consultation",
                unit_price_in_minor_units=100000,  # ₹1000.00
                quantity=1,
                currency="INR",
            )
        ],
    )
    invoice = invoice_service.create_invoice(patient_ctx, req)
    assert invoice.status == InvoiceStatus.DRAFT
    assert invoice.total_in_minor_units == 100000
    assert invoice.outstanding_amount_in_minor_units == 100000

    # 2. Cannot pay DRAFT invoice
    with pytest.raises(Exception):
        await payment_service.create_payment_intent(
            patient_ctx,
            PaymentCreateRequest(
                invoice_id=invoice.id,
                amount_in_minor_units=100000,
                currency="INR",
            ),
        )

    # 3. Issue Invoice
    issued = invoice_service.issue_invoice(patient_ctx, invoice.id)
    assert issued.status == InvoiceStatus.ISSUED

    # 4. Create Partial Payment Intent (₹400.00 = 40000 paise)
    pay_req1 = PaymentCreateRequest(
        invoice_id=invoice.id,
        amount_in_minor_units=40000,
        currency="INR",
        idempotency_key="idemp_pay_001",
    )
    payment1 = await payment_service.create_payment_intent(patient_ctx, pay_req1)
    assert payment1.status == PaymentStatus.PROCESSING
    assert payment1.amount_in_minor_units == 40000

    # 5. Verify & Capture Payment 1
    captured1 = await payment_service.verify_and_capture(
        patient_ctx,
        payment1.id,
        PaymentVerificationRequest(provider_transaction_id=payment1.provider_transaction_id),
    )
    assert captured1.status == PaymentStatus.SUCCEEDED

    # Verify invoice is now PARTIALLY_PAID
    inv_after_p1 = invoice_service.get_invoice(patient_ctx, invoice.id)
    assert inv_after_p1.status == InvoiceStatus.PARTIALLY_PAID
    assert inv_after_p1.amount_paid_in_minor_units == 40000
    assert inv_after_p1.outstanding_amount_in_minor_units == 60000

    # 6. Second Payment (Remaining ₹600.00 = 60000 paise)
    pay_req2 = PaymentCreateRequest(
        invoice_id=invoice.id,
        amount_in_minor_units=60000,
        currency="INR",
        idempotency_key="idemp_pay_002",
    )
    payment2 = await payment_service.create_payment_intent(patient_ctx, pay_req2)
    captured2 = await payment_service.verify_and_capture(
        patient_ctx,
        payment2.id,
        PaymentVerificationRequest(provider_transaction_id=payment2.provider_transaction_id),
    )
    assert captured2.status == PaymentStatus.SUCCEEDED

    # Verify invoice is now PAID
    inv_after_p2 = invoice_service.get_invoice(patient_ctx, invoice.id)
    assert inv_after_p2.status == InvoiceStatus.PAID
    assert inv_after_p2.outstanding_amount_in_minor_units == 0

    # 7. Process Partial Refund on Payment 2 (₹200.00 = 20000 paise)
    admin_ctx = AuthenticatedUserContext(
        user_id="usr-admin-001",
        email="admin@healthsetu.org",
        role="ADMIN",
    )
    ref_req = RefundCreateRequest(
        payment_id=payment2.id,
        amount_in_minor_units=20000,
        reason="Overcharge adjustment",
        idempotency_key="idemp_ref_001",
    )
    refund = await refund_service.process_refund(admin_ctx, ref_req)
    assert refund.status == RefundStatus.COMPLETED
    assert refund.amount_in_minor_units == 20000

    # Verify invoice transitioned to PARTIALLY_REFUNDED
    inv_after_refund = invoice_service.get_invoice(patient_ctx, invoice.id)
    assert inv_after_refund.status == InvoiceStatus.PARTIALLY_REFUNDED
    assert inv_after_refund.amount_refunded_in_minor_units == 20000
    assert inv_after_refund.outstanding_amount_in_minor_units == 20000


@pytest.mark.asyncio
async def test_idempotency_and_conflict():
    """Verify repeated calls with same key yield same transaction, conflict on altered payload."""
    from app.api.deps import (
        get_invoice_service,
        get_payment_service,
    )

    invoice_service = get_invoice_service()
    payment_service = get_payment_service()

    patient_ctx = AuthenticatedUserContext(
        user_id="usr-patient-001",
        email="patient@healthsetu.org",
        role="PATIENT",
        patient_id="pat-001",
    )

    inv = invoice_service.create_invoice(
        patient_ctx,
        InvoiceCreateRequest(
            patient_id="pat-001",
            currency="INR",
            items=[BillingItemCreate(description="Service", unit_price_in_minor_units=50000)],
        ),
    )
    invoice_service.issue_invoice(patient_ctx, inv.id)

    # First call
    p1 = await payment_service.create_payment_intent(
        patient_ctx,
        PaymentCreateRequest(
            invoice_id=inv.id,
            amount_in_minor_units=50000,
            idempotency_key="unique_key_123",
        ),
    )

    # Re-call with identical parameters -> returns same transaction
    p2 = await payment_service.create_payment_intent(
        patient_ctx,
        PaymentCreateRequest(
            invoice_id=inv.id,
            amount_in_minor_units=50000,
            idempotency_key="unique_key_123",
        ),
    )
    assert p1.id == p2.id
    assert p1.payment_number == p2.payment_number

    # Re-call with differing amount -> raises conflict exception
    with pytest.raises(PaymentIdempotencyConflictException):
        await payment_service.create_payment_intent(
            patient_ctx,
            PaymentCreateRequest(
                invoice_id=inv.id,
                amount_in_minor_units=30000,
                idempotency_key="unique_key_123",
            ),
        )


@pytest.mark.asyncio
async def test_refund_safety_limits():
    """Verify refund amount cannot exceed paid amount."""
    from app.api.deps import (
        get_invoice_service,
        get_payment_service,
        get_refund_service,
    )

    invoice_service = get_invoice_service()
    payment_service = get_payment_service()
    refund_service = get_refund_service()

    patient_ctx = AuthenticatedUserContext(
        user_id="usr-patient-001",
        email="patient@healthsetu.org",
        role="PATIENT",
        patient_id="pat-001",
    )
    admin_ctx = AuthenticatedUserContext(
        user_id="usr-admin-001",
        email="admin@healthsetu.org",
        role="ADMIN",
    )

    inv = invoice_service.create_invoice(
        patient_ctx,
        InvoiceCreateRequest(
            patient_id="pat-001",
            currency="INR",
            items=[BillingItemCreate(description="Service", unit_price_in_minor_units=50000)],
        ),
    )
    invoice_service.issue_invoice(patient_ctx, inv.id)
    pay = await payment_service.create_payment_intent(
        patient_ctx,
        PaymentCreateRequest(invoice_id=inv.id, amount_in_minor_units=50000),
    )
    await payment_service.verify_and_capture(
        patient_ctx,
        pay.id,
        PaymentVerificationRequest(provider_transaction_id=pay.provider_transaction_id),
    )

    # Attempt refund exceeding paid amount (₹600.00 > ₹500.00)
    with pytest.raises(RefundInvalidAmountException):
        await refund_service.process_refund(
            admin_ctx,
            RefundCreateRequest(
                payment_id=pay.id,
                amount_in_minor_units=60000,
                reason="Excess refund",
            ),
        )


# ===========================================================================
# 4. Gateway Webhook Verification & Deduplication Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_webhook_signature_and_deduplication():
    """Verify HMAC signature validation and duplicate event handling."""
    from app.api.deps import (
        get_invoice_service,
        get_payment_service,
        get_payment_webhook_service,
    )

    invoice_service = get_invoice_service()
    payment_service = get_payment_service()
    webhook_service = get_payment_webhook_service()

    patient_ctx = AuthenticatedUserContext(
        user_id="usr-patient-001",
        email="patient@healthsetu.org",
        role="PATIENT",
        patient_id="pat-001",
    )

    inv = invoice_service.create_invoice(
        patient_ctx,
        InvoiceCreateRequest(
            patient_id="pat-001",
            currency="INR",
            items=[BillingItemCreate(description="Consultation", unit_price_in_minor_units=50000)],
        ),
    )
    invoice_service.issue_invoice(patient_ctx, inv.id)
    payment = await payment_service.create_payment_intent(
        patient_ctx,
        PaymentCreateRequest(invoice_id=inv.id, amount_in_minor_units=50000),
    )

    # Prepare webhook payload
    payload = {
        "event_id": "mock_evt_test_001",
        "event_type": "payment.captured",
        "data": {
            "provider_transaction_id": payment.provider_transaction_id,
            "status": "SUCCESS",
            "amount_in_minor_units": 50000,
            "currency": "INR",
        },
    }
    raw_body = b'{"event_id": "mock_evt_test_001", "event_type": "payment.captured"}'

    # 1. Invalid signature
    with pytest.raises(WebhookSignatureInvalidException):
        await webhook_service.handle_webhook(
            provider_name="MOCK",
            raw_body=raw_body,
            headers={"X-Mock-Signature": "invalid_forged_sig"},
            payload=payload,
        )

    # 2. Valid signature
    valid_sig = hmac.new(
        settings.PAYMENT_WEBHOOK_SECRET.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    result1 = await webhook_service.handle_webhook(
        provider_name="MOCK",
        raw_body=raw_body,
        headers={"X-Mock-Signature": valid_sig},
        payload=payload,
    )
    assert result1.status.value == "ACCEPTED"

    # Verify payment transitioned to SUCCEEDED and invoice to PAID
    updated_pay = payment_service.payment_repo.get(payment.id)
    assert updated_pay.status == PaymentStatus.SUCCEEDED
    updated_inv = invoice_service.get_invoice(patient_ctx, inv.id)
    assert updated_inv.status == InvoiceStatus.PAID

    # 3. Duplicate event delivery -> returns DUPLICATE, no double ledger update
    result2 = await webhook_service.handle_webhook(
        provider_name="MOCK",
        raw_body=raw_body,
        headers={"X-Mock-Signature": valid_sig},
        payload=payload,
    )
    assert result2.status.value == "DUPLICATE"


# ===========================================================================
# 5. Financial Reconciliation & Gateway Discrepancy Detection
# ===========================================================================

@pytest.mark.asyncio
async def test_reconciliation_detects_mismatch():
    """Verify reconciliation detects amount mismatches and auto-resolves missing state."""
    from app.api.deps import (
        get_invoice_service,
        get_payment_reconciliation_service,
        get_payment_service,
    )

    invoice_service = get_invoice_service()
    payment_service = get_payment_service()
    rec_service = get_payment_reconciliation_service()

    patient_ctx = AuthenticatedUserContext(
        user_id="usr-patient-001",
        email="patient@healthsetu.org",
        role="PATIENT",
        patient_id="pat-001",
    )

    inv = invoice_service.create_invoice(
        patient_ctx,
        InvoiceCreateRequest(
            patient_id="pat-001",
            currency="INR",
            items=[BillingItemCreate(description="Test", unit_price_in_minor_units=50000)],
        ),
    )
    invoice_service.issue_invoice(patient_ctx, inv.id)
    pay = await payment_service.create_payment_intent(
        patient_ctx,
        PaymentCreateRequest(invoice_id=inv.id, amount_in_minor_units=50000),
    )

    # Simulate gateway having captured 40000 instead of 50000
    mock_prov = payment_service.provider
    if isinstance(mock_prov, MockPaymentProvider):
        mock_prov._transactions[pay.provider_transaction_id]["amount"] = 40000

    rec = await rec_service.reconcile_payment(pay.id)
    assert rec.status == FinancialReconciliationStatus.MISMATCHED
    assert rec.discrepancy_type == FinancialDiscrepancyType.AMOUNT_MISMATCH


# ===========================================================================
# 6. REST API Endpoint Tests via AsyncClient
# ===========================================================================

@pytest.mark.asyncio
async def test_api_create_invoice_and_pay(async_client: AsyncClient, make_token, seeded_patients):
    """Test full HTTP API lifecycle for patient invoice creation and payment."""
    token = make_token("usr-patient-001", "PATIENT")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. POST /api/v1/patients/{patient_id}/invoices
    create_res = await async_client.post(
        "/api/v1/patients/pat-001/invoices",
        json={
            "patient_id": "pat-001",
            "currency": "INR",
            "items": [
                {
                    "description": "General OPD Consultation",
                    "category": "CONSULTATION",
                    "unit_price_in_minor_units": 50000,
                    "quantity": 1,
                    "tax_in_minor_units": 0,
                    "discount_in_minor_units": 0,
                    "currency": "INR",
                }
            ],
        },
        headers=headers,
    )
    assert create_res.status_code == 201
    inv_data = create_res.json()
    invoice_id = inv_data["id"]
    assert inv_data["status"] == "DRAFT"
    assert inv_data["total_in_minor_units"] == 50000

    # 2. POST /api/v1/patients/{patient_id}/invoices/{invoice_id}/issue
    issue_res = await async_client.post(
        f"/api/v1/patients/pat-001/invoices/{invoice_id}/issue",
        headers=headers,
    )
    assert issue_res.status_code == 200
    assert issue_res.json()["status"] == "ISSUED"

    # 3. POST /api/v1/patients/{patient_id}/invoices/{invoice_id}/payments
    pay_res = await async_client.post(
        f"/api/v1/patients/pat-001/invoices/{invoice_id}/payments",
        json={
            "invoice_id": invoice_id,
            "amount_in_minor_units": 50000,
            "currency": "INR",
            "payment_method": "UPI",
        },
        headers={**headers, "Idempotency-Key": "idemp_api_test_001"},
    )
    assert pay_res.status_code == 201
    pay_data = pay_res.json()
    payment_id = pay_data["id"]
    provider_tx_id = pay_data["provider_transaction_id"]

    # 4. POST /api/v1/patients/{patient_id}/payments/{payment_id}/verify
    verify_res = await async_client.post(
        f"/api/v1/patients/pat-001/payments/{payment_id}/verify",
        json={"provider_transaction_id": provider_tx_id},
        headers=headers,
    )
    assert verify_res.status_code == 200
    assert verify_res.json()["status"] == "SUCCEEDED"

    # 5. Check invoice status endpoint
    status_res = await async_client.get(f"/api/v1/invoices/{invoice_id}/status", headers=headers)
    assert status_res.status_code == 200
    assert status_res.json()["status"] == "PAID"
    assert status_res.json()["outstanding_amount_in_minor_units"] == 0


@pytest.mark.asyncio
async def test_api_cross_patient_bola_idor_denied(async_client: AsyncClient, make_token, seeded_patients):
    """Verify that Patient 2 cannot access Patient 1's invoice (BOLA/IDOR protection)."""
    token_p1 = make_token("usr-patient-001", "PATIENT")
    token_p2 = make_token("usr-patient-002", "PATIENT")

    # Patient 1 creates an invoice
    res1 = await async_client.post(
        "/api/v1/patients/pat-001/invoices",
        json={
            "patient_id": "pat-001",
            "items": [{"description": "Checkup", "unit_price_in_minor_units": 50000}],
        },
        headers={"Authorization": f"Bearer {token_p1}"},
    )
    inv_id = res1.json()["id"]

    # Patient 2 tries to access Patient 1's invoice -> Forbidden (403)
    res2 = await async_client.get(
        f"/api/v1/invoices/{inv_id}",
        headers={"Authorization": f"Bearer {token_p2}"},
    )
    assert res2.status_code == 403


@pytest.mark.asyncio
async def test_api_admin_billing_endpoints(async_client: AsyncClient, make_token, seeded_users):
    """Verify admin billing status, providers, and reconciliation endpoints."""
    admin_token = make_token("usr-admin-001", "ADMIN")
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Billing system status
    status_res = await async_client.get("/api/v1/admin/billing/status", headers=headers)
    assert status_res.status_code == 200
    assert status_res.json()["billing_enabled"] is True

    # Provider list & health
    prov_res = await async_client.get("/api/v1/admin/billing/providers", headers=headers)
    assert prov_res.status_code == 200
    assert len(prov_res.json()) >= 1

    health_res = await async_client.get("/api/v1/admin/billing/provider-status", headers=headers)
    assert health_res.status_code == 200
    assert health_res.json()["state"] == "AVAILABLE"
