"""SMS Delivery Provider Adapter (Phase 29).

CRITICAL PRIVACY INVARIANT:
- SMS is transmitted over unencrypted telecommunication protocols.
- SMS must NEVER contain unmasked PHI (prescriptions, diagnostic narratives, full medical history).
- Validates E.164 phone number specifications.
"""

from __future__ import annotations

import re
import time
import uuid

from app.integrations.notifications.base import (
    NotificationProvider,
    ProviderDeliveryRequest,
    ProviderDeliveryResult,
)
from app.schemas.notification import NotificationChannel
from app.schemas.notification_delivery import DeliveryStatus

# E.164 phone format or Indian 10-digit standard
PHONE_REGEX = re.compile(r"^\+?[1-9]\d{7,14}$")

# Disallowed clinical keywords in SMS to prevent unencrypted PHI exposure
FORBIDDEN_SMS_PHI_TERMS = [
    "diagnosis:",
    "prescription details:",
    "dosage:",
    "mg daily",
    "biopsy",
    "malignancy",
    "oncology narrative",
    "psychiatric evaluation",
]


class MockSMSNotificationProvider(NotificationProvider):
    """Reliable, privacy-safe SMS gateway provider adapter."""

    def __init__(
        self,
        name: str = "mock_sms_provider",
        api_key: str = "test_sms_key",
        simulate_failure: bool = False,
        simulate_timeout: bool = False,
        simulate_rate_limit: bool = False,
    ) -> None:
        super().__init__(name=name, channel=NotificationChannel.SMS)
        self.api_key = api_key
        self.simulate_failure = simulate_failure
        self.simulate_timeout = simulate_timeout
        self.simulate_rate_limit = simulate_rate_limit
        self.sent_messages: list[ProviderDeliveryRequest] = []

    def validate_configuration(self) -> bool:
        return bool(self.api_key and len(self.api_key) > 4)

    async def send(self, request: ProviderDeliveryRequest) -> ProviderDeliveryResult:
        start_time = time.perf_counter()

        # 1. Clean phone number and validate format
        clean_phone = re.sub(r"[\s\-\(\)]", "", request.recipient_target)
        if not PHONE_REGEX.match(clean_phone):
            result = ProviderDeliveryResult(
                success=False,
                status=DeliveryStatus.FAILED,
                error_message=f"Invalid phone number format: '{request.recipient_target}' (Must be E.164)",
                error_category="INVALID_RECIPIENT",
                is_retryable=False,
                latency_ms=(time.perf_counter() - start_time) * 1000,
            )
            self.record_metrics(result)
            return result

        # 2. Strict Privacy Guard: Detect unmasked PHI leakage in SMS
        lower_body = request.body.lower()
        for term in FORBIDDEN_SMS_PHI_TERMS:
            if term in lower_body:
                result = ProviderDeliveryResult(
                    success=False,
                    status=DeliveryStatus.FAILED,
                    error_message=f"SMS body contains forbidden raw clinical PHI term '{term}'. Use authenticated portal deep-link instead.",
                    error_category="PRIVACY_VIOLATION_BLOCKED",
                    is_retryable=False,
                    latency_ms=(time.perf_counter() - start_time) * 1000,
                )
                self.record_metrics(result)
                return result

        # 3. Simulate failure modes
        if self.simulate_timeout:
            result = ProviderDeliveryResult(
                success=False,
                status=DeliveryStatus.FAILED,
                error_message="SMS gateway connection timed out",
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
                error_message="SMS carrier throughput limit exceeded (HTTP 429)",
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
                error_message="SMS gateway upstream network error 500",
                error_category="UPSTREAM_FAILURE",
                is_retryable=True,
                latency_ms=(time.perf_counter() - start_time) * 1000,
            )
            self.record_metrics(result)
            return result

        # 4. Successful dispatch
        msg_id = f"sms-msg-{uuid.uuid4().hex[:12]}"
        self.sent_messages.append(request)

        result = ProviderDeliveryResult(
            success=True,
            status=DeliveryStatus.SENT,
            provider_message_id=msg_id,
            latency_ms=(time.perf_counter() - start_time) * 1000,
            raw_response={"message_id": msg_id, "recipient": clean_phone, "parts": 1},
        )
        self.record_metrics(result)
        return result

    async def check_status(self, provider_message_id: str) -> DeliveryStatus:
        return DeliveryStatus.DELIVERED

    async def cancel(self, provider_message_id: str) -> bool:
        return False
