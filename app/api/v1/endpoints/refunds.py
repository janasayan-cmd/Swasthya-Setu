"""Refund Endpoints (Phase 32).

Provides REST APIs for:
- Initiating refunds against succeeded payments
- Querying refund status and transaction history
- Administrative refund auditing and governance
"""

from __future__ import annotations

import logging
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, Header, Query, status

from app.api.deps import (
    get_current_user,
    get_refund_service,
)
from app.schemas.refund import (
    RefundCreateRequest,
    RefundListResponse,
    RefundRecord,
    RefundResponse,
    RefundStatus,
)
from app.schemas.user import AuthenticatedUserContext
from app.services.refund_service import RefundService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Billing & Refunds"])


# ---------------------------------------------------------------------------
# Patient / General Refund APIs
# ---------------------------------------------------------------------------

@router.post(
    "/patients/{patient_id}/payments/{payment_id}/refund",
    response_model=RefundResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Request Refund for Payment",
    description="Initiates an authorized refund against a SUCCEEDED payment.",
)
async def create_patient_refund(
    patient_id: str,
    payment_id: str,
    request: RefundCreateRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    refund_service: Annotated[RefundService, Depends(get_refund_service)],
    idempotency_key_header: Optional[str] = Header(None, alias="Idempotency-Key"),
) -> RefundResponse:
    request.payment_id = payment_id
    if idempotency_key_header and not request.idempotency_key:
        request.idempotency_key = idempotency_key_header

    refund = await refund_service.process_refund(current_user, request)
    return RefundResponse.model_validate(refund)


@router.post(
    "/refunds",
    response_model=RefundResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Process Refund",
    description="Initiates an authorized refund against a SUCCEEDED payment.",
)
async def process_refund(
    request: RefundCreateRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    refund_service: Annotated[RefundService, Depends(get_refund_service)],
    idempotency_key_header: Optional[str] = Header(None, alias="Idempotency-Key"),
) -> RefundResponse:
    if idempotency_key_header and not request.idempotency_key:
        request.idempotency_key = idempotency_key_header

    refund = await refund_service.process_refund(current_user, request)
    return RefundResponse.model_validate(refund)


@router.get(
    "/refunds/{refund_id}",
    response_model=RefundResponse,
    summary="Get Refund by ID",
    description="Retrieves refund transaction record under authorization controls.",
)
async def get_refund(
    refund_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    refund_service: Annotated[RefundService, Depends(get_refund_service)],
) -> RefundResponse:
    refund = refund_service.get_refund(current_user, refund_id)
    return RefundResponse.model_validate(refund)


@router.get(
    "/payments/{payment_id}/refunds",
    response_model=List[RefundResponse],
    summary="List Refunds for Payment",
    description="Lists all refund transactions issued against a specific payment.",
)
async def list_payment_refunds(
    payment_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    refund_service: Annotated[RefundService, Depends(get_refund_service)],
) -> List[RefundResponse]:
    refunds = refund_service.list_by_payment(current_user, payment_id)
    return [RefundResponse.model_validate(r) for r in refunds]


@router.get(
    "/patients/{patient_id}/refunds",
    response_model=RefundListResponse,
    summary="List Patient Refunds",
    description="Lists refunds issued to an authorized patient.",
)
async def list_patient_refunds(
    patient_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    refund_service: Annotated[RefundService, Depends(get_refund_service)],
    status: Optional[RefundStatus] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> RefundListResponse:
    refunds, total = refund_service.list_by_patient(
        current_user, patient_id, status=status, limit=limit, offset=offset
    )
    return RefundListResponse(
        items=[RefundResponse.model_validate(r) for r in refunds],
        total=total,
        limit=limit,
        offset=offset,
    )


# ---------------------------------------------------------------------------
# Administrative Refunds API
# ---------------------------------------------------------------------------

@router.get(
    "/admin/billing/refunds",
    response_model=RefundListResponse,
    summary="Admin List Refunds",
    description="Queries all refund transactions across HealthSetu.",
)
async def admin_list_refunds(
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    refund_service: Annotated[RefundService, Depends(get_refund_service)],
    status: Optional[RefundStatus] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> RefundListResponse:
    refunds, total = refund_service.list_all(current_user, status=status, limit=limit, offset=offset)
    return RefundListResponse(
        items=[RefundResponse.model_validate(r) for r in refunds],
        total=total,
        limit=limit,
        offset=offset,
    )
