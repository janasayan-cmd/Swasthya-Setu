# Phase 75: Governance Change Portfolio Oversight, Cross-Initiative Dependency Management & Cumulative Impact Coordination

## 1. Architectural Overview & Executive Summary

Phase 75 establishes a centralized, governed, and multi-tenant portfolio coordination layer for HealthSetu. It coordinates multiple approved clinical safety governance changes across organizational boundaries, departments, clinical facilities, teams, and routine operational workflows. 

While individual governance changes originate in Phase 72 (Management Review & Decisions), transition through Phase 73 (Decision Implementation & Commitment Verification), and are evaluated for adoption in Phase 74 (Governance Change Adoption & Operational Sustainability Monitoring), Phase 75 operates at the cross-initiative portfolio level to solve systemic multi-initiative challenges:
- **Visibility & Lineage**: Maintaining complete end-to-end traceability from each portfolio initiative back to authoritative Phase 72 management decisions and Phase 73 implementation milestones.
- **Dependency Topology**: Modeling cross-initiative dependencies (prerequisites, blocking relationships, shared resource dependencies) with cycle detection (preventing circular deadlocks).
- **Conflict Identification**: Automatically detecting scheduling overlaps, scope collisions, and resource contention across concurrently executing initiatives.
- **Cumulative Operational Impact**: Quantifying operational change burden (simultaneous workflow changes, training loads, facility disruptions) without conflating operational burden with clinical safety efficacy.
- **Escalation & Governance Alignment**: Routing cross-initiative issues to authoritative remediation workflows (Phase 54 Corrective Action, Phase 49 Incident Investigation, Phase 63 Risk Register, Phase 67 Escalation) and packaging portfolio reviews for Phase 72 executive management referral.

---

## 2. Invariants & Clinical Safety Boundaries

1. **Portfolio Oversight is Coordination, Not Clinical Authority**:
   Phase 75 provides visibility, conflict detection, advisory sequencing, and cumulative burden analysis. It does **not** possess independent clinical governance authority to approve clinical policies or declare clinical workflows safe.
2. **Authoritative Record Integrity**:
   Phase 75 **never** overrides Phase 72 management decisions, modifies Phase 73 implementation records, replaces Phase 74 adoption assessments, replaces Phase 55 effectiveness verifications, or replaces Phase 63 risk dispositions.
3. **Signals vs. Clinical Findings**:
   Cross-initiative conflicts, dependency delays, and drift signals detected by portfolio algorithms are coordination flags requiring human review, not unilaterally declared clinical safety non-conformances.
4. **Advisory Sequencing**:
   Scheduling coordination assessments generate advisory sequencing recommendations; they do not unilaterally alter authoritative Phase 73 implementation target dates without authorized governance review.
5. **Operational Burden vs. Clinical Outcomes**:
   Cumulative impact assessments measure change friction, staff training hours, and concurrent workflow changes. They clearly disclaim any prediction of clinical treatment outcomes or patient safety efficacy.
6. **Separation of Duties**:
   A portfolio creator or designated lead cannot approve their own portfolio. Formal portfolio approval requires review by an authorized governance authority.

---

## 3. Core Domain Entities & Workflows

### 3.1 Governance Change Portfolio Lifecycle
```
[ DRAFT ] ────────► [ SUBMITTED ] ────────► [ APPROVED ] ────────► [ ACTIVE ]
    ▲                                           │                      │
    │ (Revisions)                               │ (Rejection)          ▼
    └───────────────────────────────────────────┴────────────── [ SUSPENDED ]
                                                                       │
                                                                       ▼
                                                                [ ARCHIVED ]
```
- **DRAFT**: Initial portfolio definition, boundary scoping, initiative grouping.
- **SUBMITTED**: Submitted for formal review.
- **APPROVED**: Approved by an independent governance authority (creator != approver).
- **ACTIVE**: Actively monitored; dependencies, conflicts, and cumulative impact are tracked.
- **SUSPENDED**: Temporarily halted due to critical systemic conflicts or organizational shifts.
- **ARCHIVED**: Formally retired with historical audit provenance preserved.

### 3.2 Portfolio Initiatives & Authoritative Lineage
Portfolio initiatives link directly to underlying operational records:
- `decision_id` (Phase 72 Management Decision)
- `implementation_id` (Phase 73 Implementation Record)
- `adoption_record_id` (Phase 74 Adoption Tracking Record, optional)

Each initiative tracks:
- Coordination status: `ON_TRACK`, `AT_RISK`, `DELAYED`, `BLOCKED`, `COMPLETED`, `WITHDRAWN`.
- Scope definitions (departments, clinical facilities, target roles).
- Timeline expectations (planned start, target completion).

### 3.3 Dependency Modeling & Cycle Detection
- Dependencies define relationships: `FINISH_TO_START`, `START_TO_START`, `RESOURCE_PREREQUISITE`, `ADOPTION_PREREQUISITE`.
- Directed Graph Traversal using Depth-First Search (DFS) ensures no circular dependencies are introduced (`CIRCULAR_INITIATIVE_DEPENDENCY_DETECTED`).
- Status lifecycle: `PROPOSED` ➔ `CONFIRMED` ➔ `RESOLVED` (or `DISPUTED`).
- Initiatives whose prerequisite initiatives are delayed or blocked are automatically marked as `BLOCKED`.

### 3.4 Cross-Initiative Conflict Detection & Management
- Automated scanning detects:
  - **Schedule Overlaps**: Overlapping deployment windows in the same department or facility.
  - **Scope Collisions**: Multiple initiatives altering identical clinical workflows, roles, or policies.
  - **Resource Contention**: Competing demand for shared subject-matter experts, training facilities, or compliance leads.
- Status lifecycle: `DETECTED` ➔ `UNDER_REVIEW` ➔ `DISPOSED` (or `DISMISSED`).
- Disposition strategies: `RESCHEDULE_INITIATIVE`, `SCOPE_DECONFLICT`, `RESOURCE_REALLOCATION`, `ACCEPT_CONCURRENT_RISK`, `ESCALATE_TO_MANAGEMENT`.

### 3.5 Cumulative Operational Impact Assessment
Aggregates operational friction metrics:
- Concurrent initiative counts per department and facility.
- Estimated total staff training hours required.
- Operational disruption score and qualitative rating (`LOW`, `MODERATE`, `HIGH`, `CRITICAL`).
- Mandatory clinical safety notice affirming that operational burden metrics do not measure clinical efficacy.

### 3.6 Cross-Initiative Issues & Formal Governance Review Referral
- Issues logged at the portfolio level can be routed to authoritative modules:
  - Phase 54: Corrective Action referral.
  - Phase 49: Clinical Safety Incident Investigation referral.
  - Phase 63: Clinical Safety Risk Register referral.
  - Phase 67: Cross-Workflow Escalation referral.
- Formal Portfolio Reviews package initiatives, open conflicts, and cumulative impacts.
- Approved portfolio reviews can be referred directly to Phase 72 Management Review agendas.

---

## 4. Multi-Tenant Architecture & Access Control
- All repository operations and services strictly filter by `tenant_id` (derived from `organization_id`).
- Role-Based Access Control (RBAC):
  - Authorized Roles: `ADMIN`, `CLINICAL_SAFETY_OFFICER`, `GOVERNANCE_LEAD`, `MANAGEMENT_REVIEWER`.
  - Prohibited Roles: `PATIENT` (rejection with HTTP 403 `INSUFFICIENT_PERMISSIONS`).
- Separation of duties strictly enforced in `approve_portfolio`.

---

## 5. Background Coordination Job
The `portfolio_coordination_background_service` runs periodically or on-demand:
1. Re-evaluates dependency graphs across all active portfolios.
2. Identifies newly blocked initiatives whose prerequisites have slipped.
3. Scans for undeclared scheduling overlaps and concurrent scope collisions.
4. Generates an auditable execution summary.
