# Phase 84: Database Dependencies & Relational Persistence Specification

## Notice for Database Engineering Teammate

In compliance with the **Strict Database Ownership Boundary**, this document specifies the proposed persistence structures required for **Phase 84: Clinical Safety Governance Organizational Resilience Capability Assessment, Competency Assurance & Operational Readiness Verification**.

The backend layer does **not** create or modify database tables, ORM models, schemas, migrations, indexes, constraints, foreign keys, triggers, or functions. All Phase 84 backend logic is currently backed by an isolated, thread-safe in-memory repository (`GovernanceResilienceCapabilityRepository`).

This document details the complete relational specification for the 10 entities when database migration is scheduled.

---

## 1. Entities Overview

| Entity Name | Primary Key | Business Purpose | Upstream Reference |
|---|---|---|---|
| `resilience_capability_frameworks` | `framework_id` (VARCHAR(64)) | Stores version-controlled capability frameworks, assessment dimensions, and required proficiencies | Standalone configuration |
| `role_capability_requirements` | `requirement_id` (VARCHAR(64)) | Stores role-to-capability competency mapping, primary/backup criteria, and required evidence | `resilience_capability_frameworks` |
| `resilience_capability_assessments` | `assessment_id` (VARCHAR(64)) | Tracks individual capability assessment lifecycles, evidence submissions, and independent verifications | Core Users, `resilience_capability_frameworks` |
| `capability_demonstration_records` | `demonstration_id` (VARCHAR(64)) | Stores practical demonstration observations (tabletops, simulated disruptions, recovery handoffs) | `resilience_capability_assessments`, Phase 81 Exercises |
| `team_resilience_readiness_records` | `team_assessment_id` (VARCHAR(64)) | Stores team and collective readiness evaluations without score averaging, highlighting vacancies | Facilities, Departments, Core Users |
| `delegated_authority_readiness_records` | `delegation_readiness_id` (VARCHAR(64)) | Evaluates emergency delegate operational preparedness without creating or altering legal authority | Core Users, Phase 80 Continuity |
| `resilience_capability_gaps` | `gap_id` (VARCHAR(64)) | Tracks evidence-based capability gaps, human validations, and Phase 54/63 referrals | Phase 54 CAPA, Phase 63 Risk |
| `operational_readiness_records` | `readiness_id` (VARCHAR(64)) | Stores multi-level operational readiness determinations and independent verifications | Facilities, Departments, Organizations |
| `capability_development_proposals` | `proposal_id` (VARCHAR(64)) | Manages targeted drills, knowledge reviews, and remediation proposals | Phase 83 Recommendations |
| `capability_reassessment_records` | `reassessment_id` (VARCHAR(64)) | Stores event-driven and scheduled reassessment triggers and historical outcomes | `resilience_capability_assessments` |

---

## 2. Table Specifications

### 2.1 `resilience_capability_frameworks`
- **Columns**:
  - `framework_id` VARCHAR(64) PRIMARY KEY
  - `tenant_id` VARCHAR(64) NOT NULL
  - `framework_name` VARCHAR(255) NOT NULL
  - `description` TEXT NOT NULL
  - `version` INT NOT NULL DEFAULT 1
  - `lifecycle_state` VARCHAR(32) NOT NULL DEFAULT 'DRAFT' -- DRAFT, SUBMITTED, APPROVED, PUBLISHED, SUPERSEDED, ARCHIVED
  - `capabilities_json` JSONB NOT NULL DEFAULT '[]'
  - `created_by` VARCHAR(64) NOT NULL
  - `submitted_by` VARCHAR(64) NULL
  - `approved_by` VARCHAR(64) NULL
  - `published_at` TIMESTAMPTZ NULL
  - `review_date` TIMESTAMPTZ NULL
  - `effective_date` TIMESTAMPTZ NULL
  - `disclaimer` TEXT NOT NULL
  - `created_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `updated_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
- **Indexes**:
  - `ix_rcf_tenant_state` (`tenant_id`, `lifecycle_state`)
  - `ix_rcf_tenant_version` (`tenant_id`, `framework_id`, `version`)

### 2.2 `role_capability_requirements`
- **Columns**:
  - `requirement_id` VARCHAR(64) PRIMARY KEY
  - `tenant_id` VARCHAR(64) NOT NULL
  - `role_name` VARCHAR(128) NOT NULL
  - `framework_id` VARCHAR(64) NOT NULL REFERENCES `resilience_capability_frameworks`(`framework_id`)
  - `framework_version` INT NOT NULL DEFAULT 1
  - `organizational_scope` VARCHAR(64) NOT NULL DEFAULT 'GLOBAL'
  - `required_capabilities_json` JSONB NOT NULL DEFAULT '[]'
  - `status` VARCHAR(32) NOT NULL DEFAULT 'DRAFT' -- DRAFT, APPROVED, SUPERSEDED
  - `created_by` VARCHAR(64) NOT NULL
  - `approved_by` VARCHAR(64) NULL
  - `disclaimer` TEXT NOT NULL
  - `created_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `updated_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
- **Indexes**:
  - `ix_rcr_tenant_role` (`tenant_id`, `role_name`)
  - `ix_rcr_tenant_framework` (`tenant_id`, `framework_id`)

### 2.3 `resilience_capability_assessments`
- **Columns**:
  - `assessment_id` VARCHAR(64) PRIMARY KEY
  - `tenant_id` VARCHAR(64) NOT NULL
  - `framework_id` VARCHAR(64) NOT NULL REFERENCES `resilience_capability_frameworks`(`framework_id`)
  - `framework_version` INT NOT NULL DEFAULT 1
  - `applicable_role` VARCHAR(128) NOT NULL
  - `subject_user_id` VARCHAR(64) NOT NULL
  - `assessor_id` VARCHAR(64) NULL
  - `verifier_id` VARCHAR(64) NULL
  - `lifecycle_state` VARCHAR(32) NOT NULL DEFAULT 'DRAFT'
  - `assessment_outcome` VARCHAR(32) NOT NULL DEFAULT 'INSUFFICIENT_EVIDENCE'
  - `evidence_references` JSONB NOT NULL DEFAULT '[]'
  - `criteria_evaluated` JSONB NOT NULL DEFAULT '[]'
  - `limitations` TEXT NULL
  - `reviewer_comments` TEXT NULL
  - `scheduled_date` TIMESTAMPTZ NULL
  - `assessed_at` TIMESTAMPTZ NULL
  - `verified_at` TIMESTAMPTZ NULL
  - `next_assessment_due` TIMESTAMPTZ NULL
  - `disclaimer` TEXT NOT NULL
  - `created_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `updated_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
- **Indexes**:
  - `ix_rca_tenant_subject` (`tenant_id`, `subject_user_id`)
  - `ix_rca_tenant_state` (`tenant_id`, `lifecycle_state`)
  - `ix_rca_next_due` (`tenant_id`, `next_assessment_due`)

### 2.4 `capability_demonstration_records`
- **Columns**:
  - `demonstration_id` VARCHAR(64) PRIMARY KEY
  - `tenant_id` VARCHAR(64) NOT NULL
  - `capability_id` VARCHAR(64) NOT NULL
  - `assessment_id` VARCHAR(64) NULL REFERENCES `resilience_capability_assessments`(`assessment_id`)
  - `scenario_reference` VARCHAR(64) NULL
  - `participant_user_id` VARCHAR(64) NULL
  - `team_reference` VARCHAR(64) NULL
  - `method` VARCHAR(64) NOT NULL
  - `expected_behavior` TEXT NOT NULL
  - `observed_behavior` TEXT NOT NULL
  - `evidence_references` JSONB NOT NULL DEFAULT '[]'
  - `outcome` VARCHAR(32) NOT NULL DEFAULT 'INCONCLUSIVE'
  - `review_status` VARCHAR(32) NOT NULL DEFAULT 'RECORDED'
  - `assessor_observations` TEXT NULL
  - `limitations` TEXT NULL
  - `reassessment_recommended` BOOLEAN NOT NULL DEFAULT FALSE
  - `recorded_by` VARCHAR(64) NOT NULL
  - `reviewed_by` VARCHAR(64) NULL
  - `demonstrated_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `disclaimer` TEXT NOT NULL
- **Indexes**:
  - `ix_cdr_tenant_capability` (`tenant_id`, `capability_id`)
  - `ix_cdr_participant` (`tenant_id`, `participant_user_id`)

### 2.5 `team_resilience_readiness_records`
- **Columns**:
  - `team_assessment_id` VARCHAR(64) PRIMARY KEY
  - `tenant_id` VARCHAR(64) NOT NULL
  - `team_name` VARCHAR(128) NOT NULL
  - `department_id` VARCHAR(64) NULL
  - `facility_id` VARCHAR(64) NULL
  - `framework_id` VARCHAR(64) NOT NULL REFERENCES `resilience_capability_frameworks`(`framework_id`)
  - `framework_version` INT NOT NULL DEFAULT 1
  - `role_coverage_json` JSONB NOT NULL DEFAULT '[]'
  - `critical_vacancies` JSONB NOT NULL DEFAULT '[]'
  - `backup_deficits` JSONB NOT NULL DEFAULT '[]'
  - `readiness_outcome` VARCHAR(64) NOT NULL DEFAULT 'NOT_ASSESSED'
  - `conditions_imposed` TEXT NULL
  - `limitations` TEXT NULL
  - `assessed_by` VARCHAR(64) NOT NULL
  - `assessed_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `disclaimer` TEXT NOT NULL
- **Indexes**:
  - `ix_trr_tenant_team` (`tenant_id`, `team_name`)
  - `ix_trr_outcome` (`tenant_id`, `readiness_outcome`)

### 2.6 `delegated_authority_readiness_records`
- **Columns**:
  - `delegation_readiness_id` VARCHAR(64) PRIMARY KEY
  - `tenant_id` VARCHAR(64) NOT NULL
  - `delegated_authority_reference` VARCHAR(64) NOT NULL
  - `delegate_user_id` VARCHAR(64) NOT NULL
  - `delegator_role` VARCHAR(128) NOT NULL
  - `authorized_scope` VARCHAR(128) NOT NULL
  - `delegation_valid_until` TIMESTAMPTZ NULL
  - `awareness_demonstrated` BOOLEAN NOT NULL DEFAULT FALSE
  - `documentation_capability_verified` BOOLEAN NOT NULL DEFAULT FALSE
  - `escalation_pathway_verified` BOOLEAN NOT NULL DEFAULT FALSE
  - `practical_scenario_demonstrated` BOOLEAN NOT NULL DEFAULT FALSE
  - `status` VARCHAR(64) NOT NULL DEFAULT 'INSUFFICIENT_EVIDENCE'
  - `limitations` TEXT NULL
  - `assessed_by` VARCHAR(64) NOT NULL
  - `assessed_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `disclaimer` TEXT NOT NULL
- **Indexes**:
  - `ix_dar_tenant_delegate` (`tenant_id`, `delegate_user_id`)
  - `ix_dar_status` (`tenant_id`, `status`)

### 2.7 `resilience_capability_gaps`
- **Columns**:
  - `gap_id` VARCHAR(64) PRIMARY KEY
  - `tenant_id` VARCHAR(64) NOT NULL
  - `category` VARCHAR(64) NOT NULL
  - `severity` VARCHAR(32) NOT NULL DEFAULT 'MEDIUM'
  - `title` VARCHAR(255) NOT NULL
  - `description` TEXT NOT NULL
  - `affected_capability_id` VARCHAR(64) NULL
  - `affected_role` VARCHAR(128) NULL
  - `affected_team_id` VARCHAR(64) NULL
  - `evidence_references` JSONB NOT NULL DEFAULT '[]'
  - `status` VARCHAR(32) NOT NULL DEFAULT 'DETECTED'
  - `identified_by` VARCHAR(64) NOT NULL
  - `validated_by` VARCHAR(64) NULL
  - `capa_referral_id` VARCHAR(64) NULL
  - `risk_referral_id` VARCHAR(64) NULL
  - `resolution_notes` TEXT NULL
  - `detected_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `validated_at` TIMESTAMPTZ NULL
  - `disclaimer` TEXT NOT NULL
- **Indexes**:
  - `ix_rcg_tenant_status` (`tenant_id`, `status`)
  - `ix_rcg_category` (`tenant_id`, `category`)

### 2.8 `operational_readiness_records`
- **Columns**:
  - `readiness_id` VARCHAR(64) PRIMARY KEY
  - `tenant_id` VARCHAR(64) NOT NULL
  - `scope_type` VARCHAR(32) NOT NULL -- ORGANIZATION, FACILITY, DEPARTMENT, TEAM
  - `scope_id` VARCHAR(64) NOT NULL
  - `framework_version` INT NOT NULL DEFAULT 1
  - `critical_unmet_requirements` JSONB NOT NULL DEFAULT '[]'
  - `unresolved_exceptions` JSONB NOT NULL DEFAULT '[]'
  - `outcome` VARCHAR(64) NOT NULL DEFAULT 'NOT_ASSESSED'
  - `conditions` TEXT NULL
  - `valid_until` TIMESTAMPTZ NULL
  - `assessor_id` VARCHAR(64) NOT NULL
  - `verifier_id` VARCHAR(64) NULL
  - `assessed_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `verified_at` TIMESTAMPTZ NULL
  - `disclaimer` TEXT NOT NULL
- **Indexes**:
  - `ix_orr_tenant_scope` (`tenant_id`, `scope_type`, `scope_id`)
  - `ix_orr_outcome` (`tenant_id`, `outcome`)

### 2.9 `capability_development_proposals`
- **Columns**:
  - `proposal_id` VARCHAR(64) PRIMARY KEY
  - `tenant_id` VARCHAR(64) NOT NULL
  - `linked_gap_id` VARCHAR(64) NULL REFERENCES `resilience_capability_gaps`(`gap_id`)
  - `target_capability_id` VARCHAR(64) NOT NULL
  - `target_role_or_team` VARCHAR(128) NOT NULL
  - `proposed_intervention` VARCHAR(64) NOT NULL
  - `rationalization` TEXT NOT NULL
  - `expected_improvement` TEXT NOT NULL
  - `assigned_owner` VARCHAR(64) NOT NULL
  - `target_completion_date` TIMESTAMPTZ NULL
  - `status` VARCHAR(32) NOT NULL DEFAULT 'PROPOSED'
  - `proposed_by` VARCHAR(64) NOT NULL
  - `approved_by` VARCHAR(64) NULL
  - `completion_evidence` TEXT NULL
  - `created_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `completed_at` TIMESTAMPTZ NULL
  - `disclaimer` TEXT NOT NULL
- **Indexes**:
  - `ix_cdp_tenant_status` (`tenant_id`, `status`)
  - `ix_cdp_owner` (`tenant_id`, `assigned_owner`)

### 2.10 `capability_reassessment_records`
- **Columns**:
  - `reassessment_id` VARCHAR(64) PRIMARY KEY
  - `tenant_id` VARCHAR(64) NOT NULL
  - `subject_type` VARCHAR(32) NOT NULL
  - `subject_id` VARCHAR(64) NOT NULL
  - `trigger_reason` VARCHAR(64) NOT NULL
  - `target_assessment_id` VARCHAR(64) NULL REFERENCES `resilience_capability_assessments`(`assessment_id`)
  - `notes` TEXT NULL
  - `status` VARCHAR(32) NOT NULL DEFAULT 'TRIGGERED'
  - `scheduled_date` TIMESTAMPTZ NULL
  - `completed_at` TIMESTAMPTZ NULL
  - `created_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `disclaimer` TEXT NOT NULL
- **Indexes**:
  - `ix_crr_tenant_status` (`tenant_id`, `status`)
  - `ix_crr_trigger` (`tenant_id`, `trigger_reason`)
