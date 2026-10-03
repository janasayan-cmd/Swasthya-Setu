"""Payment Provider Abstraction (Phase 32).

Defines the pluggable interface for payment gateways (e.g. Razorpay, Stripe, Mock)
without hardcoding any specific provider into business logic.

SAFETY INVARIANTS:
- PROVIDER FAILURE ≠ PAYMENT SUCCESS
- UNKNOWN PROVIDER RESULT ≠ FAILED OR SUCCESSFUL (Requires reconciliation)
- Secrets / credentials must come from configuration, never committed to code.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional

from app.schemas.payment import PaymentRecord
from app.schemas.refund import RefundRecord


class ProviderState(str, Enum):
    """Health and configuration state of a payment provider."""
    AVAILABLE = "AVAILABLE"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"
    DISABLED = "DISABLED"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    UNKNOWN = "UNKNOWN"


@dataclass
class ProviderIntentResult:
    """Outcome of initiating a transaction with an external payment provider."""
    success: bool
    provider_transaction_id: str
    provider_status: str
    provider_order_id: Optional[str] = None
    client_secret: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    raw_response: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProviderStatusResult:
    """Outcome of querying an external transaction status."""
    success: bool
    provider_transaction_id: str
    status: str
    amount_in_minor_units: int
    currency: str
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    raw_response: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProviderRefundResult:
    """Outcome of refund processing with an external provider."""
    success: bool
    provider_refund_id: str
    provider_status: str
    amount_in_minor_units: int
    currency: str
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    raw_response: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedWebhookEvent:
    """Normalized webhook payload after provider-specific parsing."""
    event_id: str
    event_type: str
    provider_transaction_id: Optional[str]
    status: Optional[str]
    amount_in_minor_units: Optional[int]
    currency: Optional[str]
    raw_event: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProviderHealthResult:
    """Health status check response for provider monitoring."""
    state: ProviderState
    message: str
    latency_ms: float = 0.0


class PaymentProvider(ABC):
    """Abstract interface that all payment gateway integrations must implement."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier (e.g. MOCK, RAZORPAY, STRIPE)."""
        pass

    @abstractmethod
    async def create_payment_intent(
        self,
        payment: PaymentRecord,
        options: Optional[Dict[str, Any]] = None,
    ) -> ProviderIntentResult:
        """Initiate payment session/intent with external gateway."""
        pass

    @abstractmethod
    async def get_payment_status(self, provider_transaction_id: str) -> ProviderStatusResult:
        """Query real-time status of transaction from external gateway."""
        pass

    @abstractmethod
    async def capture_payment(
        self,
        provider_transaction_id: str,
        amount_in_minor_units: int,
    ) -> ProviderStatusResult:
        """Capture authorized transaction."""
        pass

    @abstractmethod
    async def cancel_payment(self, provider_transaction_id: str, reason: str) -> ProviderStatusResult:
        """Cancel an open/unsettled payment intent."""
        pass

    @abstractmethod
    async def refund_payment(self, refund: RefundRecord) -> ProviderRefundResult:
        """Process refund with external gateway."""
        pass

    @abstractmethod
    def verify_webhook(self, raw_body: bytes, headers: Dict[str, str]) -> bool:
        """Cryptographically verify signature and integrity of incoming webhook."""
        pass

    @abstractmethod
    def parse_webhook(self, payload: Dict[str, Any]) -> ParsedWebhookEvent:
        """Extract standardized event structure from provider-specific webhook payload."""
        pass

    @abstractmethod
    async def health_check(self) -> ProviderHealthResult:
        """Verify reachability and credentials of payment gateway."""
        pass
