# Phase 27: Administration, Support Operations & Controlled Backoffice

## 1. Overview & Architectural Principles

Phase 27 establishes a dedicated, secure backend administration and support-operations layer for the HealthSetu platform.

Internal operators, system administrators, security engineers, and support personnel require tools to inspect system health, track job executions, review integration statuses, declare and triage operational incidents, and perform privacy-safe troubleshooting without violating clinical boundaries or exposing protected health information (PHI).

### Core Invariants

```
ADMIN ACCESS != CLINICAL AUTHORITY
SUPPORT ACCESS != UNLIMITED DATA ACCESS
ADMIN ACTION != CLINICAL DECISION
DEBUGGING != DIRECT DATABASE MODIFICATION
OPERATIONAL OVERRIDE != CLINICAL OVERRIDE
SYSTEM ACCESS != PATIENT DATA ACCESS
JOB RETRY != DUPLICATE CLINICAL ACTION
PROVIDER FAILURE != CLEAR / SUCCESS
CONFIGURATION CHANGE != CLINICAL DATA REWRITE
AUDIT ACCESS != AUDIT MODIFICATION
```

The administrative layer is strictly segregated from ordinary patient, doctor, and hospital portal APIs.

---

## 2. Architecture & Request Pipeline

```
Admin Client
    ↓ HTTPS
Security Middleware (Headers, Payload Size, Rate Limiting)
    ↓
Authentication (JWT Verification & Account State)
    ↓
Admin Authorization (_require_admin_permission & Capability Policy)
    ↓
Admin Service (Inspection, Telemetry, Safety Invariants)
    ↓
Existing Domain Services / Repositories (Jobs, Incidents, Audit, Config)
    ↓
Audit Logging (Append-Only Event Emission)
```

For asynchronous administrative actions:
```
Admin API (/api/v1/admin/...)
    ↓
Admin Service
    ↓
Job Orchestrator (Phase 22 Queue)
    ↓
Idempotent Worker Execution
    ↓
Domain Service & Audit Emission
```

---

## 3. Dedicated Namespace

All administrative and operational endpoints are housed under:
`/api/v1/admin/`

No clinical modification routes exist in this namespace. Generic database endpoints (such as `POST /admin/database/update`, `POST /admin/patient/modify-any-field`, or raw SQL execution) are strictly prohibited and do not exist.

---

## 4. System Status & Health Probes

Administrative operators inspect operational telemetry across all internal and external dependencies:
- **API**: FastAPI HTTP Gateway
- **Database**: PostgreSQL connection health and pool metrics
- **Background Workers**: Async job queue depth and concurrency
- **Object Storage**: Encrypted document storage mount
- **OCR Provider**: Dual-engine pipeline status (Gemini + ClearScript)
- **Medication Terminology**: Local registry and RxNorm integration
- **Medication Safety**: Rule engine for DDIs and allergy contraindications
- **AI Provider**: Multimodal clinical reasoning engine (Gemini Flash)
- **Interoperability**: FHIR R4 and HL7 2.5 bundle exchange status
- **Geolocation**: Haversine distance and OSM provider

Operational statuses are strictly classified:
- `AVAILABLE`
- `DEGRADED`
- `UNAVAILABLE`
- `DISABLED`
- `NOT_CONFIGURED`
- `UNKNOWN`

**Safety Rule**: A disabled dependency (`DISABLED`) or failing provider (`UNAVAILABLE`) is never masked as healthy or successful.

---

## 5. Background Job Governance & Retry Safety

Admin operators manage asynchronous background tasks through `/api/v1/admin/jobs`:
- List jobs with pagination, status, and job-type filtering
- Inspect job execution parameters without raw clinical payloads
- Idempotently retry failed jobs
- Cancel pending or queued jobs

### Retry Safety Rules:
1. **COMPLETED Jobs**: Retrying a completed job is strictly forbidden (HTTP 400 `JOB_RETRY_NOT_ALLOWED`). This prevents duplicate clinical actions, duplicate transfers, or duplicate medication events.
2. **PROCESSING Jobs**: Retrying a job currently in flight is forbidden to avoid race conditions.
3. **CANCELLED Jobs**: Explicitly cancelled jobs cannot be retried without manual intervention.
4. **Retry Limit**: If `attempt >= max_retries`, automated retry is blocked (manual escalation required).

---

## 6. External Provider Telemetry & Testing

Monitors status, version, last success timestamp, and error category for external providers.

Controlled connectivity testing (`POST /api/v1/admin/integrations/{name}/test`):
- Disabled by default via `ADMIN_PROVIDER_TESTING_ENABLED=False` (HTTP 403 `INTEGRATION_TEST_NOT_ALLOWED`).
- When enabled, executes synthetic non-PHI probes with strict timeouts.
- Never sends real patient data.
- Never produces false clinical success states.
- Never exposes secrets, passwords, or API keys in response payloads or logs.
