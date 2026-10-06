# HealthSetu — Phase 44: Clinical Data Sharing, External Access & Controlled Data Exchange

## 1. Executive Summary & Objective

Phase 44 implements controlled clinical data sharing and exchange between authorized patients, clinicians, care teams, facilities, organizations, and registered external systems.
It builds directly upon the Phase 43 centralized consent and access evaluation engine (`ConsentAccessService`).

### Core Safety Invariants
- `DATA SHARING != DATA CREATION`
- `DATA SHARING != CLINICAL DECISION`
- `DATA SHARING != DIAGNOSIS / TREATMENT / PRESCRIPTION / MEDICATION CHANGE / TRIAGE / EMERGENCY DISPATCH`
- `CONSENT != SHARING REQUEST != SHARING APPROVAL != CLINICAL APPROVAL`
- `READ ACCESS != EXPORT ACCESS != DOWNLOAD ACCESS != SHARE ACCESS != MODIFY ACCESS`
- `AI != SHARING AUTHORITY` (AI cannot authorize, approve, or expand sharing scope)
- `QUEUED AUTHORIZATION != CURRENT AUTHORIZATION` (JIT re-evaluation of consent immediately before dispatch)
- `PROVIDER TIMEOUT != SUCCESS`
- `PROVIDER UNAVAILABLE != SHARED`
- `UNKNOWN DELIVERY STATUS != DELIVERED`

---

## 2. Architecture & Pipeline

```
AUTHENTICATION (Phase 2)
    ↓
ACTOR & PATIENT IDENTIFICATION
    ↓
RESOURCE & ACTION SCOPE VALIDATION (Explicit scopes: MEDICATIONS, ALLERGIES, etc.)
    ↓
PURPOSE LIMITATION (CARE_DELIVERY, CARE_CONTINUITY)
    ↓
PHASE 43 CONSENT & ACCESS EVALUATION (ConsentAccessService)
    ↓
PHASE 24 PRIVACY & MINIMUM NECESSARY FILTERING
    ↓
DESTINATION VALIDATION & SSRF CHECK (sharing_security.py)
    ↓
DATA SNAPSHOT RETRIEVAL & INTEROPERABILITY MAPPING (FHIRMapper)
    ↓
OUTBOUND PROVENANCE RECORDING (SharingProvenanceService)
    ↓
SHARING PROVIDER ADAPTER DISPATCH (SharingProviderRegistry)
    ↓
STRUCTURED AUDIT EMISSION (AuditService)
    ↓
DELIVERY STATUS TRACKING (SHARED, DELIVERED, or FAILED)
```

---

## 3. Asynchronous Worker & JIT Consent Re-Evaluation

For queued exports and asynchronous exchanges:
1. Consent granted at queue time is NOT assumed to remain valid at execution time.
2. `SharingWorker` or `SharingService.execute_sharing` calls `SharingPolicyService.evaluate_sharing_policy()` immediately before data payload extraction.
3. If patient withdrew consent or consent expired during queue delay, the worker immediately halts, transitions status to `REVOKED` or `EXPIRED`, and emits an audit denial event.

---

## 4. API Specification

| Method | Path | Summary | Access |
|---|---|---|---|
| `POST` | `/api/v1/sharing-requests` | Create sharing request | Authenticated Users |
| `GET` | `/api/v1/sharing-requests` | List sharing requests | Requester / Patient / Admin |
| `GET` | `/api/v1/sharing-requests/{id}` | Get sharing request by ID | Requester / Patient / Recipient |
| `POST` | `/api/v1/sharing-requests/{id}/approve` | Approve sharing request | Target Patient |
| `POST` | `/api/v1/sharing-requests/{id}/deny` | Deny sharing request | Target Patient |
| `POST` | `/api/v1/sharing-requests/{id}/cancel` | Cancel sharing request | Requester / Patient |
| `POST` | `/api/v1/sharing-requests/{id}/execute` | Execute sharing transmission | Requester / Patient |
| `GET` | `/api/v1/sharing-requests/{id}/status` | Poll delivery status | Requester / Patient / Recipient |
| `GET` | `/api/v1/sharing-requests/{id}/history` | Lifecycle transition history | Requester / Patient / Recipient |
| `GET` | `/api/v1/patients/{patient_id}/sharing-requests` | List patient sharing requests | Patient / Admin |
| `GET` | `/api/v1/patients/{patient_id}/shared-data` | Patient shared data summary | Patient / Admin |
| `POST` | `/api/v1/patients/{patient_id}/exports` | Create controlled snapshot export | Patient / Authorized Clinician |
| `GET` | `/api/v1/exports/{export_id}` | Get export artifact | Requester / Patient |
| `GET` | `/api/v1/exports/{export_id}/status` | Poll export generation status | Requester / Patient |
| `POST` | `/api/v1/exports/{export_id}/cancel` | Cancel export | Requester / Patient |
| `POST` | `/api/v1/internal/sharing/evaluate` | Evaluate policy eligibility | Internal Service / Clinician |
