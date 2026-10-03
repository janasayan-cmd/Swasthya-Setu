# Phase 33: Insurance & Claim Reconciliation Architecture

## 1. Objective & Discrepancy Categorization

Reconciliation ensures that HealthSetu financial ledgers accurately reflect external clearinghouse adjudication records without manual data loss.

### Discrepancy Types
- `AMOUNT_MISMATCH`: Difference between submitted claim items and approved clearinghouse total.
- `STATUS_MISMATCH`: Internal claim status diverges from clearinghouse status.
- `MISSING_EXTERNAL_RECORD`: Clearinghouse reports no record of transaction reference.
- `MISSING_INTERNAL_RECORD`: Inbound webhook contains reference unknown to HealthSetu.
- `ITEM_MISMATCH`: Line item quantities or service codes differ.
- `AUTHORIZATION_MISMATCH`: Prior authorization number missing or rejected by payer.
- `STALE_CLAIM`: Claim remaining in `SUBMITTED` state beyond configured timeout.

---

## 2. Reconciliation Lifecycle States

- `MATCHED`: Internal records and external clearinghouse balances match perfectly.
- `MISMATCHED`: Discrepancy detected and logged for operational review.
- `PENDING`: Reconciliation job queued.
- `RESOLVED`: Discrepancy investigated and amended by authorized administrator.
- `FAILED`: Provider error during reconciliation inquiry.
