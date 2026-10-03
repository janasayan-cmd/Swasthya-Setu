# Phase 33: Real-Time Eligibility & Benefit Verification

## 1. Point-in-Time Verification Principles

Eligibility verification is strictly a **point-in-time** snapshot from an external payer clearinghouse:
- Active coverage today does **NOT** guarantee future coverage.
- Active coverage does **NOT** guarantee that a specific service or procedure will be approved or reimbursed.
- Incomplete response data is flagged with explicit limitations and uncertainty notes.

### Safety Invariants:
- `UNKNOWN ≠ INELIGIBLE`
- `UNKNOWN ≠ ELIGIBLE`
- `PROVIDER FAILURE ≠ ELIGIBLE`
- `PROVIDER TIMEOUT ≠ INELIGIBLE`

---

## 2. Normalized Eligibility State Machine

```
              ┌───────────────────────────┐
              │ Eligibility Verification  │
              └─────────────┬─────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
   ┌──────────┐      ┌────────────┐       ┌───────────┐
   │ ELIGIBLE │      │ INELIGIBLE │       │  UNKNOWN  │
   └──────────┘      └────────────┘       └─────┬─────┘
                                                │
                                                ▼
                                         ┌─────────────┐
                                         │ Reconcile / │
                                         │   Manual    │
                                         └─────────────┘
```

When an inquiry returns `ELIGIBLE`, unverified policy records transition to `ACTIVE`. When an inquiry returns `INELIGIBLE`, active policies transition to `INACTIVE`.

---

## 3. Benefit Categorization & Integer Monetary Limits

Supported standard categories:
- `CONSULTATION`: Outpatient visits and specialty consults.
- `DIAGNOSTIC`: Laboratory tests and advanced radiology.
- `INPATIENT`: Hospital admission, ICU, and room rent cappings.
- `OUTPATIENT`: Day-care procedures.
- `PHARMACY`: Prescription drug coverage.
- `EMERGENCY`: Acute care admissions.

All copayments, coinsurance, and deductibles are stored and calculated in integer minor currency units (e.g. paise for INR).
