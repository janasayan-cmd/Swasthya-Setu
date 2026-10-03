# Phase 32: Payment Provider Abstraction & Gateway Integration

## 1. Gateway Interface

To decouple HealthSetu business logic from any single external gateway vendor (e.g., Razorpay, Stripe, PayU), all interactions pass through `PaymentProvider` (`app/integrations/payments/base.py`):

```python
class PaymentProvider(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Provider code e.g. MOCK, RAZORPAY, STRIPE."""
        pass

    @abstractmethod
    async def create_payment_intent(self, payment: PaymentRecord) -> ProviderIntentResult:
        pass

    @abstractmethod
    async def get_payment_status(self, provider_transaction_id: str) -> ProviderStatusResult:
        pass

    @abstractmethod
    async def capture_payment(self, provider_transaction_id: str, amount_in_minor_units: int) -> ProviderStatusResult:
        pass

    @abstractmethod
    async def refund_payment(self, refund: RefundRecord) -> ProviderRefundResult:
        pass

    @abstractmethod
    def verify_webhook(self, raw_body: bytes, headers: Dict[str, str]) -> bool:
        pass

    @abstractmethod
    def parse_webhook(self, payload: Dict[str, Any]) -> ParsedWebhookEvent:
        pass

    @abstractmethod
    async def health_check(self) -> ProviderHealthResult:
        pass
```

---

## 2. Mock Provider Capabilities

The `MockPaymentProvider` (`app/integrations/payments/providers/mock.py`) is implemented for comprehensive offline testing and local development:
- **Instant Success Simulation**: Generates valid transaction references, order IDs, and client secrets.
- **Controlled Error Simulation**: Can be configured via `set_simulation(simulate_failure=True)` or `simulate_timeout=True`.
- **Ambiguous Outcome Simulation**: `simulate_unknown=True` returns an unconfirmed provider status, demonstrating how HealthSetu moves the transaction to `RECONCILIATION_REQUIRED` rather than falsely marking it failed or paid.
- **HMAC-SHA256 Webhook Verification**: Uses `settings.PAYMENT_WEBHOOK_SECRET` to validate signatures passed in `X-Mock-Signature`.
