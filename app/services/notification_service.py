"""Notification Orchestration Service (Phase 29).

Central coordinator for HealthSetu notifications, communication preferences,
template rendering, multi-channel dispatch, recipient inbox operations,
and audit/analytics telemetry.

ARCHITECTURAL INVARIANTS:
- NOTIFICATION != CLINICAL DECISION
- MESSAGE DELIVERY != CLINICAL VERIFICATION
- REMINDER != PRESCRIPTION / MEDICATION CHANGE
- SENT != DELIVERED != READ != CLINICAL ACTION
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import logging
from typing import Any, Dict, List, Optional, Tuple
import uuid

from app.core.config import Settings, get_settings
from app.core.exceptions import (
    DuplicateNotificationException,
    NotificationAccessDeniedException,
    NotificationDisabledException,
    NotificationNotFoundException,
    UnauthorizedClinicalContentException,
    ValidationException,
)
from app.repositories.notification_delivery_repository import (
    NotificationDeliveryRepository,
)
from app.repositories.notification_repository import NotificationRepository
from app.schemas.analytics import AnalyticsEvent
from app.schemas.audit import AuditEventType
from app.schemas.notification import (
    NotificationBulkCreate,
    NotificationCategory,
    NotificationChannel,
    NotificationCreate,
    NotificationListResponse,
    NotificationPriority,
    NotificationRead,
    NotificationStatus,
    NotificationType,
    get_notification_category,
)
from app.schemas.notification_delivery import DeliveryStatus, NotificationDelivery
from app.schemas.notification_preferences import (
    NotificationPreferences,
    NotificationPreferencesUpdate,
)
from app.services.analytics_service import AnalyticsService
from app.services.audit_service import AuditService
from app.services.communication_service import CommunicationService
from app.services.notification_preference_service import (
    NotificationPreferenceService,
)
from app.services.notification_template_service import (
    NotificationTemplateService,
)

logger = logging.getLogger(__name__)


class NotificationService:
    """Service orchestrating notification creation, delivery, and lifecycle management."""

    def __init__(
        self,
        notification_repository: NotificationRepository,
        delivery_repository: NotificationDeliveryRepository,
        template_service: NotificationTemplateService,
        preference_service: NotificationPreferenceService,
        communication_service: CommunicationService,
        audit_service: Optional[AuditService] = None,
        analytics_service: Optional[AnalyticsService] = None,
        settings: Optional[Settings] = None,
    ) -> None:
        self.notification_repo = notification_repository
        self.delivery_repo = delivery_repository
        self.template_service = template_service
        self.preference_service = preference_service
        self.communication_service = communication_service
        self.audit_service = audit_service
        self.analytics_service = analytics_service
        self.settings = settings or get_settings()

    def _generate_idempotency_key(self, payload: NotificationCreate) -> str:
        """Derive a deterministic idempotency key for notification deduplication."""
        raw = f"{payload.notification_type.value}:{payload.resource_type or ''}:{payload.resource_id or ''}:{payload.recipient_id}:{payload.event_version}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _resolve_contact_target(
        self,
        recipient_id: str,
        channel: NotificationChannel,
        metadata: Dict[str, Any],
    ) -> str:
        """Resolve contact target address for recipient per channel."""
        # 1. Check explicit contact override in metadata
        if channel == NotificationChannel.EMAIL:
            if "recipient_email" in metadata:
                return str(metadata["recipient_email"])
            return f"{recipient_id}@example.healthsetu.internal"
        elif channel == NotificationChannel.SMS:
            if "recipient_phone" in metadata:
                return str(metadata["recipient_phone"])
            return "+919876543210"
        elif channel == NotificationChannel.PUSH:
            if "device_token" in metadata:
                return str(metadata["device_token"])
            return f"push_token_{recipient_id}_device_alpha"
        return recipient_id

    async def create_and_dispatch(
        self,
        payload: NotificationCreate,
        actor_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> NotificationRead:
        """Create, render, and dispatch a new notification event."""
        # 0. Feature gate
        if not self.settings.NOTIFICATIONS_ENABLED:
            raise NotificationDisabledException("Notification delivery is globally disabled.")

        # 1. Idempotency Check
        idempotency_key = payload.idempotency_key or self._generate_idempotency_key(payload)
        if self.settings.NOTIFICATION_DEDUPLICATION_ENABLED:
            existing = self.notification_repo.get_by_idempotency_key(idempotency_key)
            if existing:
                logger.info(
                    "Duplicate notification ignored via idempotency key '%s' (Notification ID: %s)",
                    idempotency_key,
                    existing.id,
                )
                return existing

        # 2. Preferences & Language Resolution
        user_prefs = self.preference_service.get_preferences(payload.recipient_id)
        lang = payload.language or user_prefs.language or self.settings.NOTIFICATION_DEFAULT_LANGUAGE

        # 3. Resolve Eligible Channels
        eligible_channels = self.preference_service.resolve_eligible_channels(
            user_id=payload.recipient_id,
            notification_type=payload.notification_type,
            priority=payload.priority,
            requested_channels=payload.channels,
        )

        # 4. Render Template
        title, body, tpl_version = self.template_service.render_notification(
            notification_type=payload.notification_type,
            variables=payload.template_variables,
            language=lang,
        )

        # 5. Instantiate and persist Notification record
        now = datetime.now(timezone.utc)
        notification_id = f"notif-{uuid.uuid4().hex[:12]}"
        category = get_notification_category(payload.notification_type)

        notification = NotificationRead(
            id=notification_id,
            recipient_id=payload.recipient_id,
            notification_type=payload.notification_type,
            category=category,
            priority=payload.priority,
            status=NotificationStatus.PROCESSING,
            title=title,
            body=body,
            channels=eligible_channels,
            resource_type=payload.resource_type,
            resource_id=payload.resource_id,
            idempotency_key=idempotency_key,
            created_at=now,
            read_at=None,
            dismissed_at=None,
            metadata={
                **payload.metadata,
                "template_version": tpl_version,
                "language": lang,
                "initiating_actor": actor_id or "system",
            },
        )
        self.notification_repo.create(notification)

        # 6. Audit creation
        if self.audit_service:
            try:
                await self.audit_service.record(
                    event_type=AuditEventType.NOTIFICATION_CREATED,
                    outcome="ALLOW",
                    action=f"Notification created: {payload.notification_type.value}",
                    actor_id=actor_id or "system",
                    resource_type="NOTIFICATION",
                    resource_id=notification_id,
                    metadata={"recipient_id": payload.recipient_id},
                )
            except Exception as e:
                logger.warning("Failed to record audit event for notification creation: %s", e)

        # 7. Dispatch across eligible channels
        successful_dispatches = 0
        failed_dispatches = 0

        for ch in eligible_channels:
            target = self._resolve_contact_target(
                recipient_id=payload.recipient_id,
                channel=ch,
                metadata=payload.metadata,
            )
            try:
                deliv = await self.communication_service.dispatch_channel(
                    notification_id=notification_id,
                    channel=ch,
                    recipient_target=target,
                    title=title,
                    body=body,
                    priority=payload.priority,
                    metadata=payload.metadata,
                )
                if deliv.status in (DeliveryStatus.SENT, DeliveryStatus.DELIVERED):
                    successful_dispatches += 1
                else:
                    failed_dispatches += 1
            except Exception as e:
                logger.warning("Error dispatching channel %s for notification %s: %s", ch.value, notification_id, e)
                failed_dispatches += 1

        # 8. Update final notification status
        final_status = NotificationStatus.DELIVERED if successful_dispatches > 0 else NotificationStatus.FAILED
        updated_notification = self.notification_repo.update_status(notification_id, final_status)

        # 9. Record Analytics telemetry
        if self.analytics_service:
            try:
                self.analytics_service.record_event(
                    AnalyticsEvent(
                        event_type="notification_dispatched",
                        service="notification_service",
                        status_code=200 if successful_dispatches > 0 else 500,
                        duration_ms=0.0,
                        feature_name="notifications",
                        resource_type="NOTIFICATION",
                        result_category="SUCCESS" if successful_dispatches > 0 else "FAILURE",
                        metadata={
                            "notification_type": payload.notification_type.value,
                            "category": category.value,
                            "channel_count": len(eligible_channels),
                            "successful_count": successful_dispatches,
                            "failed_count": failed_dispatches,
                        },
                    )
                )
            except Exception as e:
                logger.warning("Failed to record analytics event: %s", e)

        return updated_notification or notification

    def list_user_notifications(
        self,
        user_id: str,
        unread_only: bool = False,
        limit: int = 50,
        offset: int = 0,
        category: Optional[NotificationCategory] = None,
    ) -> NotificationListResponse:
        """Fetch notifications in recipient's in-app inbox."""
        items, total, unread = self.notification_repo.list_for_recipient(
            recipient_id=user_id,
            unread_only=unread_only,
            limit=limit,
            offset=offset,
            category=category,
        )
        return NotificationListResponse(
            items=items,
            total=total,
            unread_count=unread,
            limit=limit,
            offset=offset,
        )

    def get_user_notification(self, notification_id: str, user_id: str) -> NotificationRead:
        """Fetch single notification enforcing ownership boundary (IDOR / BOLA protection)."""
        n = self.notification_repo.get(notification_id)
        if not n:
            raise NotificationNotFoundException(notification_id)
        if n.recipient_id != user_id:
            logger.warning("BOLA/IDOR attempt: User %s attempted to access Notification %s", user_id, notification_id)
            raise NotificationAccessDeniedException("You do not have access to this notification.")
        return n

    async def mark_as_read(self, notification_id: str, user_id: str) -> NotificationRead:
        """Mark notification as read in recipient inbox."""
        # Check ownership first
        self.get_user_notification(notification_id, user_id)

        updated = self.notification_repo.mark_as_read(notification_id=notification_id, recipient_id=user_id)
        if not updated:
            raise NotificationNotFoundException(notification_id)

        if self.audit_service:
            try:
                await self.audit_service.record(
                    event_type=AuditEventType.NOTIFICATION_READ,
                    outcome="ALLOW",
                    action="Mark notification read",
                    actor_id=user_id,
                    resource_type="NOTIFICATION",
                    resource_id=notification_id,
                )
            except Exception as e:
                logger.warning("Failed to record notification read audit event: %s", e)

        return updated

    async def mark_as_dismissed(self, notification_id: str, user_id: str) -> NotificationRead:
        """Dismiss notification from recipient inbox."""
        self.get_user_notification(notification_id, user_id)

        updated = self.notification_repo.mark_as_dismissed(notification_id=notification_id, recipient_id=user_id)
        if not updated:
            raise NotificationNotFoundException(notification_id)

        if self.audit_service:
            try:
                await self.audit_service.record(
                    event_type=AuditEventType.NOTIFICATION_DISMISSED,
                    outcome="ALLOW",
                    action="Dismiss notification",
                    actor_id=user_id,
                    resource_type="NOTIFICATION",
                    resource_id=notification_id,
                )
            except Exception as e:
                logger.warning("Failed to record notification dismissed audit event: %s", e)

        return updated

    def get_delivery_record(self, delivery_id: str, user_id: Optional[str] = None) -> NotificationDelivery:
        """Fetch delivery attempt record with authorization verification."""
        deliv = self.delivery_repo.get_delivery(delivery_id)
        if not deliv:
            from app.core.exceptions import DeliveryNotFoundException
            raise DeliveryNotFoundException(delivery_id)

        if user_id:
            # Verify recipient ownership via linked notification
            notif = self.notification_repo.get(deliv.notification_id)
            if notif and notif.recipient_id != user_id:
                raise NotificationAccessDeniedException("Access to delivery record denied.")

        return deliv

    # ---------------------------------------------------------------------------
    # Administrative & Backoffice Operations
    # ---------------------------------------------------------------------------

    def admin_list_notifications(
        self,
        limit: int = 50,
        offset: int = 0,
        status: Optional[NotificationStatus] = None,
        recipient_id: Optional[str] = None,
    ) -> Tuple[List[NotificationRead], int]:
        """Admin view of notifications across system."""
        return self.notification_repo.list_admin(
            limit=limit,
            offset=offset,
            status=status,
            recipient_id=recipient_id,
        )

    def admin_get_notification(self, notification_id: str) -> NotificationRead:
        """Admin view of single notification."""
        notif = self.notification_repo.get(notification_id)
        if not notif:
            raise NotificationNotFoundException(notification_id)
        return notif

    def admin_list_failures(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[NotificationDelivery], int]:
        """Admin query for failed delivery attempts."""
        return self.delivery_repo.list_failures(limit=limit, offset=offset)

    async def admin_bulk_dispatch(
        self,
        payload: NotificationBulkCreate,
        actor_id: str,
    ) -> Dict[str, Any]:
        """Execute rate-controlled administrative bulk notification dispatch."""
        if len(payload.recipient_ids) > 1000:
            raise ValidationException("Bulk dispatch limit cannot exceed 1000 recipients.")

        bulk_op_id = f"bulk-notif-{uuid.uuid4().hex[:10]}"
        if self.audit_service:
            try:
                await self.audit_service.record(
                    event_type=AuditEventType.NOTIFICATION_BULK_OPERATION_STARTED,
                    outcome="ALLOW",
                    action=f"Bulk dispatch: {payload.notification_type.value}",
                    actor_id=actor_id,
                    resource_type="NOTIFICATION_BULK",
                    resource_id=bulk_op_id,
                    metadata={"recipient_count": len(payload.recipient_ids)},
                )
            except Exception as e:
                logger.warning("Audit error on bulk dispatch start: %s", e)

        dispatched_count = 0
        failed_count = 0

        for r_id in payload.recipient_ids:
            item_payload = NotificationCreate(
                recipient_id=r_id,
                notification_type=payload.notification_type,
                channels=payload.channels,
                template_variables=payload.template_variables,
                priority=payload.priority,
                metadata={"bulk_operation_id": bulk_op_id, "admin_reason": payload.reason},
            )
            try:
                await self.create_and_dispatch(item_payload, actor_id=actor_id)
                dispatched_count += 1
            except Exception as e:
                logger.warning("Bulk dispatch failed for recipient %s: %s", r_id, e)
                failed_count += 1

        if self.audit_service:
            try:
                await self.audit_service.record(
                    event_type=AuditEventType.NOTIFICATION_BULK_OPERATION_COMPLETED,
                    outcome="ALLOW",
                    action="Bulk dispatch completed",
                    actor_id=actor_id,
                    resource_type="NOTIFICATION_BULK",
                    resource_id=bulk_op_id,
                    metadata={"dispatched": dispatched_count, "failed": failed_count},
                )
            except Exception as e:
                logger.warning("Audit error on bulk dispatch complete: %s", e)

        return {
            "bulk_operation_id": bulk_op_id,
            "total_recipients": len(payload.recipient_ids),
            "dispatched_count": dispatched_count,
            "failed_count": failed_count,
        }
