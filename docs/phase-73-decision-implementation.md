# Phase 73: Clinical Safety Governance Decision Implementation, Commitment Verification & Outcome Assurance
## Architecture & Operational Specification

**Document Version:** 1.0.0  
**Phase:** 73  
**Scope:** Backend Only  
**Predecessor:** Phase 72 (Clinical Safety Governance Management Review, Executive Oversight & Decision Follow-Through)

---

### 1. Executive Summary & Domain Invariants

Phase 73 implements the Governance Decision Implementation and Outcome Assurance layer for HealthSetu. It bridges executive management decisions formalized in Phase 72 with active execution, cross-workflow delegation, independent milestone verification, and intended-outcome reconciliation.

#### Fundamental Domain Invariants
1. **Decision vs. Implementation**: An approved management decision is not automatically an implemented action. Formal implementation initiatives, approved plans, and assigned owners are strictly required.
2. **Implementation vs. Outcome**: An implementation marked complete does not automatically establish that the intended outcome has been achieved. Outcome reconciliation requires documented rationale and verified evidence.
3. **Separation of Duties**: An implementation owner or milestone submitter must not independently verify their own work (`SEPARATION_OF_DUTIES_VIOLATION`).
4. **Submission vs. Verification**: A milestone must not be marked verified merely because its responsible owner submitted a completion update.
5. **No Workflow Duplication**: Phase 73 does not replace authoritative engines (Phase 54 CAPA, Phase 55 effectiveness, Phase 63 risk, Phase 67 escalation, Phase 69 compliance, Phase 70 audit, Phase 49 incident); it delegates to them via structured handoffs.
6. **Preservation During Supersession**: When a Phase 72 decision is amended or superseded, completed implementation history is preserved rather than silently rolled back.

---

### 2. Core Functional Pillars

#### 2.1 Approved Decision Intake
- Validates eligibility of Phase 72 decisions: only `APPROVED` decisions with valid authorization can be ingested.
- Automatically quarantines or rejects draft, rejected, withdrawn, or superseded decisions.
- Idempotent intake prevents duplicate conflicting records.

#### 2.2 Decision Implementation Register
- Centralizes initiatives across 11 standard categories (`GOVERNANCE_PROCESS_CHANGE`, `POLICY_UPDATE`, `CONTROL_IMPLEMENTATION`, `COMPLIANCE_REMEDIATION`, `CORRECTIVE_ACTION`, `RISK_REVIEW_REFERRAL`, `AUDIT_FOLLOW_UP`, `TRAINING_OR_COMPETENCY_ACTION`, `SYSTEM_CONFIGURATION_CHANGE`, `OPERATIONAL_WORKFLOW_CHANGE`, `OTHER`).
- Tracks lifecycle states from `PLANNING` through `APPROVED`, `IN_PROGRESS`, `BLOCKED`, `PENDING_VERIFICATION`, `VERIFIED`, `RECONCILED`, and `CLOSED`.

#### 2.3 Implementation Planning & Versioning
- Structured implementation plans with work items, target dates, expected evidence, verification criteria, and completion conditions.
- Plan modification requires documented change reason and deactivates prior versions with full audit provenance.
- Implementation cannot become executable (`IN_PROGRESS`) without an approved plan.

#### 2.4 Ownership, Accountability & Separation of Duties
- Designates roles: `EXECUTIVE_SPONSOR`, `DECISION_OWNER`, `IMPLEMENTATION_LEAD`, `WORK_ITEM_OWNER`, `SUPPORTING_TEAM_MEMBER`, `INDEPENDENT_VERIFIER`, `GOVERNANCE_REVIEWER`, `ESCALATION_OWNER`.
- Enforces strict separation of duties: implementation leads cannot be designated as independent verifiers for their own initiatives.

#### 2.5 Dependencies & Prerequisite Management
- Tracks prerequisites across Phase 49–72 workflows.
- Graph-based DFS cycle detection blocks circular dependencies (`CIRCULAR_DEPENDENCY_DETECTED`).
- Authorized governance waivers require executive authorization and documented justification.

#### 2.6 Destination Workflow Handoffs
- Dispatches implementation actions to authoritative destination workflows:
  - Phase 54: Corrective and Preventive Actions (CAPA)
  - Phase 55: Effectiveness Monitoring
  - Phase 63: Risk Reviews
  - Phase 67: Governance Escalations
  - Phase 69: Compliance Reassessments
  - Phase 70: Audit Follow-Ups
  - Phase 49: Incident Escalations
- Tracks handoff status, latest destination status, and retry coordination.

#### 2.7 Milestones, Evidence & Independent Verification
- Tracks milestones through `NOT_STARTED`, `IN_PROGRESS`, `SUBMITTED`, `VERIFIED`, `REJECTED`.
- Attaches and classifies evidence (`STANDARD`, `RESTRICTED`, `CONFIDENTIAL`).
- Reviews evidence for validity or flags contradictory findings.
- Independent verification verifies criteria against evidence without allowing self-verification.

#### 2.8 Outcome Reconciliation
- Evaluates delivered implementation against original decision intent.
- Outcome states: `NOT_ASSESSED`, `OUTCOME_ACHIEVED`, `PARTIALLY_ACHIEVED`, `NOT_ACHIEVED`, `INCONCLUSIVE`, `SUPERSEDED`, `CANCELLED_WITH_AUTHORIZATION`.
- Prevents declaring `OUTCOME_ACHIEVED` without supporting verified evidence.

#### 2.9 Exceptions & Decision Change Impact Coordination
- Logs implementation exceptions and coordinates referral to Phase 67.
- Detects Phase 72 decision amendments or supersession, analyzes impact on ongoing milestones, dependencies, and handoffs, and records authorized disposition (`CONTINUE`, `MODIFY`, `SUSPEND`, `CANCEL`).

#### 2.10 Controlled Closure & Management Reporting
- Closure readiness validation (`check_closure_readiness`):
  1. Milestones in acceptable terminal states.
  2. Mandatory dependencies satisfied or waived.
  3. Verified evidence on record.
  4. Outcome assessment completed.
- Reopening mechanism preserves history.
- Aggregated executive oversight reports on active, blocked, overdue, and reconciled initiatives.

---

### 3. REST API Reference

Base Path: `/api/v1/governance-decision-implementation`

| Method | Path | Description |
|---|---|---|
| `GET` | `/reports/overview` | Aggregated executive oversight metrics |
| `GET` | `/reports/overdue` | Overdue implementation milestones |
| `GET` | `/reports/outcomes` | All outcome assessments |
| `POST` | `/reports/generate` | Generate formal oversight report |
| `GET` | `/reports/{report_id}` | Get report by ID |
| `POST` | `/decisions/intake` | Ingest approved Phase 72 decision |
| `GET` | `/decisions` | List decision intake records |
| `GET` | `/decisions/{decision_id}/implementation-status` | Check implementation status for decision |
| `POST` | `/implementations` | Register new decision implementation |
| `GET` | `/implementations` | List implementations |
| `GET` | `/implementations/{implementation_id}` | Get implementation by ID |
| `PATCH` | `/implementations/{implementation_id}` | Update implementation details |
| `POST` | `/implementations/{implementation_id}/submit` | Submit implementation for approval |
| `POST` | `/implementations/{implementation_id}/approve` | Formally approve implementation |
| `POST` | `/implementations/{implementation_id}/plans` | Create or version implementation plan |
| `GET` | `/implementations/{implementation_id}/plans` | List plans for implementation |
| `GET` | `/plans/{plan_id}` | Get plan by ID |
| `PATCH` | `/plans/{plan_id}` | Update draft plan |
| `POST` | `/plans/{plan_id}/submit` | Submit plan for approval |
| `POST` | `/plans/{plan_id}/approve` | Approve implementation plan |
| `POST` | `/implementations/{implementation_id}/assignments` | Assign implementation role |
| `GET` | `/implementations/{implementation_id}/assignments` | List assignments |
| `PATCH` | `/assignments/{assignment_id}` | Update assignment |
| `POST` | `/assignments/{assignment_id}/accept` | Accept, decline, or delegate assignment |
| `POST` | `/implementations/{implementation_id}/dependencies` | Link prerequisite dependency |
| `GET` | `/implementations/{implementation_id}/dependencies` | List dependencies |
| `POST` | `/dependencies/{dependency_id}/reconcile` | Reconcile dependency status |
| `POST` | `/dependencies/{dependency_id}/waive` | Authorize formal waiver on dependency |
| `POST` | `/implementations/{implementation_id}/milestones` | Add implementation milestone |
| `GET` | `/implementations/{implementation_id}/milestones` | List milestones |
| `GET` | `/milestones/{milestone_id}` | Get milestone by ID |
| `PATCH` | `/milestones/{milestone_id}` | Update milestone |
| `POST` | `/milestones/{milestone_id}/submit` | Submit completed milestone |
| `POST` | `/milestones/{milestone_id}/verify` | Independently verify milestone |
| `POST` | `/milestones/{milestone_id}/evidence` | Attach evidence reference |
| `GET` | `/milestones/{milestone_id}/evidence` | List evidence for milestone |
| `POST` | `/evidence/{evidence_id}/review` | Review evidence artifact |
| `POST` | `/implementations/{implementation_id}/handoffs` | Dispatch destination handoff |
| `GET` | `/implementations/{implementation_id}/handoffs` | List handoffs |
| `POST` | `/handoffs/{handoff_id}/reconcile` | Reconcile destination status |
| `GET` | `/handoffs/{handoff_id}` | Get handoff by ID |
| `POST` | `/implementations/{implementation_id}/outcome-assessment` | Reconcile implementation outcome |
| `GET` | `/implementations/{implementation_id}/outcome-assessment` | Get outcome assessment |
| `GET` | `/implementations/{implementation_id}/exceptions` | List implementation exceptions |
| `POST` | `/implementations/{implementation_id}/exceptions/{exception_id}/refer` | Refer exception to Phase 67 |
| `POST` | `/implementations/{implementation_id}/change-impact/review` | Assess and record decision change impact |
| `GET` | `/implementations/{implementation_id}/change-impact` | List change impact assessments |
| `POST` | `/implementations/{implementation_id}/closure-check` | Validate closure readiness |
| `POST` | `/implementations/{implementation_id}/close` | Formally close implementation |
| `POST` | `/implementations/{implementation_id}/reopen` | Reopen closed implementation |
