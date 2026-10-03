# Phase 32: Billing, Invoicing & Operational Financial Transaction Management

## 1. Overview & Clinical Invariant Rules

Phase 32 delivers the operational backend financial transaction layer for the HealthSetu platform.

### Core Principles
- **BILLING ≠ CLINICAL DECISION**
- **PAYMENT ≠ CLINICAL VERIFICATION**
- **INVOICE ≠ MEDICAL RECORD**
- **PAYMENT STATUS ≠ APPOINTMENT STATUS**
- **PAYMENT SUCCESS ≠ CLINICAL SERVICE COMPLETION**
- **PAYMENT FAILURE ≠ CLINICAL FAILURE**
- **REFUND ≠ CLINICAL REVERSAL**
- **APPOINTMENT BOOKED ≠ PAYMENT COMPLETED**
- **PAYMENT COMPLETED ≠ PATIENT SEEN**

Payment failure must **NEVER** automatically cancel clinical care or appointments without explicit, configured administrative policies. Financial records are operational ledgers, strictly separate from clinical diagnoses, medication regimens, and patient safety assessments.

---

## 2. Integer Minor Unit Monetary Model

To avoid floating-point rounding errors and precision loss inherent in standard IEEE 754 representations:
- **All monetary calculations are performed in integer minor units** (e.g., paise for INR, cents for USD).
- ₹500.00 is strictly represented as `50000`.
- Deterministic calculation formula:
  $$\text{Item Total} = (\text{unit\_price} \times \text{quantity}) + \text{tax} - \text{discount}$$
  $$\text{Invoice Total} = \sum \text{Item Total}$$
  $$\text{Outstanding Balance} = \text{Invoice Total} - \text{Amount Paid} + \text{Amount Refunded}$$
- Calculations are performed deterministically in `app/services/billing_validation_service.py`. No LLMs or approximations are used.

---

## 3. Invoice Lifecycle State Machine

```
              ┌─────────┐
              │  DRAFT  │
              └────┬────┘
                   │ issue()
                   ▼
              ┌─────────┐
              │ ISSUED  ├──────────────────┐
              └────┬────┘                  │
                   │                       │
      ┌────────────┴────────────┐          │ cancel()
      │ payment                 │ payment  │ (only if amount_paid == 0)
      ▼ (partial)               ▼ (full)   ▼
┌───────────────┐          ┌────────┐ ┌───────────┐
│PARTIALLY_PAID │          │  PAID  │ │ CANCELLED │
└───────┬───────┘          └───┬────┘ └───────────┘
        │ full payment         │
        ▼                      │ refund
     ┌──────┐                  ▼
     │ PAID │       ┌────────────────────┐
     └──────┘       │ PARTIALLY_REFUNDED │
                    └──────────┬─────────┘
                               │ full refund
                               ▼
                        ┌──────────┐
                        │ REFUNDED │
                        └──────────┘
```

---

## 4. Multi-Tenant Authorization Scopes

| Role | Permitted Actions | Restricted Actions |
|---|---|---|
| **PATIENT** | Create draft self-invoices, view self-invoices, initiate payments for self | Cannot view external patient invoices, cannot issue administrative refunds |
| **DOCTOR** | View assigned appointment billing status if permitted | Cannot access patient credit card details, full transaction logs, or initiate refunds |
| **FACILITY / ORG ADMIN** | Manage invoices and view payments scoped to their facility/org | Cannot view or modify records from external facilities/orgs |
| **OPERATIONS / SYSTEM ADMIN** | Full administrative visibility, gateway connectivity tests, payment reconciliation | Protected under `ADMIN_BILLING_VIEW`, `ADMIN_BILLING_MANAGE`, `ADMIN_PAYMENT_RECONCILE` |
