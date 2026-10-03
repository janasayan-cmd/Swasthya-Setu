# HealthSetu — Phase 35: Alert REST API Reference

## 1. Alert Ingestion API
- `POST /api/v1/alerts/ingest`: Ingest domain event to evaluate alert creation rules. Returns 201 with `AlertRecord` if created, or existing record if duplicate idempotency key is matched.
  - Authorized Roles: `DOCTOR`, `CLINICIAN`, `ADMIN`, `SYSTEM_ADMIN`.

## 2. Alert Query & Listing APIs
- `GET /api/v1/alerts`: List alerts with filtering by `status`, `severity`, `category`, `patient_id`, `requires_acknowledgement`, and date ranges. Enforces caller relationship and tenant scoping.
- `GET /api/v1/alerts/{alert_id}`: Retrieve full alert details including recipients, provenance, and escalation status.
- `GET /api/v1/alerts/{alert_id}/history`: Retrieve complete audit ledger of all status transitions, acknowledgements, resolutions, and escalations.

## 3. Clinician Inbox APIs
- `GET /api/v1/clinicians/me/alerts`: Retrieve inbox of active alerts targeted to the authenticated clinician or their clinical care teams.
  - Supports filtering by `status`, `severity`, `category`, and `requires_acknowledgement`.

## 4. Patient Alert APIs
- `GET /api/v1/patients/{patient_id}/alerts`: Retrieve alerts for a specific patient.
  - Patients can only query their own `patient_id` (BOLA/IDOR protected).
  - Alert titles and summaries are automatically sanitized to remove panic/alarmist language.

## 5. Alert Lifecycle Workflow APIs
- `POST /api/v1/alerts/{alert_id}/acknowledge`: Formally acknowledge an alert.
  - Body: `{"note": "optional acknowledgement note"}`
  - Stops escalation timers and records clinician identifier and timestamp.
  - Cannot be re-acknowledged if already acknowledged or resolved.
- `POST /api/v1/alerts/{alert_id}/resolve`: Formally resolve an alert.
  - Body: `{"reason": "mandatory explanation of clinical or operational resolution"}`
  - Transitions alert to `RESOLVED`, halts all further escalation.
- `POST /api/v1/alerts/{alert_id}/dismiss`: Dismiss an alert deemed non-actionable or informational.
  - Body: `{"reason": "mandatory dismissal justification"}`
  - Critical alerts requiring acknowledgement cannot be dismissed without resolution.

## 6. Escalation APIs
- `POST /api/v1/alerts/{alert_id}/escalate`: Manually or automatically evaluate and advance alert escalation to next tier.
  - Query parameter `force=true` bypasses timer threshold for authorized clinical supervisors.
  - Escalates: Tier 0 (Clinician) -> Tier 1 (Care Team) -> Tier 2 (Facility Lead) -> Tier 3 (Org Safety Officer).

## 7. Administrative APIs
- `GET /api/v1/admin/alerts`: System-wide paginated alert overview across all facilities and organizations.
  - Authorized Roles: `ADMIN`, `SYSTEM_ADMIN`, `OPERATIONS_ADMIN`.
- `GET /api/v1/admin/alerts/policies`: Inspect registered alert policies, version numbers, matching criteria, severity assignments, and escalation timeouts.
  - Authorized Roles: `ADMIN`, `SYSTEM_ADMIN`, `OPERATIONS_ADMIN`.
