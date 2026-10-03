# HealthSetu — Phase 35: Clinical Safety Boundaries & Regression Suite

## 1. Technical Requirements Document (TRD) Section 45 Verification
HealthSetu mandates 18 clinical safety regression rules for alerts, verified in `tests/test_phase35_alerts.py`:

1. **ALERT DOES NOT DIAGNOSE**: Communicates factual test or event information, never disease diagnoses.
2. **ALERT DOES NOT PRESCRIBE**: Contains no dosage or prescribing directives.
3. **ALERT DOES NOT CHANGE MEDICATION**: Alert creation does not mutate patient medication records.
4. **ALERT DOES NOT CHANGE ALLERGY DATA**: Alert domain services have zero allergy mutation capability.
5. **ALERT DOES NOT CHANGE TRIAGE**: Alerts reflect calculated triage urgency without recalculating or modifying it.
6. **ALERT DOES NOT CREATE A CARE PLAN**: Alerts highlight findings; they cannot formulate treatment plans.
7. **ALERT DOES NOT INVENT A CRITICAL RESULT**: Non-critical results without authoritative panic flags are never elevated.
8. **ALERT DOES NOT TREAT PROVIDER FAILURE AS SUCCESS**: Provider errors cannot transition alerts to `RESOLVED`.
9. **ALERT DOES NOT TREAT MISSING INFORMATION AS NORMAL**: Missing critical flags do not default to safe or normal.
10. **ALERT DOES NOT TREAT AI OUTPUT AS CLINICAL AUTHORITY**: AI models cannot autonomously assign alert severity.
11. **ALERT DELIVERY DOES NOT EQUAL ACKNOWLEDGEMENT**: Provider delivery receipt does not satisfy clinician acknowledgement.
12. **ACKNOWLEDGEMENT DOES NOT EQUAL CLINICAL ACTION**: Acknowledging an alert marks review, not clinical resolution.
13. **ESCALATION DOES NOT EQUAL EMERGENCY DISPATCH**: Escalation routes internally to care teams and safety officers, never 911.
14. **IMPORTED DATA DOES NOT BECOME VERIFIED ONLY BECAUSE OF ALERT**: Generating an alert leaves imported data preliminary until verified by clinician.
15. **DUPLICATE EVENTS DO NOT CREATE UNCONTROLLED DUPLICATES**: Multiple event deliveries return the existing single alert record.
16. **RESOLVED ALERTS ARE NOT RE-ESCALATED**: Escalation stops immediately upon alert resolution.
17. **FAILED NOTIFICATIONS ARE NOT REPORTED AS DELIVERED**: Simulated provider delivery failures are surfaced honestly.
18. **UNKNOWN PROVIDER STATE IS NOT REPORTED AS SAFE**: Degraded or unverified provider states are reported as `DEGRADED`.

---

## 2. Patient-Facing Content Sanitization
When notifications or alerts are delivered to patients (e.g. via the patient portal or SMS):
- Alarmist clinical jargon (e.g., "Critical Panic Value", "Acute Toxicity", "Immediate Provider Review") is filtered out.
- The title is converted to standard patient-friendly language: `"Important Health Update"`.
- The body directs the patient to review findings or schedule an appointment with their care team without inducing panic.
