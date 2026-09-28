# Phase 26: Cross-Source Clinical Reconciliation & Provenance

## 1. Overview
Reconciliation evaluates clinical facts across disparate sources (e.g. verified internal records, patient self-reports, external FHIR imports, document extractions) to identify discrepancies without unilaterally declaring a "winner".

### Safety Boundaries
1. **No Autonomous Overwrites**: Newer or imported records never replace internally verified data automatically.
2. **Explicit Provenance**: Every clinical resource records its source category:
   - `PATIENT_REPORTED`
   - `CLINICIAN_ENTERED`
   - `DOCUMENT_EXTRACTED`
   - `OCR_EXTRACTED`
   - `IMPORTED`
   - `AI_EXTRACTED`
   - `SYSTEM_GENERATED`
3. **Verification States**: Only human clinicians with explicit authorization can transition unverified data to `CLINICIAN_VERIFIED`.

## 2. Multi-Source Reconciliation Workflow
```
Reconciliation Request
  ↓
Extract & Normalize Internal & External Items
  ↓
Pairwise Concept Alignment (Allergens, Medications, Vitals, Demographics)
  ↓
Conflict & Duplicate Detection
  ↓
Reconciliation Record Created (PENDING / UNRESOLVED / RESOLVED)
  ↓
Clinician Review via /patients/{id}/reconciliation/{id}/resolve
  ↓
Audit Event Logged + Version Concurrency Validation
```

## 3. Supported Scopes
- `ALL`: Evaluates all clinical scopes.
- `MEDICATIONS`: Compares prescribed drugs, dosage, strengths, and frequencies.
- `ALLERGIES`: Compares allergens, severities, and clinical statuses.
- `EXTERNAL_DATA`: Evaluates imported demographic and observation records.
