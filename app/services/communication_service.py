"""Communication Delivery Service (Phase 29).

Coordinates physical multi-channel dispatches (Email, SMS, Push, In-App),
enforces recipient contact validation, sliding-window rate limiting,
provider failover, and delivery attempt persistence.
"""

from __future__ import annotations

import collections
from datetime import datetime, timezone
import logging
import re
import threading
import time
from typing import Any, Dict, List, Optional
import uuid

from app.core.config import Settings, get_settings
from app.core.exceptions import (
    ChannelDisabledException,
    InvalidRecipientException,
    NotificationRateLimitExceededException,
    ProviderDeliveryException,
    ProviderUnavailableException,
)
from app.integrations.notifications import (
    NotificationProviderRegistry,
    ProviderDeliveryRequest,
    ProviderDeliveryResult,
    get_notification_provider_registry,
)
from app.repositories.notification_delivery_repository import (
    NotificationDeliveryRepository,
)
from app.schemas.notification import (
    NotificationChannel,
    NotificationPriority,
)
from app.schemas.notification_delivery import DeliveryStatus, NotificationDelivery

logger = logging.getLogger(__name__)

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
PHONE_REGEX = re.compile(r"^\+?[1-9]\d{7,14}$")


def mask_target(target: str, channel: NotificationChannel) -> str:
    """Mask recipient target to avoid exposing contact info in logs and diagnostics."""
    if not target:
        return ""
    if channel == NotificationChannel.EMAIL:
        if "@" in target:
            name, domain = target.split("@", 1)
            masked_name = name[0] + "***" if len(name) > 1 else "*"
            return f"{masked_name}@{domain}"
        return "***"
    elif channel == NotificationChannel.SMS:
        clean = re.sub(r"[^\d+]", "", target)
        if len(clean) >= 6:
            return clean[:3] + "****" + clean[-2:]
        return "****"
    elif channel == NotificationChannel.PUSH:
        if len(target) > 8:
            return target[:4] + "..." + target[-4:]
        return "token_***"
    return target


class CommunicationService:
    """Service orchestrating external channel dispatches and resilience controls."""

    def __init__(
        self,
        delivery_repository: NotificationDeliveryRepository,
        provider_registry: Optional[NotificationProviderRegistry] = None,
        settings: Optional[Settings] = None,
    ) -> None:
        self.delivery_repo = delivery_repository
        self.provider_registry = provider_registry or get_notification_provider_registry()
        self.settings = settings or get_settings()

        # In-memory sliding window rate limiter: recipient_target -> deque of timestamps
        self._rate_limit_lock = threading.RLock()
        self._recipient_timestamps: Dict[str, collections.deque] = collections.defaultdict(collections.deque)

    def _check_rate_limit(self, recipient_target: str) -> None:
        """Enforce per-recipient per-minute rate limit ceiling."""
        if not self.settings.NOTIFICATION_RATE_LIMIT_ENABLED:
            return

        now = time.time()
        window_seconds = 60.0
        limit = self.settings.NOTIFICATION_RATE_LIMIT_PER_MINUTE

        with self._rate_limit_lock:
            q = self._recipient_timestamps[recipient_target]
            # Evict timestamps older than 60 seconds
            while q and q[0] <= now - window_seconds:
                q.popleft()

            if len(q) >= limit:
                logger.warning(
                    "Notification rate limit exceeded for recipient target %s",
                    mask_target(recipient_target, NotificationChannel.EMAIL),
                )
                raise NotificationRateLimitExceededException(
                    f"Recipient dispatch limit of {limit} messages per minute exceeded."
                )

            q.append(now)

    def validate_contact_target(self, channel: NotificationChannel, target: str) -> str:
        """Validate contact target formatting per channel."""
        stripped = (target or "").strip()
        if not stripped:
            raise InvalidRecipientException(f"Contact target for channel '{channel.value}' cannot be empty.")

        if channel == NotificationChannel.EMAIL:
            if not EMAIL_REGEX.match(stripped):
                raise InvalidRecipientException(f"Invalid email address format: '{stripped}'.")
            return stripped

        elif channel == NotificationChannel.SMS:
            clean = re.sub(r"[\s\-\(\)]", "", stripped)
            if not PHONE_REGEX.match(clean):
                raise InvalidRecipientException(f"Invalid phone number format: '{stripped}' (must be E.164 compliant).")
            return clean

        elif channel == NotificationChannel.PUSH:
            if len(stripped) < 16:
                raise InvalidRecipientException(f"Invalid push device token length for recipient: '{stripped}'.")
            return stripped

        elif channel == NotificationChannel.IN_APP:
            return stripped

        raise ChannelDisabledException(channel=channel.value)

    async def dispatch_channel(
        self,
        notification_id: str,
        channel: NotificationChannel,
        recipient_target: str,
        title: str,
        body: str,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> NotificationDelivery:
        """Deliver a message across an individual channel."""
        now = datetime.now(timezone.utc)
        delivery_id = f"deliv-{uuid.uuid4().hex[:12]}"
        masked_target_str = mask_target(recipient_target, channel)

        # 1. Channel feature gate check
        if channel == NotificationChannel.EMAIL and not self.settings.EMAIL_NOTIFICATIONS_ENABLED:
            raise ChannelDisabledException(channel="EMAIL")
        if channel == NotificationChannel.SMS and not self.settings.SMS_NOTIFICATIONS_ENABLED:
            raise ChannelDisabledException(channel="SMS")
        if channel == NotificationChannel.PUSH and not self.settings.PUSH_NOTIFICATIONS_ENABLED:
            raise ChannelDisabledException(channel="PUSH")
        if channel == NotificationChannel.IN_APP and not self.settings.IN_APP_NOTIFICATIONS_ENABLED:
            raise ChannelDisabledException(channel="IN_APP")

        # 2. In-App delivery is handled immediately in-memory/DB
        if channel == NotificationChannel.IN_APP:
            deliv = NotificationDelivery(
                id=delivery_id,
                notification_id=notification_id,
                channel=channel,
                recipient_target=masked_target_str,
                provider="in_app_inbox",
                provider_message_id=f"inapp-{uuid.uuid4().hex[:8]}",
                status=DeliveryStatus.DELIVERED,
                sent_at=now,
                delivered_at=now,
                created_at=now,
                updated_at=now,
                metadata=metadata or {},
            )
            return self.delivery_repo.create_delivery(deliv)

        # 3. Target verification & Rate Limiting for external channels
        clean_target = self.validate_contact_target(channel, recipient_target)
        self._check_rate_limit(clean_target)

        # 4. Resolve provider
        providers = self.provider_registry.get_providers_for_channel(channel)
        if not providers:
            raise ProviderUnavailableException(
                provider="none",
                message=f"No provider configured for delivery channel '{channel.value}'.",
            )

        # Create QUEUED delivery record
        deliv = NotificationDelivery(
            id=delivery_id,
            notification_id=notification_id,
            channel=channel,
            recipient_target=masked_target_str,
            provider=providers[0].name,
            status=DeliveryStatus.QUEUED,
            created_at=now,
            updated_at=now,
            metadata=metadata or {},
        )
        self.delivery_repo.create_delivery(deliv)

        req = ProviderDeliveryRequest(
            notification_id=notification_id,
            delivery_id=delivery_id,
            channel=channel,
            recipient_target=clean_target,
            body=body,
            subject=title,
            priority=priority,
            metadata=metadata or {},
        )

        # 5. Attempt dispatch with failover if configured
        last_result: Optional[ProviderDeliveryResult] = None
        for idx, provider in enumerate(providers):
            self.delivery_repo.update_status(
                delivery_id=delivery_id,
                status=DeliveryStatus.SENDING,
            )
            result = await provider.send(req)
            last_result = result

            if result.success:
                updated = self.delivery_repo.update_status(
                    delivery_id=delivery_id,
                    status=result.status,
                    provider_message_id=result.provider_message_id,
                    sent_at=datetime.now(timezone.utc),
                )
                return updated or deliv

            # If failed, check if failover is permitted
            logger.warning(
                "Delivery failed on provider %s (channel %s): %s",
                provider.name,
                channel.value,
                result.error_message,
            )
            if not (self.settings.NOTIFICATION_PROVIDER_FAILOVER_ENABLED and idx < len(providers) - 1):
                break

            logger.info("Attempting failover to secondary provider for channel %s...", channel.value)

        # Handle terminal failure
        err_msg = last_result.error_message if last_result else "Provider dispatch failed"
        err_cat = last_result.error_category if last_result else "UNKNOWN"
        updated = self.delivery_repo.update_status(
            delivery_id=delivery_id,
            status=DeliveryStatus.FAILED,
            error_message=err_msg,
            error_category=err_cat,
        )

        if last_result and last_result.error_category == "INVALID_RECIPIENT":
            raise InvalidRecipientException(err_msg)

        return updated or deliv
