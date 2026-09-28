# Phase 26: Data Quality Architecture & Rule Engine

## 1. Overview
The Data Quality subsystem in HealthSetu provides deterministic, reproducible validation of patient clinical records across multiple acquisition channels:
- Patient-reported data
- Clinician-entered data
- Uploaded and OCR/extracted documents
- Prescription extractions and medication normalizations
- Interoperability imports (FHIR/HL7)
- External healthcare facility records

### Core Principle
```
DATA QUALITY DETECTION != CLINICAL DECISION
RECONCILIATION != DIAGNOSIS
CONFLICT DETECTION != AUTOMATIC CORRECTION
DUPLICATE DETECTION != AUTOMATIC MERGING
NEWER DATA != AUTOMATICALLY CORRECT DATA
EXTRACTED / IMPORTED DATA != VERIFIED DATA
AI OUTPUT != CLINICAL TRUTH
```

## 2. Deterministic Rule Architecture
Rules are organized under `app/integrations/data_quality/` and extend `DataQualityRule`:
- **Completeness Rules** (`completeness_rules.py`):
  - `R-COMP-001`: Patient demographics completeness (DOB, sex, contact info).
  - `R-COMP-002`: Allergy clinical completeness (allergen, severity, status).
  - `R-COMP-003`: Medication record completeness (drug name, strength, dosage form).
- **Duplicate Detection Rules** (`duplicate_rules.py`):
  - `R-DUP-001`: Medical document duplicates based on SHA-256 content hashes.
  - `R-DUP-002`: Medication duplicates based on normalized drug name and dosage form.
  - `R-DUP-003`: Allergy duplicates based on allergen concept.
  *Duplicates are flagged as candidates for review; never merged automatically.*
- **Conflict Detection Rules** (`conflict_rules.py`):
  - `R-CONF-001`: Allergy status conflicts across records (e.g. active vs resolved).
  - `R-CONF-002`: Medication dosage/strength conflicts for active medications.
- **Stale Data Rules** (`stale_data_rules.py`):
  - `R-STALE-001`: Clinical observations exceeding the configured threshold (`STALE_DATA_THRESHOLD_DAYS`).
- **Provenance Validation Rules** (`provenance_rules.py`):
  - `R-PROV-001`: Detects missing origin source or creation timestamps.
  - `R-PROV-002`: Flags unverified external imports and OCR extractions for human clinician review.

## 3. Finding Lifecycle & Concurrency
Findings are assigned unique deterministic identifiers (`dqf_...`) and tracked through states:
`PENDING` -> `IN_REVIEW` -> `RESOLVED` / `REJECTED` / `UNRESOLVED`.
Every review and resolution updates the integer `version` field. When an authorized clinician submits a resolution, optimistic concurrency checking prevents overwriting concurrent edits (`409 Conflict`).
