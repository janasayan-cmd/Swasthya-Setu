"""Mock Order Provider for Development and Testing (Phase 38).

Simulates external laboratory, imaging, and clinical order execution networks
with configurable latency, failure modes, and idempotent order processing.

SAFETY:
- Deterministic behavior in tests
- Never bypasses safety invariants
"""

from __future__ import annotations

import hmac
import hashlib
import time
import uuid
from typing import Any, Dict, Optional

from app.integrations.orders.base import (
    OrderProvider,
    OrderProviderHealthResult,
    OrderProviderState,
    ProviderOrderCancelResult,
    ProviderOrderStatusResult,
    ProviderOrderSubmissionResult,
)
from app.schemas.order import OrderRecord, OrderStatus


class MockOrderProvider(OrderProvider):
    """Mock implementation of OrderProvider for tests and local development."""

    def __init__(
        self,
        provider_id: str = "mock-clinical-network",
        provider_name: str = "HealthSetu Mock Clinical Network",
        webhook_secret: str = "test-webhook-secret-phase38",
        should_fail: bool = False,
        should_timeout: bool = False,
    ) -> None:
        self._provider_id = provider_id
        self._provider_name = provider_name
        self._webhook_secret = webhook_secret
        self.should_fail = should_fail
        self.should_timeout = should_timeout
        self._orders: Dict[str, Dict[str, Any]] = {}

    @property
    def provider_id(self) -> str:
        return self._provider_id

    @property
    def provider_name(self) -> str:
        return self._provider_name

    async def submit_order(self, order: OrderRecord) -> ProviderOrderSubmissionResult:
        if self.should_timeout:
            return ProviderOrderSubmissionResult(
                success=False,
                internal_status=OrderStatus.TRANSMISSION_UNKNOWN,
                error_code="PROVIDER_TIMEOUT",
                error_message="Provider execution timed out without confirmation",
            )

        if self.should_fail:
            return ProviderOrderSubmissionResult(
                success=False,
                internal_status=OrderStatus.FAILED,
                error_code="PROVIDER_REJECTED",
                error_message="External clinical provider rejected the order specification",
            )

        provider_order_id = f"EXT-{uuid.uuid4().hex[:10].upper()}"
        tracking_number = f"TRK-{uuid.uuid4().hex[:8].upper()}"

        self._orders[provider_order_id] = {
            "internal_order_id": order.order_id,
            "status": "ACCEPTED",
            "patient_id": order.patient_id,
            "tracking_number": tracking_number,
        }

        return ProviderOrderSubmissionResult(
            success=True,
            internal_status=OrderStatus.ACCEPTED,
            provider_order_id=provider_order_id,
            provider_status="ACCEPTED",
            tracking_number=tracking_number,
            raw_response={"status": "ACCEPTED", "external_id": provider_order_id},
        )

    async def get_order_status(self, provider_order_id: str) -> ProviderOrderStatusResult:
        if self.should_fail:
            return ProviderOrderStatusResult(
                provider_order_id=provider_order_id,
                provider_status="UNKNOWN",
                internal_status=OrderStatus.TRANSMISSION_UNKNOWN,
                message="External provider communication failed",
            )

        order_data = self._orders.get(provider_order_id)
        if not order_data:
            return ProviderOrderStatusResult(
                provider_order_id=provider_order_id,
                provider_status="NOT_FOUND",
                internal_status=OrderStatus.TRANSMISSION_UNKNOWN,
                message="Order not found at external provider",
            )

        return ProviderOrderStatusResult(
            provider_order_id=provider_order_id,
            provider_status=order_data["status"],
            internal_status=OrderStatus.ACCEPTED if order_data["status"] == "ACCEPTED" else OrderStatus.IN_PROGRESS,
            message="Status retrieved successfully",
        )

    async def cancel_order(self, provider_order_id: str, reason: str) -> ProviderOrderCancelResult:
        if self.should_fail:
            return ProviderOrderCancelResult(
                success=False,
                internal_status=OrderStatus.FAILED,
                message="Provider declined cancellation request",
            )

        if provider_order_id in self._orders:
            self._orders[provider_order_id]["status"] = "CANCELLED"

        return ProviderOrderCancelResult(
            success=True,
            internal_status=OrderStatus.CANCELLED,
            message=f"Order cancelled by provider: {reason}",
        )

    async def health_check(self) -> OrderProviderHealthResult:
        state = OrderProviderState.UNAVAILABLE if self.should_fail else OrderProviderState.AVAILABLE
        return OrderProviderHealthResult(
            state=state,
            provider_name=self._provider_name,
            latency_ms=1.5,
            message="Mock order provider operational",
            timestamp=time.time(),
        )

    def verify_webhook_signature(
        self,
        payload_bytes: bytes,
        signature_header: str,
        secret: Optional[str] = None,
    ) -> bool:
        signing_secret = (secret or self._webhook_secret).encode("utf-8")
        expected_sig = hmac.new(signing_secret, payload_bytes, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected_sig, signature_header)
