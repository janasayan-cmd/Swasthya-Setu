# Phase 27: Administrative & Support Operations API Specification

## 1. Base URL
All endpoints in this specification are mounted under the dedicated administrative prefix:
`/api/v1/admin`

All requests require HTTP Bearer authentication and valid administrative role authorization.

---

## 2. API Endpoints Catalog

### System Status & Health
| Method | Path | Summary | Required Permission |
|---|---|---|---|
| `GET` | `/system/status` | Composite dependency availability overview | `admin:system_view` |
| `GET` | `/system/health` | Deep operational diagnostics and backlog | `admin:system_view` |
| `GET` | `/system/readiness` | High-availability readiness probe | `admin:system_view` |

### Background Job Management
| Method | Path | Summary | Required Permission |
|---|---|---|---|
| `GET` | `/jobs` | Paginated list of background tasks | `admin:jobs_view` |
| `GET` | `/jobs/{job_id}` | Detailed job execution telemetry | `admin:jobs_view` |
| `POST` | `/jobs/{job_id}/retry` | Idempotent retry of eligible failed job | `admin:jobs_manage` |
| `POST` | `/jobs/{job_id}/cancel` | Safe cancellation of queued job | `admin:jobs_manage` |

### External Integration Monitoring
| Method | Path | Summary | Required Permission |
|---|---|---|---|
| `GET` | `/integrations` | Registry of configured external providers | `admin:integrations_view` |
| `GET` | `/integrations/{name}` | Specific provider connectivity and telemetry | `admin:integrations_view` |
| `POST` | `/integrations/{name}/test` | Controlled synthetic non-PHI ping | `admin:integrations_view` |

### Operational Incident Management
| Method | Path | Summary | Required Permission |
|---|---|---|---|
| `GET` | `/incidents` | Query operational incidents with filters | `admin:incidents_view` |
| `POST` | `/incidents` | Declare new operational incident | `admin:incidents_manage` |
| `GET` | `/incidents/{id}` | Inspect full incident report and history | `admin:incidents_view` |
| `POST` | `/incidents/{id}/acknowledge` | Acknowledge incident (OPEN -> INVESTIGATING) | `admin:incidents_manage` |
| `POST` | `/incidents/{id}/update` | Update incident triage notes and severity | `admin:incidents_manage` |
| `POST` | `/incidents/{id}/resolve` | Resolve or close incident with summary | `admin:incidents_manage` |

### Audit & Security Telemetry
| Method | Path | Summary | Required Permission |
|---|---|---|---|
| `GET` | `/audit` | Query immutable administrative audit trail | `admin:audit_view` |
| `GET` | `/security-events` | Query sanitized security audit events | `admin:security_view` |

### Governance & Support
| Method | Path | Summary | Required Permission |
|---|---|---|---|
| `GET` | `/data-quality` | Aggregate clinical data-quality metrics | `admin:system_view` |
| `GET` | `/configuration` | Operational configuration and flags overview | `admin:configuration_view` |
| `GET` | `/support/patients/search` | Privacy-safe patient account discovery | `admin:support_view` |

---

## 3. Response Format Standards

### Success Response
```json
{
  "success": true,
  "data": { ... },
  "request_id": "req-20261002-abc123"
}
```

### Error Response
```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Safe human-readable explanation.",
    "request_id": "req-20261002-abc123",
    "details": null
  }
}
```

---

## 4. Error Codes

| Code | HTTP Status | Description |
|---|---|---|
| `ADMIN_ACCESS_DENIED` | 403 | Caller has no administrative role (e.g. Doctor, Patient) |
| `ADMIN_PERMISSION_REQUIRED` | 403 | Caller lacks specific capability permission |
| `ADMIN_RESOURCE_NOT_FOUND` | 404 | Target admin resource not found |
| `ADMIN_ACTION_NOT_ALLOWED` | 400 | Operational action violates safety invariants |
| `JOB_RETRY_NOT_ALLOWED` | 400 | Retrying completed or processing job forbidden |
| `JOB_CANCEL_NOT_ALLOWED` | 400 | Cancelling terminal job forbidden |
| `INTEGRATION_NOT_FOUND` | 404 | Provider not recognized in registry |
| `INTEGRATION_TEST_NOT_ALLOWED` | 403 | Provider testing disabled by config |
| `INCIDENT_NOT_FOUND` | 404 | Incident ID does not exist |
| `INCIDENT_INVALID_STATE` | 400 | Invalid state transition (e.g., modifying closed incident) |
| `SUPPORT_LOOKUP_NOT_ALLOWED` | 403 | Support query violates privacy policy |
