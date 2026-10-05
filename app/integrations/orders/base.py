"""Clinical Order Provider Abstraction (Phase 38).

Defines the pluggable interface for external clinical order execution systems
(laboratories, imaging networks, pharmacy systems, and referral networks)
without hardcoding any provider into domain services.

CRITICAL ARCHITECTURAL & SAFETY INVARIANTS:
- PROVIDER FAILURE != SUCCESS
- PROVIDER SUCCESS != CLINICAL SUCCESS
- UNKNOWN PROVIDER STATE != COMPLETED ORDER
- PROVIDER TIMEOUT != IMMEDIATE RETRY (must preserve uncertainty)
- NO PROVIDER MODELS LEAK INTO THE DOMAIN
- PROVIDER RESPONSE IS NORMALIZED BEFORE INGESTION
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from app.schemas.order import OrderRecord, OrderStatus


class OrderProviderState(str, Enum):
    """Operational health state of the order provider gateway."""

    AVAILABLE = "AVAILABLE"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"
    DISABLED = "DISABLED"
    UNKNOWN = "UNKNOWN"


@dataclass
class OrderProviderHealthResult:
    """Outcome of health check against order provider gateway."""

    state: OrderProviderState
    provider_name: str
    latency_ms: float
    message: str = "Order execution gateway operational"
    timestamp: float = 0.0


@dataclass
class ProviderOrderSubmissionResult:
    """Normalized outcome of submitting a clinical order to external provider."""

    success: bool
    internal_status: OrderStatus
    provider_order_id: Optional[str] = None
    provider_status: Optional[str] = None
    tracking_number: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    raw_response: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProviderOrderCancelResult:
    """Outcome of attempting to cancel an order with external provider."""

    success: bool
    internal_status: OrderStatus
    message: str = "Order cancelled successfully"
    raw_response: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProviderOrderStatusResult:
    """Status synchronization result from order provider."""

    provider_order_id: str
    provider_status: str
    internal_status: OrderStatus
    raw_status: Optional[str] = None
    message: Optional[str] = None


class OrderProvider(ABC):
    """Abstract base class for clinical order provider integrations."""

    @property
    @abstractmethod
    def provider_id(self) -> str:
        """Unique identifier for this provider adapter."""
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable name of the provider or network."""
        pass

    @abstractmethod
    async def submit_order(self, order: OrderRecord) -> ProviderOrderSubmissionResult:
        """Submit an authorized clinical order to the external provider.

        SAFETY:
        - Must be idempotent (caller provides correlation_id).
        - Provider failure must never be masked as success.
        - Timeout must return an explicit timeout result without guessing.
        """
        pass

    @abstractmethod
    async def get_order_status(self, provider_order_id: str) -> ProviderOrderStatusResult:
        """Query real-time status of an order with external provider."""
        pass

    @abstractmethod
    async def cancel_order(self, provider_order_id: str, reason: str) -> ProviderOrderCancelResult:
        """Request order cancellation with external provider."""
        pass

    @abstractmethod
    async def health_check(self) -> OrderProviderHealthResult:
        """Verify connectivity and operational status."""
        pass

    @abstractmethod
    def verify_webhook_signature(
        self,
        payload_bytes: bytes,
        signature_header: str,
        secret: Optional[str] = None,
    ) -> bool:
        """Verify HMAC signature on incoming webhooks."""
        pass
