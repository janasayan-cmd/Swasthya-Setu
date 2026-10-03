# HealthSetu — Phase 34: Diagnostic Results & Analyte Management

## 1. Overview
The Diagnostic Result Service handles the ingestion, validation, normalization, versioning, and clinical verification of laboratory observations and quantitative/qualitative analyte measurements.

## 2. Analyte Measurement Model
Every diagnostic result item preserves:
- **Analyte Concept**: `analyte_name`, `analyte_code` (e.g. LOINC `718-7`), and `system`.
- **Measurement Type**:
  - Quantitative: `numeric_value`, `unit`, and `reference_range`.
  - Qualitative: `qualitative_value` (e.g., `POSITIVE`, `NEGATIVE`, `DETECTED`, `REACTIVE`).
- **Abnormal Flag**: Provider-assigned flag (`NORMAL`, `HIGH`, `LOW`, `CRITICAL`, `ABNORMAL`, `POSITIVE`, `NEGATIVE`, `INCONCLUSIVE`).
- **Provenance**: Testing laboratory identifier, external result ID, timestamps, technician notes.

## 3. Strict Clinical Safety Invariants
1. **No Silent Unit Conversions**: Units (e.g., `mg/dL` vs `mmol/L`) are never converted without an explicitly validated conversion specification. Missing units are never guessed.
2. **Authoritative Reference Intervals**: Reference ranges are preserved exactly as reported by the testing laboratory. If not supplied, `is_available` is set to `False`. The system never invents reference ranges.
3. **Critical Panic Value Handling**:
   - When an analyte carries `AbnormalFlag.CRITICAL`, the record is marked `has_critical_flag = True`.
   - Emits audit event `CRITICAL_RESULT_REVIEW_REQUIRED`.
   - Dispatches high-priority notification to the clinician or care team.
   - **Crucial**: The system NEVER autonomously prescribes medication, adjusts dosage, orders follow-up tests, or alters triage urgency.

## 4. Immutable Versioning & Amendments (Section 26 & 56)
When a laboratory amends or corrects a previously issued result:
- The existing result is preserved with `is_current = False` and `verification_status = SUPERSEDED`.
- A new result record is created with:
  - `version = previous_version + 1`
  - `is_current = True`
  - `supersedes_result_id = previous_result_id`
  - `correction_reason` documented.
- Historical records are never overwritten or deleted, ensuring complete auditability.

## 5. Clinician Verification Workflow (Phase 10 Integration)
- Ingested or extracted results initially sit in `REVIEW_REQUIRED`.
- Authorized clinicians inspect the observation fact, units, and reference intervals.
- Clinician actions:
  - `VERIFY`: Updates status to `VERIFIED`, records `verified_by`, timestamp, and commentary.
  - `REJECT`: Updates status to `REJECTED` if data is corrupt or incompatible.
- Patients are granted access only to factual result data, clearly separated from speculative interpretations.
