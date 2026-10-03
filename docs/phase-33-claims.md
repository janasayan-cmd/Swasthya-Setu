# Phase 33: Medical Claims, Adjudication & Idempotency Management

## 1. Claim Lifecycle State Transitions

```
               ┌─────────┐
               │  DRAFT  │
               └────┬────┘
                    │ validate & submit
                    ▼
               ┌─────────┐
               │SUBMITTED├──────────────┐
               └────┬────┘              │
                    │                   │
         ┌──────────┴──────────┐        │ timeout/ambiguous
         ▼                     ▼        ▼
    ┌──────────┐          ┌─────────┐┌─────────┐
    │ RECEIVED │          │ PENDING ││ UNKNOWN │
    └────┬─────┘          └────┬────┘└────┬────┘
         │                     │          │ reconcile
         └──────────┬──────────┘          ▼
                    ▼               ┌─────────────┐
             ┌──────────────┐       │RECONCILIATION│
             │  ADJUDICATED │       │  REQUIRED   │
             └──────┬───────┘       └─────────────┘
                    │
      ┌─────────────┼─────────────┐
      ▼             ▼             ▼
┌──────────┐  ┌───────────┐ ┌──────────┐
│ APPROVED │  │ PARTIALLY │ │  DENIED  │
└────┬─────┘  │ APPROVED  │ └────┬─────┘
     │        └─────┬─────┘      │ resubmit
     ▼              ▼            ▼
 ┌──────┐       ┌──────┐    ┌────────────┐
 │ PAID │       │ PAID │    │RESUBMITTED │
 └──────┘       └──────┘    └────────────┘
```

---

## 2. Integer Minor Unit Monetary Model

To avoid floating-point errors:
$$\text{Line Item Total} = (\text{unit\_price} \times \text{quantity}) + \text{tax} - \text{discount}$$
$$\text{Claim Total} = \sum \text{Line Item Total}$$

Calculated deterministically in `app/services/insurance_validation_service.py`.

---

## 3. Payer Claim Payment vs Patient Payment Separation

- **Payer Claim Payment**: Represents remittance advice from insurance payer directly to healthcare facility or provider.
- **Patient Payment**: Managed via Phase 32 billing and invoices representing patient responsibility (copay, coinsurance, deductible).
- Payer claim payment and patient payment are stored in distinct ledgers and never collapsed into a single status.
