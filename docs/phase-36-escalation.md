# HealthSetu — Phase 36: Task Escalation & Overdue Processing

## 1. Overview
The Task Escalation and Overdue Evaluation Service monitors task completion deadlines and applies configurable multi-tier escalation paths. It ensures overdue clinical and operational tasks receive appropriate supervisor and leadership visibility without converting routine administrative delays into artificial emergencies.

---

## 2. Escalation Hierarchy

| Tier | Level | Target Recipient | Action Taken |
|---|---|---|---|
| **Tier 0** | 0 | Assigned Practitioner | Normal execution within deadline |
| **Tier 1** | 1 | Assignee + Care Team Lead | Reminder notification; overdue state flagged |
| **Tier 2** | 2 | Department Supervisor / Facility Lead | Clinical Alert generated (Phase 35); supervisor inbox notified |
| **Tier 3** | 3 | Facility Medical Director / Org Admin | High-priority leadership escalation notification |

---

## 3. Escalation Stop Conditions
Escalation evaluation immediately terminates when a task reaches any of the following terminal states:
- `COMPLETED`: Work fulfilled by assigned clinician.
- `VERIFICATION_PENDING`: Work submitted, awaiting supervisor verification.
- `VERIFIED`: Formally approved by supervisor.
- `CANCELLED`: Explicitly cancelled with documented rationale.
- `REJECTED`: Assignment rejected and returned to unassigned pool.
- `EXPIRED`: Auto-expired according to retention/policy parameters.

Once in a terminal state, subsequent overdue evaluation sweeps ignore the task.

---

## 4. Integration with Alerts (Phase 35) & Notifications (Phase 29)
1. **Alert Generation**: Escalating high-priority tasks (Level 2+) raises a `CLINICAL_ALERT` or `FOLLOW_UP_ALERT` via `AlertService`.
2. **Notification Dispatch**: Dispatches urgent templated notifications (`TASK_ESCALATED`, `TASK_OVERDUE`) through Phase 29 `NotificationService`.
3. **Clinical Safety Boundary**: Overdue task escalation NEVER triggers automated emergency dispatch, autonomous treatment, or prescription changes.
