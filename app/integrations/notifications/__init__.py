"""Notification Integrations Module (Phase 29).

Provides vendor-agnostic provider abstractions, email/SMS/push adapters,
and a thread-safe registry with failover and diagnostic health checks.
"""

from __future__ import annotations

import logging
import threading
from typing import Dict, List, Optional

from app.core.config import Settings, get_settings
from app.integrations.notifications.base import (
    NotificationProvider,
    ProviderDeliveryRequest,
    ProviderDeliveryResult,
)
from app.integrations.notifications.email.provider import MockEmailNotificationProvider
from app.integrations.notifications.push.provider import MockPushNotificationProvider
from app.integrations.notifications.sms.provider import MockSMSNotificationProvider
from app.schemas.notification import NotificationChannel
from app.schemas.notification_provider import (
    NotificationProviderStatus,
    ProviderStatusEnum,
    ProviderTestResponse,
)

logger = logging.getLogger(__name__)


class NotificationProviderRegistry:
    """Thread-safe registry for notification channel provider adapters."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()
        self._lock = threading.RLock()
        self._providers: Dict[NotificationChannel, List[NotificationProvider]] = {
            NotificationChannel.EMAIL: [],
            NotificationChannel.SMS: [],
            NotificationChannel.PUSH: [],
        }
        self._initialize_providers()

    def _initialize_providers(self) -> None:
        """Initialize configured channel adapters."""
        with self._lock:
            # Email provider
            email_provider = MockEmailNotificationProvider(
                name=self.settings.EMAIL_PROVIDER,
                api_key=self.settings.EMAIL_PROVIDER_API_KEY,
            )
            self._providers[NotificationChannel.EMAIL] = [email_provider]

            # SMS provider
            sms_provider = MockSMSNotificationProvider(
                name=self.settings.SMS_PROVIDER,
                api_key=self.settings.SMS_PROVIDER_API_KEY,
            )
            self._providers[NotificationChannel.SMS] = [sms_provider]

            # Push provider
            push_provider = MockPushNotificationProvider(
                name=self.settings.PUSH_PROVIDER,
                api_key=self.settings.PUSH_PROVIDER_API_KEY,
            )
            self._providers[NotificationChannel.PUSH] = [push_provider]

    def register_provider(self, provider: NotificationProvider, is_primary: bool = False) -> None:
        """Register an adapter for a channel."""
        with self._lock:
            channel_providers = self._providers.setdefault(provider.channel, [])
            if is_primary:
                channel_providers.insert(0, provider)
            else:
                channel_providers.append(provider)

    def get_provider(
        self,
        channel: NotificationChannel,
        provider_name: Optional[str] = None,
    ) -> Optional[NotificationProvider]:
        """Retrieve the primary or named provider adapter for a channel."""
        with self._lock:
            channel_providers = self._providers.get(channel, [])
            if not channel_providers:
                return None
            if provider_name:
                for p in channel_providers:
                    if p.name == provider_name:
                        return p
                return None
            return channel_providers[0]

    def get_providers_for_channel(self, channel: NotificationChannel) -> List[NotificationProvider]:
        """Retrieve all registered providers for a channel (primary + failover backups)."""
        with self._lock:
            return list(self._providers.get(channel, []))

    def list_provider_statuses(self) -> List[NotificationProviderStatus]:
        """Collect status snapshots for all registered adapters."""
        statuses: List[NotificationProviderStatus] = []
        with self._lock:
            for channel, providers in self._providers.items():
                for p in providers:
                    statuses.append(p.get_status())
        return statuses

    def get_provider_status_by_name(self, name: str) -> Optional[NotificationProviderStatus]:
        """Fetch status for a specific provider by name."""
        with self._lock:
            for channel, providers in self._providers.items():
                for p in providers:
                    if p.name == name:
                        return p.get_status()
        return None

    async def test_provider_connectivity(
        self,
        channel: NotificationChannel,
        test_target: str,
        provider_name: Optional[str] = None,
    ) -> ProviderTestResponse:
        """Execute a safe, isolated connectivity test against a provider."""
        provider = self.get_provider(channel=channel, provider_name=provider_name)
        if not provider:
            return ProviderTestResponse(
                provider_name=provider_name or "unknown",
                channel=channel,
                success=False,
                latency_ms=0.0,
                message=f"No provider registered for channel '{channel.value}'.",
                details={"configured": False},
            )

        req = ProviderDeliveryRequest(
            notification_id="test-ping",
            delivery_id="test-ping-deliv",
            channel=channel,
            recipient_target=test_target,
            body="HealthSetu diagnostic connectivity test. Please disregard.",
            subject="HealthSetu Diagnostic Ping",
            priority=self.settings.NOTIFICATION_DEFAULT_LANGUAGE,  # safe dummy
        )

        res = await provider.send(req)
        return ProviderTestResponse(
            provider_name=provider.name,
            channel=channel,
            success=res.success,
            latency_ms=res.latency_ms,
            message="Connectivity verified successfully." if res.success else (res.error_message or "Test delivery failed."),
            details={
                "delivery_status": res.status.value,
                "error_category": res.error_category,
                "is_retryable": res.is_retryable,
            },
        )


_global_provider_registry = NotificationProviderRegistry()


def get_notification_provider_registry() -> NotificationProviderRegistry:
    """Singleton getter for notification provider registry."""
    return _global_provider_registry


__all__ = [
    "NotificationProvider",
    "ProviderDeliveryRequest",
    "ProviderDeliveryResult",
    "MockEmailNotificationProvider",
    "MockSMSNotificationProvider",
    "MockPushNotificationProvider",
    "NotificationProviderRegistry",
    "get_notification_provider_registry",
]
