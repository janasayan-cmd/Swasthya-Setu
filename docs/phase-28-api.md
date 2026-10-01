# HealthSetu Phase 28: API Specification & Contracts

## 1. Authentication & Base URL
All requests require standard Bearer token authorization:
`Authorization: Bearer <access_token>`

Base path: `/api/v1`

---

## 2. Admin Analytics Endpoints (`/api/v1/admin/analytics/`)
*Requires permission: `admin:analytics_view`*

### `GET /admin/analytics/overview`
Returns platform-wide request volumes, overall error rate, latency percentiles, top route templates, and active anomalies.

**Query Parameters:**
- `start_time` (ISO 8601)
- `end_time` (ISO 8601)
- `environment` (e.g. `production`, `staging`)
- `endpoint` (route template pattern)

### `GET /admin/analytics/api-usage`
Returns detailed endpoint breakdown, status code distribution, time-bucketed points, and rate-limit triggers.

### `GET /admin/analytics/errors`
Returns error volume, 4xx client errors, 5xx server errors, error categories, and top failing route templates.

### `GET /admin/analytics/latency`
Returns latency sample count, min, max, avg, p50, p90, p95, p99 percentiles, and distribution buckets (`<50ms` through `>5s`).

### `GET /admin/analytics/jobs`
Returns background worker job throughput, completion counts, failure counts, retries, cancellations, and processing durations.

### `GET /admin/analytics/providers`
Returns telemetry on external integrations (OCR, Gemini AI, RxNorm, FHIR), uptime percentages, timeouts, failures, and costs.

### `GET /admin/analytics/features`
Returns platform feature invocation frequency, success rates, failure rates, and execution durations.

### `GET /admin/analytics/anomalies`
Lists detected operational usage anomalies.

### `POST /admin/analytics/anomalies/{anomaly_id}/acknowledge`
Acknowledges an operational anomaly.
**Payload:**
```json
{
  "notes": "Investigating upstream connectivity"
}
```

### `POST /admin/analytics/anomalies/{anomaly_id}/resolve`
Resolves an operational anomaly.
**Payload:**
```json
{
  "resolution_notes": "Database connection pool restarted and verified healthy."
}
```

### `GET /admin/analytics/costs`
Returns resource consumption and expenditure breakdown across AI tokens, OCR pages, safety evaluations, and compute.

---

## 3. Scoped Tenant Analytics Endpoints

### `GET /organizations/{organization_id}/analytics`
*Requires permission: `organization:analytics_view`*
Scoped operational telemetry for the caller's organization.

### `GET /facilities/{facility_id}/analytics`
*Requires permission: `facility:analytics_view`*
Scoped operational telemetry for the caller's facility.
