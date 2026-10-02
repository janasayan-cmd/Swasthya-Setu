# Phase 30: Authorized Search, Indexing & Clinical Resource Retrieval — Architecture

## 1. Executive Summary & Boundaries

Phase 30 establishes an authorized, multi-tenant search and clinical resource retrieval layer for HealthSetu. It enables patients, clinicians, and administrators to discover and navigate existing clinical resources without bypassing consent, tenant isolation, or role-based boundaries.

### Inviolable Safety & Security Invariants
- **SEARCH ≠ CLINICAL DECISION**: Search results do not diagnose, assess acuity, or recommend treatments.
- **SEARCH ≠ DIAGNOSIS / TRIAGE / MEDICATION SAFETY**: Acuity assessment remains Phase 8; drug safety checks remain Phase 7.
- **SEARCH RELEVANCE ≠ CLINICAL PRIORITY**: Textual relevance ordering (exact, prefix, contains) never represents medical severity or clinical urgency.
- **SEARCH FAILURE ≠ NO RESULTS**: A provider outage or timeout raises an explicit error (`SEARCH_PROVIDER_UNAVAILABLE`), preventing workflows from erroneously assuming a patient or record does not exist.
- **SEARCH INDEX ≠ SOURCE OF TRUTH**: The HealthSetu PostgreSQL database is the single clinical source of truth. Search indexes are disposable retrieval mechanisms.
- **SEARCH RESULT MINIMIZATION**: Search results return only minimum necessary identifiers and displays (`resource_type`, `resource_id`, `display`, `match_type`, `status`, `provenance`). Complete clinical histories or raw notes are never returned in search results.
- **PRE-SEARCH SCOPE INJECTION**: Authorization filters (patient ID, organization ID, facility ID) are injected *prior* to database query execution to prevent information leakage via result counts, timing, or autocomplete.

---

## 2. Architecture Diagram

```
                 CLIENT (Patient / Clinician / Admin)
                                 │
                                 ▼
                     ┌───────────────────────┐
                     │   FastAPI Endpoints   │
                     │  /api/v1/search...    │
                     └───────────┬───────────┘
                                 │
                                 ▼
                    Authentication & Session
                                 │
                                 ▼
                   Authorization & Scope Guard
             (Role, Patient ID, Org/Facility Boundaries)
                                 │
                                 ▼
                     Search Normalization
          (NFKC Unicode, Control Char Strip, Case-Folding)
                                 │
                                 ▼
                       Search Service
                                 │
                 ┌───────────────┴───────────────┐
                 ▼                               ▼
       PostgresSearchProvider            External Provider
         (Direct Repository)                 (Adapter)
                 │                               │
                 └───────────────┬───────────────┘
                                 ▼
                      Existing Domain Data
             (Patients, Encounters, Docs, Meds, etc.)
                                 │
                                 ▼
                     Search Result Service
              (Minimization, Provenance, Allowlist Sort)
                                 │
                   ┌─────────────┴─────────────┐
                   ▼                           ▼
            Audit Service              Metrics & Logging
        (PHI-Safe Audit Event)        (Zero-PHI Latency/Counts)
```

---

## 3. Component Responsibilities

1. **`SearchNormalizationService`**:
   - Strips dangerous characters and quotes.
   - Collapses whitespace and normalizes Unicode (NFKC).
   - Validates minimum (2 chars) and maximum (200 chars) length bounds.
   - Strictly performs **zero** clinical interpretation (e.g., "Paracetamol 500mg" is normalized purely as text).

2. **`SearchAuthorizationService`**:
   - Injects scope based on `AuthenticatedUserContext`.
   - Patients can only search their own records (`actor_patient_id` injected).
   - Doctors can search authorized patient records, clinician directory, and facilities.
   - Enforces multi-tenant organizational isolation (`actor_org_id` and `actor_facility_id`).
   - Protects against patient enumeration attacks.

3. **`SearchProvider` Abstraction**:
   - Abstract base class defining `search`, `search_resource`, `get_suggestions`, `health_check`, `get_index_status`, and `rebuild_index`.
   - `PostgresSearchProvider`: Implements unified retrieval directly against existing domain repositories.

4. **`SearchResultService`**:
   - Applies allowlisted sorting (`relevance`, `name`, `status`).
   - Performs bounded pagination (`page >= 1`, `1 <= page_size <= 100`).
   - Attaches data provenance (source system, source version, originating organization).
   - Enforces minimum necessary data minimization.

5. **`SearchService` Orchestrator**:
   - Coordinates end-to-end execution.
   - Records centralized audit events (`SEARCH_EXECUTED`, `PATIENT_SEARCH_EXECUTED`, etc.).
   - Dispatches operational telemetry.
