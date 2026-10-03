"""Invoice Endpoints (Phase 32).

Provides REST APIs for:
- Patient-scoped invoices (create, list, retrieve, issue, cancel)
- General invoice status and line item inspection
- Organization and facility-scoped invoice querying
- Administrative invoice auditing
"""

from __future__ import annotations

import logging
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import (
    get_current_user,
    get_invoice_service,
)
from app.schemas.billing_item import BillingItemRecord
from app.schemas.invoice import (
    InvoiceCancelRequest,
    InvoiceCreateRequest,
    InvoiceListResponse,
    InvoiceResponse,
    InvoiceStatus,
)
from app.schemas.user import AuthenticatedUserContext
from app.services.invoice_service import InvoiceService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Billing & Invoices"])


# ---------------------------------------------------------------------------
# Patient-Scoped Invoice APIs
# ---------------------------------------------------------------------------

@router.post(
    "/patients/{patient_id}/invoices",
    response_model=InvoiceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Draft Invoice for Patient",
    description="Creates a new draft invoice with deterministic integer minor unit totals.",
)
async def create_patient_invoice(
    patient_id: str,
    request: InvoiceCreateRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    invoice_service: Annotated[InvoiceService, Depends(get_invoice_service)],
) -> InvoiceResponse:
    # Ensure patient_id in URL matches request body
    request.patient_id = patient_id
    invoice = invoice_service.create_invoice(current_user, request)
    return InvoiceResponse.model_validate(invoice)


@router.get(
    "/patients/{patient_id}/invoices",
    response_model=InvoiceListResponse,
    summary="List Patient Invoices",
    description="Lists invoices for authorized patient with optional status filtering.",
)
async def list_patient_invoices(
    patient_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    invoice_service: Annotated[InvoiceService, Depends(get_invoice_service)],
    status: Optional[InvoiceStatus] = Query(None, description="Filter by invoice lifecycle status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> InvoiceListResponse:
    invoices, total = invoice_service.list_by_patient(
        current_user, patient_id, status=status, limit=limit, offset=offset
    )
    return InvoiceListResponse(
        items=[InvoiceResponse.model_validate(inv) for inv in invoices],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/patients/{patient_id}/invoices/{invoice_id}",
    response_model=InvoiceResponse,
    summary="Get Patient Invoice by ID",
    description="Retrieves invoice details for authorized patient.",
)
async def get_patient_invoice(
    patient_id: str,
    invoice_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    invoice_service: Annotated[InvoiceService, Depends(get_invoice_service)],
) -> InvoiceResponse:
    invoice = invoice_service.get_invoice(current_user, invoice_id)
    return InvoiceResponse.model_validate(invoice)


@router.post(
    "/patients/{patient_id}/invoices/{invoice_id}/issue",
    response_model=InvoiceResponse,
    summary="Issue Draft Invoice",
    description="Transitions a DRAFT invoice to ISSUED, making it active and payable.",
)
async def issue_patient_invoice(
    patient_id: str,
    invoice_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    invoice_service: Annotated[InvoiceService, Depends(get_invoice_service)],
) -> InvoiceResponse:
    invoice = invoice_service.issue_invoice(current_user, invoice_id)
    return InvoiceResponse.model_validate(invoice)


@router.post(
    "/patients/{patient_id}/invoices/{invoice_id}/cancel",
    response_model=InvoiceResponse,
    summary="Cancel Invoice",
    description="Cancels an unpaid invoice with a mandatory audit reason.",
)
async def cancel_patient_invoice(
    patient_id: str,
    invoice_id: str,
    request: InvoiceCancelRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    invoice_service: Annotated[InvoiceService, Depends(get_invoice_service)],
) -> InvoiceResponse:
    invoice = invoice_service.cancel_invoice(current_user, invoice_id, request)
    return InvoiceResponse.model_validate(invoice)


# ---------------------------------------------------------------------------
# General Invoice APIs
# ---------------------------------------------------------------------------

@router.get(
    "/invoices/{invoice_id}",
    response_model=InvoiceResponse,
    summary="Get Invoice by ID",
    description="Retrieves invoice by ID under authorization controls.",
)
async def get_invoice(
    invoice_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    invoice_service: Annotated[InvoiceService, Depends(get_invoice_service)],
) -> InvoiceResponse:
    invoice = invoice_service.get_invoice(current_user, invoice_id)
    return InvoiceResponse.model_validate(invoice)


@router.get(
    "/invoices/{invoice_id}/items",
    response_model=List[BillingItemRecord],
    summary="Get Invoice Line Items",
    description="Retrieves the breakdown of billable line items attached to an invoice.",
)
async def get_invoice_items(
    invoice_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    invoice_service: Annotated[InvoiceService, Depends(get_invoice_service)],
) -> List[BillingItemRecord]:
    invoice = invoice_service.get_invoice(current_user, invoice_id)
    return invoice.items


@router.get(
    "/invoices/{invoice_id}/status",
    summary="Get Lightweight Invoice Status",
    description="Retrieves lifecycle status and balance information.",
)
async def get_invoice_status(
    invoice_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    invoice_service: Annotated[InvoiceService, Depends(get_invoice_service)],
) -> dict:
    invoice = invoice_service.get_invoice(current_user, invoice_id)
    return {
        "invoice_id": invoice.id,
        "invoice_number": invoice.invoice_number,
        "status": invoice.status.value,
        "total_in_minor_units": invoice.total_in_minor_units,
        "amount_paid_in_minor_units": invoice.amount_paid_in_minor_units,
        "outstanding_amount_in_minor_units": invoice.outstanding_amount_in_minor_units,
        "currency": invoice.currency,
    }


# ---------------------------------------------------------------------------
# Organization and Facility Scoped APIs
# ---------------------------------------------------------------------------

@router.get(
    "/organizations/{organization_id}/invoices",
    response_model=InvoiceListResponse,
    summary="List Organization Invoices",
    description="Lists invoices scoped to an organization for authorized staff.",
)
async def list_organization_invoices(
    organization_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    invoice_service: Annotated[InvoiceService, Depends(get_invoice_service)],
    status: Optional[InvoiceStatus] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> InvoiceListResponse:
    invoices, total = invoice_service.list_by_organization(
        current_user, organization_id, status=status, limit=limit, offset=offset
    )
    return InvoiceListResponse(
        items=[InvoiceResponse.model_validate(inv) for inv in invoices],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/facilities/{facility_id}/invoices",
    response_model=InvoiceListResponse,
    summary="List Facility Invoices",
    description="Lists invoices scoped to a facility for authorized personnel.",
)
async def list_facility_invoices(
    facility_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    invoice_service: Annotated[InvoiceService, Depends(get_invoice_service)],
    status: Optional[InvoiceStatus] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> InvoiceListResponse:
    invoices, total = invoice_service.list_by_facility(
        current_user, facility_id, status=status, limit=limit, offset=offset
    )
    return InvoiceListResponse(
        items=[InvoiceResponse.model_validate(inv) for inv in invoices],
        total=total,
        limit=limit,
        offset=offset,
    )


# ---------------------------------------------------------------------------
# Administrative Invoices API
# ---------------------------------------------------------------------------

@router.get(
    "/admin/billing/invoices",
    response_model=InvoiceListResponse,
    summary="Admin List Invoices",
    description="Administrative query across all invoices under strong permission checks.",
)
async def admin_list_invoices(
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    invoice_service: Annotated[InvoiceService, Depends(get_invoice_service)],
    status: Optional[InvoiceStatus] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> InvoiceListResponse:
    invoices, total = invoice_service.list_all(current_user, status=status, limit=limit, offset=offset)
    return InvoiceListResponse(
        items=[InvoiceResponse.model_validate(inv) for inv in invoices],
        total=total,
        limit=limit,
        offset=offset,
    )
