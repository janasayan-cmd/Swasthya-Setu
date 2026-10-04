# Phase 37: Clinical Workflow Orchestration & Controlled Action Chains

## Architecture & System Overview

### 1. Architectural Position

Phase 37 sits above tasks and async jobs in the HealthSetu backend architecture:

```
Domain Event
    ↓
Approved Workflow Definition (Versioned)
    ↓
Workflow Instance (WF-12345)
    ├── Step 1: Create Diagnostic Review Task (Phase 36 Task Service)
    ├── Step 2: Human Approval Gate (Authorized Clinician / Doctor)
    └── Step 3: Domain Verification Action (Deterministic Completion)
    ↓
Workflow Complete (Audited, Provenance Locked)
```

The orchestration layer coordinates existing domain services. It does NOT replace:
- Medication safety services (Phase 7)
- Clinical task service (Phase 36)
- Alert & escalation engine (Phase 35)
- Notification service (Phase 29)
- Async job workers (Phase 22)
- Clinical history / encounters (Phase 4)

---

### 2. Core Lifecycle State Machines

#### Workflow State Machine
```
CREATED ──→ READY ──→ RUNNING ──┬──→ WAITING (Waiting for Task/Event)
                               ├──→ AWAITING_APPROVAL (Human Gate)
                               ├──→ PAUSED ──→ RUNNING (Resume)
                               ├──→ BLOCKED
                               ├──→ COMPLETED (All steps complete)
                               ├──→ FAILED (Step failure / Exhausted retries)
                               └──→ CANCELLED (Admin/Clinician cancel)
```

#### Step State Machine
```
PENDING ──→ READY ──→ RUNNING ──┬──→ WAITING
                               ├──→ AWAITING_APPROVAL
                               ├──→ COMPLETED
                               ├──→ FAILED ──→ READY (Bounded Retry)
                               └──→ CANCELLED
```

---

### 3. Key Orchestration Subsystems

1. **`WorkflowDefinitionService`**:
   - Manages versioned, backend-controlled workflow templates (`diagnostic_review`, `medication_safety_review`, `discharge_follow_up`, `transfer_coordination`, `document_processing`).
   - Ordinary API clients cannot upload arbitrary code or inject unvetted steps.
2. **`WorkflowValidationService`**:
   - Validates explicit state transition graphs.
   - Enforces clinical boundaries: disallows forbidden mutations (altering medications, allergies, diagnoses, triage levels, or emergency dispatch).
   - Validates that AI output or suggestions cannot act as authoritative gatekeepers.
3. **`WorkflowStepService`**:
   - Evaluates dependency resolution before step execution.
   - Dispatches deterministic actions (`CREATE_TASK`, `SEND_NOTIFICATION`, `WAIT_FOR_EVENT`, `HUMAN_APPROVAL`).
   - Manages bounded retries with failure logging.
4. **`WorkflowApprovalService`**:
   - Manages human gatekeeping for high-stakes steps.
   - Enforces role requirements (`DOCTOR`, `ADMIN`).
   - Records approval audit records with clinical disclaimers.
5. **`WorkflowService`**:
   - Master orchestrator for workflow instantiation, advancement, callbacks, pause, resume, and cancellation.
   - Deduplicates requests by client idempotency key or logical identity `(source_event_type, source_event_id, definition_id, version, patient_id)`.
