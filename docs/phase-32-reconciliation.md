# Phase 32: Financial Transaction Reconciliation Architecture

## 1. Architectural Role & Invariants

Financial reconciliation (`app/services/payment_reconciliation_service.py`) ensures that internal ledgers accurately mirror external payment gateway reality.

### Critical Invariants
- **NEVER SILENTLY OVERWRITE FINANCIAL RECORDS**: Any adjustment preserves the original transaction, original amounts, and timestamped resolution notes.
- **FINANCIAL RECONCILIATION ≠ CLINICAL RECORD RECONCILIATION**: Financial transaction balancing is strictly decoupled from Phase 26 clinical record reconciliation.

---

## 2. Discrepancy Taxonomy

| Discrepancy Type | Description | Remediation Workflow |
|---|---|---|
| `AMOUNT_MISMATCH` | External provider captured amount differs from invoice expected amount | Transaction moved to `RECONCILIATION_REQUIRED`; flagged for admin review |
| `CURRENCY_MISMATCH` | External transaction currency differs from system ledger | Blocked from completing; flagged for administrative audit |
| `STATUS_MISMATCH` | Internal status is `SUCCEEDED` while gateway indicates `FAILED` / `REFUNDED` | Flagged as critical conflict for financial operations review |
| `MISSING_IN_PROVIDER` | Transaction recorded internally without matching gateway confirmation | Flagged as phantom transaction |
| `DUPLICATE_PROVIDER_TRANSACTION` | Gateway processed multiple charges for one invoice | Flagged for automated or manual refund |

---

## 3. Reconciliation Life Cycle

```
HealthSetu Transaction
         │
         ▼
External Gateway Transaction
         │
         ├── Provider Reference Check
         ├── Amount Check (Minor Units)
         ├── Currency Check (ISO 4217)
         └── Lifecycle State Check
         │
         ├── Perfect Match ──────────> MATCHED (Audited)
         │
         └── Discrepancy Detected ───> MISMATCHED (Logged to Registry)
                                           │
                                           ▼
                                    Controlled Admin
                                  Resolution Workflow
```
