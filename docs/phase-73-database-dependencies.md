# Phase 73: Clinical Safety Governance Decision Implementation, Commitment Verification & Outcome Assurance
## Database Dependencies Specification

**Document Version:** 1.0.0  
**Phase:** 73 (Clinical Safety Governance Decision Implementation, Commitment Verification & Outcome Assurance)  
**Boundary:** Backend application layer contract requirements for the database team.  
**Notice:** Backend does NOT create migrations, alter schemas, or manage DDL. This document defines the exact PostgreSQL entities, fields, constraints, and indexes required by HealthSetu backend services.

---

### 1. Conceptual Architecture & Isolation Boundary

Phase 73 translates approved Phase 72 management decisions into authorized implementation initiatives, structured plans, milestones, evidence collection, independent verification, and outcome reconciliation.
- All entities are strictly isolated by `organization_id` and optionally `facility_id`.
- Complete versioning and historical traceability are preserved across plans, assignments, and verification.
- Foreign key linkages connect implementation records with Phase 72 decisions, reviews, and destination workflows (Phases 49, 54, 55, 63, 67, 69, 70).

---

### 2. Required Database Entities

#### 2.1 Table: `decision_intakes`
Stores ingested approved decisions from Phase 72 and eligibility verification records.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `intake_id` | VARCHAR(64) | PRIMARY KEY | Unique identifier (`gdit-uuid`) |
| `decision_id` | VARCHAR(64) | NOT NULL, INDEXED | Foreign key to `management_decisions` |
| `source_review_id` | VARCHAR(64) | NOT NULL, INDEXED | Foreign key to `management_reviews` |
| `decision_version` | INTEGER | NOT NULL DEFAULT 1 | Version of ingested decision |
| `decision_title` | VARCHAR(255) | NOT NULL | Title of decision |
| `decision_category` | VARCHAR(64) | NOT NULL | Decision category |
| `decision_rationale` | TEXT | NOT NULL | Decision rationale |
| `decided_by_id` | VARCHAR(64) | NOT NULL | Authoritative decider ID |
| `decided_by_role` | VARCHAR(64) | NOT NULL | Decider role |
| `decided_at` | TIMESTAMPTZ | NOT NULL | Timestamp decision was made |
| `effective_date` | TIMESTAMPTZ | NULLABLE | Effective date |
| `supporting_evidence_refs` | JSONB | NOT NULL DEFAULT '[]' | Evidence artifact references |
| `assigned_management_owner` | VARCHAR(64) | NULLABLE | Designated management owner |
| `required_outcome` | TEXT | NOT NULL | Intended outcome |
| `conditions_and_limitations` | JSONB | NOT NULL DEFAULT '[]' | Stipulations and caveats |
| `supersession_status` | VARCHAR(32) | NOT NULL DEFAULT 'ACTIVE' | Status (`ACTIVE`, `SUPERSEDED`) |
| `intake_status` | VARCHAR(32) | NOT NULL, INDEXED | Status (`INTAKE_ACCEPTED`, `INTAKE_REJECTED`, `QUARANTINED`) |
| `rejection_reason` | TEXT | NULLABLE | Reason if rejected |
| `organization_id` | VARCHAR(64) | NOT NULL, INDEXED | Tenant isolation |
| `facility_id` | VARCHAR(64) | NULLABLE, INDEXED | Facility isolation |
| `ingested_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Ingestion timestamp |
| `ingested_by` | VARCHAR(64) | NOT NULL | Ingesting user ID |
| `metadata` | JSONB | NOT NULL DEFAULT '{}' | Extensible attributes |

#### 2.2 Table: `decision_implementations`
Stores central implementation initiatives linked to decisions.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `implementation_id` | VARCHAR(64) | PRIMARY KEY | Unique identifier (`gdim-uuid`) |
| `decision_id` | VARCHAR(64) | NOT NULL, INDEXED | Foreign key to `management_decisions` |
| `intake_id` | VARCHAR(64) | NOT NULL, INDEXED | Foreign key to `decision_intakes` |
| `title` | VARCHAR(255) | NOT NULL | Implementation title |
| `description` | TEXT | NOT NULL | Implementation description |
| `intended_outcome` | TEXT | NOT NULL | Target goal |
| `responsible_owner_id` | VARCHAR(64) | NOT NULL, INDEXED | Implementation lead user ID |
| `accountable_lead_id` | VARCHAR(64) | NOT NULL, INDEXED | Executive sponsor user ID |
| `supporting_teams` | JSONB | NOT NULL DEFAULT '[]' | Collaborating clinical/technical units |
| `category` | VARCHAR(64) | NOT NULL, INDEXED | Implementation category enum |
| `priority` | VARCHAR(32) | NOT NULL, INDEXED | Priority enum (`CRITICAL`, `HIGH`, etc.) |
| `status` | VARCHAR(32) | NOT NULL, INDEXED | Lifecycle status enum |
| `target_completion_date` | TIMESTAMPTZ | NOT NULL, INDEXED | Target delivery date |
| `actual_completion_date` | TIMESTAMPTZ | NULLABLE | Actual closure timestamp |
| `required_approvals` | JSONB | NOT NULL DEFAULT '[]' | List of required approval roles |
| `closure_conditions` | JSONB | NOT NULL DEFAULT '[]' | Specific criteria for closure |
| `organization_id` | VARCHAR(64) | NOT NULL, INDEXED | Tenant isolation |
| `facility_id` | VARCHAR(64) | NULLABLE, INDEXED | Facility isolation |
| `created_by` | VARCHAR(64) | NOT NULL | Creator user ID |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Creation timestamp |
| `updated_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Last update timestamp |
| `metadata` | JSONB | NOT NULL DEFAULT '{}' | Extensible attributes |

#### 2.3 Table: `implementation_plans`
Stores versioned implementation plans.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `plan_id` | VARCHAR(64) | PRIMARY KEY | Unique identifier (`gdipl-uuid`) |
| `implementation_id` | VARCHAR(64) | NOT NULL, INDEXED | Foreign key to `decision_implementations` |
| `version` | INTEGER | NOT NULL | Monotonically increasing version |
| `objectives` | JSONB | NOT NULL DEFAULT '[]' | Structured plan objectives |
| `work_items` | JSONB | NOT NULL DEFAULT '[]' | Breakdown of work items |
| `target_dates` | JSONB | NOT NULL DEFAULT '{}' | Schedule of milestones and deliverables |
| `expected_evidence` | JSONB | NOT NULL DEFAULT '[]' | Expected evidence artifacts |
| `verification_criteria` | JSONB | NOT NULL DEFAULT '[]' | Criteria for independent verification |
| `completion_conditions` | JSONB | NOT NULL DEFAULT '[]' | Completion rules |
| `approval_status` | VARCHAR(32) | NOT NULL, INDEXED | Status (`DRAFT`, `APPROVED`, etc.) |
| `approved_by` | VARCHAR(64) | NULLABLE | Approver user ID |
| `approved_at` | TIMESTAMPTZ | NULLABLE | Approval timestamp |
| `change_reason` | TEXT | NULLABLE | Justification for new version |
| `is_active` | BOOLEAN | NOT NULL DEFAULT TRUE, INDEXED | Active version flag |
| `created_by` | VARCHAR(64) | NOT NULL | Creator user ID |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Creation timestamp |
| `updated_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Last update timestamp |
| `metadata` | JSONB | NOT NULL DEFAULT '{}' | Extensible attributes |

#### 2.4 Table: `implementation_assignments`
Stores ownership assignments, acceptance tracking, and separation of duties records.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `assignment_id` | VARCHAR(64) | PRIMARY KEY | Unique identifier (`gdas-uuid`) |
| `implementation_id` | VARCHAR(64) | NOT NULL, INDEXED | Foreign key to `decision_implementations` |
| `user_id` | VARCHAR(64) | NOT NULL, INDEXED | Assigned user ID |
| `user_name` | VARCHAR(255) | NULLABLE | User display name |
| `role` | VARCHAR(64) | NOT NULL, INDEXED | Functional role enum |
| `acceptance_status` | VARCHAR(32) | NOT NULL, INDEXED | Status (`PENDING`, `ACCEPTED`, `DECLINED`, `DELEGATED`) |
| `delegated_to_id` | VARCHAR(64) | NULLABLE | User ID if delegated |
| `scope_of_responsibility` | TEXT | NOT NULL | Ownership scope |
| `assigned_by` | VARCHAR(64) | NOT NULL | Assigning user ID |
| `assigned_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Assignment timestamp |
| `accepted_at` | TIMESTAMPTZ | NULLABLE | Acceptance timestamp |
| `metadata` | JSONB | NOT NULL DEFAULT '{}' | Extensible attributes |

#### 2.5 Table: `implementation_dependencies`
Stores prerequisites, external workflow dependencies, and authorized waivers.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `dependency_id` | VARCHAR(64) | PRIMARY KEY | Unique identifier (`gddp-uuid`) |
| `implementation_id` | VARCHAR(64) | NOT NULL, INDEXED | Foreign key to `decision_implementations` |
| `dependency_type` | VARCHAR(64) | NOT NULL | Dependency type enum |
| `source_workflow` | VARCHAR(64) | NOT NULL, INDEXED | Originating workflow |
| `source_record_id` | VARCHAR(64) | NOT NULL, INDEXED | Prerequisite record identifier |
| `required_state` | VARCHAR(64) | NOT NULL DEFAULT 'COMPLETED' | Required prerequisite status |
| `status` | VARCHAR(32) | NOT NULL, INDEXED | Dependency status enum |
| `responsible_owner_id` | VARCHAR(64) | NULLABLE | Owner responsible for satisfying dependency |
| `blocking_reason` | TEXT | NULLABLE | Explanation if blocked or failed |
| `waiver_authorized_by` | VARCHAR(64) | NULLABLE | Authorizing role user ID |
| `waiver_rationale` | TEXT | NULLABLE | Justification for waiver |
| `waived_at` | TIMESTAMPTZ | NULLABLE | Waiver timestamp |
| `last_verified_at` | TIMESTAMPTZ | NULLABLE | Last reconciliation timestamp |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Creation timestamp |
| `metadata` | JSONB | NOT NULL DEFAULT '{}' | Extensible attributes |

#### 2.6 Table: `implementation_milestones`
Stores individual implementation milestones.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `milestone_id` | VARCHAR(64) | PRIMARY KEY | Unique identifier (`gdms-uuid`) |
| `implementation_id` | VARCHAR(64) | NOT NULL, INDEXED | Foreign key to `decision_implementations` |
| `title` | VARCHAR(255) | NOT NULL | Milestone title |
| `description` | TEXT | NOT NULL | Description |
| `responsible_owner_id` | VARCHAR(64) | NOT NULL, INDEXED | Responsible owner user ID |
| `start_date` | TIMESTAMPTZ | NULLABLE | Planned start |
| `target_date` | TIMESTAMPTZ | NOT NULL, INDEXED | Planned due date |
| `completion_date` | TIMESTAMPTZ | NULLABLE | Actual completion date |
| `status` | VARCHAR(32) | NOT NULL, INDEXED | Milestone status enum |
| `expected_output` | TEXT | NOT NULL | Tangible output description |
| `required_evidence_types` | JSONB | NOT NULL DEFAULT '[]' | List of required evidence categories |
| `dependency_ids` | JSONB | NOT NULL DEFAULT '[]' | Prerequisite milestone/dependency IDs |
| `submission_notes` | TEXT | NULLABLE | Owner completion notes |
| `submitted_at` | TIMESTAMPTZ | NULLABLE | Submission timestamp |
| `verification_status` | VARCHAR(32) | NOT NULL DEFAULT 'UNVERIFIED' | Verification state |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Creation timestamp |
| `updated_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Last update timestamp |
| `metadata` | JSONB | NOT NULL DEFAULT '{}' | Extensible attributes |

#### 2.7 Table: `implementation_evidence`
Stores referenced evidence artifacts and review status.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `evidence_id` | VARCHAR(64) | PRIMARY KEY | Unique identifier (`gdev-uuid`) |
| `implementation_id` | VARCHAR(64) | NOT NULL, INDEXED | Foreign key to `decision_implementations` |
| `milestone_id` | VARCHAR(64) | NULLABLE, INDEXED | Optional link to milestone |
| `source_record_ref` | VARCHAR(255) | NOT NULL | Reference to external evidence record |
| `evidence_type` | VARCHAR(64) | NOT NULL | Type of evidence |
| `version` | VARCHAR(32) | NOT NULL DEFAULT '1.0' | Artifact version |
| `owner_id` | VARCHAR(64) | NOT NULL | Submitting user ID |
| `submitted_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Submission timestamp |
| `access_classification` | VARCHAR(32) | NOT NULL DEFAULT 'STANDARD' | Data classification |
| `review_status` | VARCHAR(32) | NOT NULL DEFAULT 'PENDING_REVIEW' | Review status (`ACCEPTED`, etc.) |
| `reviewed_by` | VARCHAR(64) | NULLABLE | Reviewer user ID |
| `review_comments` | TEXT | NULLABLE | Review findings |
| `metadata` | JSONB | NOT NULL DEFAULT '{}' | Extensible attributes |

#### 2.8 Table: `implementation_verifications`
Stores independent verification checks and outcomes.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `verification_id` | VARCHAR(64) | PRIMARY KEY | Unique identifier (`gdvr-uuid`) |
| `implementation_id` | VARCHAR(64) | NOT NULL, INDEXED | Foreign key to `decision_implementations` |
| `milestone_id` | VARCHAR(64) | NULLABLE, INDEXED | Link to verified milestone |
| `verification_criteria` | JSONB | NOT NULL DEFAULT '[]' | Evaluated criteria |
| `evidence_reviewed` | JSONB | NOT NULL DEFAULT '[]' | Referenced evidence IDs |
| `outcome` | VARCHAR(32) | NOT NULL, INDEXED | Outcome enum (`VERIFIED`, `REJECTED`, etc.) |
| `verifier_id` | VARCHAR(64) | NOT NULL, INDEXED | Verifying user ID |
| `verifier_role` | VARCHAR(64) | NOT NULL | Verifier role |
| `verified_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Verification timestamp |
| `rationale` | TEXT | NOT NULL | Verification justification |
| `outstanding_deficiencies` | JSONB | NOT NULL DEFAULT '[]' | Deficiencies found |
| `required_remediation` | TEXT | NULLABLE | Corrective remediation required |
| `metadata` | JSONB | NOT NULL DEFAULT '{}' | Extensible attributes |

#### 2.9 Table: `workflow_handoffs`
Stores delegation records to authoritative destination workflows.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `handoff_id` | VARCHAR(64) | PRIMARY KEY | Unique identifier (`gdho-uuid`) |
| `implementation_id` | VARCHAR(64) | NOT NULL, INDEXED | Foreign key to `decision_implementations` |
| `destination_workflow` | VARCHAR(64) | NOT NULL, INDEXED | Workflow enum (`PHASE_54_CAPA`, etc.) |
| `destination_record_id` | VARCHAR(64) | NULLABLE, INDEXED | ID in destination workflow |
| `requested_outcome` | TEXT | NOT NULL | Outcome requested from destination |
| `responsible_owner_id` | VARCHAR(64) | NOT NULL | Delegated owner |
| `status` | VARCHAR(32) | NOT NULL, INDEXED | Handoff status enum |
| `latest_destination_status` | VARCHAR(64) | NULLABLE | Status in target workflow |
| `dispatched_at` | TIMESTAMPTZ | NULLABLE | Dispatch timestamp |
| `reconciled_at` | TIMESTAMPTZ | NULLABLE | Reconciliation timestamp |
| `retry_count` | INTEGER | NOT NULL DEFAULT 0 | Dispatch retry counter |
| `metadata` | JSONB | NOT NULL DEFAULT '{}' | Extensible attributes |

#### 2.10 Table: `outcome_assessments`
Stores formal reconciliation of delivered implementation against intended decision outcomes.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `assessment_id` | VARCHAR(64) | PRIMARY KEY | Unique identifier (`gdoa-uuid`) |
| `implementation_id` | VARCHAR(64) | NOT NULL, INDEXED | Foreign key to `decision_implementations` |
| `decision_id` | VARCHAR(64) | NOT NULL, INDEXED | Foreign key to `management_decisions` |
| `state` | VARCHAR(32) | NOT NULL, INDEXED | Outcome state enum (`OUTCOME_ACHIEVED`, etc.) |
| `rationale` | TEXT | NOT NULL | Outcome justification |
| `supporting_evidence_refs` | JSONB | NOT NULL DEFAULT '[]' | Evidence references |
| `destination_workflow_outcome` | JSONB | NOT NULL DEFAULT '{}' | Results from destination engines |
| `remaining_limitations` | JSONB | NOT NULL DEFAULT '[]' | Unresolved caveats or limitations |
| `unresolved_dependencies` | JSONB | NOT NULL DEFAULT '[]' | Pending prerequisites |
| `assessed_by` | VARCHAR(64) | NOT NULL | Assessing user ID |
| `assessed_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Assessment timestamp |
| `metadata` | JSONB | NOT NULL DEFAULT '{}' | Extensible attributes |

#### 2.11 Table: `implementation_exceptions`
Stores exceptions and Phase 67 escalation references.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `exception_id` | VARCHAR(64) | PRIMARY KEY | Unique identifier (`gdex-uuid`) |
| `implementation_id` | VARCHAR(64) | NOT NULL, INDEXED | Foreign key to `decision_implementations` |
| `decision_id` | VARCHAR(64) | NOT NULL, INDEXED | Foreign key to `management_decisions` |
| `category` | VARCHAR(64) | NOT NULL, INDEXED | Exception category enum |
| `description` | TEXT | NOT NULL | Description of exception |
| `priority` | VARCHAR(32) | NOT NULL DEFAULT 'HIGH' | Priority tier |
| `owner_id` | VARCHAR(64) | NOT NULL | Responsible owner |
| `detection_timestamp` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Detection timestamp |
| `escalation_reference_id` | VARCHAR(64) | NULLABLE, INDEXED | Link to Phase 67 escalation |
| `resolution_reference` | TEXT | NULLABLE | Resolution reference |
| `resolved_at` | TIMESTAMPTZ | NULLABLE | Resolution timestamp |
| `metadata` | JSONB | NOT NULL DEFAULT '{}' | Extensible attributes |

#### 2.12 Table: `decision_change_impacts`
Stores impact analysis and authorized dispositions when a Phase 72 decision is amended or superseded.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `impact_id` | VARCHAR(64) | PRIMARY KEY | Unique identifier (`gdci-uuid`) |
| `implementation_id` | VARCHAR(64) | NOT NULL, INDEXED | Foreign key to `decision_implementations` |
| `decision_id` | VARCHAR(64) | NOT NULL, INDEXED | Foreign key to `management_decisions` |
| `previous_decision_status` | VARCHAR(32) | NOT NULL | Prior status |
| `new_decision_status` | VARCHAR(32) | NOT NULL | New status |
| `superseded_by_decision_id` | VARCHAR(64) | NULLABLE, INDEXED | Superseding decision ID |
| `impacted_milestones` | JSONB | NOT NULL DEFAULT '[]' | Affected milestone IDs |
| `impacted_dependencies` | JSONB | NOT NULL DEFAULT '[]' | Affected dependency IDs |
| `impacted_handoffs` | JSONB | NOT NULL DEFAULT '[]' | Affected handoff IDs |
| `recommended_disposition` | VARCHAR(32) | NOT NULL | Recommended action (`CONTINUE`, etc.) |
| `disposition_decision` | VARCHAR(32) | NULLABLE | Authorized decision |
| `disposition_authorized_by` | VARCHAR(64) | NULLABLE | Authorizing user ID |
| `reviewed_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Review timestamp |
| `metadata` | JSONB | NOT NULL DEFAULT '{}' | Extensible attributes |

#### 2.13 Table: `implementation_reports`
Stores executive oversight reports.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `report_id` | VARCHAR(64) | PRIMARY KEY | Unique identifier (`gdrp-uuid`) |
| `report_type` | VARCHAR(32) | NOT NULL | `OVERVIEW`, `OVERDUE`, `OUTCOMES` |
| `reporting_period` | VARCHAR(64) | NOT NULL | Reporting period |
| `title` | VARCHAR(255) | NOT NULL | Report title |
| `executive_summary` | TEXT | NOT NULL | Executive brief |
| `metrics` | JSONB | NOT NULL DEFAULT '{}' | Aggregated oversight metrics |
| `generated_by` | VARCHAR(64) | NOT NULL | Generator user ID |
| `generated_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Generation timestamp |
| `metadata` | JSONB | NOT NULL DEFAULT '{}' | Extensible attributes |
