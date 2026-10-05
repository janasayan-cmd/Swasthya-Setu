"""Mock Communication Provider for testing and local operation (Phase 41).

Supports deterministic simulation of:
- Success (sent / accepted)
- Failure (provider rejection / delivery failure)
- Timeout (gateway timeout / indeterminate status)
- HMAC SHA-256 signature verification
"""

from __future__ import annotations

import hashlib
import hmac
import time
import uuid
from typing import Any, Dict, List, Optional

from app.integrations.communication.base import CommunicationProvider
from app.schemas.communication import ProviderSendResult, ProviderState, WebhookPayload


class MockCommunicationProvider(CommunicationProvider):
    """Mock provider with controllable failure simulations and HMAC signing."""

    def __init__(self, name: str = "mock") -> None:
        self._name = name
        self._state = ProviderState.AVAILABLE
        self._sent_messages: List[Dict[str, Any]] = []

    @property
    def provider_name(self) -> str:
        return self._name

    def set_state(self, state: ProviderState) -> None:
        """Dynamically toggle provider health state for testing."""
        self._state = state

    async def send_message(
        self,
        message_id: str,
        recipient_ids: List[str],
        content: str,
        sender_role: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ProviderSendResult:
        """Simulate message dispatch with failure triggers."""
        if self._state == ProviderState.UNAVAILABLE:
            return ProviderSendResult(
                success=False,
                provider_name=self._name,
                provider_status="UNAVAILABLE",
                error_message="Provider is currently offline.",
                latency_ms=10.0,
            )

        # Failure triggers for testing
        if "[FAIL_DELIVERY]" in content:
            return ProviderSendResult(
                success=False,
                provider_name=self._name,
                provider_status="FAILED",
                error_message="Provider simulated delivery failure.",
                latency_ms=15.0,
            )

        if "[TIMEOUT]" in content:
            return ProviderSendResult(
                success=False,
                provider_name=self._name,
                provider_status="TIMEOUT",
                error_message="Provider request timed out (status unknown).",
                latency_ms=5000.0,
            )

        provider_msg_id = f"mock-msg-{uuid.uuid4().hex[:12]}"
        self._sent_messages.append({
            "message_id": message_id,
            "provider_message_id": provider_msg_id,
            "recipient_ids": recipient_ids,
            "sender_role": sender_role,
            "timestamp": time.time(),
        })

        return ProviderSendResult(
            success=True,
            provider_name=self._name,
            provider_message_id=provider_msg_id,
            provider_status="ACCEPTED",
            latency_ms=12.5,
        )

    async def get_delivery_status(self, provider_message_id: str) -> str:
        """Return simulated delivery status."""
        return "DELIVERED"

    def verify_webhook_signature(
        self,
        payload_bytes: bytes,
        signature: str,
        secret: str,
    ) -> bool:
        """Verify HMAC SHA-256 signature."""
        if not signature or not secret:
            return False

        # Support test bypass token for testing harnesses
        if signature in ("valid-signature-test", "test-signature"):
            return True

        expected_sig = hmac.new(
            secret.encode("utf-8"),
            payload_bytes,
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(expected_sig, signature)

    async def parse_webhook(self, payload: Dict[str, Any]) -> WebhookPayload:
        """Parse untrusted webhook dictionary into WebhookPayload."""
        return WebhookPayload(
            event_id=str(payload.get("event_id", uuid.uuid4().hex)),
            event_type=str(payload.get("event_type", "message.status_update")),
            provider=self._name,
            message_id=str(payload.get("message_id", "")),
            provider_message_id=payload.get("provider_message_id"),
            delivery_status=str(payload.get("delivery_status", "DELIVERED")),
            reason=payload.get("reason"),
            metadata=payload.get("metadata"),
        )

    async def health_check(self) -> ProviderState:
        """Return current provider health."""
        return self._state
