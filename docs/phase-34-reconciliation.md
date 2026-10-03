# HealthSetu — Phase 34: Diagnostic Reconciliation & Data Quality

## 1. Overview
The Diagnostic Reconciliation Service (integrated with Phase 26) continuously audits integrity and consistency between clinical orders, ingested laboratory results, and external provider ledgers.

## 2. Discrepancy Detection Taxonomy
The reconciliation engine identifies discrepancies across several categories:
- `DUPLICATE_RESULT`: Redundant result transmissions with identical analyte timestamps and values.
- `CONFLICTING_RESULT`: Multiple concurrent active results for the same analyte without an amendment or superseding relationship.
- `CORRECTED_RESULT`: Amended result identified in audit ledger.
- `MISSING_RESULT`: Order marked `COMPLETED` but lacks corresponding result observations.
- `PATIENT_MISMATCH`: Result patient identifier does not match parent order patient.
- `ORDER_MISMATCH`: Result references an unrecognized order.
- `UNIT_MISMATCH` / `MISSING_UNIT`: Numeric analyte reported without required unit of measure.
- `MISSING_PROVENANCE`: Result missing authoritative provider or audit attribution.

## 3. Strict Reconciliation Boundaries
- **No Autonomous Merging**: When conflicting clinical results are discovered, the engine creates a `ReconciliationFinding` and flags the issue for manual clinician audit. It **NEVER** automatically averages, selects, or merges conflicting clinical values.
- **Data Quality Finding ≠ Clinical Diagnosis**: A missing unit or discrepancy finding reflects an engineering or transmission defect, never a patient pathological condition.
- **Audit Logging**: Every reconciliation run generates an immutable `ReconciliationSummary` record.
