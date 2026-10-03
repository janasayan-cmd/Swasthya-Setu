# HealthSetu — Phase 35: Alert Escalation Engine Architecture

## 1. Purpose & Clinical Safety Scope
The Escalation Engine prevents critical safety notifications from remaining unaddressed due to clinician unavailability, off-duty status, or technical delivery impediments. When an alert configured for escalation is unacknowledged within its policy deadline, the engine automatically advances communication to progressively higher supervisory tiers.

**CRITICAL SAFETY PRINCIPLE**:
`ESCALATION ≠ EMERGENCY DISPATCH`.
Escalation transfers organizational awareness within the clinical facility. It never connects to 911 or dispatches physical emergency ambulances.

---

## 2. Multi-Tier Escalation Hierarchy
Alerts advance across defined tiers (0 through 3):

```
[Tier 0: Primary Clinician]
       │ (Unacknowledged after timeout, e.g. 15-30m)
       ▼
[Tier 1: Departmental Care Team]
       │ (Unacknowledged after timeout)
       ▼
[Tier 2: Facility Clinical Supervisor / On-Call Lead]
       │ (Unacknowledged after timeout)
       ▼
[Tier 3: Organization Medical Safety / Quality Officer]
```

- **Tier 0 (Primary / Responsible Clinician)**: The clinician directly assigned to the patient or who ordered the diagnostic test.
- **Tier 1 (Departmental Care Team)**: The nursing station, ward care team, or on-duty cross-coverage clinician (`care_team_{facility_id}`).
- **Tier 2 (Facility Clinical Supervisor)**: Facility medical director or chief on-call physician (`facility_lead_{facility_id}`).
- **Tier 3 (Organization Medical Safety & Quality Officer)**: Network-level patient safety executive (`org_quality_officer_{org_id}`).

---

## 3. Escalation Stop Conditions
Escalation immediately terminates and advances no further under any of the following conditions:
1. **ALREADY_ACKNOWLEDGED**: The alert has been formally acknowledged by an authorized user (`alert.status == ACKNOWLEDGED`).
2. **ALREADY_RESOLVED**: The alert has been resolved (`alert.status == RESOLVED`).
3. **ALREADY_DISMISSED**: The alert was dismissed (`alert.status == DISMISSED`).
4. **MAX_TIER_REACHED**: Tier 3 has already been notified (`alert.escalation_level >= 3`).
5. **ESCALATION_DISABLED**: The alert policy or individual alert record has `escalation_enabled == False`.

---

## 4. Asynchronous Background Execution
- Celery worker task `app.workers.tasks.alerts.check_unacknowledged_alerts` runs on a scheduled cadence (every 1-2 minutes).
- Queries for overdue unacknowledged alerts where `next_escalation_deadline <= NOW()`.
- Dispatches notifications via `NotificationService` and logs audit events for each escalation step.
