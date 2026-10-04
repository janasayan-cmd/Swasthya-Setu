# Phase 37: Clinical Workflows API Reference

## Base Path: `/api/v1`

All requests require authentication with a Bearer JWT token. Access is strictly scoped by role, organization, and patient relationship.

---

### 1. Workflow Management Endpoints

#### `POST /workflows`
- **Summary**: Create or trigger an approved clinical workflow instance idempotently.
- **Permission**: `WORKFLOW_CREATE`
- **Request Body**:
```json
{
  "workflow_definition": "diagnostic_review",
  "workflow_version": "1.0",
  "source_type": "diagnostic_result",
  "source_id": "RES-2026-9901",
  "patient_id": "PAT-1001",
  "facility_id": "FAC-001",
  "correlation_id": "CORR-LAB-9901",
  "idempotency_key": "IDEM-WF-9901",
  "initial_context": {
    "test_name": "Serum Potassium",
    "critical_flag": true
  }
}
```
- **Response**: `201 Created` with `WorkflowRecord`.

#### `GET /workflows`
- **Summary**: List workflows matching filters.
- **Permission**: `WORKFLOW_READ`
- **Query Parameters**:
  - `status`: Filter by `WorkflowStatus`
  - `category`: Filter by `WorkflowCategory`
  - `patient_id`: Filter by patient
  - `facility_id`: Filter by facility
  - `page`: Page index (default 1)
  - `page_size`: Page limit (default 20, max 100)
- **Response**: `200 OK` with `WorkflowListResponse`.

#### `GET /workflows/{workflow_id}`
- **Summary**: Retrieve workflow details and current step states.
- **Permission**: `WORKFLOW_READ`

#### `GET /workflows/{workflow_id}/steps`
- **Summary**: Retrieve ordered runtime step instances.
- **Permission**: `WORKFLOW_READ`

#### `GET /workflows/{workflow_id}/history`
- **Summary**: Retrieve transition history audit trail.
- **Permission**: `WORKFLOW_READ`

#### `GET /workflows/{workflow_id}/approvals`
- **Summary**: Retrieve recorded approval decisions.
- **Permission**: `WORKFLOW_READ`

---

### 2. Human Approval Gate Endpoints

#### `POST /workflows/{workflow_id}/steps/{step_id}/approve`
- **Summary**: Authorize and approve a human approval gate step.
- **Permission**: `WORKFLOW_APPROVE` (Role: `DOCTOR` or `ADMIN`)
- **Request Body**:
```json
{
  "decision": "APPROVED",
  "comments": "Reviewed diagnostic lab result. Approved verification.",
  "policy_version": "1.0"
}
```
- **Response**: `200 OK` with updated `WorkflowRecord`.

#### `POST /workflows/{workflow_id}/steps/{step_id}/reject`
- **Summary**: Explicitly reject a human approval gate step.
- **Permission**: `WORKFLOW_APPROVE` (Role: `DOCTOR` or `ADMIN`)

---

### 3. Workflow Control Endpoints

#### `POST /workflows/{workflow_id}/pause`
- **Summary**: Pause execution of a running workflow.
- **Permission**: `WORKFLOW_PAUSE`
- **Request Body**:
```json
{
  "reason": "Awaiting second laboratory confirmation specimen."
}
```

#### `POST /workflows/{workflow_id}/resume`
- **Summary**: Resume execution of a paused workflow.
- **Permission**: `WORKFLOW_RESUME`

#### `POST /workflows/{workflow_id}/cancel`
- **Summary**: Cancel active workflow without erasing history.
- **Permission**: `WORKFLOW_CANCEL`
- **Request Body**:
```json
{
  "reason": "Encounter cancelled by ordering clinician.",
  "cancel_pending_tasks": true
}
```

---

### 4. Patient and Staff Shortcuts

#### `GET /patients/{patient_id}/workflows`
- **Permission**: `WORKFLOW_READ`
- Scoped to patient or authorized care team.

#### `GET /clinicians/me/workflows`
- **Permission**: `WORKFLOW_READ`
- Scoped to clinician's assigned facility.

---

### 5. Administrative Endpoints

- `GET /admin/workflows`: View all system workflows across tenants.
- `GET /admin/workflows/{workflow_id}`: Admin state inspection.
- `GET /admin/workflow-definitions`: List approved workflow templates.
- `GET /admin/workflow-failures`: Operational triage of failed workflows.
- `GET /admin/workflow-metrics`: Aggregate counts by status (no PHI).
