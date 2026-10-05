"""Clinical Order Sets, Protocol Templates & Controlled Order Composition Endpoints (Phase 39).

ARCHITECTURAL CONTRACT & CORE SAFETY PRINCIPLES:
- ORDER SET != CLINICAL DECISION
- ORDER SET != DIAGNOSIS
- ORDER SET != TREATMENT
- ORDER SET != PRESCRIPTION
- ORDER SET SELECTION != ORDER AUTHORIZATION
- ORDER SET EXPANSION != ORDER EXECUTION
- ORDER GENERATED FROM TEMPLATE MUST PASS THROUGH PHASE 38
- PREVIEW != EXECUTION (Preview mode never creates orders)
- SUSPENDED TEMPLATES CANNOT GENERATE EXECUTABLE ORDERS
- UNAPPROVED TEMPLATES CANNOT GENERATE EXECUTABLE ORDERS
- AI CANNOT APPROVE, ACTIVATE, OR EXECUTE ORDER SETS
- DUPLICATE EXECUTIONS ARE PREVENTED VIA IDEMPOTENCY
- PARTIAL EXECUTION IS ACCURATELY REPRESENTED
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, status

from app.api.deps import (
    get_current_user,
    get_order_set_service,
)
from app.schemas.order_set import (
    OrderSetActivateRequest,
    OrderSetApproveRequest,
    OrderSetDeprecateRequest,
    OrderSetDiffResponse,
    OrderSetPreviewRequest,
    OrderSetPreviewResponse,
    OrderSetSuspendRequest,
    OrderSetTemplateCreate,
    OrderSetTemplateRecord,
    OrderSetTemplateVersion,
    OrderSetVersionCreate,
    TemplateScope,
    TemplateStatus,
    TemplateType,
)
from app.schemas.order_set_execution import (
    ChildOrderExecutionSummary,
    OrderSetExecuteRequest,
    OrderSetExecutionRecord,
)
from app.schemas.user import AuthenticatedUserContext
from app.services.order_set_service import OrderSetService

# Clinical router for /order-sets
router = APIRouter(tags=["Clinical Order Sets & Protocols"])

# Admin router for /admin/order-sets
admin_router = APIRouter(prefix="/admin/order-sets", tags=["Admin - Clinical Order Sets"])

# Execution router for /order-set-executions
execution_router = APIRouter(prefix="/order-set-executions", tags=["Clinical Order Set Executions"])


# ===========================================================================
# Administrative Endpoints (TRD Section 42)
# ===========================================================================

@admin_router.post(
    "",
    response_model=OrderSetTemplateRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new order set template",
)
async def create_template(
    payload: OrderSetTemplateCreate,
    actor: AuthenticatedUserContext = Depends(get_current_user),
    service: OrderSetService = Depends(get_order_set_service),
) -> OrderSetTemplateRecord:
    """Create a new clinical order set template with Draft Version 1."""
    return await service.create_template(payload, actor)


@admin_router.get(
    "",
    response_model=List[OrderSetTemplateRecord],
    summary="List all templates (admin view)",
)
async def list_admin_templates(
    scope: Optional[TemplateScope] = Query(default=None),
    template_type: Optional[TemplateType] = Query(default=None),
    status_filter: Optional[TemplateStatus] = Query(default=None, alias="status"),
    search: Optional[str] = Query(default=None),
    actor: AuthenticatedUserContext = Depends(get_current_user),
    service: OrderSetService = Depends(get_order_set_service),
) -> List[OrderSetTemplateRecord]:
    """Retrieve templates matching administrative query filters."""
    return await service.list_templates(
        actor=actor,
        scope=scope,
        template_type=template_type,
        status=status_filter,
        search_query=search,
    )


@admin_router.get(
    "/{order_set_id}",
    response_model=OrderSetTemplateRecord,
    summary="Get template by ID (admin view)",
)
async def get_admin_template(
    order_set_id: str,
    actor: AuthenticatedUserContext = Depends(get_current_user),
    service: OrderSetService = Depends(get_order_set_service),
) -> OrderSetTemplateRecord:
    """Retrieve full template record including complete version history."""
    return await service.get_template(order_set_id, actor)


@admin_router.post(
    "/{order_set_id}/versions",
    response_model=OrderSetTemplateVersion,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new template version",
)
async def create_version(
    order_set_id: str,
    payload: OrderSetVersionCreate,
    actor: AuthenticatedUserContext = Depends(get_current_user),
    service: OrderSetService = Depends(get_order_set_service),
) -> OrderSetTemplateVersion:
    """Create a new immutable version of an existing order set template."""
    return await service.create_version(order_set_id, payload, actor)


@admin_router.post(
    "/{order_set_id}/approve",
    response_model=OrderSetTemplateVersion,
    summary="Approve a template version",
)
async def approve_version(
    order_set_id: str,
    payload: OrderSetApproveRequest,
    actor: AuthenticatedUserContext = Depends(get_current_user),
    service: OrderSetService = Depends(get_order_set_service),
) -> OrderSetTemplateVersion:
    """Clinically approve a template version. AI actors CANNOT approve templates."""
    return await service.approve_version(order_set_id, payload, actor)


@admin_router.post(
    "/{order_set_id}/activate",
    response_model=OrderSetTemplateVersion,
    summary="Activate an approved template version",
)
async def activate_version(
    order_set_id: str,
    payload: Optional[OrderSetActivateRequest] = None,
    actor: AuthenticatedUserContext = Depends(get_current_user),
    service: OrderSetService = Depends(get_order_set_service),
) -> OrderSetTemplateVersion:
    """Activate an approved template version for clinical ordering."""
    ver_id = payload.version_id if payload else None
    return await service.activate_version(order_set_id, ver_id, actor)


@admin_router.post(
    "/{order_set_id}/suspend",
    response_model=OrderSetTemplateRecord,
    summary="Emergency suspend a template",
)
async def suspend_template(
    order_set_id: str,
    payload: OrderSetSuspendRequest,
    actor: AuthenticatedUserContext = Depends(get_current_user),
    service: OrderSetService = Depends(get_order_set_service),
) -> OrderSetTemplateRecord:
    """Emergency suspension of a template. Blocks new executions."""
    return await service.suspend_template(order_set_id, payload.reason, actor)


@admin_router.post(
    "/{order_set_id}/deprecate",
    response_model=OrderSetTemplateRecord,
    summary="Deprecate an order set template",
)
async def deprecate_template(
    order_set_id: str,
    payload: OrderSetDeprecateRequest,
    actor: AuthenticatedUserContext = Depends(get_current_user),
    service: OrderSetService = Depends(get_order_set_service),
) -> OrderSetTemplateRecord:
    """Deprecate a template while preserving historical executions."""
    return await service.deprecate_template(order_set_id, payload.reason, actor)


@admin_router.get(
    "/{order_set_id}/versions",
    response_model=List[OrderSetTemplateVersion],
    summary="List all versions of a template",
)
async def list_template_versions(
    order_set_id: str,
    actor: AuthenticatedUserContext = Depends(get_current_user),
    service: OrderSetService = Depends(get_order_set_service),
) -> List[OrderSetTemplateVersion]:
    """List all version records for a template."""
    template = await service.get_template(order_set_id, actor)
    return template.versions


@admin_router.get(
    "/{order_set_id}/diff",
    response_model=OrderSetDiffResponse,
    summary="Diff two template versions",
)
async def diff_template_versions(
    order_set_id: str,
    from_version: int = Query(default=1, ge=1),
    to_version: int = Query(default=2, ge=1),
    actor: AuthenticatedUserContext = Depends(get_current_user),
    service: OrderSetService = Depends(get_order_set_service),
) -> OrderSetDiffResponse:
    """Compare two versions of an order set template."""
    return await service.diff_versions(order_set_id, from_version, to_version, actor)


# ===========================================================================
# Clinical Endpoints (TRD Section 43)
# ===========================================================================

@router.get(
    "/order-sets",
    response_model=List[OrderSetTemplateRecord],
    summary="List available active order sets",
)
async def list_order_sets(
    scope: Optional[TemplateScope] = Query(default=None),
    template_type: Optional[TemplateType] = Query(default=None),
    search: Optional[str] = Query(default=None),
    actor: AuthenticatedUserContext = Depends(get_current_user),
    service: OrderSetService = Depends(get_order_set_service),
) -> List[OrderSetTemplateRecord]:
    """Retrieve available active approved clinical order sets for ordering."""
    return await service.list_templates(
        actor=actor,
        scope=scope,
        template_type=template_type,
        status=TemplateStatus.ACTIVE,
        search_query=search,
    )


@router.get(
    "/order-sets/{order_set_id}",
    response_model=OrderSetTemplateRecord,
    summary="Get order set details",
)
async def get_order_set(
    order_set_id: str,
    actor: AuthenticatedUserContext = Depends(get_current_user),
    service: OrderSetService = Depends(get_order_set_service),
) -> OrderSetTemplateRecord:
    """Retrieve active order set template definition."""
    return await service.get_template(order_set_id, actor)


@router.get(
    "/order-sets/{order_set_id}/versions",
    response_model=List[OrderSetTemplateVersion],
    summary="List versions of an order set",
)
async def list_order_set_versions(
    order_set_id: str,
    actor: AuthenticatedUserContext = Depends(get_current_user),
    service: OrderSetService = Depends(get_order_set_service),
) -> List[OrderSetTemplateVersion]:
    """Retrieve versions of an order set template."""
    template = await service.get_template(order_set_id, actor)
    return template.versions


@router.post(
    "/order-sets/{order_set_id}/preview",
    response_model=OrderSetPreviewResponse,
    summary="Preview order set expansion",
)
async def preview_order_set(
    order_set_id: str,
    payload: OrderSetPreviewRequest,
    actor: AuthenticatedUserContext = Depends(get_current_user),
    service: OrderSetService = Depends(get_order_set_service),
) -> OrderSetPreviewResponse:
    """Preview order set expansion without creating clinical orders.

    SAFETY: PREVIEW != EXECUTION. Never executes orders or calls providers.
    """
    return await service.preview_order_set(order_set_id, payload, actor)


@router.post(
    "/order-sets/{order_set_id}/execute",
    response_model=OrderSetExecutionRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Execute order set and compose child orders",
)
async def execute_order_set(
    order_set_id: str,
    payload: OrderSetExecuteRequest,
    actor: AuthenticatedUserContext = Depends(get_current_user),
    service: OrderSetService = Depends(get_order_set_service),
) -> OrderSetExecutionRecord:
    """Compose and create child clinical orders through Phase 38 OrderService.

    SAFETY:
    - AI CANNOT EXECUTE ORDER SETS.
    - Missing parameters are NEVER silently inferred.
    - Idempotency key prevents duplicate orders.
    """
    return await service.execute_order_set(order_set_id, payload, actor)


# ===========================================================================
# Execution Endpoints (TRD Section 43)
# ===========================================================================

@execution_router.get(
    "/{execution_id}",
    response_model=OrderSetExecutionRecord,
    summary="Get order set execution details",
)
async def get_execution_record(
    execution_id: str,
    actor: AuthenticatedUserContext = Depends(get_current_user),
    service: OrderSetService = Depends(get_order_set_service),
) -> OrderSetExecutionRecord:
    """Retrieve status and summary of an order set execution instance."""
    return await service.get_execution(execution_id, actor)


@execution_router.get(
    "/{execution_id}/orders",
    response_model=List[ChildOrderExecutionSummary],
    summary="Get child orders created for this execution",
)
async def get_execution_child_orders(
    execution_id: str,
    actor: AuthenticatedUserContext = Depends(get_current_user),
    service: OrderSetService = Depends(get_order_set_service),
) -> List[ChildOrderExecutionSummary]:
    """Retrieve child orders composed by this order set execution."""
    execution = await service.get_execution(execution_id, actor)
    return execution.child_orders


@execution_router.get(
    "/{execution_id}/history",
    response_model=List[Dict[str, Any]],
    summary="Get audit history of execution",
)
async def get_execution_history(
    execution_id: str,
    actor: AuthenticatedUserContext = Depends(get_current_user),
    service: OrderSetService = Depends(get_order_set_service),
) -> List[Dict[str, Any]]:
    """Retrieve execution state change history."""
    execution = await service.get_execution(execution_id, actor)
    return execution.history
