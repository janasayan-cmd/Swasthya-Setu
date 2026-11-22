# Phase 81: Database Dependencies & Relational Persistence Specification

## Notice for Database Engineering Teammate

In compliance with the **Strict Database Ownership Boundary**, this document specifies the proposed persistence structures required for **Phase 81: Clinical Safety Governance Resilience Validation, Continuity Exercise Assurance & Recovery Effectiveness Verification**.

The backend layer does **not** create or modify database tables, ORM models, schemas, migrations, indexes, constraints, foreign keys, triggers, or functions. All Phase 81 backend logic is currently backed by an isolated, thread-safe in-memory repository (`GovernanceContinuityAssuranceRepository`).

This document details the complete relational specification for the 11 entities when database migration is scheduled.

---

## 1. Entities Overview

| Entity Name | Primary Key | Business Purpose | Upstream Reference |
|---|---|---|---|
| `continuity_assurance_frameworks` | `framework_id` (VARCHAR(64)) | Stores version-controlled assurance frameworks and assessment dimensions | None (standalone configuration) |
| `continuity_plan_validations` | `validation_id` (VARCHAR(64)) | Stores controlled plan validation outcomes and criteria completeness evaluations | Phase 80 `governance_continuity_plans` |
| `continuity_coverage_assessments` | `assessment_id` (VARCHAR(64)) | Stores critical capability coverage assessments and identified coverage gaps | Phase 80 `governance_capabilities` |
| `continuity_exercise_evaluations` | `evaluation_id` (VARCHAR(64)) | Stores structured exercise evaluations distinguishing completion from operational effectiveness | Phase 80 `continuity_exercises` |
| `continuity_scenario_assessments` | `scenario_id` (VARCHAR(64)) | Stores advisory stress evaluations and disruption scenario coverage | Phase 80 `governance_capabilities` |
| `personnel_readiness_records` | `readiness_id` (VARCHAR(64)) | Stores personnel coverage, verified substitute authority, and separation of duties | Core User & Auth System |
| `dependency_resilience_records` | `assessment_id` (VARCHAR(64)) | Stores dependency resilience assessments, SPOFs, and alternative testing evidence | Phase 80 `governance_continuity_dependencies` |
| `recovery_performance_assessments` | `assessment_id` (VARCHAR(64)) | Stores recovery performance against approved RTO/MTPD targets and restoration stages | Phase 80 `governance_recovery_records` |
| `reconciliation_assurance_records` | `assurance_id` (VARCHAR(64)) | Stores reconciliation integrity evaluations, provenance validation, and conflict routing | Phase 80 `temporary_governance_decisions` |
| `independent_validation_programmes` | `programme_id` (VARCHAR(64)) | Stores independent validation reviews, evaluator assignments, and conflict-of-interest declarations | Phase 70 Audit Framework |
| `continuity_assurance_findings` | `finding_id` (VARCHAR(64)) | Stores structured findings, severities, and routing to CAPA, Risk, and Audit | Phase 54 CAPA, Phase 63 Risk, Phase 70 Audit |

---

## 2. Table Specifications

### 2.1 `continuity_assurance_frameworks`
- **Columns**:
  - `framework_id` VARCHAR(64) PRIMARY KEY
  - `framework_name` VARCHAR(255) NOT NULL
  - `description` TEXT NOT NULL
  - `version` INT NOT NULL DEFAULT 1
  - `status` VARCHAR(32) NOT NULL DEFAULT 'DRAFT' -- DRAFT, SUBMITTED, APPROVED, SUPERSEDED
  - `organizational_scope` VARCHAR(64) NOT NULL DEFAULT 'GLOBAL'
  - `dimensions_json` JSONB NOT NULL DEFAULT '[]'
  - `effective_date` TIMESTAMPTZ NULL
  - `review_date` TIMESTAMPTZ NULL
  - `scoring_method` VARCHAR(64) NOT NULL DEFAULT 'QUALITATIVE_TIERED'
  - `created_by` VARCHAR(64) NOT NULL
  - `created_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `submitted_by` VARCHAR(64) NULL
  - `submitted_at` TIMESTAMPTZ NULL
  - `approved_by` VARCHAR(64) NULL
  - `approved_at` TIMESTAMPTZ NULL
  - `approval_notes` TEXT NULL
  - `tenant_id` VARCHAR(64) NOT NULL DEFAULT 'default'
- **Indexes & Constraints**:
  - `idx_caf_tenant_status`: `(tenant_id, status)`
  - `chk_caf_status`: `status IN ('DRAFT', 'SUBMITTED', 'APPROVED', 'SUPERSEDED')`

### 2.2 `continuity_plan_validations`
- **Columns**:
  - `validation_id` VARCHAR(64) PRIMARY KEY
  - `plan_id` VARCHAR(64) NOT NULL -- References Phase 80 governance_continuity_plans
  - `plan_version` INT NOT NULL DEFAULT 1
  - `framework_version` INT NOT NULL DEFAULT 1
  - `review_scope` VARCHAR(128) NOT NULL
  - `validation_outcome` VARCHAR(64) NOT NULL DEFAULT 'UNABLE_TO_DETERMINE'
  - `review_status` VARCHAR(32) NOT NULL DEFAULT 'DRAFT'
  - `evaluated_criteria_json` JSONB NOT NULL DEFAULT '[]'
  - `missing_evidence_json` JSONB NOT NULL DEFAULT '[]'
  - `failed_criteria_json` JSONB NOT NULL DEFAULT '[]'
  - `unverified_criteria_json` JSONB NOT NULL DEFAULT '[]'
  - `observations_json` JSONB NOT NULL DEFAULT '[]'
  - `remediation_recommendations_json` JSONB NOT NULL DEFAULT '[]'
  - `limitations` TEXT NULL
  - `evaluated_by` VARCHAR(64) NOT NULL
  - `evaluated_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `reviewed_by` VARCHAR(64) NULL
  - `reviewed_at` TIMESTAMPTZ NULL
  - `tenant_id` VARCHAR(64) NOT NULL DEFAULT 'default'
- **Indexes & Constraints**:
  - `idx_cpv_tenant_plan`: `(tenant_id, plan_id)`
  - `idx_cpv_outcome`: `(tenant_id, validation_outcome)`

### 2.3 `continuity_coverage_assessments`
- **Columns**:
  - `assessment_id` VARCHAR(64) PRIMARY KEY
  - `scope_level` VARCHAR(64) NOT NULL DEFAULT 'GLOBAL'
  - `scope_id` VARCHAR(64) NULL
  - `assessed_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `assessed_by` VARCHAR(64) NOT NULL
  - `total_critical_capabilities` INT NOT NULL DEFAULT 0
  - `covered_capabilities_count` INT NOT NULL DEFAULT 0
  - `uncovered_capabilities_count` INT NOT NULL DEFAULT 0
  - `coverage_percentage` NUMERIC(5,2) NOT NULL DEFAULT 0.00
  - `summaries_json` JSONB NOT NULL DEFAULT '[]'
  - `detected_gaps_json` JSONB NOT NULL DEFAULT '[]'
  - `limitations` TEXT NULL
  - `tenant_id` VARCHAR(64) NOT NULL DEFAULT 'default'
- **Indexes**:
  - `idx_cca_tenant_assessed`: `(tenant_id, assessed_at DESC)`

### 2.4 `continuity_exercise_evaluations`
- **Columns**:
  - `evaluation_id` VARCHAR(64) PRIMARY KEY
  - `exercise_id` VARCHAR(64) NOT NULL -- References Phase 80 continuity_exercises
  - `exercise_type` VARCHAR(64) NOT NULL
  - `plan_id` VARCHAR(64) NOT NULL
  - `plan_version` INT NOT NULL DEFAULT 1
  - `evaluated_by` VARCHAR(64) NOT NULL
  - `evaluator_role` VARCHAR(128) NOT NULL
  - `evaluated_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `criteria_evaluations_json` JSONB NOT NULL DEFAULT '[]'
  - `review_outcome` VARCHAR(64) NOT NULL -- DEMONSTRATED_EFFECTIVE, PARTIALLY_EFFECTIVE, INEFFECTIVE, INCONCLUSIVE
  - `passed_count` INT NOT NULL DEFAULT 0
  - `failed_count` INT NOT NULL DEFAULT 0
  - `partially_demonstrated_count` INT NOT NULL DEFAULT 0
  - `untested_count` INT NOT NULL DEFAULT 0
  - `unable_to_determine_count` INT NOT NULL DEFAULT 0
  - `deviations_json` JSONB NOT NULL DEFAULT '[]'
  - `limitations` TEXT NULL
  - `follow_up_requirements_json` JSONB NOT NULL DEFAULT '[]'
  - `tenant_id` VARCHAR(64) NOT NULL DEFAULT 'default'
- **Indexes**:
  - `idx_cee_tenant_exercise`: `(tenant_id, exercise_id)`

### 2.5 `continuity_scenario_assessments`
- **Columns**:
  - `scenario_id` VARCHAR(64) PRIMARY KEY
  - `scenario_type` VARCHAR(64) NOT NULL
  - `scenario_title` VARCHAR(255) NOT NULL
  - `scenario_description` TEXT NOT NULL
  - `severity_level` VARCHAR(32) NOT NULL DEFAULT 'HIGH'
  - `affected_capability_ids_json` JSONB NOT NULL DEFAULT '[]'
  - `required_dependencies_json` JSONB NOT NULL DEFAULT '[]'
  - `assumptions_json` JSONB NOT NULL DEFAULT '[]'
  - `expected_continuity_response` TEXT NOT NULL
  - `expected_recovery_sequence_json` JSONB NOT NULL DEFAULT '[]'
  - `evaluation_outcome` VARCHAR(64) NOT NULL DEFAULT 'UNTESTED'
  - `actual_exercise_ref` VARCHAR(64) NULL
  - `identified_weaknesses_json` JSONB NOT NULL DEFAULT '[]'
  - `recommended_mitigations_json` JSONB NOT NULL DEFAULT '[]'
  - `limitations` TEXT NULL
  - `is_advisory_only` BOOLEAN NOT NULL DEFAULT TRUE
  - `created_by` VARCHAR(64) NOT NULL
  - `created_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `evaluated_by` VARCHAR(64) NULL
  - `evaluated_at` TIMESTAMPTZ NULL
  - `tenant_id` VARCHAR(64) NOT NULL DEFAULT 'default'
- **Indexes**:
  - `idx_csa_tenant_type`: `(tenant_id, scenario_type)`

### 2.6 `personnel_readiness_records`
- **Columns**:
  - `readiness_id` VARCHAR(64) PRIMARY KEY
  - `role_key` VARCHAR(128) NOT NULL
  - `role_name` VARCHAR(255) NOT NULL
  - `primary_owner_id` VARCHAR(64) NOT NULL
  - `approved_substitute_id` VARCHAR(64) NOT NULL
  - `organizational_scope` VARCHAR(64) NOT NULL DEFAULT 'GLOBAL'
  - `authority_source_doc_ref` VARCHAR(255) NOT NULL
  - `competency_evidence_ref` VARCHAR(255) NOT NULL
  - `readiness_status` VARCHAR(64) NOT NULL DEFAULT 'UNVERIFIED_AUTHORITY'
  - `authority_verified_valid` BOOLEAN NOT NULL DEFAULT FALSE
  - `delegation_expiration_date` TIMESTAMPTZ NULL
  - `separation_of_duties_verified` BOOLEAN NOT NULL DEFAULT FALSE
  - `last_exercise_participated_ref` VARCHAR(64) NULL
  - `outstanding_readiness_gaps_json` JSONB NOT NULL DEFAULT '[]'
  - `evaluated_by` VARCHAR(64) NOT NULL
  - `evaluated_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `verified_by` VARCHAR(64) NULL
  - `verified_at` TIMESTAMPTZ NULL
  - `tenant_id` VARCHAR(64) NOT NULL DEFAULT 'default'
- **Indexes**:
  - `idx_prr_tenant_role`: `(tenant_id, role_key)`

### 2.7 `dependency_resilience_records`
- **Columns**:
  - `assessment_id` VARCHAR(64) PRIMARY KEY
  - `dependency_id` VARCHAR(64) NOT NULL -- References Phase 80 governance_continuity_dependencies
  - `source_capability_id` VARCHAR(64) NOT NULL
  - `dependency_type` VARCHAR(64) NOT NULL
  - `criticality` VARCHAR(32) NOT NULL DEFAULT 'HIGH'
  - `has_alternative` BOOLEAN NOT NULL DEFAULT FALSE
  - `alternative_arrangement_ref` VARCHAR(255) NULL
  - `testing_evidence_ref` VARCHAR(255) NULL
  - `evidence_timestamp` TIMESTAMPTZ NULL
  - `is_spof` BOOLEAN NOT NULL DEFAULT FALSE
  - `resilience_evaluation` VARCHAR(64) NOT NULL DEFAULT 'UNABLE_TO_DETERMINE'
  - `unresolved_limitations` TEXT NULL
  - `recommended_follow_up_json` JSONB NOT NULL DEFAULT '[]'
  - `evaluated_by` VARCHAR(64) NOT NULL
  - `evaluated_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `tenant_id` VARCHAR(64) NOT NULL DEFAULT 'default'
- **Indexes**:
  - `idx_drr_tenant_dep`: `(tenant_id, dependency_id)`

### 2.8 `recovery_performance_assessments`
- **Columns**:
  - `assessment_id` VARCHAR(64) PRIMARY KEY
  - `recovery_id` VARCHAR(64) NOT NULL -- References Phase 80 governance_recovery_records
  - `capability_id` VARCHAR(64) NOT NULL
  - `disruption_detected_at` TIMESTAMPTZ NOT NULL
  - `detection_to_activation_request_minutes` NUMERIC(10,2) NULL
  - `activation_approval_duration_minutes` NUMERIC(10,2) NULL
  - `arrangement_establishment_duration_minutes` NUMERIC(10,2) NULL
  - `time_to_technical_restoration_minutes` NUMERIC(10,2) NULL
  - `time_to_operational_restoration_minutes` NUMERIC(10,2) NULL
  - `time_to_governance_verification_minutes` NUMERIC(10,2) NULL
  - `time_to_reconciliation_minutes` NUMERIC(10,2) NULL
  - `approved_rto_minutes` INT NULL
  - `rto_outcome` VARCHAR(64) NOT NULL DEFAULT 'TARGET_NOT_DEFINED'
  - `approved_mtpd_minutes` INT NULL
  - `mtpd_outcome` VARCHAR(64) NOT NULL DEFAULT 'TARGET_NOT_DEFINED'
  - `current_restoration_stage` VARCHAR(64) NOT NULL DEFAULT 'TECHNICAL_RESTORATION'
  - `is_governance_verified` BOOLEAN NOT NULL DEFAULT FALSE
  - `deviations_json` JSONB NOT NULL DEFAULT '[]'
  - `limitations` TEXT NULL
  - `evaluated_by` VARCHAR(64) NOT NULL
  - `evaluated_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `tenant_id` VARCHAR(64) NOT NULL DEFAULT 'default'
- **Indexes**:
  - `idx_rpa_tenant_rec`: `(tenant_id, recovery_id)`

### 2.9 `reconciliation_assurance_records`
- **Columns**:
  - `assurance_id` VARCHAR(64) PRIMARY KEY
  - `reconciliation_batch_id` VARCHAR(64) NOT NULL
  - `activation_id` VARCHAR(64) NOT NULL
  - `total_temporary_decisions` INT NOT NULL DEFAULT 0
  - `total_reconciled` INT NOT NULL DEFAULT 0
  - `unresolved_conflicts_count` INT NOT NULL DEFAULT 0
  - `unresolved_conflict_ids_json` JSONB NOT NULL DEFAULT '[]'
  - `integrity_status` VARCHAR(64) NOT NULL DEFAULT 'VERIFIED_INTEGRAL'
  - `has_full_provenance` BOOLEAN NOT NULL DEFAULT TRUE
  - `receiving_workflow_references_json` JSONB NOT NULL DEFAULT '[]'
  - `findings_generated_json` JSONB NOT NULL DEFAULT '[]'
  - `limitations` TEXT NULL
  - `evaluated_by` VARCHAR(64) NOT NULL
  - `evaluated_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `tenant_id` VARCHAR(64) NOT NULL DEFAULT 'default'
- **Indexes**:
  - `idx_rar_tenant_act`: `(tenant_id, activation_id)`

### 2.10 `independent_validation_programmes`
- **Columns**:
  - `programme_id` VARCHAR(64) PRIMARY KEY
  - `programme_name` VARCHAR(255) NOT NULL
  - `scope_description` TEXT NOT NULL
  - `objectives_json` JSONB NOT NULL DEFAULT '[]'
  - `framework_version` INT NOT NULL DEFAULT 1
  - `target_plan_ids_json` JSONB NOT NULL DEFAULT '[]'
  - `status` VARCHAR(32) NOT NULL DEFAULT 'PLANNED'
  - `assigned_evaluators_json` JSONB NOT NULL DEFAULT '[]'
  - `independence_status` VARCHAR(64) NOT NULL DEFAULT 'PENDING_DECLARATION'
  - `evidence_requests_json` JSONB NOT NULL DEFAULT '[]'
  - `associated_finding_ids_json` JSONB NOT NULL DEFAULT '[]'
  - `final_report_ref` VARCHAR(255) NULL
  - `management_response` TEXT NULL
  - `created_by` VARCHAR(64) NOT NULL
  - `created_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `approved_by` VARCHAR(64) NULL
  - `approved_at` TIMESTAMPTZ NULL
  - `tenant_id` VARCHAR(64) NOT NULL DEFAULT 'default'
- **Indexes**:
  - `idx_ivp_tenant_status`: `(tenant_id, status)`

### 2.11 `continuity_assurance_findings`
- **Columns**:
  - `finding_id` VARCHAR(64) PRIMARY KEY
  - `category` VARCHAR(64) NOT NULL
  - `severity` VARCHAR(32) NOT NULL DEFAULT 'HIGH'
  - `title` VARCHAR(255) NOT NULL
  - `description` TEXT NOT NULL
  - `affected_capability_id` VARCHAR(64) NOT NULL
  - `related_plan_id` VARCHAR(64) NULL
  - `related_plan_version` INT NULL
  - `source_evidence_ref` VARCHAR(255) NOT NULL
  - `validation_criteria_ref` VARCHAR(255) NOT NULL
  - `detection_method` VARCHAR(128) NOT NULL DEFAULT 'INDEPENDENT_VALIDATION'
  - `impact_description` TEXT NOT NULL
  - `assigned_owner` VARCHAR(64) NOT NULL
  - `recommended_action` TEXT NOT NULL
  - `status` VARCHAR(64) NOT NULL DEFAULT 'IDENTIFIED'
  - `destination_workflow` VARCHAR(64) NULL
  - `referral_reference_id` VARCHAR(64) NULL
  - `referral_notes` TEXT NULL
  - `phase55_effectiveness_ref` VARCHAR(64) NULL
  - `closure_rationale` TEXT NULL
  - `limitations` TEXT NULL
  - `identified_by` VARCHAR(64) NOT NULL
  - `identified_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `updated_at` TIMESTAMPTZ NULL
  - `closed_at` TIMESTAMPTZ NULL
  - `tenant_id` VARCHAR(64) NOT NULL DEFAULT 'default'
- **Indexes**:
  - `idx_caf_tenant_status`: `(tenant_id, status)`
  - `idx_caf_category`: `(tenant_id, category)`
  - `idx_caf_affected`: `(tenant_id, affected_capability_id)`

---

## 3. Data Retention and Versioning Policies
- **Retention**: Continuity validation evaluations, exercise assessments, and recovery metrics must be retained for at least 7 years in accordance with clinical safety governance standards.
- **Audit Trails**: All modifications to records must be captured via append-only audit journals.
- **Tenant Isolation**: Every query must filter strictly on `tenant_id`.
