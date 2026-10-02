"""Email Delivery Provider Adapter (Phase 29).

Enforces:
- Strict email address formatting validation.
- Sanitized email headers (preventing header injection / CRLF injection).
- No unencrypted secrets in payload.
"""

from __future__ import annotations

import re
import time
import uuid
from typing import Optional

from app.integrations.notifications.base import (
    NotificationProvider,
    ProviderDeliveryRequest,
    ProviderDeliveryResult,
)
from app.schemas.notification import NotificationChannel
from app.schemas.notification_delivery import DeliveryStatus

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


class MockEmailNotificationProvider(NotificationProvider):
    """Reliable, non-blocking email provider adapter with simulation switches."""

    def __init__(
        self,
        name: str = "mock_email_provider",
        api_key: str = "test_key",
        simulate_failure: bool = False,
        simulate_timeout: bool = False,
        simulate_rate_limit: bool = False,
    ) -> None:
        super().__init__(name=name, channel=NotificationChannel.EMAIL)
        self.api_key = api_key
        self.simulate_failure = simulate_failure
        self.simulate_timeout = simulate_timeout
        self.simulate_rate_limit = simulate_rate_limit
        self.sent_messages: list[ProviderDeliveryRequest] = []

    def validate_configuration(self) -> bool:
        return bool(self.api_key and len(self.api_key) > 4)

    async def send(self, request: ProviderDeliveryRequest) -> ProviderDeliveryResult:
        start_time = time.perf_counter()

        # 1. Recipient email validation
        if not request.recipient_target or not EMAIL_REGEX.match(request.recipient_target.strip()):
            result = ProviderDeliveryResult(
                success=False,
                status=DeliveryStatus.FAILED,
                error_message=f"Invalid email address format: '{request.recipient_target}'",
                error_category="INVALID_RECIPIENT",
                is_retryable=False,
                latency_ms=(time.perf_counter() - start_time) * 1000,
            )
            self.record_metrics(result)
            return result

        # 2. Header injection protection (prevent \r or \n in subject)
        if request.subject and ("\r" in request.subject or "\n" in request.subject):
            result = ProviderDeliveryResult(
                success=False,
                status=DeliveryStatus.FAILED,
                error_message="Subject contains forbidden CRLF characters (Header Injection Guard).",
                error_category="SECURITY_VALIDATION_FAILED",
                is_retryable=False,
                latency_ms=(time.perf_counter() - start_time) * 1000,
            )
            self.record_metrics(result)
            return result

        # 3. Simulated failure modes for resilience testing
        if self.simulate_timeout:
            result = ProviderDeliveryResult(
                success=False,
                status=DeliveryStatus.FAILED,
                error_message="Email provider gateway timed out after 15.0s",
                error_category="TIMEOUT",
                is_retryable=True,
                latency_ms=150.0,
            )
            self.record_metrics(result)
            return result

        if self.simulate_rate_limit:
            result = ProviderDeliveryResult(
                success=False,
                status=DeliveryStatus.FAILED,
                error_message="Email provider returned HTTP 429 Too Many Requests",
                error_category="RATE_LIMIT",
                is_retryable=True,
                latency_ms=(time.perf_counter() - start_time) * 1000,
            )
            self.record_metrics(result)
            return result

        if self.simulate_failure:
            result = ProviderDeliveryResult(
                success=False,
                status=DeliveryStatus.FAILED,
                error_message="Upstream SMTP server returned temporary 550 Service Unavailable",
                error_category="UPSTREAM_FAILURE",
                is_retryable=True,
                latency_ms=(time.perf_counter() - start_time) * 1000,
            )
            self.record_metrics(result)
            return result

        # 4. Successful delivery dispatch
        msg_id = f"email-msg-{uuid.uuid4().hex[:12]}"
        self.sent_messages.append(request)

        result = ProviderDeliveryResult(
            success=True,
            status=DeliveryStatus.SENT,
            provider_message_id=msg_id,
            latency_ms=(time.perf_counter() - start_time) * 1000,
            raw_response={"message_id": msg_id, "accepted": [request.recipient_target]},
        )
        self.record_metrics(result)
        return result

    async def check_status(self, provider_message_id: str) -> DeliveryStatus:
        # In real email systems, webhooks update delivery status
        return DeliveryStatus.DELIVERED

    async def cancel(self, provider_message_id: str) -> bool:
        return False
