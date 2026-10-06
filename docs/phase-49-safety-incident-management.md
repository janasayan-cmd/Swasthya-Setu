# Phase 49: Clinical Safety Incident Management & Database Team Contract

## Document Type
Technical Architecture & Database Handoff Contract

## Phase Overview
Phase 49 establishes the backend capability to detect, record, investigate, contain, and track clinically relevant safety incidents and safety-related operational failures. It connects decision traceability (Phase 47) and runtime safety controls (Phase 48) into a governed safety-incident lifecycle.

---

## 1. Core Principles & Governance Rules
1. **INCIDENT ≠ ERROR**: An incident records an unexpected or risky condition; not every incident is an error.
2. **ERROR ≠ CLINICAL HARM**: An error does not automatically constitute patient harm.
3. **SAFETY SIGNAL ≠ CONFIRMED INCIDENT**: Signals are lightweight event notifications that undergo correlation and triage before becoming confirmed incidents.
4. **BLOCKED ACTION ≠ SUCCESSFUL ACTION**: A safety gate blocking an unsafe action prevents execution; it is recorded as a safety signal/near miss without claiming clinical harm.
5. **ROOT-CAUSE HYPOTHESIS ≠ FACT**: Hypotheses remain proposed until confirmed through authorized clinical/investigative review.
6. **AI AUTHORITY PROHIBITION**: AI models/agents may draft timelines and suggest candidate root causes, but AI CANNOT autonomously:
   - Confirm root causes
   - Confirm patient harm
   - Close safety incidents
   - Assign legal blame or liability
7. **TEMPORAL INTEGRITY**: Preserves distinct timestamps (`occurred_at`, `detected_at`, `recorded_at`, `contained_at`, `resolved_at`, `closed_at`, `reopened_at`).
8. **CLINICAL RECORD IMMUTABILITY**: Safety incident investigation never alters historical clinical records directly; corrections must route via Phase 46 versioning.

---

## 2. API Endpoints
All endpoints follow the Phase 23 standard response format `StandardSuccessResponse[T]`.

- `POST /api/v1/incidents/signals`: Ingest runtime safety signal from safety gates, workflows, external providers, or clinicians.
- `POST /api/v1/incidents`: Directly register a clinical safety incident candidate.
- `GET /api/v1/incidents`: Filter and list safety incidents by status, incident type, or patient ID.
- `GET /api/v1/incidents/{incident_id}`: Retrieve full safety incident details.
- `GET /api/v1/incidents/{incident_id}/timeline`: Reconstructed factual chronological timeline.
- `GET /api/v1/incidents/{incident_id}/evidence`: List attached evidence references (pointers only, PHI excluded).
- `POST /api/v1/incidents/{incident_id}/evidence`: Attach foreign evidence reference (decision trace ID, audit event, etc.).
- `GET /api/v1/incidents/{incident_id}/investigation`: Retrieve consolidated investigation state.
- `POST /api/v1/incidents/{incident_id}/triage`: Perform clinical/safety officer triage (assessing severity and containment requirement).
- `POST /api/v1/incidents/{incident_id}/assign`: Assign lead human safety investigator (AI roles prohibited).
- `POST /api/v1/incidents/{incident_id}/contain`: Execute and record active risk containment (e.g. disabling provider, pausing workflow).
- `POST /api/v1/incidents/{incident_id}/hypotheses`: Propose root-cause hypothesis (starts in `PROPOSED` status).
- `PATCH /api/v1/incidents/hypotheses/{hypothesis_id}`: Update hypothesis status (`SUPPORTED`, `REJECTED`, `CONFIRMED`).
- `GET /api/v1/incidents/{incident_id}/corrective-actions`: List remediation and preventive actions.
- `POST /api/v1/incidents/{incident_id}/corrective-actions`: Create remediation action.
- `PATCH /api/v1/incidents/corrective-actions/{action_id}`: Advance action status (`IN_PROGRESS`, `COMPLETED`, `VERIFIED`).
- `POST /api/v1/incidents/{incident_id}/resolve`: Mark incident resolved with remediation summary.
- `POST /api/v1/incidents/{incident_id}/close`: Validate prerequisites (containment & corrective actions) and formally close.
- `POST /api/v1/incidents/{incident_id}/reopen`: Reopen resolved/closed incident upon recurrence or new findings.
- `GET /api/v1/patients/{patient_id}/incidents`: Retrieve safety incidents scoped to a specific patient.
