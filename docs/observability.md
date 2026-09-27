# HealthSetu — Production Observability Architecture (Phase 18)

## 1. Overview & Architecture

HealthSetu implements three synchronized telemetry pillars for production visibility:
1. **Structured Logging (JSON)**: Operational log events with contextual `request_id`.
2. **Metrics Instrumentation**: Prometheus & JSON operational counters, gauges, and percentile latency timers.
3. **Request Tracing**: Correlation across API gateways, service boundaries, repositories, and external providers.

```
                    INTERNET
                       |
                       v
              healthsetu.com (Frontend)
                       |
                       | HTTPS
                       v
              api.healthsetu.com (Ingress)
                       |
                       v
                FASTAPI BACKEND
                       |
        ┌──────────────┼───────────────┐
        |              |               |
        v              v               v
   STRUCTURED        BOUNDED        CORRELATED
   JSON LOGS         METRICS          TRACES
  (app/core/logging) (app/core/metrics) (X-Request-ID)
        |              |               |
        └──────────────┼───────────────┘
                       |
                       v
       OPERATIONAL OBSERVABILITY PLATFORM
            (Dashboards & Alerting)
```

---

## 2. Separation of Telemetry vs. Clinical Audit

| Dimension | Operational Telemetry (Phase 18) | Clinical Audit Trail (Phase 15) |
| :--- | :--- | :--- |
| **Core Question** | *"Is the application healthy, performant, and available?"* | *"Who accessed or altered protected clinical records?"* |
| **Storage Destination** | Ephemeral logs (stdout), metrics registry, Prometheus `/metrics` | Dedicated, immutable audit table in PostgreSQL |
| **Failure Mode** | Best-effort; telemetry loss does not block clinical care | Fail-closed; clinical mutations fail if audit fails |
| **PHI Allowance** | **ZERO PHI** allowed under any circumstance | Authorized actor and patient reference IDs recorded |

---

## 3. Request Correlation (`X-Request-ID`)

* Inbound requests with an `X-Request-ID` header (matching `^[a-zA-Z0-9\-_]{8,64}$`) are preserved.
* Missing or invalid headers trigger generation of a new UUIDv4.
* The `request_id` is propagated:
  * In the response header `X-Request-ID`
  * In the async ContextVar `request_id_ctx_var`
  * In all structured JSON log records
  * In standard error envelopes (`StandardErrorResponse.error.request_id`)

---

## 4. Centralized PHI Log Sanitization

Centralized log sanitization in `app/core/log_sanitizer.py` executes before any log record is emitted:
* **Credential Redaction**: `password`, `token`, `access_token`, `refresh_token`, `api_key`, `secret`, `database_url`.
* **Identity Redaction**: `patient_name`, `first_name`, `last_name`, `address`, `phone`, `email`, `ssn`, `dob`.
* **Clinical Content Redaction**: `diagnosis`, `prescription`, `medication`, `allergy`, `symptoms`, `clinical_notes`, `document_content`, `ocr_output`, `ai_prompt`, `ai_response`.
* **Value-Pattern Matching**: Automatically scrubs JWT tokens, Bearer tokens, and regex patterns for credentials.

---

## 5. Metrics Specification & Exposition

Application metrics are exposed via:
* **Prometheus Text Format**: `GET /api/v1/metrics` or root `/metrics`
* **Structured JSON Summary**: `GET /api/v1/metrics?format=json`

### Core Metrics Table
| Metric Name | Type | Labels / Cardinality | Description |
| :--- | :--- | :--- | :--- |
| `http_requests_total` | Counter | `method`, `route`, `status_code` | Total processed HTTP requests |
| `http_requests_in_progress` | Gauge | None | Number of concurrent active requests |
| `http_4xx_total` | Counter | None | Total HTTP 4xx client errors |
| `http_5xx_total` | Counter | None | Total HTTP 5xx server errors |
| `authentication_failures_total` | Counter | None | Failed login and authentication attempts |
| `authorization_denials_total` | Counter | None | Access denials (permission or consent) |
| `database_errors_total` | Counter | None | DB connection or query execution errors |
| `external_provider_errors_total` | Counter | `provider` | Errors communicating with external services |
| `background_job_failures_total` | Counter | `job_type` | Failed asynchronous jobs |

*Cardinality Protection*: Dynamic path parameters (e.g. `/patients/pat-001/medications`) are normalized to route templates (`/patients/{patient_id}/medications`).

---

## 6. Slow Request Detection

Configured via `SLOW_REQUEST_THRESHOLD_MS` (default: 2000ms):
* When request latency $\ge 2000\text{ms}$, the middleware emits a structured `WARNING` log:
  ```json
  {
    "level": "WARNING",
    "message": "SLOW REQUEST: GET /api/v1/patients/{patient_id}/care-plans took 2450ms (threshold: 2000ms)",
    "request_id": "...",
    "duration_ms": 2450.0,
    "version": "0.1.0"
  }
  ```
