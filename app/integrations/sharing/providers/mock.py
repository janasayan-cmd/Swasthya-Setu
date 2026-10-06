"""Mock Sharing Provider Adapter (Phase 44).

Deterministic mock adapter for unit and integration testing.
Allows simulating timeouts, transient 5xx, provider outages, and successful deliveries.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

from app.integrations.sharing.base import (
    ProviderDeliveryState,
    ProviderShareResult,
    SharingProvider,
)


class MockSharingProvider(SharingProvider):
    """Mock implementation of SharingProvider."""

    def __init__(
        self,
        provider_name: str = "mock",
        default_state: ProviderDeliveryState = ProviderDeliveryState.SUCCESS,
    ) -> None:
        self._name = provider_name
        self._default_state = default_state
        self._deliveries: Dict[str, Dict[str, Any]] = {}
        # Simulation toggles
        self.simulate_timeout: bool = False
        self.simulate_unavailable: bool = False
        self.simulate_failure: bool = False
        self.forced_state: Optional[ProviderDeliveryState] = None

    @property
    def provider_name(self) -> str:
        return self._name

    async def share(
        self,
        payload: Dict[str, Any],
        destination_url: Optional[str] = None,
        recipient_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ProviderShareResult:
        ref = f"mock-ref-{uuid.uuid4().hex[:12]}"

        if self.simulate_timeout:
            return ProviderShareResult(
                success=False,
                state=ProviderDeliveryState.TIMEOUT,
                provider_reference=ref,
                message="Simulated external provider network timeout",
                retryable=True,
            )

        if self.simulate_unavailable:
            return ProviderShareResult(
                success=False,
                state=ProviderDeliveryState.UNAVAILABLE,
                provider_reference=ref,
                message="Simulated external provider 503 unavailable",
                retryable=True,
            )

        if self.simulate_failure:
            return ProviderShareResult(
                success=False,
                state=ProviderDeliveryState.FAILED,
                provider_reference=ref,
                message="Simulated external provider fatal delivery rejection",
                retryable=False,
            )

        state = self.forced_state or self._default_state
        success = state == ProviderDeliveryState.SUCCESS

        self._deliveries[ref] = {
            "payload_summary": list(payload.keys()),
            "destination_url": destination_url,
            "recipient_id": recipient_id,
            "state": state,
            "metadata": metadata or {},
        }

        return ProviderShareResult(
            success=success,
            state=state,
            provider_reference=ref,
            message="Payload accepted for delivery by mock provider" if success else "Mock delivery failed",
            retryable=state in (ProviderDeliveryState.TIMEOUT, ProviderDeliveryState.UNAVAILABLE, ProviderDeliveryState.RETRY_PENDING),
            raw_response={"mock_status": 200 if success else 500, "mock_ref": ref},
        )

    async def get_status(self, provider_reference: str) -> ProviderDeliveryState:
        record = self._deliveries.get(provider_reference)
        if not record:
            return ProviderDeliveryState.UNKNOWN
        return record.get("state", ProviderDeliveryState.UNKNOWN)

    async def cancel(self, provider_reference: str) -> bool:
        if provider_reference in self._deliveries:
            self._deliveries[provider_reference]["state"] = ProviderDeliveryState.FAILED
            return True
        return False

    async def health(self) -> Dict[str, Any]:
        if self.simulate_unavailable:
            return {"status": "UNAVAILABLE", "provider": self._name}
        return {"status": "HEALTHY", "provider": self._name}
