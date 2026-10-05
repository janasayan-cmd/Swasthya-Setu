# Phase 42: Patient Engagement, Consented Self-Service & Care Journey Action Management

## 1. Overview & Objectives

HealthSetu Phase 42 implements the secure, auditable backend layer enabling patients to perform authorized self-service actions across their care journey:
- Responding to care-team requests and questionnaires
- Confirming appointment attendance
- Acknowledging receipt of discharge instructions and care plans
- Submitting requested health documents (reusing Phase 5 storage)
- Confirming communication preferences
- Recording explicit patient refusal / opt-out
- Submitting corrections to prior submissions without overwriting history

---

## 2. Non-Negotiable Clinical Safety Principles

The patient self-service layer is an **operational interaction mechanism, NOT a clinical authority**:

* **`PATIENT ACTION ≠ CLINICAL DECISION`**
* **`PATIENT RESPONSE ≠ CLINICAL VERIFICATION`**
* **`PATIENT ACKNOWLEDGEMENT ≠ CLINICAL UNDERSTANDING OR ADHERENCE`**
* **`PATIENT CONFIRMATION ≠ CLINICAL CONSENT UNLESS EXPLICITLY DEFINED`**
* **`PATIENT SUBMISSION ≠ VERIFIED MEDICAL DATA`**
* **`PATIENT QUESTIONNAIRE ≠ DIAGNOSIS`**
* **`PATIENT REPORTED SYMPTOM ≠ TRIAGE RESULT`**
* **`PATIENT MEDICATION ENTRY ≠ VERIFIED MEDICATION`**
* **`PATIENT ALLERGY ENTRY ≠ VERIFIED ALLERGY`**
* **`PATIENT ACTION ≠ CLINICAL ORDER`**
* **`PATIENT ACTION ≠ PRESCRIPTION`**
* **`PATIENT ACTION ≠ MEDICATION CHANGE`**
* **`PATIENT ACTION ≠ EMERGENCY DISPATCH`**
* **`WORKFLOW COMPLETION ≠ CLINICAL OUTCOME`**
* **`AI SUGGESTION ≠ PATIENT AUTHORIZATION`**

Any attempt to directly mutate authoritative clinical diagnosis tables, medication lists, allergy charts, or dispatch emergency services from self-service endpoints is strictly rejected (`PATIENT_ACTION_AUTONOMOUS_CLINICAL_PROHIBITED`).

---

## 3. Architecture & Data Flow

```
Patient Client
     ↓
Authentication (Phase 2 JWT)
     ↓
Authorization & Scoping (PatientActionAuthorizationService)
     ↓
Action & Rate Validation (PatientActionValidationService)
     ↓
Master Orchestrator (PatientActionService)
     ├── Questionnaires (QuestionnaireService)
     ├── Submissions & Provenance (PatientSubmissionService)
     └── Audit Trail (AuditService)
     ↓
Database Repository Contract (PatientActionRepository)
     ↓
Async Workflow & Notification Integration (Phase 22, Phase 29, Phase 36)
     ↓
Authorized Clinician Review Queue
```

---

## 4. Action Lifecycle

```
CREATED
  ↓
AVAILABLE
  ↓
STARTED
  ↓
SUBMITTED
  ↓
COMPLETED

Alternative / Terminal States:
- EXPIRED (action passed configured deadline without submission; EXPIRED != PATIENT FAILURE)
- CANCELLED (cancelled by workflow or patient refusal)
- REJECTED (declined by clinician during review)
- NEEDS_REVIEW (clinician requested correction from patient)
```

---

## 5. REST API Endpoints (`/api/v1`)

### Patient Action Endpoints
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/patient-actions` | Create a new patient action instance |
| `GET` | `/api/v1/patient-actions` | List actions assigned to current patient |
| `GET` | `/api/v1/patient-actions/{action_id}` | Retrieve action details with authorization |
| `POST` | `/api/v1/patient-actions/{action_id}/start` | Transition action to `STARTED` |
| `POST` | `/api/v1/patient-actions/{action_id}/submit` | Submit patient response (supports idempotency) |
| `POST` | `/api/v1/patient-actions/{action_id}/complete` | Mark operational action as `COMPLETED` |
| `POST` | `/api/v1/patient-actions/{action_id}/cancel` | Cancel action with stated reason |
| `POST` | `/api/v1/patient-actions/{action_id}/acknowledge` | Acknowledge receipt of notice or care plan |
| `POST` | `/api/v1/patient-actions/{action_id}/refuse` | Record explicit patient refusal / opt-out |
| `POST` | `/api/v1/patient-actions/{action_id}/correct` | Submit correction preserving history (v1 -> v2) |
| `GET` | `/api/v1/patient-actions/{action_id}/history` | Retrieve full audit history of transitions |
| `GET` | `/api/v1/patients/{patient_id}/actions` | Scoped action retrieval for specific patient |
| `POST` | `/api/v1/patient-actions/{action_id}/documents` | Link Phase 5 secure document to action |
| `GET` | `/api/v1/patient-actions/{action_id}/documents` | List documents linked to action |
| `GET` | `/api/v1/admin/patient-actions` | Clinician / Admin operational action listing |
| `GET` | `/api/v1/admin/patient-actions/{action_id}` | Clinician / Admin retrieve single action |
| `POST` | `/api/v1/admin/patient-actions/{action_id}/review` | Clinician review: ACCEPT, REJECT, REQUEST_CORRECTION |

### Questionnaire Endpoints
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/patient-actions/{action_id}/questionnaire` | Retrieve structured questions for action |
| `POST` | `/api/v1/patient-actions/{action_id}/questionnaire/submit` | Submit answers with validation & idempotency |

---

## 6. Audit Events

* `PATIENT_ACTION_CREATED`
* `PATIENT_ACTION_ACCESSED`
* `PATIENT_ACTION_STARTED`
* `PATIENT_ACTION_SUBMITTED`
* `PATIENT_ACTION_COMPLETED`
* `PATIENT_ACTION_CANCELLED`
* `PATIENT_ACTION_EXPIRED`
* `PATIENT_ACTION_REJECTED`
* `PATIENT_ACTION_NEEDS_REVIEW`
* `PATIENT_ACTION_ACKNOWLEDGED`
* `PATIENT_ACTION_REFUSED`
* `PATIENT_RESPONSE_CREATED`
* `PATIENT_RESPONSE_CORRECTED`
* `QUESTIONNAIRE_VIEWED`
* `QUESTIONNAIRE_SUBMITTED`
* `DOCUMENT_SUBMISSION_CREATED`
* `CARE_PLAN_ACKNOWLEDGED`
* `APPOINTMENT_CONFIRMATION_COMPLETED`
* `PATIENT_ACTION_REMINDER_SENT`
