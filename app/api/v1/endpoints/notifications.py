"""Notification & Communication API Endpoints (Phase 29).

Enforces:
- Recipient inbox operations with IDOR / BOLA authorization checks.
- User communication preference controls.
- Channel delivery status queries.
- Controlled notification creation (restricted to authorized clinical/admin roles).
- Dedicated administrative governance, provider diagnostics, and bulk dispatches.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, status

from app.api.deps import (
    get_communication_service,
    get_current_user,
    get_notification_preference_service,
    get_notification_service,
    require_permission,
)
from app.core.exceptions import (
    ForbiddenException,
    NotificationAccessDeniedException,
    NotificationNotFoundException,
)
from app.core.policies import Permission
from app.schemas.user import AuthenticatedUserContext
from app.schemas.notification import (
    NotificationBulkCreate,
    NotificationCategory,
    NotificationCreate,
    NotificationListResponse,
    NotificationRead,
    NotificationStatus,
)
from app.schemas.notification_delivery import NotificationDelivery
from app.schemas.notification_preferences import (
    NotificationPreferences,
    NotificationPreferencesUpdate,
)
from app.schemas.notification_provider import (
    NotificationProviderStatus,
    ProviderTestRequest,
    ProviderTestResponse,
)
from app.services.communication_service import CommunicationService
from app.services.notification_preference_service import (
    NotificationPreferenceService,
)
from app.services.notification_service import NotificationService

router = APIRouter(tags=["Notifications & Communications"])


# ---------------------------------------------------------------------------
# Recipient In-App Inbox & Notification APIs
# ---------------------------------------------------------------------------

@router.get(
    "/notifications",
    response_model=NotificationListResponse,
    summary="List authenticated user's notifications",
    dependencies=[Depends(require_permission(Permission.NOTIFICATION_READ))],
)
async def list_notifications(
    unread_only: bool = Query(default=False, description="Filter for unread notifications only"),
    limit: int = Query(default=50, ge=1, le=100, description="Page limit"),
    offset: int = Query(default=0, ge=0, description="Page offset"),
    category: Optional[NotificationCategory] = Query(default=None, description="Optional category filter"),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: NotificationService = Depends(get_notification_service),
) -> NotificationListResponse:
    """Fetch notifications in recipient's in-app inbox."""
    return service.list_user_notifications(
        user_id=current_user.user_id,
        unread_only=unread_only,
        limit=limit,
        offset=offset,
        category=category,
    )


@router.post(
    "/notifications",
    response_model=NotificationRead,
    status_code=status.HTTP_201_CREATED,
    summary="Issue and dispatch a notification",
    dependencies=[Depends(require_permission(Permission.NOTIFICATION_CREATE))],
)
async def create_notification(
    payload: NotificationCreate,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: NotificationService = Depends(get_notification_service),
) -> NotificationRead:
    """Issue a new domain notification to a recipient."""
    return await service.create_and_dispatch(
        payload=payload,
        actor_id=current_user.user_id,
    )


@router.get(
    "/notifications/{notification_id}",
    response_model=NotificationRead,
    summary="Get single notification detail",
    dependencies=[Depends(require_permission(Permission.NOTIFICATION_READ))],
)
async def get_notification(
    notification_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: NotificationService = Depends(get_notification_service),
) -> NotificationRead:
    """Fetch single notification enforcing ownership verification."""
    return service.get_user_notification(
        notification_id=notification_id,
        user_id=current_user.user_id,
    )


@router.post(
    "/notifications/{notification_id}/read",
    response_model=NotificationRead,
    summary="Mark notification as read",
    dependencies=[Depends(require_permission(Permission.NOTIFICATION_READ))],
)
async def mark_notification_as_read(
    notification_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: NotificationService = Depends(get_notification_service),
) -> NotificationRead:
    """Mark a notification as read in recipient inbox."""
    return await service.mark_as_read(
        notification_id=notification_id,
        user_id=current_user.user_id,
    )


@router.post(
    "/notifications/{notification_id}/dismiss",
    response_model=NotificationRead,
    summary="Dismiss notification",
    dependencies=[Depends(require_permission(Permission.NOTIFICATION_DISMISS))],
)
async def dismiss_notification(
    notification_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: NotificationService = Depends(get_notification_service),
) -> NotificationRead:
    """Dismiss a notification from recipient inbox view."""
    return await service.mark_as_dismissed(
        notification_id=notification_id,
        user_id=current_user.user_id,
    )


@router.get(
    "/notification-preferences",
    response_model=NotificationPreferences,
    summary="Get authenticated user's notification preferences",
    dependencies=[Depends(require_permission(Permission.NOTIFICATION_PREFERENCE_READ))],
)
async def get_notification_preferences(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: NotificationPreferenceService = Depends(get_notification_preference_service),
) -> NotificationPreferences:
    """Fetch recipient communication preferences."""
    return service.get_preferences(user_id=current_user.user_id)


@router.put(
    "/notification-preferences",
    response_model=NotificationPreferences,
    summary="Update authenticated user's notification preferences",
    dependencies=[Depends(require_permission(Permission.NOTIFICATION_PREFERENCE_MANAGE))],
)
async def update_notification_preferences(
    payload: NotificationPreferencesUpdate,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: NotificationPreferenceService = Depends(get_notification_preference_service),
) -> NotificationPreferences:
    """Update recipient communication preferences."""
    return service.update_preferences(user_id=current_user.user_id, update=payload)


@router.get(
    "/notification-deliveries/{delivery_id}",
    response_model=NotificationDelivery,
    summary="Get delivery attempt tracking record",
)
async def get_delivery_record(
    delivery_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: NotificationService = Depends(get_notification_service),
) -> NotificationDelivery:
    """Fetch delivery attempt status record with authorization check."""
    return service.get_delivery_record(delivery_id=delivery_id, user_id=current_user.user_id)


# ---------------------------------------------------------------------------
# Administrative Notification & Governance APIs
# ---------------------------------------------------------------------------

@router.get(
    "/admin/notifications",
    response_model=Dict[str, Any],
    summary="Admin list notifications across system",
    dependencies=[Depends(require_permission(Permission.ADMIN_NOTIFICATION_VIEW))],
)
async def admin_list_notifications(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    status_filter: Optional[NotificationStatus] = Query(default=None, alias="status"),
    recipient_id: Optional[str] = Query(default=None),
    service: NotificationService = Depends(get_notification_service),
) -> Dict[str, Any]:
    """Administrative overview of system notifications."""
    items, total = service.admin_list_notifications(
        limit=limit,
        offset=offset,
        status=status_filter,
        recipient_id=recipient_id,
    )
    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get(
    "/admin/notifications/{notification_id}",
    response_model=NotificationRead,
    summary="Admin get single notification",
    dependencies=[Depends(require_permission(Permission.ADMIN_NOTIFICATION_VIEW))],
)
async def admin_get_notification(
    notification_id: str,
    service: NotificationService = Depends(get_notification_service),
) -> NotificationRead:
    """Fetch single notification for administrative inspection."""
    return service.admin_get_notification(notification_id=notification_id)


@router.get(
    "/admin/notification-providers",
    response_model=List[NotificationProviderStatus],
    summary="List active provider statuses and health telemetry",
    dependencies=[Depends(require_permission(Permission.ADMIN_NOTIFICATION_VIEW))],
)
async def admin_list_providers(
    comm_service: CommunicationService = Depends(get_communication_service),
) -> List[NotificationProviderStatus]:
    """Inspect active notification adapters and operational availability."""
    return comm_service.provider_registry.list_provider_statuses()


@router.get(
    "/admin/notification-providers/{provider}",
    response_model=NotificationProviderStatus,
    summary="Get single provider status",
    dependencies=[Depends(require_permission(Permission.ADMIN_NOTIFICATION_VIEW))],
)
async def admin_get_provider_status(
    provider: str,
    comm_service: CommunicationService = Depends(get_communication_service),
) -> NotificationProviderStatus:
    """Fetch operational diagnostics for a specific provider."""
    st = comm_service.provider_registry.get_provider_status_by_name(provider)
    if not st:
        raise NotificationNotFoundException(f"Provider '{provider}' was not found.")
    return st


@router.post(
    "/admin/notification-providers/{provider}/test",
    response_model=ProviderTestResponse,
    summary="Execute provider connectivity test",
    dependencies=[Depends(require_permission(Permission.ADMIN_NOTIFICATION_PROVIDER_TEST))],
)
async def admin_test_provider(
    provider: str,
    payload: ProviderTestRequest,
    comm_service: CommunicationService = Depends(get_communication_service),
) -> ProviderTestResponse:
    """Diagnostic ping test against an external notification provider."""
    return await comm_service.provider_registry.test_provider_connectivity(
        channel=payload.channel,
        test_target=payload.test_target,
        provider_name=provider,
    )


@router.get(
    "/admin/notification-failures",
    response_model=Dict[str, Any],
    summary="List failed delivery attempts",
    dependencies=[Depends(require_permission(Permission.ADMIN_NOTIFICATION_VIEW))],
)
async def admin_list_failures(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    service: NotificationService = Depends(get_notification_service),
) -> Dict[str, Any]:
    """Retrieve failed delivery records for troubleshooting."""
    items, total = service.admin_list_failures(limit=limit, offset=offset)
    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.post(
    "/admin/notifications/bulk",
    response_model=Dict[str, Any],
    summary="Administrative bulk notification dispatch",
    dependencies=[Depends(require_permission(Permission.ADMIN_NOTIFICATION_MANAGE))],
)
async def admin_bulk_dispatch(
    payload: NotificationBulkCreate,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    service: NotificationService = Depends(get_notification_service),
) -> Dict[str, Any]:
    """Execute administrative broadcast or bulk operational communication."""
    return await service.admin_bulk_dispatch(payload=payload, actor_id=current_user.user_id)
