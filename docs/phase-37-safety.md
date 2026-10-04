# Phase 37: Clinical Safety & Governance Invariants

## Core Principles

```
WORKFLOW ≠ CLINICAL DECISION
WORKFLOW ≠ DIAGNOSIS
WORKFLOW ≠ TREATMENT
WORKFLOW ≠ PRESCRIPTION
WORKFLOW ≠ MEDICATION CHANGE
WORKFLOW ≠ TRIAGE
WORKFLOW ≠ EMERGENCY DISPATCH

WORKFLOW DEFINITION ≠ WORKFLOW INSTANCE
WORKFLOW STEP ≠ CLINICAL ACTION
TASK COMPLETION ≠ CLINICAL OUTCOME
AUTOMATED TRANSITION ≠ CLINICAL AUTHORITY
APPROVAL REQUEST ≠ APPROVAL
APPROVAL ≠ CLINICAL TRUTH
AI SUGGESTION ≠ WORKFLOW AUTHORIZATION
```

---

## 20 Mandatory Clinical Safety Regression Tests (TRD Section 60)

| # | Invariant | Enforcement Implementation |
|---|---|---|
| **1** | **WORKFLOW DOES NOT DIAGNOSE** | Workflow orchestrator coordinates task creation and notification; it contains no diagnostic reasoning engine or diagnostic mutation endpoints. |
| **2** | **WORKFLOW DOES NOT PRESCRIBE** | Prescription creation remains strictly within Phase 6 clinician-authenticated prescribing services. |
| **3** | **WORKFLOW DOES NOT CHANGE MEDICATION** | Orchestrator cannot alter medication orders directly; only clinical tasks assigned to authorized prescribers can effect medication reconciliation. |
| **4** | **WORKFLOW DOES NOT CHANGE ALLERGY DATA** | Allergy management remains strictly within Phase 4 allergy repositories. |
| **5** | **WORKFLOW DOES NOT CHANGE TRIAGE** | Triage levels are determined solely by Phase 8 triage engine, never overridden by workflow progression. |
| **6** | **WORKFLOW DOES NOT CREATE AUTONOMOUS TREATMENT** | Treatment plans require human clinical authorization. |
| **7** | **WORKFLOW DOES NOT DISPATCH EMERGENCY SERVICES** | Workflow cannot directly invoke EMS dispatch APIs without clinical human gatekeeping. |
| **8** | **WORKFLOW DOES NOT TURN ABNORMAL RESULTS INTO DIAGNOSES** | An abnormal diagnostic result triggers review workflows and tasks, but never auto-populates diagnosis tables. |
| **9** | **WORKFLOW DOES NOT TURN PROVIDER FAILURE INTO SUCCESS** | External provider failures enter `WAITING`, `RETRY_PENDING`, or `FAILED` states; they are never coerced to `COMPLETED` or `SUCCESS`. |
| **10** | **WORKFLOW DOES NOT TURN MISSING INFORMATION INTO NORMAL** | Missing lab values or incomplete records are never defaulted to normal or clinically safe. |
| **11** | **WORKFLOW DOES NOT TURN AI OUTPUT INTO CLINICAL AUTHORITY** | AI suggestions cannot bypass approval gates, alter workflow definitions, or declare clinical safety. |
| **12** | **WORKFLOW COMPLETION DOES NOT EQUAL CLINICAL OUTCOME** | Workflow completion signifies that defined operational coordination steps finished; it is not a declaration of patient health or cure. |
| **13** | **TASK COMPLETION DOES NOT AUTOMATICALLY COMPLETE THE WORKFLOW** | A task completion unblocks a linked step; subsequent steps and verification gates must still be satisfied. |
| **14** | **ALERT DELIVERY DOES NOT AUTOMATICALLY COMPLETE A WORKFLOW** | Alert transmission is an operational notification step; clinical review remains separate. |
| **15** | **APPROVAL DOES NOT MEAN PATIENT SAFETY IS CONFIRMED** | Approval represents human authorization to advance the administrative/clinical step; it does not replace diagnostic truth. |
| **16** | **PROVIDER REQUEST SUCCESS DOES NOT EQUAL CLINICAL OUTCOME** | HTTP 200 from a lab or document provider only confirms transmission, not patient health. |
| **17** | **IMPORTED DATA DOES NOT BECOME VERIFIED THROUGH WORKFLOW COMPLETION ALONE** | Ingested documents require human review gates before clinical records are modified. |
| **18** | **DUPLICATE EVENTS DO NOT CREATE DUPLICATE WORKFLOW INSTANCES** | Strict deduplication via client `idempotency_key` and logical identity `(source_event_type, source_event_id, definition_id, version, patient_id)`. |
| **19** | **RETRIES DO NOT CREATE DUPLICATE CLINICAL SIDE EFFECTS** | Step execution actions utilize deterministic idempotency keys and pre-action status checks. |
| **20** | **CANCELLING A WORKFLOW DOES NOT SILENTLY DELETE ITS HISTORY** | Cancellation transitions state to `CANCELLED` and preserves full immutable history in `workflow_history`. |
