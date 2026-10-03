# Phase 33: Payer Provider Abstraction & Gateway Integration

## 1. Gateway Architecture

The platform mediates between internal services and insurance clearinghouses via `PayerProvider`:

```
┌────────────────────────────────┐
│ HealthSetu Claim & Auth Engine │
└───────────────┬────────────────┘
                │
                ▼
      ┌──────────────────┐
      │  PayerProvider   │  (app/integrations/payers/base.py)
      └─────────┬────────┘
                │
      ┌─────────┴─────────┐
      ▼                   ▼
┌──────────────┐    ┌───────────────────────────┐
│ MockProvider │    │ National Payer / Clearing │
└──────────────┘    └───────────────────────────┘
```

---

## 2. Inbound Webhook Verification & Deduplication

Payer clearinghouses emit asynchronous events (`claim.adjudicated`, `preauth.approved`, etc.) to:
`POST /api/v1/webhooks/payers/{provider}`

### Security Enforcement:
1. **HMAC-SHA256 Signature Verification**: Header `X-Payer-Signature` is checked using `settings.PAYER_WEBHOOK_SECRET`.
2. **Replay & Duplicate Protection**: Ingested `event_id` is tracked in `PayerWebhookRepository`. Duplicate deliveries immediately return `PayerWebhookEventStatus.DUPLICATE`.
3. **Safe State Transitions**: Incoming status updates advance claim or authorization states using `InsuranceValidationService`.
