# HealthSetu — Phase 25: Operational Safety Kill Switches

## 1. Objective & Philosophy

Emergency kill switches provide rapid, administrative circuit breaking for mission-critical platform components when external dependencies fail, anomalous outputs are observed, or security incidents occur.

A kill switch:
- Halts all new operations immediately.
- Preserves historical records, previous evaluations, and audit logs.
- Prevents false-positive success or synthetic clinical clearance.
- Yields explicit operational HTTP 503 (`KILL_SWITCH_ACTIVE`) errors to callers.

---

## 2. Canonical Kill Switches (TRD Sec 23)

| Switch Name | Target Capabilities | Failure Behavior |
|---|---|---|
| `AI_PROCESSING_KILL_SWITCH` | Generative AI, copilot assistance, clinical summarization | Blocks new AI tasks; returns `503 KillSwitchActiveException`. |
| `MEDICATION_SAFETY_PROVIDER_KILL_SWITCH` | Medication interaction checks, contraindication checks | Blocks safety checks; explicitly returns `SAFETY_EVALUATION_UNAVAILABLE` (Never `CLEAR`). |
| `DOCUMENT_PROCESSING_KILL_SWITCH` | Optical character recognition, document text structuring | Pauses OCR worker queues; document stays in `QUEUED` state. |
| `INTEROPERABILITY_KILL_SWITCH` | FHIR R4 gateways, external EHR import/export | Rejects external sync attempts with HTTP 503. |

---

## 3. Operational Security & Privilege (TRD Sec 24)

- **Strict Access Control**: Only actors possessing `Permission.KILL_SWITCH_MANAGE` (`ADMIN` / `SYSTEM_ADMIN`) can activate or deactivate kill switches.
- **Mandatory Justification**: Every activation/deactivation requires a descriptive `reason` parameter (minimum length validated).
- **Full Auditability**: Every state change publishes an immutable audit record (`KILL_SWITCH_ENABLED` / `KILL_SWITCH_DISABLED`) with actor identity, timestamp, previous state, and reason.
- **Immediate Cache Eviction**: Activating a kill switch flushes the in-memory feature cache so the shutdown propagates instantaneously across the node.
