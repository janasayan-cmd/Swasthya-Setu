# HealthSetu — Phase 45: External Data Ingestion, Clinical Reconciliation & Trusted Record Integration

## 1. Overview & System Mission

HealthSetu Phase 45 implements safe, provenance-aware, controlled ingestion of clinical and healthcare data from external authorized sources (hospitals, clinics, laboratories, diagnostic centers, healthcare networks, interoperability providers, and FHIR/HL7 gateways).

### Foundational Invariant:
```
IMPORT ≠ VERIFICATION
IMPORT ≠ CLINICAL TRUTH
EXTERNAL DATA ≠ HEALTHSETU TRUTH
EXTERNAL DATA ≠ DIAGNOSIS
EXTERNAL DATA ≠ TREATMENT
EXTERNAL DATA ≠ PRESCRIPTION AUTHORITY
EXTERNAL DATA ≠ MEDICATION CHANGE
EXTERNAL DATA ≠ TRIAGE
EXTERNAL DATA ≠ EMERGENCY DISPATCH
FHIR VALID ≠ CLINICALLY VERIFIED
AI EXTRACTION ≠ CLINICAL VERIFICATION
AI MATCH ≠ PATIENT IDENTITY CONFIRMATION
AI SUGGESTION ≠ RECORD UPDATE
DATABASE REMAINS SOURCE OF TRUTH
NO AUTOMATIC CLINICAL OVERWRITE
NO SILENT MERGE
NO SILENT PATIENT MATCH
```

**External clinical data enters HealthSetu as untrusted/unverified input (`UNVERIFIED`), subject to multi-stage technical and domain reconciliation before any clinical consumer can access it.**

---

## 2. Ingestion Pipeline Lifecycle

```
External Source (Hospital / Lab / Network)
                   │
                   ▼
[1] Source Authentication & Credential Verification
                   │
                   ▼
[2] Source Authorization & Scope Check
                   │
                   ▼
[3] Interoperability & Payload Validation (FHIR R4 / Schema)
                   │
                   ▼
[4] Deterministic Patient Identity Resolution (Strict rules; No silent merges)
                   │
                   ▼
[5] Phase 43 Consent & Access Verification (Active recheck at execution time)
                   │
                   ▼
[6] Provenance Recording & Cryptographic Hash (SHA-256)
                   │
                   ▼
[7] Phase 13 Resource Mapping
                   │
                   ▼
[8] Phase 26 Domain Reconciliation & Duplicate Detection
                   │
        ┌──────────┴──────────┐
        │                     │
[Clean / Matched]     [Conflict / Review Required]
        │                     │
        ▼                     ▼
[Stage as UNVERIFIED]  [Create Review Task (Phase 36)]
        │                     │
        └──────────┬──────────┘
                   ▼
[9] Audit Trail Emission (Phase 24 / RFC-Compliant Audit)
                   │
                   ▼
[10] Authorized Clinical Retrieval (Tagged as External UNVERIFIED)
```

---

## 3. Core Principles & Boundaries

### 3.1 Source Trust vs. Clinical Truth
- External source trust states: `REGISTERED`, `AUTHORIZED`, `ACTIVE`, `DEGRADED`, `SUSPENDED`, `REVOKED`.
- An authorized, accredited laboratory sending a valid FHIR DiagnosticReport does **not** make the result verified or automatically diagnostic.
- Data status defaults to `UNVERIFIED` until clinician review or domain reconciliation confirms it.

### 3.2 Deterministic Identity Resolution & AI Boundaries
- External identifiers (e.g., MRN, National Health ID) are resolved using exact matching rules.
- Demographics require a multi-field match (Exact Name + DOB + Gender + Mobile). Single demographic matches yield `MATCH_CANDIDATE` or `REVIEW_REQUIRED`.
- Multiple matching candidates halt automatic progression (`MULTIPLE_MATCHES`).
- **AI Boundary**: AI agents/models are **strictly prohibited** from confirming patient identities or merging records (`AIPatientMatchProhibitedException`). AI is limited to candidate suggestions only.

### 3.3 Domain Boundaries (No Second Systems)
- **Phase 13 (Interoperability)**: Used for FHIR R4 validation and domain mapping. Phase 45 does not create duplicate FHIR parsers.
- **Phase 26 (Reconciliation & Data Quality)**: Invoked for domain reconciliation, deduplication, and conflict detection across medications, allergies, diagnostic reports, and conditions.
- **Phase 43 (Consent)**: Re-evaluated at ingestion runtime. Even if a source is authorized, if patient consent is revoked, ingestion is halted (`IngestionConsentRevokedException`).
- **Phase 6 / 7 (Medications)**: External medications cannot silently modify active prescription lists.
- **Phase 34 (Diagnostic Results)**: Laboratory values are preserved with reference ranges and units; missing units or reference ranges are never assumed normal.

---

## 4. API Reference

### Ingestion Operations
- `POST /api/v1/ingestions`: Ingest external clinical payload (JSON / FHIR R4).
- `GET /api/v1/ingestions`: List ingestion records with filtering.
- `GET /api/v1/ingestions/{ingestion_id}`: Get ingestion record and provenance details.
- `GET /api/v1/ingestions/{ingestion_id}/status`: Get ingestion lifecycle status.
- `GET /api/v1/ingestions/{ingestion_id}/history`: Provenance and transformation history.
- `POST /api/v1/ingestions/{ingestion_id}/cancel`: Cancel pending/processing ingestion.

### Patient External Records
- `GET /api/v1/patients/{patient_id}/external-records`: Retrieve external clinical records for a patient (annotated with trust status).
- `GET /api/v1/patients/{patient_id}/import-history`: Retrieve historical ingestion events for a patient.

### Reconciliation Resolution
- `GET /api/v1/reconciliation/{reconciliation_id}`: Retrieve reconciliation review session.
- `POST /api/v1/reconciliation/{reconciliation_id}/resolve`: Clinician resolution of conflicting items (`ACCEPT_SOURCE`, `ACCEPT_TARGET`, `MERGE`, `REJECT`).

### Provider Webhooks
- `POST /api/v1/integrations/{provider}/webhook`: Inbound webhook endpoint with HMAC signature validation and timestamp replay protection.

### Internal Processing
- `POST /api/v1/internal/ingestion/process`: Internal task worker endpoint for processing queued ingestion jobs.

---

## 5. Security & Threat Mitigations

1. **Webhook Replay Protection**: Nonce/Event-ID cache combined with strict timestamp drift windows (max 300s).
2. **Payload Size Limits**: Strict ceiling enforced (configurable, default 10MB) to prevent parser exhaustion / denial of service.
3. **Identifier Isolation**: Organization-scoped namespaces prevent cross-facility identifier collisions.
4. **Audit Logging**: All stages generate structured audit events without logging sensitive unencrypted PHI.
