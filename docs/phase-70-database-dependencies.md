# Phase 70: Independent Clinical Safety Governance Audit Management
## Database Dependencies Specification

**Document Version:** 1.0.0  
**Phase:** 70 (Independent Clinical Safety Governance Audit Planning, Execution, Findings & Follow-Up Management)  
**Boundary:** Backend application layer contract requirements for the database team.  
**Notice:** Backend does NOT create migrations, alter schemas, or manage DDL. This document defines the exact PostgreSQL entities, fields, constraints, and indexes required by HealthSetu backend services.

---

### 1. Conceptual Architecture & Isolation Boundary

Phase 70 manages the independent audit lifecycle that evaluates clinical safety governance processes, controls, evidence, and compliance across HealthSetu.
- Entities are tenant-isolated via `organization_id` and optionally `facility_id`.
- Complete versioning, auditor independence records, scope changes, execution evidence, findings, auditee responses, reports, and follow-up links are immutably preserved.
- Separation of duties is strictly enforced: an auditor cannot verify their own independence, and an author cannot approve their own audit report.

---

### 2. Required Database Entities

#### 2.1 Table: `audit_programmes`
Stores strategic clinical safety governance audit programmes.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `programme_id` | VARCHAR(64) | PRIMARY KEY | Unique identifier (`gprg-uuid`) |
| `name` | VARCHAR(255) | NOT NULL | Programme title |
| `description` | TEXT | NOT NULL | Programme charter and context |
| `objectives` | JSONB | NOT NULL DEFAULT '[]' | High-level governance objectives |
| `category` | VARCHAR(64) | NOT NULL, INDEXED | Programme category enum |
| `priority` | VARCHAR(32) | NOT NULL, INDEXED | Priority tier enum |
| `status` | VARCHAR(32) | NOT NULL, INDEXED | Programme status enum |
| `organization_id` | VARCHAR(64) | NOT NULL, INDEXED | Tenant isolation |
| `facility_id` | VARCHAR(64) | NULLABLE, INDEXED | Facility isolation |
| `responsible_owner_id` | VARCHAR(64) | NOT NULL | Governance lead user ID |
| `responsible_owner_role` | VARCHAR(64) | NOT NULL | Role of responsible owner |
| `planned_start_date` | TIMESTAMPTZ | NULLABLE | Planned start |
| `planned_end_date` | TIMESTAMPTZ | NULLABLE | Planned completion |
| `related_framework_ids` | JSONB | NOT NULL DEFAULT '[]' | Associated Phase 69 framework IDs |
| `approved_by` | VARCHAR(64) | NULLABLE | Governance approver user ID |
| `approved_at` | TIMESTAMPTZ | NULLABLE | Approval timestamp |
| `approval_rationale` | TEXT | NULLABLE | Governance approval rationale |
| `created_by` | VARCHAR(64) | NOT NULL | Creator user ID |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Creation timestamp |
| `updated_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Last update timestamp |
| `metadata` | JSONB | NOT NULL DEFAULT '{}' | Extensible attributes |

#### 2.2 Table: `clinical_safety_audits`
Stores individual safety governance audits conducted under programmes.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `audit_id` | VARCHAR(64) | PRIMARY KEY | Unique identifier (`gaud-uuid`) |
| `programme_id` | VARCHAR(64) | NOT NULL, FK to `audit_programmes`, INDEXED | Parent programme ID |
| `title` | VARCHAR(255) | NOT NULL | Audit title |
| `description` | TEXT | NOT NULL | Scope overview and context |
| `category` | VARCHAR(64) | NOT NULL, INDEXED | Audit category enum |
| `priority` | VARCHAR(32) | NOT NULL, INDEXED | Priority enum |
| `lifecycle_status` | VARCHAR(32) | NOT NULL, INDEXED | 12-state lifecycle enum |
| `organization_id` | VARCHAR(64) | NOT NULL, INDEXED | Tenant isolation |
| `facility_id` | VARCHAR(64) | NULLABLE, INDEXED | Facility isolation |
| `lead_auditor_id` | VARCHAR(64) | NULLABLE, INDEXED | Appointed lead auditor |
| `scope_id` | VARCHAR(64) | NULLABLE | Approved scope reference |
| `planned_start_date` | TIMESTAMPTZ | NULLABLE | Planned start timestamp |
| `planned_end_date` | TIMESTAMPTZ | NULLABLE | Planned end timestamp |
| `actual_start_date` | TIMESTAMPTZ | NULLABLE | Execution start timestamp |
| `actual_end_date` | TIMESTAMPTZ | NULLABLE | Actual completion timestamp |
| `closure_rationale` | TEXT | NULLABLE | Formal closure justification |
| `cancellation_reason` | TEXT | NULLABLE | Justification if cancelled |
| `paused_reason` | TEXT | NULLABLE | Justification if paused |
| `created_by` | VARCHAR(64) | NOT NULL | Creator user ID |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Creation timestamp |
| `updated_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Last update timestamp |
| `metadata` | JSONB | NOT NULL DEFAULT '{}' | Extensible attributes |

#### 2.3 Table: `audit_scopes`
Stores formal boundaries, inclusions, exclusions, and amendments for an audit.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `scope_id` | VARCHAR(64) | PRIMARY KEY | Unique identifier (`gscp-uuid`) |
| `audit_id` | VARCHAR(64) | NOT NULL, FK to `clinical_safety_audits`, INDEXED | Associated audit |
| `version` | INT | NOT NULL DEFAULT 1 | Scope version number |
| `status` | VARCHAR(32) | NOT NULL, INDEXED | Scope status (DRAFT, APPROVED, FROZEN, AMENDED) |
| `included_governance_processes` | JSONB | NOT NULL DEFAULT '[]' | In-scope processes |
| `included_safety_controls` | JSONB | NOT NULL DEFAULT '[]' | In-scope safety controls |
| `included_compliance_requirements` | JSONB | NOT NULL DEFAULT '[]' | In-scope Phase 69 requirements |
| `included_workflow_phases` | JSONB | NOT NULL DEFAULT '[]' | In-scope workflow phases |
| `included_facilities` | JSONB | NOT NULL DEFAULT '[]' | In-scope facilities |
| `evaluation_period_start` | TIMESTAMPTZ | NULLABLE | Start of evaluated timeframe |
| `evaluation_period_end` | TIMESTAMPTZ | NULLABLE | End of evaluated timeframe |
| `scope_limitations` | JSONB | NOT NULL DEFAULT '[]' | Known limitations or constraints |
| `scope_exclusions` | JSONB | NOT NULL DEFAULT '[]' | Out-of-scope items with justifications |
| `is_frozen` | BOOLEAN | NOT NULL DEFAULT FALSE | True if execution started |
| `frozen_at` | TIMESTAMPTZ | NULLABLE | Freeze timestamp |
| `frozen_by` | VARCHAR(64) | NULLABLE | User ID who froze scope |
| `approved_by` | VARCHAR(64) | NULLABLE | Approver user ID |
| `approved_at` | TIMESTAMPTZ | NULLABLE | Approval timestamp |
| `change_history` | JSONB | NOT NULL DEFAULT '[]' | Full version change log |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Creation timestamp |
| `updated_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Last update timestamp |
| `metadata` | JSONB | NOT NULL DEFAULT '{}' | Extensible attributes |

#### 2.4 Table: `auditor_assignments`
Stores auditor roster assignments and independent reviews.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `assignment_id` | VARCHAR(64) | PRIMARY KEY | Unique identifier (`gasn-uuid`) |
| `audit_id` | VARCHAR(64) | NOT NULL, FK to `clinical_safety_audits`, INDEXED | Associated audit |
| `auditor_id` | VARCHAR(64) | NOT NULL, INDEXED | Assigned user ID |
| `auditor_name` | VARCHAR(255) | NULLABLE | Auditor full name |
| `auditor_role` | VARCHAR(64) | NOT NULL | Functional role enum |
| `independence_status` | VARCHAR(64) | NOT NULL, INDEXED | Independence verification enum |
| `declared_conflicts` | JSONB | NOT NULL DEFAULT '[]' | Self-declared conflicts of interest |
| `conflict_mitigation` | TEXT | NULLABLE | Documented mitigation strategy |
| `independence_reviewed_by` | VARCHAR(64) | NULLABLE | Independent reviewer ID |
| `independence_reviewed_at` | TIMESTAMPTZ | NULLABLE | Review timestamp |
| `independence_review_rationale` | TEXT | NULLABLE | Review rationale |
| `assigned_by` | VARCHAR(64) | NOT NULL | Assigning user ID |
| `assigned_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Assignment timestamp |
| `is_active` | BOOLEAN | NOT NULL DEFAULT TRUE | Active flag |
| `reassignment_reason` | TEXT | NULLABLE | Reason if reassigned or deactivated |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Creation timestamp |
| `metadata` | JSONB | NOT NULL DEFAULT '{}' | Extensible attributes |

#### 2.5 Table: `audit_criteria`
Stores verifiable criteria mapped to Phase 69 frameworks and controls.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `criterion_id` | VARCHAR(64) | PRIMARY KEY | Unique identifier (`gcrt-uuid`) |
| `audit_id` | VARCHAR(64) | NOT NULL, FK to `clinical_safety_audits`, INDEXED | Associated audit |
| `criterion_code` | VARCHAR(64) | NOT NULL, INDEXED | Unique human-readable code |
| `title` | VARCHAR(255) | NOT NULL | Criterion title |
| `description` | TEXT | NOT NULL | Criterion details |
| `source_framework_id` | VARCHAR(64) | NULLABLE, INDEXED | Phase 69 framework reference |
| `source_requirement_id` | VARCHAR(64) | NULLABLE, INDEXED | Phase 69 requirement reference |
| `source_control_id` | VARCHAR(64) | NULLABLE | Control reference |
| `expected_evidence_description` | TEXT | NOT NULL | Expected supporting evidence |
| `sampling_strategy` | TEXT | NULLABLE | Prescribed sampling method |
| `is_active` | BOOLEAN | NOT NULL DEFAULT TRUE | Active flag |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Creation timestamp |
| `metadata` | JSONB | NOT NULL DEFAULT '{}' | Extensible attributes |

#### 2.6 Table: `audit_evidence_requests`
Stores formal evidence requests directed to auditees.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `request_id` | VARCHAR(64) | PRIMARY KEY | Unique identifier (`gevq-uuid`) |
| `audit_id` | VARCHAR(64) | NOT NULL, FK to `clinical_safety_audits`, INDEXED | Associated audit |
| `criterion_id` | VARCHAR(64) | NULLABLE, INDEXED | Linked criterion ID |
| `description` | TEXT | NOT NULL | Evidence requested |
| `responsible_auditee_id` | VARCHAR(64) | NOT NULL, INDEXED | Target auditee user ID |
| `responsible_auditee_role` | VARCHAR(64) | NOT NULL | Role of auditee |
| `requested_by` | VARCHAR(64) | NOT NULL | Auditor user ID |
| `requested_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Request timestamp |
| `due_date` | TIMESTAMPTZ | NULLABLE, INDEXED | Due date for submission |
| `status` | VARCHAR(32) | NOT NULL, INDEXED | Request lifecycle status |
| `submitted_evidence_refs` | JSONB | NOT NULL DEFAULT '[]' | Submitted evidence IDs |
| `auditee_notes` | TEXT | NULLABLE | Submission notes |
| `submission_timestamp` | TIMESTAMPTZ | NULLABLE | Submission timestamp |
| `review_outcome` | VARCHAR(32) | NULLABLE | ACCEPTED, REJECTED, PARTIALLY_ACCEPTED |
| `review_comments` | TEXT | NULLABLE | Auditor evaluation notes |
| `reviewed_by` | VARCHAR(64) | NULLABLE | Auditor reviewer ID |
| `reviewed_at` | TIMESTAMPTZ | NULLABLE | Review timestamp |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Creation timestamp |
| `metadata` | JSONB | NOT NULL DEFAULT '{}' | Extensible attributes |

#### 2.7 Table: `audit_tests`
Stores audit test procedures, sampling, observations, and results.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `test_id` | VARCHAR(64) | PRIMARY KEY | Unique identifier (`gtst-uuid`) |
| `audit_id` | VARCHAR(64) | NOT NULL, FK to `clinical_safety_audits`, INDEXED | Associated audit |
| `criterion_id` | VARCHAR(64) | NOT NULL, INDEXED | Criterion tested |
| `test_procedure` | TEXT | NOT NULL | Procedure steps |
| `sampling_approach` | VARCHAR(128) | NULLABLE | Sampling methodology |
| `sample_selection_reference` | TEXT | NULLABLE | Sample identifiers/records |
| `outcome` | VARCHAR(32) | NOT NULL, INDEXED | Outcome enum (PASSED, FAILED, INCONCLUSIVE, etc.) |
| `observations` | TEXT | NULLABLE | Auditor observations |
| `evidence_refs` | JSONB | NOT NULL DEFAULT '[]' | Supporting evidence citations |
| `auditor_notes` | TEXT | NULLABLE | Working notes |
| `executed_by` | VARCHAR(64) | NULLABLE | Auditor user ID |
| `executed_at` | TIMESTAMPTZ | NULLABLE | Execution timestamp |
| `reviewed_by` | VARCHAR(64) | NULLABLE | Peer/lead reviewer ID |
| `reviewed_at` | TIMESTAMPTZ | NULLABLE | Review timestamp |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Creation timestamp |
| `metadata` | JSONB | NOT NULL DEFAULT '{}' | Extensible attributes |

#### 2.8 Table: `audit_findings`
Stores audit observations, gaps, classifications, and CAPA links.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `finding_id` | VARCHAR(64) | PRIMARY KEY | Unique identifier (`gafd-uuid`) |
| `audit_id` | VARCHAR(64) | NOT NULL, FK to `clinical_safety_audits`, INDEXED | Associated audit |
| `criterion_id` | VARCHAR(64) | NULLABLE, INDEXED | Criterion reference |
| `test_id` | VARCHAR(64) | NULLABLE, INDEXED | Test reference |
| `category` | VARCHAR(64) | NOT NULL, INDEXED | Finding category enum |
| `severity` | VARCHAR(32) | NOT NULL, INDEXED | Severity tier enum |
| `status` | VARCHAR(32) | NOT NULL, INDEXED | Status enum |
| `finding_statement` | TEXT | NOT NULL | Core deficiency statement |
| `observed_condition` | TEXT | NOT NULL | Condition observed during audit |
| `expected_condition` | TEXT | NOT NULL | Standard or requirement expectation |
| `gap_description` | TEXT | NOT NULL | Analysis of variance |
| `potential_impact` | TEXT | NULLABLE | Impact on clinical safety |
| `evidence_refs` | JSONB | NOT NULL DEFAULT '[]' | Supporting evidence links |
| `responsible_owner_id` | VARCHAR(64) | NULLABLE | Auditee owner ID |
| `responsible_owner_role` | VARCHAR(64) | NULLABLE | Auditee owner role |
| `is_confirmed` | BOOLEAN | NOT NULL DEFAULT FALSE, INDEXED | Lead auditor confirmation |
| `confirmed_by` | VARCHAR(64) | NULLABLE | Confirming auditor ID |
| `confirmed_at` | TIMESTAMPTZ | NULLABLE | Confirmation timestamp |
| `is_disputed` | BOOLEAN | NOT NULL DEFAULT FALSE, INDEXED | Dispute flag |
| `dispute_rationale` | TEXT | NULLABLE | Auditee dispute explanation |
| `corrective_action_ref` | VARCHAR(64) | NULLABLE, INDEXED | Linked Phase 54 action ID |
| `phase55_eval_ref` | VARCHAR(64) | NULLABLE, INDEXED | Linked Phase 55 evaluation ID |
| `is_closed` | BOOLEAN | NOT NULL DEFAULT FALSE, INDEXED | Closure flag |
| `closed_by` | VARCHAR(64) | NULLABLE | User ID who closed finding |
| `closed_at` | TIMESTAMPTZ | NULLABLE | Closure timestamp |
| `closure_rationale` | TEXT | NULLABLE | Closure justification |
| `created_by` | VARCHAR(64) | NOT NULL | Auditor creator ID |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Creation timestamp |
| `updated_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Last update timestamp |
| `metadata` | JSONB | NOT NULL DEFAULT '{}' | Extensible attributes |

#### 2.9 Table: `auditee_responses`
Stores formal auditee responses and remediation proposals.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `response_id` | VARCHAR(64) | PRIMARY KEY | Unique identifier (`garp-uuid`) |
| `finding_id` | VARCHAR(64) | NOT NULL, FK to `audit_findings`, INDEXED | Associated finding |
| `auditee_id` | VARCHAR(64) | NOT NULL, INDEXED | Responding user ID |
| `auditee_role` | VARCHAR(64) | NOT NULL | Role of auditee |
| `response_type` | VARCHAR(32) | NOT NULL, INDEXED | ACCEPTED, DISPUTED, ACKNOWLEDGED |
| `response_statement` | TEXT | NOT NULL | Summary response |
| `explanation` | TEXT | NULLABLE | Detailed rationale |
| `supporting_evidence_refs` | JSONB | NOT NULL DEFAULT '[]' | Evidence supporting response |
| `proposed_corrective_action` | TEXT | NULLABLE | Proposed remediation |
| `proposed_completion_date` | TIMESTAMPTZ | NULLABLE | Target completion |
| `submitted_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Submission timestamp |
| `auditor_review_decision` | VARCHAR(32) | NULLABLE | ACCEPTED, REJECTED, CLARIFICATION_REQUIRED |
| `auditor_review_comments` | TEXT | NULLABLE | Auditor evaluation |
| `reviewed_by` | VARCHAR(64) | NULLABLE | Reviewing auditor ID |
| `reviewed_at` | TIMESTAMPTZ | NULLABLE | Review timestamp |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Creation timestamp |
| `metadata` | JSONB | NOT NULL DEFAULT '{}' | Extensible attributes |

#### 2.10 Table: `audit_reports`
Stores formal independent audit reports and governance approvals.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `report_id` | VARCHAR(64) | PRIMARY KEY | Unique identifier (`grpt-uuid`) |
| `audit_id` | VARCHAR(64) | NOT NULL, FK to `clinical_safety_audits`, INDEXED | Associated audit |
| `version` | INT | NOT NULL DEFAULT 1 | Report version number |
| `status` | VARCHAR(32) | NOT NULL, INDEXED | Report lifecycle enum |
| `title` | VARCHAR(255) | NOT NULL | Formal report title |
| `executive_summary` | TEXT | NOT NULL | Executive summary |
| `audit_period_start` | TIMESTAMPTZ | NULLABLE | Audit period start |
| `audit_period_end` | TIMESTAMPTZ | NULLABLE | Audit period end |
| `scope_summary` | TEXT | NOT NULL | Description of evaluated scope |
| `scope_limitations` | JSONB | NOT NULL DEFAULT '[]' | Documented limitations |
| `auditor_assignments_summary` | JSONB | NOT NULL DEFAULT '[]' | Summary of auditor roster |
| `independence_status_summary` | VARCHAR(64) | NOT NULL DEFAULT 'VERIFIED' | Independence status summary |
| `tests_performed_count` | INT | NOT NULL DEFAULT 0 | Count of executed tests |
| `tests_passed_count` | INT | NOT NULL DEFAULT 0 | Count of passed tests |
| `tests_failed_count` | INT | NOT NULL DEFAULT 0 | Count of failed tests |
| `tests_inconclusive_count` | INT | NOT NULL DEFAULT 0 | Count of inconclusive tests |
| `findings_summary` | JSONB | NOT NULL DEFAULT '{}' | Findings count by severity |
| `confirmed_finding_ids` | JSONB | NOT NULL DEFAULT '[]' | Confirmed finding IDs |
| `disputed_finding_ids` | JSONB | NOT NULL DEFAULT '[]' | Disputed finding IDs |
| `corrective_action_refs` | JSONB | NOT NULL DEFAULT '[]' | Linked Phase 54 actions |
| `audit_conclusion` | VARCHAR(64) | NOT NULL, INDEXED | Conclusion enum |
| `recommendations` | JSONB | NOT NULL DEFAULT '[]' | Recommendations |
| `created_by` | VARCHAR(64) | NOT NULL | Report author user ID |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Creation timestamp |
| `reviewed_by` | VARCHAR(64) | NULLABLE | Technical reviewer ID |
| `reviewed_at` | TIMESTAMPTZ | NULLABLE | Review timestamp |
| `review_comments` | TEXT | NULLABLE | Review comments |
| `approved_by` | VARCHAR(64) | NULLABLE | Governance approver ID |
| `approved_at` | TIMESTAMPTZ | NULLABLE | Approval timestamp |
| `approval_policy_ref` | VARCHAR(128) | NULLABLE | Policy basis for sign-off |
| `metadata` | JSONB | NOT NULL DEFAULT '{}' | Extensible attributes |

---

### 3. Recommended PostgreSQL Indexes

```sql
-- Indexes for Audit Programmes
CREATE INDEX idx_audit_prog_org_fac ON audit_programmes(organization_id, facility_id);
CREATE INDEX idx_audit_prog_status ON audit_programmes(status);

-- Indexes for Clinical Safety Audits
CREATE INDEX idx_audit_org_status ON clinical_safety_audits(organization_id, lifecycle_status);
CREATE INDEX idx_audit_prog_id ON clinical_safety_audits(programme_id);
CREATE INDEX idx_audit_lead_auditor ON clinical_safety_audits(lead_auditor_id);
CREATE INDEX idx_audit_planned_dates ON clinical_safety_audits(planned_start_date, planned_end_date);

-- Indexes for Audit Scopes
CREATE INDEX idx_audit_scope_audit_id ON audit_scopes(audit_id, version);
CREATE INDEX idx_audit_scope_status ON audit_scopes(status);

-- Indexes for Auditor Assignments
CREATE INDEX idx_auditor_asgn_audit_id ON auditor_assignments(audit_id, auditor_id);
CREATE INDEX idx_auditor_asgn_independence ON auditor_assignments(independence_status);

-- Indexes for Criteria
CREATE INDEX idx_audit_crit_audit_id ON audit_criteria(audit_id);
CREATE INDEX idx_audit_crit_code ON audit_criteria(criterion_code);

-- Indexes for Evidence Requests
CREATE INDEX idx_audit_ev_req_audit ON audit_evidence_requests(audit_id, status);
CREATE INDEX idx_audit_ev_req_auditee ON audit_evidence_requests(responsible_auditee_id);
CREATE INDEX idx_audit_ev_req_due ON audit_evidence_requests(due_date);

-- Indexes for Tests
CREATE INDEX idx_audit_tests_audit_id ON audit_tests(audit_id, outcome);
CREATE INDEX idx_audit_tests_crit ON audit_tests(criterion_id);

-- Indexes for Findings
CREATE INDEX idx_audit_find_audit_id ON audit_findings(audit_id, severity, status);
CREATE INDEX idx_audit_find_confirmed ON audit_findings(is_confirmed);
CREATE INDEX idx_audit_find_disputed ON audit_findings(is_disputed);
CREATE INDEX idx_audit_find_capa ON audit_findings(corrective_action_ref);

-- Indexes for Auditee Responses
CREATE INDEX idx_auditee_resp_finding ON auditee_responses(finding_id, response_type);

-- Indexes for Reports
CREATE INDEX idx_audit_rpt_audit_id ON audit_reports(audit_id, version);
CREATE INDEX idx_audit_rpt_status ON audit_reports(status);
```
