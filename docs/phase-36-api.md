# HealthSetu — Phase 36: Clinical Tasks & Work Queues API Documentation

## 1. Overview
The Clinical Tasks API exposes endpoints to create, assign, accept, track, and complete actionable clinical and operational work items. All endpoints follow the Phase 23 API governance conventions, strict multi-tenant authorization, and idempotency guarantees.

**Base Path**: `/api/v1`

---

## 2. Endpoints Summary

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `POST` | `/api/v1/tasks` | Create task idempotently | `DOCTOR`, `CLINICIAN`, `ADMIN` |
| `POST` | `/api/v1/tasks/from-alert/{alert_id}` | Create task from acknowledged alert | `DOCTOR`, `CLINICIAN`, `ADMIN` |
| `GET` | `/api/v1/tasks` | List tasks with filters & pagination | Authorized staff / admin |
| `GET` | `/api/v1/tasks/my` | Personal task queue for authenticated practitioner | Authenticated user |
| `GET` | `/api/v1/clinicians/me/tasks` | Clinician personal work queue alias | Clinician |
| `GET` | `/api/v1/patients/{patient_id}/tasks` | Patient task list (IDOR verified) | Patient self / Authorized care team |
| `GET` | `/api/v1/facilities/{facility_id}/tasks` | Facility work queue | Facility staff / admin |
| `GET` | `/api/v1/organizations/{organization_id}/tasks` | Organization work queue | Organization admin |
| `GET` | `/api/v1/tasks/{task_id}` | Retrieve single task by ID | Scoped clinical staff / patient self |
| `GET` | `/api/v1/tasks/{task_id}/history` | Retrieve chronological audit trail | Authorized staff |
| `POST` | `/api/v1/tasks/{task_id}/assign` | Assign task to user or team | Authorized staff |
| `POST` | `/api/v1/tasks/{task_id}/reassign` | Reassign task with reason | Authorized staff |
| `POST` | `/api/v1/tasks/{task_id}/accept` | Accept task responsibility | Assignee / clinician |
| `POST` | `/api/v1/tasks/{task_id}/start` | Transition task to `IN_PROGRESS` | Assignee |
| `POST` | `/api/v1/tasks/{task_id}/complete` | Report task completed | Assignee / clinician |
| `POST` | `/api/v1/tasks/{task_id}/verify` | Verify or reject completed task | Authorized supervisor / admin |
| `POST` | `/api/v1/tasks/{task_id}/reject` | Reject assignment with reason | Assignee |
| `POST` | `/api/v1/tasks/{task_id}/cancel` | Cancel task with justification | Authorized staff / creator |
| `POST` | `/api/v1/tasks/{task_id}/escalate` | Trigger manual or policy escalation | Authorized staff / supervisor |
| `POST` | `/api/v1/tasks/evaluate-overdue` | Evaluate overdue tasks across system | Admin / background worker |

---

## 3. Schema Contracts

### `TaskCreate`
```json
{
  "title": "Review Abnormal Electrolyte Panel",
  "description": "Evaluate Potassium value of 5.8 mEq/L against medication profile.",
  "category": "DIAGNOSTIC_REVIEW_TASK",
  "priority": "HIGH",
  "patient_id": "PAT-10023",
  "encounter_id": "ENC-5501",
  "facility_id": "FAC-NORTH-01",
  "organization_id": "ORG-HEALTH-01",
  "assignee_id": "DOC-9912",
  "assignee_type": "USER",
  "verification_required": true,
  "due_at": "2026-10-05T12:00:00Z",
  "provenance": {
    "source_type": "diagnostic_result",
    "source_id": "DX-RES-88912",
    "source_system": "diagnostic_service",
    "policy_id": "POL_CRITICAL_LAB_REVIEW"
  },
  "idempotency_key": "IDEMP-REQ-20261004-001"
}
```

### `TaskRecord` (Response Contract)
```json
{
  "id": "TSK-20261004-00001",
  "title": "Review Abnormal Electrolyte Panel",
  "description": "Evaluate Potassium value of 5.8 mEq/L against medication profile.",
  "category": "DIAGNOSTIC_REVIEW_TASK",
  "priority": "HIGH",
  "status": "ASSIGNED",
  "patient_id": "PAT-10023",
  "encounter_id": "ENC-5501",
  "organization_id": "ORG-HEALTH-01",
  "facility_id": "FAC-NORTH-01",
  "assignee_id": "DOC-9912",
  "assignee_type": "USER",
  "created_by": "DOC-9912",
  "accepted_by": null,
  "started_at": null,
  "completed_by": null,
  "verification_required": true,
  "verified_by": null,
  "due_at": "2026-10-05T12:00:00Z",
  "dependencies": [],
  "provenance": {
    "source_type": "diagnostic_result",
    "source_id": "DX-RES-88912",
    "source_system": "diagnostic_service"
  },
  "escalation_level": 0,
  "created_at": "2026-10-04T20:30:00Z",
  "updated_at": "2026-10-04T20:30:00Z"
}
```

---

## 4. Standard Error Codes
- `TASK_NOT_FOUND` (404): Task does not exist.
- `TASK_ACCESS_DENIED` (403): Caller lacks tenant or IDOR authorization.
- `TASK_INVALID_STATE` (409): Task is not in a valid state for mutation.
- `TASK_INVALID_TRANSITION` (400): Disallowed lifecycle transition.
- `TASK_ALREADY_ACCEPTED` (409): Another user already accepted this task.
- `TASK_DEPENDENCY_BLOCKED` (409): Prerequisite tasks are incomplete.
- `TASK_CANCELLATION_NOT_ALLOWED` (400): Completed or verified tasks cannot be cancelled.
- `TASK_VERIFICATION_NOT_ALLOWED` (400): Caller is unprivileged or task not pending verification.
- `TASK_DUPLICATE` (409): Duplicate task for same logical event already active.
