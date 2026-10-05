"""Clinical Orders, Results & Controlled Action Execution Endpoints (Phase 38).

CRITICAL ARCHITECTURAL & SAFETY INVARIANTS:
- ORDER != CLINICAL DECISION
- ORDER != DIAGNOSIS
- ORDER != TREATMENT
- ORDER != PRESCRIPTION
- ORDER != MEDICATION CHANGE
- ORDER CREATION != ORDER AUTHORIZATION
- ORDER AUTHORIZATION != ORDER TRANSMISSION
- ORDER TRANSMISSION != ORDER ACCEPTANCE
- PROVIDER SUCCESS RESPONSE != CLINICAL SUCCESS
- UNKNOWN PROVIDER STATE != COMPLETED ORDER
- AI cannot create an authorized clinical order by itself.
- AI cannot approve an order.
- AI cannot prescribe.
- Database remains the source of truth.
- All mutations are audit-logged.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status

from app.api.deps import (
    get_current_user,
    get_order_authorization_service,
    get_order_provider,
    get_order_service,
)
from app.integrations.orders.providers.mock import MockOrderProvider
from app.schemas.order import (
    OrderAuthorizeRequest,
    OrderCancelRequest,
    OrderCreate,
    OrderFilter,
    OrderHistoryResponse,
    OrderListResponse,
    OrderPriority,
    OrderProviderResponse,
    OrderRecord,
    OrderReconcileRequest,
    OrderResultLink,
    OrderReviseRequest,
    OrderStatus,
    OrderStatusResponse,
    OrderType,
    OrderVerifyRequest,
    OrderWebhookEvent,
    OrderWebhookResponse,
)
from app.schemas.user import AuthenticatedUserContext
from app.services.order_authorization_service import OrderAuthorizationService
from app.services.order_service import OrderService

router = APIRouter(tags=["Clinical Orders & Execution"])
admin_router = APIRouter(prefix="/admin/orders", tags=["Admin - Clinical Orders"])


# ---------------------------------------------------------------------------
# Client Endpoints (TRD Section 35)
# ---------------------------------------------------------------------------

@router.post(
    "/orders",
    response_model=OrderRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new clinical order",
)
async def create_order(
    payload: OrderCreate,
    actor: AuthenticatedUserContext = Depends(get_current_user),
    service: OrderService = Depends(get_order_service),
) -> OrderRecord:
    """Create a new clinical order.

    SAFETY:
    - Order is created in DRAFT or PENDING_AUTHORIZATION status.
    - AI cannot authorize an order.
    - Order != clinical decision.
    """
    return await service.create_order(payload, actor)


@router.get(
    "/orders",
    response_model=OrderListResponse,
    summary="List clinical orders with filtering",
)
async def list_orders(
    patient_id: Optional[str] = Query(None, description="Filter by patient ID"),
    clinician_id: Optional[str] = Query(None, description="Filter by clinician ID"),
    organization_id: Optional[str] = Query(None, description="Filter by organization ID"),
    facility_id: Optional[str] = Query(None, description="Filter by facility ID"),
    order_type: Optional[OrderType] = Query(None, description="Filter by order type"),
    status: Optional[OrderStatus] = Query(None, description="Filter by status"),
    priority: Optional[OrderPriority] = Query(None, description="Filter by priority"),
    start_date: Optional[datetime] = Query(None, description="Filter by start date"),
    end_date: Optional[datetime] = Query(None, description="Filter by end date"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    actor: AuthenticatedUserContext = Depends(get_current_user),
    service: OrderService = Depends(get_order_service),
) -> OrderListResponse:
    """List clinical orders with authorized multi-tenant scoping."""
    filters = OrderFilter(
        patient_id=patient_id,
        clinician_id=clinician_id,
        organization_id=organization_id,
        facility_id=facility_id,
        order_type=order_type,
        status=status,
        priority=priority,
        start_date=start_date,
        end_date=end_date,
        page=page,
        limit=limit,
    )
    return await service.list_orders(filters, actor)


@router.get(
    "/orders/{order_id}",
    response_model=OrderRecord,
    summary="Retrieve order details by ID",
)
async def get_order(
    order_id: str,
    actor: AuthenticatedUserContext = Depends(get_current_user),
    service: OrderService = Depends(get_order_service),
) -> OrderRecord:
    """Retrieve details for a single clinical order."""
    return await service.get_order(order_id, actor)


@router.get(
    "/patients/{patient_id}/orders",
    response_model=OrderListResponse,
    summary="List orders for a specific patient",
)
async def get_patient_orders(
    patient_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    actor: AuthenticatedUserContext = Depends(get_current_user),
    service: OrderService = Depends(get_order_service),
) -> OrderListResponse:
    """List orders for a patient, strictly enforcing patient tenancy boundaries."""
    return await service.list_orders(
        OrderFilter(patient_id=patient_id, page=page, limit=limit),
        actor,
    )


@router.get(
    "/clinicians/me/orders",
    response_model=OrderListResponse,
    summary="List orders authored by current clinician",
)
async def get_my_orders(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    actor: AuthenticatedUserContext = Depends(get_current_user),
    service: OrderService = Depends(get_order_service),
) -> OrderListResponse:
    """List orders created by the authenticated clinician."""
    return await service.list_orders(
        OrderFilter(clinician_id=actor.user_id, page=page, limit=limit),
        actor,
    )


@router.get(
    "/facilities/{facility_id}/orders",
    response_model=OrderListResponse,
    summary="List orders for a facility",
)
async def get_facility_orders(
    facility_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    actor: AuthenticatedUserContext = Depends(get_current_user),
    service: OrderService = Depends(get_order_service),
) -> OrderListResponse:
    """List orders belonging to a specific facility."""
    return await service.list_orders(
        OrderFilter(facility_id=facility_id, page=page, limit=limit),
        actor,
    )


@router.get(
    "/organizations/{organization_id}/orders",
    response_model=OrderListResponse,
    summary="List orders for an organization",
)
async def get_organization_orders(
    organization_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    actor: AuthenticatedUserContext = Depends(get_current_user),
    service: OrderService = Depends(get_order_service),
) -> OrderListResponse:
    """List orders belonging to a specific organization."""
    return await service.list_orders(
        OrderFilter(organization_id=organization_id, page=page, limit=limit),
        actor,
    )


@router.post(
    "/orders/{order_id}/authorize",
    response_model=OrderRecord,
    summary="Clinically authorize an order",
)
async def authorize_order(
    order_id: str,
    payload: OrderAuthorizeRequest,
    actor: AuthenticatedUserContext = Depends(get_current_user),
    service: OrderService = Depends(get_order_service),
) -> OrderRecord:
    """Clinically authorize an order (co-sign / approve).

    SAFETY:
    - Authorizing clinician ID is recorded immutably.
    - AI cannot authorize an order.
    """
    return await service.authorize_order(order_id, payload, actor)


@router.post(
    "/orders/{order_id}/submit",
    response_model=OrderRecord,
    summary="Submit an authorized order to external provider",
)
async def submit_order(
    order_id: str,
    actor: AuthenticatedUserContext = Depends(get_current_user),
    service: OrderService = Depends(get_order_service),
) -> OrderRecord:
    """Transmit an authorized order to the external execution network."""
    return await service.submit_order(order_id, actor)


@router.post(
    "/orders/{order_id}/cancel",
    response_model=OrderRecord,
    summary="Cancel a clinical order",
)
async def cancel_order(
    order_id: str,
    payload: OrderCancelRequest,
    actor: AuthenticatedUserContext = Depends(get_current_user),
    service: OrderService = Depends(get_order_service),
) -> OrderRecord:
    """Cancel a clinical order with required clinical justification."""
    return await service.cancel_order(order_id, payload, actor)


@router.post(
    "/orders/{order_id}/revise",
    response_model=OrderRecord,
    summary="Revise / supersede an order",
)
async def revise_order(
    order_id: str,
    payload: OrderReviseRequest,
    actor: AuthenticatedUserContext = Depends(get_current_user),
    service: OrderService = Depends(get_order_service),
) -> OrderRecord:
    """Revise an order by creating a new order that supersedes the existing order."""
    return await service.revise_order(order_id, payload, actor)


@router.get(
    "/orders/{order_id}/status",
    response_model=OrderStatusResponse,
    summary="Query order lifecycle status",
)
async def get_order_status(
    order_id: str,
    actor: AuthenticatedUserContext = Depends(get_current_user),
    service: OrderService = Depends(get_order_service),
) -> OrderStatusResponse:
    """Retrieve normalized lifecycle status for an order."""
    return await service.get_order_status(order_id, actor)


@router.get(
    "/orders/{order_id}/results",
    response_model=List[OrderResultLink],
    summary="Get linked results for an order",
)
async def get_order_results(
    order_id: str,
    actor: AuthenticatedUserContext = Depends(get_current_user),
    service: OrderService = Depends(get_order_service),
) -> List[OrderResultLink]:
    """Retrieve all diagnostic and clinical results linked to this order."""
    order = await service.get_order(order_id, actor)
    return order.result_links


@router.post(
    "/orders/{order_id}/results",
    response_model=OrderRecord,
    summary="Link a clinical result to an order",
)
async def link_order_result(
    order_id: str,
    payload: OrderResultLink,
    actor: AuthenticatedUserContext = Depends(get_current_user),
    service: OrderService = Depends(get_order_service),
) -> OrderRecord:
    """Link an external or internal diagnostic result to an order.

    SAFETY: RESULT LINKAGE != RESULT VERIFICATION.
    """
    return await service.link_result(order_id, payload, actor)


@router.get(
    "/orders/{order_id}/history",
    response_model=OrderHistoryResponse,
    summary="Retrieve order audit/history trail",
)
async def get_order_history(
    order_id: str,
    actor: AuthenticatedUserContext = Depends(get_current_user),
    service: OrderService = Depends(get_order_service),
) -> OrderHistoryResponse:
    """Retrieve complete immutable history trail for an order."""
    return await service.get_order_history(order_id, actor)


@router.post(
    "/orders/{order_id}/reconcile",
    response_model=OrderRecord,
    summary="Trigger order reconciliation",
)
async def reconcile_order(
    order_id: str,
    payload: OrderReconcileRequest,
    actor: AuthenticatedUserContext = Depends(get_current_user),
    service: OrderService = Depends(get_order_service),
) -> OrderRecord:
    """Trigger reconciliation between internal and provider order state."""
    return await service.reconcile_order(order_id, payload, actor)


@router.post(
    "/orders/{order_id}/verify",
    response_model=OrderRecord,
    summary="Clinically verify order results",
)
async def verify_order(
    order_id: str,
    payload: OrderVerifyRequest,
    actor: AuthenticatedUserContext = Depends(get_current_user),
    service: OrderService = Depends(get_order_service),
) -> OrderRecord:
    """Clinically verify and co-sign order results.

    SAFETY: Verification is an explicit clinical action. AI cannot verify results.
    """
    return await service.verify_order(order_id, payload, actor)


@router.post(
    "/orders/webhook",
    response_model=OrderWebhookResponse,
    summary="Inbound provider webhook receiver",
)
async def order_webhook(
    event: OrderWebhookEvent,
    actor: AuthenticatedUserContext = Depends(get_current_user),
    service: OrderService = Depends(get_order_service),
) -> OrderWebhookResponse:
    """Ingest external provider lifecycle updates via webhook."""
    return await service.process_webhook(event, actor)


# ---------------------------------------------------------------------------
# Admin / Operations Endpoints (TRD Section 36)
# ---------------------------------------------------------------------------

@admin_router.get(
    "",
    response_model=OrderListResponse,
    summary="Admin listing of clinical orders",
)
async def admin_list_orders(
    patient_id: Optional[str] = Query(None),
    status: Optional[OrderStatus] = Query(None),
    order_type: Optional[OrderType] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    actor: AuthenticatedUserContext = Depends(get_current_user),
    service: OrderService = Depends(get_order_service),
    authz: OrderAuthorizationService = Depends(get_order_authorization_service),
) -> OrderListResponse:
    """Administrative order list with global cross-tenant access."""
    authz.assert_can_admin(actor)
    return await service.list_orders(
        OrderFilter(patient_id=patient_id, status=status, order_type=order_type, page=page, limit=limit),
        actor,
    )


@admin_router.get(
    "/{order_id}",
    response_model=OrderRecord,
    summary="Admin get order detail",
)
async def admin_get_order(
    order_id: str,
    actor: AuthenticatedUserContext = Depends(get_current_user),
    service: OrderService = Depends(get_order_service),
    authz: OrderAuthorizationService = Depends(get_order_authorization_service),
) -> OrderRecord:
    """Administrative retrieval of order detail."""
    authz.assert_can_admin(actor)
    return await service.get_order(order_id, actor)


@admin_router.get(
    "/{order_id}/provider-status",
    summary="Admin direct provider status query",
)
async def admin_get_provider_status(
    order_id: str,
    actor: AuthenticatedUserContext = Depends(get_current_user),
    service: OrderService = Depends(get_order_service),
    provider: MockOrderProvider = Depends(get_order_provider),
    authz: OrderAuthorizationService = Depends(get_order_authorization_service),
) -> dict:
    """Query external provider directly for order execution state."""
    authz.assert_can_admin(actor)
    order = await service.get_order(order_id, actor)
    if not order.provider_order_id:
        return {"order_id": order_id, "provider_order_id": None, "status": "NOT_TRANSMITTED"}
    result = await provider.get_order_status(order.provider_order_id)
    return {
        "order_id": order_id,
        "provider_order_id": result.provider_order_id,
        "provider_status": result.provider_status,
        "internal_status": result.internal_status.value,
        "message": result.message,
    }


@admin_router.get(
    "/{order_id}/reconciliation",
    summary="Admin reconciliation inspection",
)
async def admin_get_reconciliation(
    order_id: str,
    actor: AuthenticatedUserContext = Depends(get_current_user),
    service: OrderService = Depends(get_order_service),
    authz: OrderAuthorizationService = Depends(get_order_authorization_service),
) -> dict:
    """Inspect reconciliation status and discrepancies for an order."""
    authz.assert_can_admin(actor)
    order = await service.get_order(order_id, actor)
    return {
        "order_id": order_id,
        "order_number": order.order_number,
        "current_status": order.status.value,
        "provider_order_id": order.provider_order_id,
        "reconciliation_required": order.status in (OrderStatus.RECONCILIATION_REQUIRED, OrderStatus.TRANSMISSION_UNKNOWN),
        "history_count": len(order.result_links),
    }


@admin_router.post(
    "/{order_id}/retry",
    response_model=OrderRecord,
    summary="Admin retry order transmission",
)
async def admin_retry_order(
    order_id: str,
    actor: AuthenticatedUserContext = Depends(get_current_user),
    service: OrderService = Depends(get_order_service),
    authz: OrderAuthorizationService = Depends(get_order_authorization_service),
) -> OrderRecord:
    """Idempotently retry order transmission after transient external failure."""
    authz.assert_can_admin(actor)
    return await service.submit_order(order_id, actor)


@admin_router.post(
    "/{order_id}/reconcile",
    response_model=OrderRecord,
    summary="Admin trigger reconciliation",
)
async def admin_reconcile_order(
    order_id: str,
    payload: OrderReconcileRequest,
    actor: AuthenticatedUserContext = Depends(get_current_user),
    service: OrderService = Depends(get_order_service),
    authz: OrderAuthorizationService = Depends(get_order_authorization_service),
) -> OrderRecord:
    """Administratively trigger reconciliation for an order."""
    authz.assert_can_admin(actor)
    return await service.reconcile_order(order_id, payload, actor)
