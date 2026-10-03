"""Mock Payment Provider for testing and local development (Phase 32).

Supports realistic simulation of:
- Instant success
- Explicit failures
- Ambiguous/unknown provider responses (reconciliation required)
- Gateway timeouts
- Cryptographic HMAC-SHA256 webhook verification
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import time
import uuid
from typing import Any, Dict, Optional

from app.core.config import settings
from app.integrations.payments.base import (
    ParsedWebhookEvent,
    PaymentProvider,
    ProviderHealthResult,
    ProviderIntentResult,
    ProviderRefundResult,
    ProviderState,
    ProviderStatusResult,
)
from app.schemas.payment import PaymentRecord
from app.schemas.refund import RefundRecord

logger = logging.getLogger(__name__)


class MockPaymentProvider(PaymentProvider):
    """Configurable mock provider adapter for integration and failure testing."""

    def __init__(self, webhook_secret: Optional[str] = None) -> None:
        self._webhook_secret = webhook_secret or settings.PAYMENT_WEBHOOK_SECRET
        self._transactions: Dict[str, Dict[str, Any]] = {}
        self._simulate_timeout: bool = False
        self._simulate_failure: bool = False
        self._simulate_unknown: bool = False
        self._custom_status: Optional[str] = None

    @property
    def name(self) -> str:
        return "MOCK"

    def set_simulation(
        self,
        simulate_timeout: bool = False,
        simulate_failure: bool = False,
        simulate_unknown: bool = False,
        custom_status: Optional[str] = None,
    ) -> None:
        """Configure mock behavior for tests."""
        self._simulate_timeout = simulate_timeout
        self._simulate_failure = simulate_failure
        self._simulate_unknown = simulate_unknown
        self._custom_status = custom_status

    async def create_payment_intent(
        self,
        payment: PaymentRecord,
        options: Optional[Dict[str, Any]] = None,
    ) -> ProviderIntentResult:
        if self._simulate_timeout:
            return ProviderIntentResult(
                success=False,
                provider_transaction_id="",
                provider_status="TIMEOUT",
                error_code="GATEWAY_TIMEOUT",
                error_message="Simulated gateway network timeout",
            )
        if self._simulate_failure:
            return ProviderIntentResult(
                success=False,
                provider_transaction_id="",
                provider_status="FAILED",
                error_code="PAYMENT_DECLINED",
                error_message="Card declined by issuing bank",
            )
        if self._simulate_unknown:
            tx_id = f"mock_tx_{uuid.uuid4().hex[:12]}"
            return ProviderIntentResult(
                success=False,
                provider_transaction_id=tx_id,
                provider_status="UNKNOWN",
                error_code="PROVIDER_AMBIGUOUS_RESPONSE",
                error_message="Provider transaction state unknown, reconciliation required",
            )

        tx_id = f"mock_tx_{uuid.uuid4().hex[:12]}"
        order_id = f"mock_ord_{uuid.uuid4().hex[:12]}"
        status = self._custom_status or "CREATED"

        self._transactions[tx_id] = {
            "id": tx_id,
            "order_id": order_id,
            "amount": payment.amount_in_minor_units,
            "currency": payment.currency,
            "status": status,
            "created_at": time.time(),
        }

        return ProviderIntentResult(
            success=True,
            provider_transaction_id=tx_id,
            provider_order_id=order_id,
            provider_status=status,
            client_secret=f"mock_secret_{uuid.uuid4().hex}",
            raw_response={"provider": "MOCK", "id": tx_id, "status": status},
        )

    async def get_payment_status(self, provider_transaction_id: str) -> ProviderStatusResult:
        if self._simulate_timeout:
            return ProviderStatusResult(
                success=False,
                provider_transaction_id=provider_transaction_id,
                status="TIMEOUT",
                amount_in_minor_units=0,
                currency="INR",
                error_code="GATEWAY_TIMEOUT",
                error_message="Gateway timeout during status inquiry",
            )

        tx = self._transactions.get(provider_transaction_id)
        if not tx:
            return ProviderStatusResult(
                success=False,
                provider_transaction_id=provider_transaction_id,
                status="NOT_FOUND",
                amount_in_minor_units=0,
                currency="INR",
                error_code="TRANSACTION_NOT_FOUND",
                error_message="Transaction not found in mock provider registry",
            )

        status = self._custom_status or tx["status"]
        return ProviderStatusResult(
            success=True,
            provider_transaction_id=provider_transaction_id,
            status=status,
            amount_in_minor_units=tx["amount"],
            currency=tx["currency"],
            raw_response=tx,
        )

    async def capture_payment(
        self,
        provider_transaction_id: str,
        amount_in_minor_units: int,
    ) -> ProviderStatusResult:
        tx = self._transactions.get(provider_transaction_id)
        if not tx:
            # Create a mock entry if not present
            tx = {
                "id": provider_transaction_id,
                "amount": amount_in_minor_units,
                "currency": "INR",
                "status": "CAPTURED",
            }
            self._transactions[provider_transaction_id] = tx
        else:
            tx["status"] = "CAPTURED"
            tx["amount"] = amount_in_minor_units

        return ProviderStatusResult(
            success=True,
            provider_transaction_id=provider_transaction_id,
            status="CAPTURED",
            amount_in_minor_units=amount_in_minor_units,
            currency=tx.get("currency", "INR"),
            raw_response=tx,
        )

    async def cancel_payment(self, provider_transaction_id: str, reason: str) -> ProviderStatusResult:
        tx = self._transactions.get(provider_transaction_id)
        if tx:
            tx["status"] = "CANCELLED"
            tx["cancel_reason"] = reason

        return ProviderStatusResult(
            success=True,
            provider_transaction_id=provider_transaction_id,
            status="CANCELLED",
            amount_in_minor_units=tx["amount"] if tx else 0,
            currency=tx.get("currency", "INR") if tx else "INR",
            raw_response=tx or {},
        )

    async def refund_payment(self, refund: RefundRecord) -> ProviderRefundResult:
        if self._simulate_timeout:
            return ProviderRefundResult(
                success=False,
                provider_refund_id="",
                provider_status="TIMEOUT",
                amount_in_minor_units=0,
                currency=refund.currency,
                error_code="GATEWAY_TIMEOUT",
                error_message="Simulated gateway timeout on refund",
            )
        if self._simulate_failure:
            return ProviderRefundResult(
                success=False,
                provider_refund_id="",
                provider_status="FAILED",
                amount_in_minor_units=0,
                currency=refund.currency,
                error_code="REFUND_DECLINED",
                error_message="Issuer declined refund transaction",
            )

        ref_id = f"mock_rf_{uuid.uuid4().hex[:12]}"
        return ProviderRefundResult(
            success=True,
            provider_refund_id=ref_id,
            provider_status="COMPLETED",
            amount_in_minor_units=refund.amount_in_minor_units,
            currency=refund.currency,
            raw_response={"refund_id": ref_id, "status": "COMPLETED"},
        )

    def verify_webhook(self, raw_body: bytes, headers: Dict[str, str]) -> bool:
        signature = headers.get("x-mock-signature") or headers.get("X-Mock-Signature")
        if not signature:
            return False
        expected_sig = hmac.new(
            self._webhook_secret.encode("utf-8"),
            raw_body,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(signature, expected_sig)

    def parse_webhook(self, payload: Dict[str, Any]) -> ParsedWebhookEvent:
        event_id = payload.get("event_id") or f"mock_ev_{uuid.uuid4().hex[:8]}"
        event_type = payload.get("event_type") or "payment.captured"
        data = payload.get("data", {})
        tx_id = data.get("provider_transaction_id") or data.get("id")
        status = data.get("status", "SUCCESS")
        amount = data.get("amount_in_minor_units") or data.get("amount")
        currency = data.get("currency", "INR")

        return ParsedWebhookEvent(
            event_id=event_id,
            event_type=event_type,
            provider_transaction_id=tx_id,
            status=status,
            amount_in_minor_units=int(amount) if amount is not None else None,
            currency=currency,
            raw_event=payload,
        )

    async def health_check(self) -> ProviderHealthResult:
        start = time.perf_counter()
        if self._simulate_failure:
            return ProviderHealthResult(
                state=ProviderState.UNAVAILABLE,
                message="Mock payment provider in simulated failure state",
                latency_ms=(time.perf_counter() - start) * 1000,
            )
        return ProviderHealthResult(
            state=ProviderState.AVAILABLE,
            message="Mock payment provider operational",
            latency_ms=(time.perf_counter() - start) * 1000,
        )
