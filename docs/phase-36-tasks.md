# HealthSetu — Phase 36: Clinical Tasks, Work Queues & Action Management

## 1. Overview & Architectural Scope
Phase 36 implements the authoritative backend infrastructure for clinical tasks, work queues, and operational action management across HealthSetu. It establishes a coordinated, policy-driven task engine that converts approved clinical and operational events into structured, assignable, prioritized, and auditable action items.

Phase 36 is strictly a **CLINICAL AND OPERATIONAL WORKFLOW COORDINATION** capability. It enables clinicians, care teams, and administrative personnel to coordinate work without becoming an autonomous clinical decision-maker.

---

## 2. Core Architectural Safety Principles
- **TASK ≠ CLINICAL DECISION**: A task coordinates human work; it never establishes clinical conclusions.
- **TASK ≠ DIAGNOSIS**: Diagnostic review tasks prompt human evaluation; they never formulate a disease diagnosis.
- **TASK ≠ PRESCRIPTION**: Medication tasks facilitate review; they never generate or alter medical prescriptions.
- **TASK ≠ TREATMENT**: Tasks organize workflow steps; they never initiate or dispense autonomous medical therapy.
- **TASK ≠ MEDICATION CHANGE**: A medication review task never automatically mutates active patient prescriptions.
- **TASK ≠ TRIAGE**: Urgency priority reflects operational deadlines; it never alters authoritative clinical triage classification.
- **TASK ≠ EMERGENCY DISPATCH**: Task escalation alerts supervisors and care teams; it never autonomously dispatches 911 or ambulances.
- **ALERT ≠ TASK**: Alerts flag conditions requiring awareness; tasks represent distinct commitments to action.
- **TASK CREATED ≠ TASK STARTED**: Creation records intent; work only starts upon explicit practitioner commencement.
- **TASK STARTED ≠ TASK COMPLETED**: Progress tracking prevents premature assumptions of fulfilled clinical action.
- **TASK COMPLETED ≠ CLINICAL OUTCOME**: Fulfilling a checklist task does not guarantee therapeutic cure or clinical recovery.
- **TASK ASSIGNED ≠ TASK ACCEPTED**: Assignment designates responsibility; acceptance records active practitioner commitment.
- **TASK ACCEPTED ≠ TASK PERFORMED**: Formal acceptance precedes actual clinical examination or procedure execution.
- **TASK PERFORMED ≠ TASK VERIFIED**: Completed actions subject to supervisor or peer review remain in verification pending until verified.
- **AI MUST NOT BECOME AUTHORITATIVE**: AI suggestions cannot autonomously generate or sign off on authoritative clinical tasks without human-in-the-loop review.
- **DATABASE REMAINS SOURCE OF TRUTH**: Durable repository state and immutable audit ledgers govern all task lifecycles.

---

## 3. Team Responsibility Boundaries
- **Backend Team Owns**:
  - FastAPI REST endpoints for task creation, queues, assignment, acceptance, start, completion, verification, cancellation, and history.
  - Pydantic domain models, validation schemas, and lifecycle constraints.
  - State transition validation matrix enforcing valid lifecycle progressions.
  - Dependency engine ensuring prerequisite tasks are satisfied before dependent tasks start.
  - Multi-tier task escalation and overdue deadline detection.
  - Multi-tenant query isolation and IDOR/BOLA authorization enforcement.
  - Integration with Phase 35 alerts, Phase 29 notifications, and Phase 22 asynchronous workers.
  - Provenance tracking and immutable history ledger for clinical compliance.
- **Database Team Owns**:
  - Relational schema tables (`tasks`, `task_assignments`, `task_history`, `task_dependencies`).
  - Primary keys, foreign key constraints, composite unique indexes, and partition schemes.
  - Transaction isolation, optimistic concurrency locking (`updated_at`), and query performance tuning.
  - Data retention, archiving, and disaster recovery replication.

---

## 4. System Integrations
- **Phase 4 (Encounters & Clinical Records)**: Associates tasks with patient encounters without modifying clinical notes.
- **Phase 7 (Medication Safety)**: Ingests medication review requests requiring pharmacist or doctor reconciliation.
- **Phase 8 (Triage & SBAR)**: Ingests clinical follow-up tasks from urgent triage determinations.
- **Phase 10 (Doctor Clinical Workflow)**: Surfaces tasks in clinician work queues and supports supervisor sign-offs.
- **Phase 11 (Hospital & Network)**: Enforces multi-tenant organizational and facility isolation boundaries.
- **Phase 12 (Transfers)**: Manages inter-facility coordination tasks.
- **Phase 13 (Interoperability & FHIR)**: Coordinates manual data reconciliation tasks for imported clinical bundles.
- **Phase 15 (Security & Audit)**: Verifies RBAC permissions and logs all task mutations into the append-only audit trail.
- **Phase 22 (Async Jobs)**: Executes background scans for overdue task detection and deadline reminders.
- **Phase 25 (Configuration)**: Governs task policy thresholds, page sizes, and feature flags.
- **Phase 26 (Data Quality)**: Creates data remediation tasks for incomplete patient demographic or encounter records.
- **Phase 29 (Multi-Channel Notifications)**: Delivers timely notifications upon assignment, approaching deadlines, and verifications.
- **Phase 34 (Diagnostics)**: Ingests critical diagnostic review tasks following abnormal laboratory results.
- **Phase 35 (Alerts & Escalation)**: Transforms acknowledged alerts into actionable follow-up tasks and raises alerts on high-priority task escalations.
