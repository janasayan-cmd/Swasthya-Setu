# HealthSetu — Phase 46: Clinical Record Versioning, Change History & Temporal Data Integrity

## 1. Overview & System Mission

HealthSetu Phase 46 implements backend support for reliable temporal handling of clinical and clinical-adjacent records (medications, allergies, prescriptions, diagnostic results, documents, and care plans).

The system explicitly distinguishes:
- Current state
- Previous state
- Corrected state
- Superseded state
- Historical state
- Imported state
- Verified state
- Source state
- Audit history
- Clinical provenance

The core objective is to prevent destructive updates from erasing critical clinical history.

### Core Architectural Invariants:
```
CURRENT STATE ≠ COMPLETE HISTORY
UPDATE ≠ OVERWRITE HISTORY
CORRECTION ≠ DELETION
SUPERSESSION ≠ DELETION
NEW VERSION ≠ NEW CLINICAL EVENT
AUDIT EVENT ≠ CLINICAL RECORD VERSION
PROVENANCE ≠ AUDIT
EXTERNAL UPDATE ≠ AUTOMATIC OVERWRITE
IMPORTED ≠ VERIFIED
VERIFIED ≠ PERMANENTLY CORRECT
AI SUGGESTION ≠ RECORD CHANGE
DRAFT ≠ FINAL
FINAL ≠ IMMUTABLE IN EVERY CASE
READ ACCESS ≠ CHANGE ACCESS
CHANGE ACCESS ≠ DELETE ACCESS
DELETE ACCESS ≠ HISTORY DELETE
CURRENT RECORD ≠ HISTORICAL RECORD
TIMESTAMP ≠ CLINICAL OCCURRENCE TIME
DATABASE REMAINS SOURCE OF TRUTH
NO SILENT HISTORY DESTRUCTION
NO SILENT OVERWRITE
NO FALSE VERSIONING
NO FAKE CHANGE AUTHOR
NO UNAUTHORIZED HISTORY ACCESS
NO AI CONTROLLED CLINICAL RECORD CHANGE
```

---

## 2. Multi-Dimensional Temporal Model

The backend preserves separate, non-interchangeable timestamps for each version:
- **EVENT TIME**: When the clinical event actually occurred.
- **RECORDED TIME**: When information was entered into HealthSetu.
- **RECEIVED TIME**: When external inbound data was received.
- **UPDATED TIME**: When the current record changed.
- **EFFECTIVE TIME**: When the state became clinically applicable.
- **EXPIRATION TIME**: When the state stopped being applicable.
- **VERIFICATION TIME**: When clinician verification occurred.
- **SUPERSESSION TIME**: When another version replaced the prior version as current.

---

## 3. Optimistic Concurrency Control

Clinical record modifications protect against lost updates:
```
Clinician A reads Version 5.
Clinician B updates Version 5 → Version 6.
Clinician A attempts to update Version 5 (expected_version = 5, current_version = 6).
→ Backend returns 409 VERSION_CONFLICT (STALE_RESOURCE).
```
No silent overwrites are permitted.

---

## 4. Controlled Version Transitions

### A. Correction Model (`POST /{resource_type}/{resource_id}/correct`)
- A correction preserves the original state:
  ```
  VERSION 1 (5 mg)
       ↓
  CORRECTED
       ↓
  VERSION 2 (10 mg)
  ```
- Version 1 remains intact in history.
- Correcting a note or typo does not create a new clinical encounter event.

### B. Supersession Model (`POST /{resource_type}/{resource_id}/supersede`)
- Newer information replaces older information for current display.
- Old version is marked `is_current = False` and retains `temporal.supersession_time`.
- SUPERSEDED ≠ DELETED.

### C. Restore Model (`POST /{resource_type}/{resource_id}/restore`)
- RESTORE ≠ HISTORY DELETION.
- Restoring Version 4 when current is Version 7 creates **Version 8** reflecting Version 4's data.
- Intervening versions 4–7 remain fully accessible in history.

---

## 5. Security, Authorization & Privacy Boundaries

1. **History Access vs Current Access**:
   Reading current state does not automatically authorize viewing full historical revisions. Access to `/history` requires explicit history scope.
2. **Phase 43 Consent Integration**:
   Consent policies gate access to historical data.
3. **AI Safety Boundary**:
   Autonomous AI agents (e.g. `role=AI`, `type=AI_AGENT`) are strictly prohibited from authoring authoritative clinical versions, approving corrections, restoring records, or modifying clinical truth.
4. **Clinical Safety Boundary**:
   Versioning engine cannot autonomously diagnose, prescribe, triage, or alter active medications without human clinician review.
