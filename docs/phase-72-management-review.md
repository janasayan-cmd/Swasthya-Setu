# Phase 72: Clinical Safety Governance Management Review, Executive Oversight & Decision Follow-Through
## Architecture & Operational Specification

**Document Version:** 1.0.0  
**Phase:** 72  
**Scope:** Backend Only  
**Predecessor:** Phase 71 (Clinical Safety Governance Audit Finding Analytics, Repeat-Issue Detection & Systemic Risk Insight)

---

### 1. Executive Summary & Domain Invariants

Phase 72 converts approved governance intelligence (Phases 49–71) into a structured executive oversight and decision follow-through workflow for HealthSetu. It establishes formal management review programmes, agenda compilation, reproducible review packages, quorum and authority verification, minute keeping, authoritative decision recording, commitment tracking, verification, and controlled closure.

#### Invariant Rules
1. **Intelligence vs. Decision**: An analytical insight (Phase 71) or audit finding (Phase 70) is not automatically a management decision. Formal human leadership review and recorded rationale are strictly required.
2. **Decision vs. Implementation**: A management decision is not automatically an implemented action. Concrete follow-through commitments with designated responsible owners, accountable leads, and explicit due dates must be assigned.
3. **Implementation vs. Effectiveness**: An implemented commitment is not automatically effective. Formal verification of completion evidence is required before closure.
4. **Authority vs. Attendance**: Meeting attendance alone does **not** confer decision-making authority (`has_decision_authority`). Only authorized leaders or designated clinical safety roles can record binding decisions (`DECISION_AUTHORIZATION_FAILED`).
5. **No Workflow Duplication**: Management commitments do not supersede or duplicate authoritative engines (Phase 54 CAPA, Phase 55 effectiveness, Phase 63 risk review, Phase 67 escalation); commitments link directly to those workflows.
6. **Controlled Review Closure**: A review cannot close without all agenda items concluded or deferred, all decisions formalized, all commitments assigned, and a management review report formally approved (`REVIEW_CLOSURE_CONDITIONS_UNMET`).

---

### 2. Core Functional Pillars

#### 2.1 Management Review Programme Governance
- Review programmes organize governance reviews into standardized schedules (`MONTHLY`, `QUARTERLY`, `SEMI_ANNUALLY`, `ANNUALLY`, `AD_HOC`).
- Categories include: `ROUTINE_GOVERNANCE`, `CLINICAL_SAFETY_GOVERNANCE`, `COMPLIANCE_OVERSIGHT`, `AUDIT_PERFORMANCE`, `RISK_AND_EXCEPTION`, `CORRECTIVE_ACTION`, `POST_INCIDENT_GOVERNANCE`, `SPECIAL_MANAGEMENT_REVIEW`.
- Programmes transition from `DRAFT` to `APPROVED` / `ACTIVE` through formal governance approval.

#### 2.2 Meeting Scheduling & Participant Management
- Supports scheduling, postponement, rescheduling with documented reasons, and cancellation.
- Tracks participants across 10 functional roles (`CHAIRPERSON`, `EXECUTIVE_REVIEWER`, `CLINICAL_SAFETY_REPRESENTATIVE`, `COMPLIANCE_REPRESENTATIVE`, `RISK_REPRESENTATIVE`, `AUDIT_REPRESENTATIVE`, `CORRECTIVE_ACTION_OWNER`, `SUBJECT_MATTER_EXPERT`, `SECRETARY`, `OBSERVER`).
- Validates conflict of interest declarations and decision authority flags.
- Validates meeting readiness (`validate_readiness`): checks programme approval, chairperson assignment, decision maker presence, quorum, and agenda availability.

#### 2.3 Agenda Management & Cross-Workflow Input Consolidation
- Organizes topics across standardized categories:
  - `STATUS_OF_PREVIOUS_ACTIONS`
  - `CHANGES_IN_INTERNAL_EXTERNAL_ISSUES`
  - `CLINICAL_SAFETY_PERFORMANCE`
  - `AUDIT_FINDINGS_AND_INTELLIGENCE`
  - `COMPLIANCE_AND_POLICY_CONFORMANCE`
  - `RISK_AND_EXCEPTION_REVIEWS`
  - `CAPA_AND_CORRECTIVE_ACTION_STATUS`
  - `RESOURCE_ADEQUACY`
  - `SAFETY_SYSTEM_EFFECTIVENESS`
  - `OPPORTUNITIES_FOR_IMPROVEMENT`
- Collects and indexes inputs from Phases 49–71 (`ConsolidatedInputRecord`).
- Compiles immutable, reproducible review packages (`ReviewPackageRecord`) with versioning and cryptographic locking.

#### 2.4 Authoritative Decisions & Decision Authority Enforcement
- Records formal management decisions across 11 standard categories (`POLICY_ADOPTION_OR_REVISION`, `RESOURCE_ALLOCATION`, `SYSTEM_MODIFICATION`, `PROCESS_CHANGE`, `CORRECTIVE_ACTION_INITIATION`, `RISK_ACCEPTANCE`, `RISK_ESCALATION`, `AUDIT_REFERRAL`, `GOVERNANCE_EXCEPTION_RESOLUTION`, `COMPLIANCE_REMEDY`, `OTHER_MANAGEMENT_ACTION`).
- Verifies that the decider possesses explicit decision authority or executive clinical role (`ADMIN`, `DOCTOR`, `GOVERNANCE_OFFICER`, `EXECUTIVE`).
- Supports explicit decision approval, deferral, and versioned supersession (`supersedes_decision_id`, `superseded_by_id`, `superseded_reason`).

#### 2.5 Action Commitments, Verification & Escalation
- Deploys actionable follow-through commitments (`ManagementCommitmentRecord`) linked to approved decisions.
- Enforces separate designations for `responsible_owner_id` (action executor) and `accountable_lead_id` (executive oversight).
- Progress monitoring with detailed audit notes and completion evidence references.
- Two-stage verification: `submit_verification` -> `verify_commitment` by authorized verifiers.
- Executive escalation: Overdue or obstructed commitments can be escalated with documented urgency and justification (`CommitmentEscalationRecord`).

#### 2.6 Previous Actions Reconciliation & Controlled Closure
- Analyzes previous reviews under the same programme to reconcile prior commitments and evaluate whether historical decisions achieved their intended goals.
- Generates comprehensive management review reports (`ManagementReviewReportRecord`) detailing attendees, agenda, decisions, commitments, and reconciliation.
- Review closure gating (`check_closure_readiness`):
  1. Agenda topics concluded or deferred.
  2. Decisions formalized.
  3. Commitments assigned.
  4. Review report approved.
- Completed reviews can be reopened (`reopen_review`) into `FOLLOW_UP` state with documented justification.

---

### 3. REST API Endpoint Mapping

Base Path: `/api/v1/governance-management-reviews`

| Method | Path | Description |
|---|---|---|
| `GET` | `/analytics/overview` | Executive metrics, status distributions, and conformance rate |
| `POST` | `/programmes` | Create review programme |
| `GET` | `/programmes` | List programmes |
| `GET` | `/programmes/{programme_id}` | Get programme by ID |
| `PUT` | `/programmes/{programme_id}` | Update programme |
| `POST` | `/programmes/{programme_id}/approve` | Formally approve programme |
| `POST` | `/reviews` | Create review meeting |
| `GET` | `/reviews` | List reviews |
| `GET` | `/reviews/{review_id}` | Get review by ID |
| `PUT` | `/reviews/{review_id}` | Update review |
| `POST` | `/reviews/{review_id}/schedule` | Advance review to SCHEDULED |
| `POST` | `/reviews/{review_id}/reschedule` | Reschedule or postpone review |
| `POST` | `/reviews/{review_id}/cancel` | Cancel review |
| `POST` | `/reviews/{review_id}/start` | Transition review to IN_PROGRESS |
| `GET` | `/reviews/{review_id}/readiness` | Check review prerequisites and quorum |
| `GET` | `/reviews/{review_id}/closure-check` | Verify closure prerequisites |
| `POST` | `/reviews/{review_id}/close` | Formally close review |
| `POST` | `/reviews/{review_id}/reopen` | Reopen completed review |
| `POST` | `/reviews/{review_id}/participants` | Add / invite participant |
| `GET` | `/reviews/{review_id}/participants` | List participants for review |
| `GET` | `/participants/{participant_id}` | Get participant by ID |
| `PUT` | `/participants/{participant_id}` | Update participant |
| `POST` | `/reviews/{review_id}/confirm-attendance` | Confirm attendance and declare conflicts |
| `POST` | `/reviews/{review_id}/agenda-items` | Add agenda topic |
| `GET` | `/reviews/{review_id}/agenda-items` | List agenda topics |
| `GET` | `/agenda-items/{agenda_item_id}` | Get agenda topic |
| `PUT` | `/agenda-items/{agenda_item_id}` | Update agenda topic |
| `DELETE` | `/agenda-items/{agenda_item_id}` | Delete agenda topic |
| `POST` | `/reviews/{review_id}/inputs/collect` | Index input from Phases 49–71 |
| `GET` | `/reviews/{review_id}/inputs` | List consolidated inputs |
| `POST` | `/reviews/{review_id}/packages/generate` | Compile review package |
| `GET` | `/reviews/{review_id}/packages` | List package versions |
| `GET` | `/packages/{package_id}` | Get package by ID |
| `POST` | `/packages/{package_id}/lock` | Lock package against changes |
| `POST` | `/reviews/{review_id}/discussions` | Record meeting discussion minutes |
| `GET` | `/reviews/{review_id}/discussions` | List meeting discussions |
| `POST` | `/reviews/{review_id}/decisions` | Record authoritative decision |
| `GET` | `/decisions` | List decisions |
| `GET` | `/decisions/{decision_id}` | Get decision by ID |
| `POST` | `/decisions/{decision_id}/approve` | Approve decision |
| `POST` | `/decisions/{decision_id}/defer` | Defer decision |
| `POST` | `/decisions/{decision_id}/supersede` | Supersede decision |
| `POST` | `/commitments` | Create follow-through commitment |
| `GET` | `/commitments` | List commitments |
| `GET` | `/commitments/{commitment_id}` | Get commitment by ID |
| `POST` | `/commitments/{commitment_id}/progress` | Update commitment progress |
| `POST` | `/commitments/{commitment_id}/submit-verification` | Submit commitment for verification |
| `POST` | `/commitments/{commitment_id}/verify` | Verify commitment implementation |
| `POST` | `/commitments/{commitment_id}/escalate` | Escalate overdue commitment |
| `GET` | `/commitments/{commitment_id}/escalations` | List escalations for commitment |
| `POST` | `/reviews/{review_id}/reports/generate` | Generate review summary report |
| `GET` | `/reviews/{review_id}/reports` | Get report for review |
| `GET` | `/reports/{report_id}` | Get report by ID |
| `POST` | `/reports/{report_id}/approve` | Approve review report |
| `POST` | `/reports/{report_id}/finalize` | Finalize review report |
| `GET` | `/reviews/{review_id}/reconcile-previous` | Reconcile prior decisions & commitments |
