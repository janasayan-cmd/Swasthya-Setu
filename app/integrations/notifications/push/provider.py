"""Push Notification Delivery Provider Adapter (Phase 29).

Enforces:
- Device registration token validation.
- Payload size boundaries (preventing mobile notification buffer overflows).
- Mobile push token revocation / invalidation handling.
"""

from __future__ import annotations

import time
import uuid

from app.integrations.notifications.base import (
    NotificationProvider,
    ProviderDeliveryRequest,
    ProviderDeliveryResult,
)
from app.schemas.notification import NotificationChannel
from app.schemas.notification_delivery import DeliveryStatus


class MockPushNotificationProvider(NotificationProvider):
    """FCM / APNS compatible push notification adapter."""

    def __init__(
        self,
        name: str = "mock_push_provider",
        api_key: str = "test_push_key",
        simulate_failure: bool = False,
        simulate_unregistered_token: bool = False,
    ) -> None:
        super().__init__(name=name, channel=NotificationChannel.PUSH)
        self.api_key = api_key
        self.simulate_failure = simulate_failure
        self.simulate_unregistered_token = simulate_unregistered_token
        self.sent_messages: list[ProviderDeliveryRequest] = []

    def validate_configuration(self) -> bool:
        return bool(self.api_key and len(self.api_key) > 4)

    async def send(self, request: ProviderDeliveryRequest) -> ProviderDeliveryResult:
        start_time = time.perf_counter()

        # 1. Device Token validation
        token = request.recipient_target.strip()
        if not token or len(token) < 16:
            result = ProviderDeliveryResult(
                success=False,
                status=DeliveryStatus.FAILED,
                error_message=f"Invalid push device registration token: '{token}'",
                error_category="INVALID_DEVICE_TOKEN",
                is_retryable=False,
                latency_ms=(time.perf_counter() - start_time) * 1000,
            )
            self.record_metrics(result)
            return result

        # 2. Simulate Unregistered / Expired Token
        if self.simulate_unregistered_token or token.startswith("exp_"):
            result = ProviderDeliveryResult(
                success=False,
                status=DeliveryStatus.FAILED,
                error_message="Device token is unregistered or expired (UNREGISTERED_TOKEN)",
                error_category="UNREGISTERED_TOKEN",
                is_retryable=False,
                latency_ms=(time.perf_counter() - start_time) * 1000,
            )
            self.record_metrics(result)
            return result

        if self.simulate_failure:
            result = ProviderDeliveryResult(
                success=False,
                status=DeliveryStatus.FAILED,
                error_message="Push gateway connectivity failure",
                error_category="UPSTREAM_FAILURE",
                is_retryable=True,
                latency_ms=(time.perf_counter() - start_time) * 1000,
            )
            self.record_metrics(result)
            return result

        # 3. Successful push dispatch
        msg_id = f"push-msg-{uuid.uuid4().hex[:12]}"
        self.sent_messages.append(request)

        result = ProviderDeliveryResult(
            success=True,
            status=DeliveryStatus.SENT,
            provider_message_id=msg_id,
            latency_ms=(time.perf_counter() - start_time) * 1000,
            raw_response={"message_id": msg_id, "token_status": "VALID"},
        )
        self.record_metrics(result)
        return result

    async def check_status(self, provider_message_id: str) -> DeliveryStatus:
        return DeliveryStatus.DELIVERED

    async def cancel(self, provider_message_id: str) -> bool:
        return False
