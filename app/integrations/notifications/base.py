"""Abstract Provider Base Architecture for Phase 29: Notification & Communication System.

SAFETY & PRIVACY INVARIANTS:
- No vendor lock-in; adapters isolate vendor-specific payloads.
- Provider credentials must NEVER appear in requests, responses, or error traces.
- Raw PHI must NEVER be passed to external SMS or push adapters.
- Provider errors must be normalized into HealthSetu DeliveryStatus.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import time

from app.schemas.notification import NotificationChannel, NotificationPriority
from app.schemas.notification_delivery import DeliveryStatus
from app.schemas.notification_provider import NotificationProviderStatus, ProviderStatusEnum


@dataclass
class ProviderDeliveryRequest:
    """Normalized delivery request dispatched to a channel provider."""

    notification_id: str
    delivery_id: str
    channel: NotificationChannel
    recipient_target: str
    body: str
    subject: Optional[str] = None
    template_name: Optional[str] = None
    variables: Dict[str, Any] = field(default_factory=dict)
    priority: NotificationPriority = NotificationPriority.NORMAL
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProviderDeliveryResult:
    """Normalized response returned from an external or internal provider."""

    success: bool
    status: DeliveryStatus
    provider_message_id: Optional[str] = None
    error_message: Optional[str] = None
    error_category: Optional[str] = None
    is_retryable: bool = False
    latency_ms: float = 0.0
    raw_response: Dict[str, Any] = field(default_factory=dict)


class NotificationProvider(ABC):
    """Abstract interface for all notification channel provider adapters."""

    def __init__(self, name: str, channel: NotificationChannel) -> None:
        self.name = name
        self.channel = channel
        self._total_requests = 0
        self._success_count = 0
        self._failure_count = 0
        self._timeout_count = 0
        self._rate_limit_count = 0
        self._last_success_at: Optional[datetime] = None
        self._last_failure_at: Optional[datetime] = None
        self._last_error: Optional[str] = None

    @abstractmethod
    async def send(self, request: ProviderDeliveryRequest) -> ProviderDeliveryResult:
        """Transmit message payload to the external provider."""
        raise NotImplementedError

    @abstractmethod
    async def check_status(self, provider_message_id: str) -> DeliveryStatus:
        """Query delivery status confirmation from the upstream network."""
        raise NotImplementedError

    @abstractmethod
    async def cancel(self, provider_message_id: str) -> bool:
        """Attempt to recall or abort an enqueued delivery."""
        raise NotImplementedError

    @abstractmethod
    def validate_configuration(self) -> bool:
        """Verify provider authentication and connection endpoint configuration."""
        raise NotImplementedError

    def get_status(self) -> NotificationProviderStatus:
        """Inspect operational telemetry and availability state."""
        is_configured = self.validate_configuration()
        if not is_configured:
            st = ProviderStatusEnum.NOT_CONFIGURED
        elif self._failure_count > 0 and self._success_count == 0:
            st = ProviderStatusEnum.UNAVAILABLE
        elif self._failure_count > (self._success_count * 0.2):
            st = ProviderStatusEnum.DEGRADED
        else:
            st = ProviderStatusEnum.AVAILABLE

        return NotificationProviderStatus(
            provider_name=self.name,
            channel=self.channel,
            status=st,
            connectivity_ok=is_configured and st != ProviderStatusEnum.UNAVAILABLE,
            total_requests=self._total_requests,
            success_count=self._success_count,
            failure_count=self._failure_count,
            timeout_count=self._timeout_count,
            rate_limit_count=self._rate_limit_count,
            last_success_at=self._last_success_at,
            last_failure_at=self._last_failure_at,
            last_error=self._last_error,
        )

    def record_metrics(self, result: ProviderDeliveryResult) -> None:
        """Internal accounting of provider interactions."""
        self._total_requests += 1
        now = datetime.now(timezone.utc)
        if result.success:
            self._success_count += 1
            self._last_success_at = now
        else:
            self._failure_count += 1
            self._last_failure_at = now
            self._last_error = result.error_message
            if result.error_category == "TIMEOUT":
                self._timeout_count += 1
            elif result.error_category == "RATE_LIMIT":
                self._rate_limit_count += 1
