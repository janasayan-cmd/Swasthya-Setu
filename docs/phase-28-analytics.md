# HealthSetu Phase 28: API Analytics, Usage Governance & Operational Intelligence

## 1. Overview & Architectural Boundaries

Phase 28 establishes a secure, non-blocking, privacy-safe backend operational analytics and usage governance layer for HealthSetu. It enables deep operational visibility into API consumption, response latency percentiles, error status distributions, platform capability invocation, external provider availability, background worker throughput, resource expenditure, and anomaly detection.

### Non-Negotiable Invariants

| Principle | Meaning & Enforcement |
|:---|:---|
| **ANALYTICS != CLINICAL DECISION** | Telemetry describes technical consumption, never patient risk, diagnosis, or triage. |
| **USAGE DATA != CLINICAL DATA** | Zero clinical narratives, notes, prescriptions, or allergies are stored in telemetry. |
| **METRICS != AUDIT RECORDS** | Statistical aggregates never replace legally required Phase 15 immutable audit logs. |
| **ANALYTICS != PATIENT PROFILING** | Operational patterns must never be aggregated into individual patient profiles. |
| **OPERATIONAL DATA != CLINICAL TRUTH** | Service metrics reflect network and server operations, not clinical evidence. |
| **USAGE SPIKE != SECURITY INCIDENT** | Surges in traffic are evaluated as operational capacity events, not hostile attacks. |
| **ANOMALY != MALICIOUS ACTIVITY** | Detected variances are tagged `ANOMALY_DETECTED`, never `SECURITY_ATTACK`. |
| **STATISTICAL SIGNAL != CLINICAL SIGNAL** | Aggregated request volume cannot inform medical triage or physician workflow. |
| **FAILED JOB != COMPLETED JOB** | Worker retries or unhandled exceptions cannot be classified as successful tasks. |
| **QUEUED JOB != COMPLETED JOB** | Enqueued background messages cannot be tallied as completed transactions. |
| **PROVIDER FAILURE != SUCCESS** | Integration timeouts or 5xx responses cannot be treated as healthy operations. |
| **FAIL-SAFE ISOLATION** | Analytics recording failure must NEVER abort or crash clinical operations. |

---

## 2. Event Model & Data Minimization

Operational telemetry events are strictly decoupled from patient health records.

### Route Template Normalization
Endpoints are parameterized with route templates:
- `/api/v1/patients/12345/medications` $\rightarrow$ `/api/v1/patients/{patient_id}/medications`
- `/api/v1/facilities/fac-999/analytics` $\rightarrow$ `/api/v1/facilities/{facility_id}/analytics`
- `/api/v1/jobs/550e8400-e29b-41d4-a716-446655440000/status` $\rightarrow$ `/api/v1/jobs/{job_id}/status`

**Under no circumstances is a raw patient ID stored as an analytics dimension.**

### Data Minimization & Sanitization
All event metadata is sanitized prior to storage. Keys matching `password`, `secret`, `api_key`, `token`, `clinical_notes`, `prescription_text`, `allergy_description`, `triage_narrative`, `phi`, or `diagnosis` are discarded. Permitted operational keys include `prompt_tokens`, `completion_tokens`, `total_tokens`, `pages_processed`, `estimated_cost_usd`, `client_version`, `duration_sec`, and `cached`.

---

## 3. High-Resolution Percentiles & Latency Buckets

Latency telemetry computes exact percentiles:
- **Min / Max / Avg Latency**
- **p50 (Median)**: Standard latency experienced by typical transactions
- **p90**: 90th percentile response threshold
- **p95**: Tail latency benchmark for SLO compliance
- **p99**: Extreme outlier latency threshold

### Distribution Buckets
1. `<50ms` (Instant / Cached)
2. `50ms-200ms` (Optimal Interactive)
3. `200ms-500ms` (Acceptable Standard)
4. `500ms-1s` (Heavy Processing)
5. `1s-5s` (Complex Aggregation / High Compute)
6. `>5s` (Degraded / Slow Request Warning)

---

## 4. Multi-Tenant Scoping & Access Control

Operational analytics enforces multi-tenant boundaries:
- **System Admins (`SYSTEM_ADMIN`, `ADMIN`, `OPERATIONS_ADMIN`)**: Possess cross-tenant platform visibility.
- **Support Operators (`SUPPORT_OPERATOR`)**: Hold read-only access to operational overview and error dashboards for debugging.
- **Clinicians / Facility Admins (`DOCTOR`)**: Scoped strictly to their assigned `organization_id` or `facility_id`. Attempts to access metrics of another organization result in `HTTP 403 Forbidden` (`ANALYTICS_ACCESS_DENIED`).
