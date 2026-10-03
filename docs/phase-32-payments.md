# Phase 32: Payments, Gateway Mediation & Idempotency Management

## 1. Architectural Overview

The payment engine coordinates between patient payment requests and third-party payment gateways (e.g., Razorpay, Stripe, Mock), upholding strict transaction integrity.

### Critical Invariants
1. **CLIENT PAYMENT STATUS ≠ AUTHORITATIVE PAYMENT STATUS**: A client saying "success" is never trusted. Transactions require server-side gateway verification.
2. **PROVIDER FAILURE ≠ PAYMENT SUCCESS**: An error or non-responsive gateway response does not yield a completed payment.
3. **UNKNOWN PAYMENT ≠ FAILED PAYMENT**: If a timeout occurs after funds may have been debited, the transaction is transitioned to `UNKNOWN` or `RECONCILIATION_REQUIRED`.
4. **NO CREDENTIAL STORAGE**: Card numbers, CVVs, PINs, and banking passwords are never accepted, processed, or logged.

---

## 2. Idempotency Flow

To prevent double-charging on network retries, clients provide an `Idempotency-Key` header or payload attribute:

```
Client                        HealthSetu Backend             Payment Gateway
  │                                   │                             │
  │─── POST /payments ───────────────>│                             │
  │    (Idempotency-Key: K1)          │── Lookup K1 (Not Found)     │
  │                                   │── Create Intent ───────────>│
  │                                   │<── Intent Response (Tx1) ───│
  │<── 201 Created (Tx1) ─────────────│                             │
  │                                   │                             │
  │─── POST /payments (Network Retry) │                             │
  │    (Idempotency-Key: K1)          │── Lookup K1 (Found Tx1)     │
  │                                   │── Verify Params Match       │
  │<── 200 OK (Returns Existing Tx1) ─│                             │
```

If a client reuses an idempotency key with conflicting parameters (e.g., different amount or invoice), `PAYMENT_IDEMPOTENCY_CONFLICT` (HTTP 409) is returned immediately.

---

## 3. Payment Status State Machine

```
              ┌─────────┐
              │ PENDING │
              └────┬────┘
                   │ gateway intent call
                   ▼
             ┌────────────┐
             │ PROCESSING │
             └─────┬──────┘
                   │
      ┌────────────┼────────────┐
      │ success    │ failure    │ timeout / ambiguous
      ▼            ▼            ▼
┌───────────┐ ┌────────┐ ┌─────────────────────────┐
│ SUCCEEDED │ │ FAILED │ │ RECONCILIATION_REQUIRED │
└─────┬─────┘ └────────┘ └───────────┬─────────────┘
      │                              │
      │ refund                       │ provider verification
      ▼                              ▼
┌──────────┐                   ┌───────────┐
│ REFUNDED │                   │ SUCCEEDED │ (or FAILED)
└──────────┘                   └───────────┘
```
