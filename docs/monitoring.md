# HealthSetu Production Monitoring Architecture

## 1. Overview & Objectives

The HealthSetu monitoring architecture provides real-time visibility into the operational state of the deployed backend services on Railway, backing PostgreSQL on Supabase, and integrated external providers (OCR, Medication Safety, AI, Interoperability).

This operational monitoring layer ensures that failures, latencies, and service degradations are detected proactively before impacting clinical workflows or patient care delivery, while strictly preserving patient privacy (PHI minimization) and clinical safety boundaries.

---

## 2. Health & Readiness Probes

HealthSetu exposes two decoupled probes at the root and `/api/v1` routes:

### 2.1 Application Health Probe (`GET /api/v1/health` and `GET /health`)
- **Purpose**: Liveness probe to verify that the FastAPI ASGI container is running, accepting connections, and able to process HTTP requests.
- **Dependency Isolation**: Does **NOT** execute network calls to PostgreSQL or external providers.
- **Response Format**:
  ```json
  {
    "status": "healthy",
    "version": "0.1.0",
    "service": "healthsetu-backend",
    "environment": "production"
  }
  ```
- **Probe Interval**: Every 10–15 seconds (Railway Healthcheck).
- **Failure Condition**: HTTP 5xx or connection timeout $\implies$ Container restarted or rescheduled.

### 2.2 Dependency Readiness Probe (`GET /api/v1/ready` and `GET /ready`)
- **Purpose**: Readiness probe to verify that downstream dependencies required for core transactional workflows (specifically PostgreSQL) are reachable and accepting connections.
- **Behavior**: Executes `SELECT 1` against the configured Supabase PostgreSQL connection pool with a strict 3-second timeout.
- **Response Format (Normal)**:
  ```json
  {
    "status": "ready",
    "database": "connected",
    "version": "0.1.0",
    "service": "healthsetu-backend"
  }
  ```
- **Response Format (Database Unavailable)**: Status Code: **503 Service Unavailable**
  ```json
  {
    "status": "unhealthy",
    "database": "disconnected",
    "error": "connection timeout or pool exhaustion"
  }
  ```
- **Critical Invariant**:
  $$\text{Application Available} \wedge \text{Database Unavailable} \implies \text{Health: OK}, \text{Readiness: NOT READY (503)}$$
  The monitoring system will **never** report system healthy when database connectivity has failed.

---

## 3. Metrics Architecture & Prometheus Integration

HealthSetu utilizes a bounded-cardinality in-memory metrics engine exposed via:
- `GET /metrics` (Prometheus text exposition format)
- `GET /api/v1/metrics?format=prometheus`
- `GET /api/v1/metrics?format=json` (structured JSON dashboard summary)

### 3.1 Bounded Cardinality Invariant
To prevent memory exhaustion and telemetry storage cost explosion:
- **No PHI or Entity IDs in Labels**: Labels **never** contain `patient_id`, `user_id`, or `request_id`.
- **Route Normalization**: All dynamic route paths are automatically normalized to route templates before metric aggregation:
  - `/api/v1/patients/pat-999/medications` $\longrightarrow$ `/api/v1/patients/{patient_id}/medications`
  - `/api/v1/prescriptions/rx-12345` $\longrightarrow$ `/api/v1/prescriptions/{id}`

### 3.2 Core Metrics Catalog

| Metric Name | Type | Labels | Description |
| :--- | :--- | :--- | :--- |
| `healthsetu_http_requests_total` | Counter | `method`, `route`, `status_code` | Total HTTP requests handled |
| `healthsetu_http_requests_in_progress` | Gauge | — | Concurrently active HTTP requests |
| `healthsetu_http_request_duration_seconds` | Summary | `method`, `route` | Latency distribution (p50, p95, p99) |
| `healthsetu_http_errors_total` | Counter | `status_class` (`4xx`, `5xx`) | Aggregated client and server errors |
| `healthsetu_database_errors_total` | Counter | `operation` | Database connection & query failures |
| `healthsetu_auth_failures_total` | Counter | `failure_type` | Authentication & token rejection events |
| `healthsetu_authz_denials_total` | Counter | `resource` | RBAC & permission access denials |
| `healthsetu_provider_requests_total` | Counter | `provider`, `status` | External provider invocation count |
| `healthsetu_provider_latency_seconds` | Summary | `provider` | External provider call duration |
| `healthsetu_background_jobs_total` | Counter | `job_name`, `status` | Async background job lifecycles |

---

## 4. External Provider Monitoring

HealthSetu tracks the operational health and error rates of each external integration independently:

1. **OCR Provider (`ocr`)**:
   - Monitored: Latency, extraction failures, document processing duration, timeouts.
   - Safety Rule: OCR failures trigger configured retry policies; never fabricate clinical text or auto-verify extractions.
2. **Medication Safety Provider (`medication_safety`)**:
   - Monitored: Interaction check latency, provider timeouts, network errors.
   - Safety Invariant: Provider failure **never** equals `CLEAR`. If the provider is unreachable, result is strictly set to `UNKNOWN` or `ERROR`.
3. **AI Consultation / SBAR Provider (`ai`)**:
   - Monitored: Model latency, token usage metadata, rate-limit (429) events, validation failures.
   - Boundary: Telemetry tracks performance metrics only; raw clinical prompts and patient responses are never logged in telemetry.
4. **Interoperability Provider (`interoperability`)**:
   - Monitored: FHIR/HL7 message export/import latency, validation errors, remote gateway timeouts.

---

## 5. Performance & Slow Request Detection

- **Slow Request Threshold**: Configured via `SLOW_REQUEST_THRESHOLD_MS` (default: 2000 ms).
- **Detection Mechanism**: Monitored in ASGI middleware (`RequestMetricsMiddleware`).
- **Telemetry Emission**: When any request exceeds the threshold, a structured `WARNING` log is emitted containing:
  - `route` (normalized template)
  - `method`
  - `duration_ms`
  - `request_id`
  - `version`
- **Latency Percentiles**: Tracked in `http_request_duration_seconds` providing `p50`, `p95`, and `p99` percentiles for every route class.

---

## 6. Railway Container Resource Monitoring

Thresholds for container alerting on Railway:

| Resource | Warning Threshold | Critical Alert Threshold | Action Required |
| :--- | :--- | :--- | :--- |
| **CPU Utilization** | > 75% for 5 mins | > 90% for 2 mins | Check for runaway background processing or scale replicas |
| **Memory (RAM)** | > 70% | > 85% | Inspect memory leaks; restart container if approaching OOM |
| **Container Restarts**| $\ge 2$ in 10 mins | $\ge 5$ in 15 mins | Immediate incident declaration; inspect crash logs |
| **HTTP 5xx Rate** | > 1% of total requests | > 5% of total requests | Follow `docs/runbooks/high-5xx.md` |
| **DB Connection Pool**| > 80% pool utilized | Pool exhaustion / timeouts | Scale connection pool or resolve connection leaks |

---

## 7. Dashboards

### 7.1 Primary Operational Dashboard
Contains high-level health indicators for 24/7 SRE monitoring:
- Service Health (`/api/v1/health`) & Readiness (`/api/v1/ready`)
- Request Rate (RPS) & Error Rates (HTTP 4xx / 5xx)
- Latency percentiles ($p50$, $p95$, $p99$)
- Container CPU, Memory, and Restart counts
- Active application version (`APP_VERSION`)

### 7.2 Critical Clinical Services Dashboard
Focused strictly on backend dependencies that impact clinical delivery:
- Medication Safety Provider availability & error rate
- Document OCR processing backlog & queue depth
- AI service latency and rate-limit counters
- Supabase PostgreSQL latency & active connection count
