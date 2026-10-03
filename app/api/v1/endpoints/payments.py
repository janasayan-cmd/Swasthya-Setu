"""Payment Endpoints (Phase 32).

Provides REST APIs for:
- Patient payment initiation (payment intents)
- Gateway outcome verification
- Transaction querying by patient, invoice, and facility
- Administrative billing operations, provider health tests, and reconciliations
"""

from __future__ import annotations

import logging
from typing import Annotated, Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, Query, status

from app.api.deps import (
    get_current_user,
    get_payment_provider,
    get_payment_reconciliation_service,
    get_payment_service,
)
from app.core.config import settings
from app.integrations.payments.base import PaymentProvider
from app.schemas.payment import (
    PaymentCreateRequest,
    PaymentListResponse,
    PaymentRecord,
    PaymentResponse,
    PaymentStatus,
    PaymentVerificationRequest,
)
from app.schemas.financial_reconciliation import (
    FinancialReconciliationRecord as ReconciliationRecord,
    FinancialReconciliationReport as ReconciliationReport,
)
from app.schemas.user import AuthenticatedUserContext
from app.services.payment_reconciliation_service import PaymentReconciliationService
from app.services.payment_service import PaymentService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Billing & Payments"])


# ---------------------------------------------------------------------------
# Patient Payment APIs
# ---------------------------------------------------------------------------

@router.post(
    "/patients/{patient_id}/invoices/{invoice_id}/payments",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Payment Intent",
    description="Initiates a payment transaction for an issued invoice with idempotency.",
)
async def create_invoice_payment(
    patient_id: str,
    invoice_id: str,
    request: PaymentCreateRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    payment_service: Annotated[PaymentService, Depends(get_payment_service)],
    idempotency_key_header: Optional[str] = Header(None, alias="Idempotency-Key"),
) -> PaymentResponse:
    request.invoice_id = invoice_id
    if idempotency_key_header and not request.idempotency_key:
        request.idempotency_key = idempotency_key_header

    payment = await payment_service.create_payment_intent(current_user, request)
    return PaymentResponse.model_validate(payment)


@router.post(
    "/patients/{patient_id}/payments/{payment_id}/verify",
    response_model=PaymentResponse,
    summary="Verify and Capture Patient Payment",
    description="Verifies gateway transaction outcome and updates invoice balance.",
)
async def verify_patient_payment(
    patient_id: str,
    payment_id: str,
    verification: PaymentVerificationRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    payment_service: Annotated[PaymentService, Depends(get_payment_service)],
) -> PaymentResponse:
    payment = await payment_service.verify_and_capture(current_user, payment_id, verification)
    return PaymentResponse.model_validate(payment)


@router.get(
    "/patients/{patient_id}/payments",
    response_model=PaymentListResponse,
    summary="List Patient Payments",
    description="Lists payment transactions for authorized patient.",
)
async def list_patient_payments(
    patient_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    payment_service: Annotated[PaymentService, Depends(get_payment_service)],
    status: Optional[PaymentStatus] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> PaymentListResponse:
    payments, total = payment_service.list_by_patient(
        current_user, patient_id, status=status, limit=limit, offset=offset
    )
    return PaymentListResponse(
        items=[PaymentResponse.model_validate(p) for p in payments],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/patients/{patient_id}/payments/{payment_id}",
    response_model=PaymentResponse,
    summary="Get Patient Payment Details",
    description="Retrieves a specific payment record for authorized patient.",
)
async def get_patient_payment(
    patient_id: str,
    payment_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    payment_service: Annotated[PaymentService, Depends(get_payment_service)],
) -> PaymentResponse:
    payment = payment_service.get_payment(current_user, payment_id)
    return PaymentResponse.model_validate(payment)


# ---------------------------------------------------------------------------
# General Payment APIs
# ---------------------------------------------------------------------------

@router.get(
    "/invoices/{invoice_id}/payments",
    response_model=List[PaymentResponse],
    summary="List Payments for Invoice",
    description="Lists all payment transactions and attempts associated with an invoice.",
)
async def list_invoice_payments(
    invoice_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    payment_service: Annotated[PaymentService, Depends(get_payment_service)],
) -> List[PaymentResponse]:
    payments = payment_service.list_by_invoice(current_user, invoice_id)
    return [PaymentResponse.model_validate(p) for p in payments]


@router.get(
    "/payments/{payment_id}",
    response_model=PaymentResponse,
    summary="Get Payment by ID",
    description="Retrieves a payment transaction by primary ID under authorization controls.",
)
async def get_payment(
    payment_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    payment_service: Annotated[PaymentService, Depends(get_payment_service)],
) -> PaymentResponse:
    payment = payment_service.get_payment(current_user, payment_id)
    return PaymentResponse.model_validate(payment)


@router.post(
    "/payments/{payment_id}/verify",
    response_model=PaymentResponse,
    summary="Verify Payment Outcome",
    description="Authoritatively validates transaction state with the external payment gateway.",
)
async def verify_payment(
    payment_id: str,
    verification: PaymentVerificationRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    payment_service: Annotated[PaymentService, Depends(get_payment_service)],
) -> PaymentResponse:
    payment = await payment_service.verify_and_capture(current_user, payment_id, verification)
    return PaymentResponse.model_validate(payment)


# ---------------------------------------------------------------------------
# Administrative Financial Operations
# ---------------------------------------------------------------------------

@router.get(
    "/admin/billing/status",
    summary="Admin Billing System Status",
    description="Retrieves billing feature flags, configuration, and default parameters.",
)
async def admin_billing_status(
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    payment_service: Annotated[PaymentService, Depends(get_payment_service)],
) -> Dict[str, Any]:
    payment_service.auth_service.check_admin_billing_access(current_user)
    return {
        "billing_enabled": settings.BILLING_ENABLED,
        "invoicing_enabled": settings.INVOICING_ENABLED,
        "payments_enabled": settings.PAYMENTS_ENABLED,
        "refunds_enabled": settings.REFUNDS_ENABLED,
        "webhooks_enabled": settings.PAYMENT_WEBHOOKS_ENABLED,
        "reconciliation_enabled": settings.PAYMENT_RECONCILIATION_ENABLED,
        "default_currency": settings.PAYMENT_DEFAULT_CURRENCY,
        "provider": settings.PAYMENT_PROVIDER,
    }


@router.get(
    "/admin/billing/providers",
    summary="Admin Payment Providers",
    description="Lists configured payment gateway adapters.",
)
async def admin_list_providers(
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    payment_service: Annotated[PaymentService, Depends(get_payment_service)],
) -> List[Dict[str, Any]]:
    payment_service.auth_service.check_admin_billing_access(current_user)
    return [
        {
            "name": payment_service.provider.name,
            "configured": True,
            "timeout_seconds": settings.PAYMENT_PROVIDER_TIMEOUT_SECONDS,
            "max_retries": settings.PAYMENT_PROVIDER_MAX_RETRIES,
        }
    ]


@router.get(
    "/admin/billing/provider-status",
    summary="Admin Provider Health Check",
    description="Executes health check against the active payment provider.",
)
async def admin_provider_status(
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    payment_service: Annotated[PaymentService, Depends(get_payment_service)],
    provider: Annotated[PaymentProvider, Depends(get_payment_provider)],
) -> Dict[str, Any]:
    payment_service.auth_service.check_admin_billing_access(current_user)
    health = await provider.health_check()
    return {
        "provider": provider.name,
        "state": health.state.value,
        "message": health.message,
        "latency_ms": health.latency_ms,
    }


@router.post(
    "/admin/billing/providers/{provider_name}/test",
    summary="Admin Test Provider Connectivity",
    description="Triggers live connectivity and credential test for the specified gateway adapter.",
)
async def admin_test_provider(
    provider_name: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    payment_service: Annotated[PaymentService, Depends(get_payment_service)],
    provider: Annotated[PaymentProvider, Depends(get_payment_provider)],
) -> Dict[str, Any]:
    payment_service.auth_service.check_admin_billing_access(current_user)
    health = await provider.health_check()
    return {
        "provider": provider_name,
        "status": health.state.value,
        "details": health.message,
        "latency_ms": health.latency_ms,
    }


@router.get(
    "/admin/billing/failures",
    response_model=List[PaymentResponse],
    summary="Admin List Failed/Unknown Payments",
    description="Queries transactions that failed or require reconciliation.",
)
async def admin_list_failures(
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    payment_service: Annotated[PaymentService, Depends(get_payment_service)],
) -> List[PaymentResponse]:
    payment_service.auth_service.check_admin_billing_access(current_user)
    payments, _ = payment_service.payment_repo.list_all()
    failed = [
        p for p in payments
        if p.status in (PaymentStatus.FAILED, PaymentStatus.UNKNOWN, PaymentStatus.RECONCILIATION_REQUIRED)
    ]
    return [PaymentResponse.model_validate(p) for p in failed]


@router.get(
    "/admin/billing/reconciliation",
    summary="Admin List Discrepancies",
    description="Queries transactions with detected financial discrepancies.",
)
async def admin_list_reconciliation_discrepancies(
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    payment_service: Annotated[PaymentService, Depends(get_payment_service)],
    reconciliation_service: Annotated[PaymentReconciliationService, Depends(get_payment_reconciliation_service)],
) -> List[ReconciliationRecord]:
    payment_service.auth_service.check_admin_billing_access(current_user)
    return reconciliation_service.list_discrepancies()


@router.post(
    "/admin/billing/payments/{payment_id}/reconcile",
    response_model=ReconciliationRecord,
    summary="Admin Reconcile Specific Payment",
    description="Manually triggers reconciliation of a transaction against the gateway.",
)
async def admin_reconcile_payment(
    payment_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    payment_service: Annotated[PaymentService, Depends(get_payment_service)],
    reconciliation_service: Annotated[PaymentReconciliationService, Depends(get_payment_reconciliation_service)],
) -> ReconciliationRecord:
    payment_service.auth_service.check_admin_billing_access(current_user)
    return await reconciliation_service.reconcile_payment(payment_id, actor_id=current_user.user_id)
