"""Diagnostic Orders Endpoints (Phase 34).

Supports clinicians creating diagnostic orders, patient and clinician order tracking,
cancellation, specimen tracking, and administrative governance.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, status

from app.api.deps import (
    get_current_user,
    get_diagnostic_authorization_service,
    get_diagnostic_order_service,
    get_diagnostic_provider,
    get_diagnostic_reconciliation_service,
)
from app.schemas.user import AuthenticatedUserContext
from app.schemas.diagnostic_order import (
    DiagnosticOrderCancelRequest,
    DiagnosticOrderCreate,
    DiagnosticOrderFilter,
    DiagnosticOrderItemCreate,
    DiagnosticOrderListResponse,
    DiagnosticOrderRecord,
    DiagnosticOrderStatus,
    DiagnosticOrderStatusUpdateRequest,
)
from app.schemas.diagnostic_reconciliation import ReconciliationSummary
from app.services.diagnostic_authorization_service import DiagnosticAuthorizationService
from app.services.diagnostic_order_service import DiagnosticOrderService
from app.services.diagnostic_reconciliation_service import DiagnosticReconciliationService

router = APIRouter(tags=["Diagnostic Orders"])


# ---------------------------------------------------------------------------
# Clinician Order Creation Workflow (Section 13)
# ---------------------------------------------------------------------------

@router.post(
    "/clinicians/me/patients/{patient_id}/diagnostic-orders",
    response_model=DiagnosticOrderRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Clinician create diagnostic order for patient",
)
async def clinician_create_patient_order(
    patient_id: str,
    payload: DiagnosticOrderCreate,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    order_service: DiagnosticOrderService = Depends(get_diagnostic_order_service),
) -> DiagnosticOrderRecord:
    """Create diagnostic order under clinician patient context."""
    # Ensure patient_id matches path
    order_data = payload.model_copy(update={"patient_id": patient_id})
    return await order_service.create_order(order_data, current_user)


@router.post(
    "/diagnostic-orders",
    response_model=DiagnosticOrderRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Create diagnostic order",
)
async def create_diagnostic_order(
    payload: DiagnosticOrderCreate,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    order_service: DiagnosticOrderService = Depends(get_diagnostic_order_service),
) -> DiagnosticOrderRecord:
    """General endpoint for creating diagnostic orders."""
    return await order_service.create_order(payload, current_user)


# ---------------------------------------------------------------------------
# Patient Order Retrieval Workflow (Section 13)
# ---------------------------------------------------------------------------

@router.get(
    "/patients/{patient_id}/diagnostic-orders",
    response_model=DiagnosticOrderListResponse,
    summary="List patient diagnostic orders",
)
async def list_patient_diagnostic_orders(
    patient_id: str,
    order_status: Optional[DiagnosticOrderStatus] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    order_service: DiagnosticOrderService = Depends(get_diagnostic_order_service),
) -> DiagnosticOrderListResponse:
    """Retrieve diagnostic orders for a patient with BOLA enforcement."""
    filters = DiagnosticOrderFilter(
        patient_id=patient_id,
        status=order_status,
        page=page,
        limit=limit,
    )
    return await order_service.list_orders(filters, current_user)


@router.get(
    "/patients/{patient_id}/diagnostic-orders/{order_id}",
    response_model=DiagnosticOrderRecord,
    summary="Get patient diagnostic order by ID",
)
async def get_patient_diagnostic_order(
    patient_id: str,
    order_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    order_service: DiagnosticOrderService = Depends(get_diagnostic_order_service),
) -> DiagnosticOrderRecord:
    """Get single patient diagnostic order by ID."""
    order = await order_service.get_order(order_id, current_user)
    return order


# ---------------------------------------------------------------------------
# Clinician Order Retrieval Workflow (Section 13)
# ---------------------------------------------------------------------------

@router.get(
    "/clinicians/me/diagnostic-orders",
    response_model=DiagnosticOrderListResponse,
    summary="List orders placed by clinician",
)
async def list_clinician_diagnostic_orders(
    patient_id: Optional[str] = Query(None),
    order_status: Optional[DiagnosticOrderStatus] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    order_service: DiagnosticOrderService = Depends(get_diagnostic_order_service),
) -> DiagnosticOrderListResponse:
    """Retrieve orders placed by current clinician."""
    clinician_id = str(
        getattr(current_user, "clinician_id", None)
        or getattr(current_user, "doctor_id", None)
        or getattr(current_user, "id", None)
        or getattr(current_user, "user_id", None)
    )
    filters = DiagnosticOrderFilter(
        clinician_id=clinician_id,
        patient_id=patient_id,
        status=order_status,
        page=page,
        limit=limit,
    )
    return await order_service.list_orders(filters, current_user)


@router.get(
    "/clinicians/me/diagnostic-orders/{order_id}",
    response_model=DiagnosticOrderRecord,
    summary="Get clinician order by ID",
)
async def get_clinician_diagnostic_order(
    order_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    order_service: DiagnosticOrderService = Depends(get_diagnostic_order_service),
) -> DiagnosticOrderRecord:
    """Retrieve clinician order details."""
    return await order_service.get_order(order_id, current_user)


@router.get(
    "/diagnostic-orders/{order_id}",
    response_model=DiagnosticOrderRecord,
    summary="Get diagnostic order by ID",
)
async def get_diagnostic_order(
    order_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    order_service: DiagnosticOrderService = Depends(get_diagnostic_order_service),
) -> DiagnosticOrderRecord:
    """General retrieval of diagnostic order by ID."""
    return await order_service.get_order(order_id, current_user)


# ---------------------------------------------------------------------------
# Order Lifecycle Transitions (Cancel & Status)
# ---------------------------------------------------------------------------

@router.post(
    "/diagnostic-orders/{order_id}/cancel",
    response_model=DiagnosticOrderRecord,
    summary="Cancel diagnostic order",
)
async def cancel_diagnostic_order(
    order_id: str,
    payload: DiagnosticOrderCancelRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    order_service: DiagnosticOrderService = Depends(get_diagnostic_order_service),
) -> DiagnosticOrderRecord:
    """Cancel order if not already completed."""
    return await order_service.cancel_order(order_id, payload, current_user)


@router.post(
    "/diagnostic-orders/{order_id}/status",
    response_model=DiagnosticOrderRecord,
    summary="Update diagnostic order status",
)
async def update_diagnostic_order_status(
    order_id: str,
    payload: DiagnosticOrderStatusUpdateRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    order_service: DiagnosticOrderService = Depends(get_diagnostic_order_service),
) -> DiagnosticOrderRecord:
    """Update order status through authorized state machine."""
    return await order_service.update_status(
        order_id=order_id,
        new_status=payload.status,
        current_user=current_user,
        reason=payload.reason,
    )


@router.post(
    "/diagnostic-orders/{order_id}/specimens/{specimen_id}/collect",
    response_model=DiagnosticOrderRecord,
    summary="Record specimen collection",
)
async def record_specimen_collection(
    order_id: str,
    specimen_id: str,
    collected_at: Optional[datetime] = None,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    order_service: DiagnosticOrderService = Depends(get_diagnostic_order_service),
) -> DiagnosticOrderRecord:
    """Mark specimen as collected."""
    collection_time = collected_at or datetime.now(timezone.utc)
    return await order_service.record_specimen_collection(
        order_id=order_id,
        specimen_id=specimen_id,
        collected_at=collection_time,
        current_user=current_user,
    )


# ---------------------------------------------------------------------------
# Administrative Diagnostics APIs (Section 62)
# ---------------------------------------------------------------------------

@router.get(
    "/admin/diagnostics/status",
    summary="Get diagnostic subsystem status",
)
async def get_admin_diagnostics_status(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    auth_service: DiagnosticAuthorizationService = Depends(get_diagnostic_authorization_service),
    provider = Depends(get_diagnostic_provider),
) -> Dict[str, Any]:
    """Admin endpoint to check diagnostic subsystem and gateway status."""
    auth_service.authorize_admin(current_user)
    health = await provider.health_check()
    return {
        "status": "OPERATIONAL",
        "provider": health.provider_name,
        "provider_state": health.state.value,
        "latency_ms": round(health.latency_ms, 2),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get(
    "/admin/diagnostics/providers",
    summary="List configured diagnostic providers",
)
async def list_admin_diagnostic_providers(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    auth_service: DiagnosticAuthorizationService = Depends(get_diagnostic_authorization_service),
    provider = Depends(get_diagnostic_provider),
) -> List[Dict[str, Any]]:
    """List diagnostic laboratory providers."""
    auth_service.authorize_admin(current_user)
    return [
        {
            "provider_id": provider.provider_id,
            "provider_name": provider.provider_name,
            "type": "MOCK" if "mock" in provider.provider_id.lower() else "EXTERNAL",
        }
    ]


@router.get(
    "/admin/diagnostics/provider-status",
    summary="Query provider real-time health",
)
async def get_admin_provider_health(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    auth_service: DiagnosticAuthorizationService = Depends(get_diagnostic_authorization_service),
    provider = Depends(get_diagnostic_provider),
) -> Dict[str, Any]:
    """Probe lab gateway connectivity."""
    auth_service.authorize_admin(current_user)
    health = await provider.health_check()
    return {
        "provider_id": provider.provider_id,
        "state": health.state.value,
        "latency_ms": round(health.latency_ms, 2),
        "message": health.message,
    }


@router.get(
    "/admin/diagnostics/failures",
    summary="List failed diagnostic orders",
)
async def list_admin_diagnostic_failures(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    auth_service: DiagnosticAuthorizationService = Depends(get_diagnostic_authorization_service),
    order_service: DiagnosticOrderService = Depends(get_diagnostic_order_service),
) -> DiagnosticOrderListResponse:
    """Retrieve failed orders for troubleshooting."""
    auth_service.authorize_admin(current_user)
    return await order_service.list_orders(
        DiagnosticOrderFilter(status=DiagnosticOrderStatus.FAILED, page=page, limit=limit),
        current_user,
    )


@router.get(
    "/admin/diagnostics/reconciliation",
    summary="List diagnostic reconciliation summaries",
)
async def list_admin_reconciliations(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    auth_service: DiagnosticAuthorizationService = Depends(get_diagnostic_authorization_service),
    rec_service: DiagnosticReconciliationService = Depends(get_diagnostic_reconciliation_service),
) -> List[ReconciliationSummary]:
    """List recent reconciliation audit summaries."""
    auth_service.authorize_admin(current_user)
    return rec_service.reconciliation_repository.list_recent()


@router.post(
    "/admin/diagnostics/providers/{provider}/test",
    summary="Test provider connectivity",
)
async def test_admin_diagnostic_provider(
    provider: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    auth_service: DiagnosticAuthorizationService = Depends(get_diagnostic_authorization_service),
    prov = Depends(get_diagnostic_provider),
) -> Dict[str, Any]:
    """Perform ping / health probe on provider adapter."""
    auth_service.authorize_admin(current_user)
    health = await prov.health_check()
    return {
        "provider": provider,
        "result": health.state.value,
        "latency_ms": round(health.latency_ms, 2),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.post(
    "/admin/diagnostic-results/{result_id}/reconcile",
    response_model=ReconciliationSummary,
    summary="Audit result reconciliation",
)
async def reconcile_admin_result(
    result_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    auth_service: DiagnosticAuthorizationService = Depends(get_diagnostic_authorization_service),
    rec_service: DiagnosticReconciliationService = Depends(get_diagnostic_reconciliation_service),
) -> ReconciliationSummary:
    """Run reconciliation check against result/order."""
    auth_service.authorize_admin(current_user)
    return await rec_service.reconcile_order(result_id, current_user)
