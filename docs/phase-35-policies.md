# HealthSetu — Phase 35: Alert Policy Engine & Deduplication

## 1. Overview
The Alert Policy Engine evaluates events emitted across HealthSetu subsystems and determines whether an alert is required, its category, authoritative severity, acknowledgement obligations, escalation paths, and deduplication behavior.

Policies are declarative, version-controlled, and stored in repository state. Policies strictly prevent AI models from inventing severity levels.

---

## 2. Built-in Alert Policies

| Policy ID | Event Type | Category | Severity | Escalation | Timeout |
|---|---|---|---|---|---|
| `POLICY_CRITICAL_DIAGNOSTIC_RESULT` | `CRITICAL_DIAGNOSTIC_RESULT_AVAILABLE` | `DIAGNOSTIC_RESULT_ALERT` | `CRITICAL` | True | 15 min |
| `POLICY_MEDICATION_SAFETY_REVIEW` | `MEDICATION_SAFETY_REVIEW_REQUIRED` | `MEDICATION_SAFETY_ALERT` | `HIGH` | True | 30 min |
| `POLICY_URGENT_TRIAGE` | `URGENT_TRIAGE_RESULT_AVAILABLE` | `TRIAGE_ALERT` | `CRITICAL` | True | 15 min |
| `POLICY_APPOINTMENT_SCHEDULED` | `APPOINTMENT_SCHEDULED` | `APPOINTMENT_ALERT` | `INFO` | False | N/A |
| `POLICY_INTEROPERABILITY_FAILURE` | `INTEROPERABILITY_IMPORT_FAILED` | `INTEROPERABILITY_ALERT` | `HIGH` | False | N/A |
| `POLICY_SECURITY_THREAT` | `SECURITY_THREAT_DETECTED` | `SECURITY_ALERT` | `CRITICAL` | True | 10 min |
| `POLICY_SYSTEM_HEALTH` | `SYSTEM_DEGRADED` | `SYSTEM_ALERT` | `HIGH` | False | N/A |

---

## 3. Deduplication & Idempotency
Alert fatigue is a known danger in clinical healthcare environments. Phase 35 prevents duplicates through multiple layers:
1. **Idempotency Keys**: Generated deterministically from `(source_system, source_event_type, source_resource_id)`. Re-submitting an identical event returns the existing `AlertRecord` rather than creating a duplicate.
2. **Cooldown Periods**: Policies define mandatory cooldown windows (e.g. 60 minutes) to suppress redundant alerts for identical conditions on the same patient.
3. **Quiet Hours / Channel Rules**: Informational alerts respect clinician quiet hours; Critical safety alerts bypass quiet hours but enforce strict deduplication.
