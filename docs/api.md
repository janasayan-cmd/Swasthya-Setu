# HealthSetu — Production API Specification & Lifecycle Policy

## 1. API Architecture & Versioning Strategy

All public HealthSetu APIs are strictly versioned under URL path prefixes:

```
https://api.healthsetu.com/api/v1/...
```

### Versioning Principles
- **Backward Compatibility**: Existing clients consuming `/api/v1` MUST NOT experience breaking schema modifications, unexpected field removals, or semantic behavior shifts.
- **Breaking Changes**: Any breaking change (e.g. required new request parameter, modified response payload shape, altered authentication flow) MUST be released under a new version prefix (e.g. `/api/v2`) and follow the formal Deprecation Policy.
- **OpenAPI 3.x Stability**: The OpenAPI schema (`/openapi.json`) serves as the single authoritative source of truth for all request/response models, parameter validation, security schemes, and error contracts.

---

## 2. Standardized Response & Error Contracts

### Success Response Envelope
All API endpoints return data enveloped in a predictable JSON structure:
```json
{
  "success": true,
  "data": { ... },
  "request_id": "c8b42fd2-1a42-4fbc-9b63-128a385f9e2b"
}
```

### Standardized Error Envelope
Errors follow a uniform schema across all modules:
```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "The provided dosage '10000mg' exceeds maximum safety thresholds.",
    "request_id": "c8b42fd2-1a42-4fbc-9b63-128a385f9e2b"
  }
}
```

### Critical Production Error Boundary (Section 11)
In production (`APP_ENV=production`), error responses MUST NEVER expose:
- Python tracebacks or stack traces.
- Raw SQL queries, table names, or database constraint error strings.
- Internal server file system paths (`/app/...` or `C:\...`).
- External provider credentials, API keys, or connection URLs.
- Protected Health Information (PHI) such as patient names, phone numbers, or unmasked identifiers.

---

## 3. Production API Domain Index (Section 12)

| Domain | Base Path | Core Capabilities & Endpoints |
| :--- | :--- | :--- |
| **Health & Probes** | `/api/v1/health`<br>`/api/v1/ready` | Liveness check (process up) and Readiness check (Supabase DB connectivity verified). |
| **Authentication** | `/api/v1/auth/*` | `/login` (Argon2id password verification, JWT issuance), `/refresh`, `/logout`, `/me`. |
| **Authorization & Consent** | `/api/v1/consents/*` | Granular patient consent creation, verification, revocation, and audit linkage. |
| **Patient Profile** | `/api/v1/patients/*` | Patient identity verification, demographic management, and profile retrieval. |
| **Clinical Records** | `/api/v1/patients/{id}/*` | `/clinical-history`, `/allergies`, `/vitals`, and `/encounters` timelines. |
| **Documents** | `/api/v1/documents/*` | File upload, SHA-256 deduplication, OCR processing, and document retrieval. |
| **Prescriptions** | `/api/v1/patients/{id}/prescriptions/*` | Structured prescription records, document extraction linkage, and items. |
| **Medications** | `/api/v1/medications/*`<br>`/api/v1/patients/{id}/medications/*` | Terminology normalization (RxNorm/SNOMED-CT), active medication records. |
| **Medication Safety** | `/api/v1/patients/{id}/medication-safety/*` | Drug-drug interaction checks, allergy alerts, dosing safety evaluations. |
| **Triage & SBAR** | `/api/v1/symptoms/*`<br>`/api/v1/triage/*`<br>`/api/v1/sbar/*` | Patient symptom intake, deterministic triage assessment, and structured SBAR. |
| **Care Plans & Discharge** | `/api/v1/discharge/*`<br>`/api/v1/care-plans/*` | Discharge summary extractions, personalized care plans, and goal tracking. |
| **Clinician Workflow** | `/api/v1/clinical-workflow/*` | Clinician workspace, encounters, versioned notes, clinical orders, and signing. |
| **Organizations** | `/api/v1/organizations/*` | Healthcare networks, participating hospitals, and health systems. |
| **Facilities & Departments** | `/api/v1/facilities/*`<br>`/api/v1/departments/*` | Facility capability discovery, departmental bed/equipment capacity tracking. |
| **Transfers** | `/api/v1/transfers/*` | Two-sided transfer coordination, referral reviews, bed acceptance workflows. |
| **Interoperability** | `/api/v1/interoperability/*` | ABDM / FHIR R4 clinical artifact export/import with full data provenance. |
| **AI Intelligence** | `/api/v1/ai/*` | Non-authoritative clinical summarization, draft generation, and usage tracking. |
| **Observability** | `/api/v1/metrics` | Prometheus exposition format metrics and runtime performance telemetry. |

---

## 4. API Deprecation Policy (Section 13)

When an endpoint, query parameter, or response field is scheduled for retirement, the following 6-step procedure is mandatory:

```
[ IDENTIFY REPLACEMENT ] ──> [ OPENAPI DEPRECATION ] ──> [ CLIENT NOTIFICATION ] ──> [ USAGE MONITORING ] ──> [ RETIREMENT RELEASE ]
```

1. **OpenAPI Flagging**: Mark the endpoint with `deprecated: true` in the FastAPI route decorator.
2. **Replacement Documentation**: Add `Deprecated-By` and `Link` headers pointing to the replacement endpoint in HTTP responses.
3. **Usage Monitoring**: Track traffic to the deprecated endpoint using Prometheus metric `http_requests_total{route="/deprecated/..."}`.
4. **Communication & SLA**: Issue written deprecation notice to API consumers with a minimum **90-day** transition window.
5. **Compatibility Maintenance**: Maintain bug fixes and compatibility throughout the deprecation window.
6. **Controlled Removal**: Remove the deprecated route only during a scheduled MAJOR or MINOR release.

---

## 5. Request Headers & Operational Standards

- **`X-Request-ID`**: Every client request SHOULD supply a unique correlation ID matching `^[a-zA-Z0-9\-_]{8,64}$`. If omitted, the backend generates a UUIDv4 and returns it in the response header.
- **`Authorization`**: Authenticated routes require `Bearer <JWT_ACCESS_TOKEN>`.
- **`Idempotency-Key`**: High-consequence mutations (e.g. transfer requests, clinical orders, care plan generation) support an `Idempotency-Key` header to prevent duplicate execution during network retries.
- **Rate Limiting**: Enforced via sliding-window rate limiters per IP / Authenticated User ID. Standard limits return `429 Too Many Requests` with a `Retry-After` header.
