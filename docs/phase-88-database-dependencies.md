# Phase 88: Database Dependencies & Relational Persistence Specification

## Notice for Database Engineering Teammate

In compliance with the **Strict Database Ownership Boundary**, this document specifies the proposed persistence structures required for **Phase 88: Clinical Safety Governance Resilience Response Strategy Optimization, Recovery Option Evaluation & Continuity Decision Support**.

The backend layer does **not** create or modify database tables, ORM models, schemas, migrations, indexes, constraints, foreign keys, triggers, or functions. All Phase 88 backend logic is currently backed by an isolated, thread-safe in-memory repository (`GovernanceResponseStrategyRepository`).

This document details the complete relational specification for the 8 primary entities when database migration is scheduled.

---

## 1. Entities Overview

| Entity Name | Primary Key | Business Purpose | Upstream Reference |
|---|---|---|---|
| `response_strategies` | `strategy_id` (VARCHAR(64)) | Stores high-level resilience response strategies, categories, RTO/RPO expectations, and approval state | Core Tenant, Phase 87 Scenario |
| `candidate_recovery_options` | `option_id` (VARCHAR(64)) | Stores candidate operational recovery options, expected capacity %, and required fallbacks | `response_strategies`, Phase 86 Fallbacks |
| `feasibility_assessments` | `assessment_id` (VARCHAR(64)) | Stores objective feasibility evaluations, evidence verification, and residual clinical risks | `candidate_recovery_options`, Phase 86/85 Evidence |
| `recovery_priority_evaluations` | `evaluation_id` (VARCHAR(64)) | Stores capability restoration priorities by clinical criticality tiers (Tier 1 Life Safety, etc.) | Phase 87 Scenario, Capabilities |
| `recovery_sequences` | `sequence_id` (VARCHAR(64)) | Stores restoration sequences, milestones, bottlenecks, and duration estimates | `recovery_priority_evaluations` |
| `recovery_comparison_records` | `comparison_id` (VARCHAR(64)) | Stores side-by-side comparative evaluations of candidate options and trade-off analyses | `candidate_recovery_options` |
| `recovery_resource_plans` | `plan_id` (VARCHAR(64)) | Stores non-autonomous resource requirement plans and competing demand detections | `candidate_recovery_options`, Phase 86 Resources |
| `recovery_recommendations` | `recommendation_id` (VARCHAR(64)) | Stores packaged decision recommendations, challenge histories, and management review decisions | `candidate_recovery_options`, Phase 72 Review Cycles |
| `continuity_handoffs` | `handoff_id` (VARCHAR(64)) | Coordinates controlled handoff to Phase 80 continuity execution workflows | `recovery_recommendations`, Phase 80 Workflows |
| `recovery_execution_trackings` | `tracking_id` (VARCHAR(64)) | Tracks operational recovery progress, deviations, and verified restoration evidence | `continuity_handoffs`, Phase 73 Executions |

---

## 2. Table Specifications

### 2.1 `response_strategies`
- **Columns**:
  - `strategy_id` VARCHAR(64) PRIMARY KEY
  - `tenant_id` VARCHAR(64) NOT NULL
  - `strategy_name` VARCHAR(255) NOT NULL
  - `strategy_category` VARCHAR(64) NOT NULL -- FALLBACK_ACTIVATION, DEGRADED_OPERATION, WORKAROUND_PROCEDURE, MANUAL_CONTINGENCY, etc.
  - `scenario_reference` VARCHAR(64) NOT NULL
  - `affected_capability_references` JSONB NOT NULL DEFAULT '[]'
  - `description` TEXT NOT NULL
  - `strategic_intent` TEXT NOT NULL
  - `operational_constraints` JSONB NOT NULL DEFAULT '[]'
  - `minimum_viable_operating_level` VARCHAR(255) NOT NULL
  - `provisional_rto_hours` NUMERIC(6, 2) NOT NULL DEFAULT 4.00
  - `provisional_rpo_hours` NUMERIC(6, 2) NOT NULL DEFAULT 1.00
  - `requires_clinical_safety_clearance` BOOLEAN NOT NULL DEFAULT TRUE
  - `status` VARCHAR(32) NOT NULL DEFAULT 'DRAFT' -- DRAFT, SUBMITTED, APPROVED, REJECTED, ARCHIVED
  - `created_by` VARCHAR(64) NOT NULL
  - `approved_by` VARCHAR(64) NULL
  - `approved_at` TIMESTAMPTZ NULL
  - `review_notes` TEXT NULL
  - `created_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `updated_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `disclaimer` TEXT NOT NULL
- **Indexes**:
  - `ix_rs_tenant_cat` (`tenant_id`, `strategy_category`)
  - `ix_rs_tenant_status` (`tenant_id`, `status`)
  - `ix_rs_scenario` (`tenant_id`, `scenario_reference`)

### 2.2 `candidate_recovery_options`
- **Columns**:
  - `option_id` VARCHAR(64) PRIMARY KEY
  - `tenant_id` VARCHAR(64) NOT NULL
  - `option_name` VARCHAR(255) NOT NULL
  - `strategy_reference` VARCHAR(64) NULL REFERENCES `response_strategies`(`strategy_id`)
  - `scenario_reference` VARCHAR(64) NOT NULL
  - `category` VARCHAR(64) NOT NULL
  - `target_capability_references` JSONB NOT NULL DEFAULT '[]'
  - `description` TEXT NOT NULL
  - `estimated_rto_hours` NUMERIC(6, 2) NOT NULL DEFAULT 4.00
  - `estimated_rpo_hours` NUMERIC(6, 2) NOT NULL DEFAULT 1.00
  - `operational_capacity_pct` NUMERIC(5, 2) NOT NULL DEFAULT 100.00
  - `required_resource_ids` JSONB NOT NULL DEFAULT '[]'
  - `required_role_references` JSONB NOT NULL DEFAULT '[]'
  - `required_fallback_references` JSONB NOT NULL DEFAULT '[]'
  - `requires_regulatory_clearance` BOOLEAN NOT NULL DEFAULT FALSE
  - `requires_board_escalation` BOOLEAN NOT NULL DEFAULT FALSE
  - `is_active` BOOLEAN NOT NULL DEFAULT TRUE
  - `created_by` VARCHAR(64) NOT NULL
  - `created_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `disclaimer` TEXT NOT NULL
- **Indexes**:
  - `ix_cro_tenant_strat` (`tenant_id`, `strategy_reference`)
  - `ix_cro_tenant_scen` (`tenant_id`, `scenario_reference`)

### 2.3 `feasibility_assessments`
- **Columns**:
  - `assessment_id` VARCHAR(64) PRIMARY KEY
  - `tenant_id` VARCHAR(64) NOT NULL
  - `option_reference` VARCHAR(64) NOT NULL REFERENCES `candidate_recovery_options`(`option_id`)
  - `assessor_id` VARCHAR(64) NOT NULL
  - `feasibility_outcome` VARCHAR(32) NOT NULL -- FEASIBLE_VERIFIED, CONDITIONALLY_FEASIBLE, NOT_FEASIBLE, INSUFFICIENT_EVIDENCE
  - `feasibility_score` NUMERIC(4, 2) NOT NULL DEFAULT 0.00
  - `resource_availability_confirmed` BOOLEAN NOT NULL DEFAULT FALSE
  - `role_coverage_confirmed` BOOLEAN NOT NULL DEFAULT FALSE
  - `fallback_readiness_confirmed` BOOLEAN NOT NULL DEFAULT FALSE
  - `clinical_safety_risk_acceptable` BOOLEAN NOT NULL DEFAULT TRUE
  - `identified_constraints` JSONB NOT NULL DEFAULT '[]'
  - `residual_safety_risks` JSONB NOT NULL DEFAULT '[]'
  - `evidence_references` JSONB NOT NULL DEFAULT '[]'
  - `assessed_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `disclaimer` TEXT NOT NULL
- **Indexes**:
  - `ix_fa_tenant_opt` (`tenant_id`, `option_reference`)
  - `ix_fa_outcome` (`tenant_id`, `feasibility_outcome`)

### 2.4 `recovery_priority_evaluations`
- **Columns**:
  - `evaluation_id` VARCHAR(64) PRIMARY KEY
  - `tenant_id` VARCHAR(64) NOT NULL
  - `scenario_reference` VARCHAR(64) NOT NULL
  - `evaluator_id` VARCHAR(64) NOT NULL
  - `prioritized_capabilities` JSONB NOT NULL DEFAULT '[]'
  - `life_safety_capabilities_prioritized` BOOLEAN NOT NULL DEFAULT TRUE
  - `prioritization_rationale` TEXT NOT NULL
  - `evaluated_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `disclaimer` TEXT NOT NULL
- **Indexes**:
  - `ix_rpe_tenant_scen` (`tenant_id`, `scenario_reference`)

### 2.5 `recovery_sequences`
- **Columns**:
  - `sequence_id` VARCHAR(64) PRIMARY KEY
  - `tenant_id` VARCHAR(64) NOT NULL
  - `priority_evaluation_reference` VARCHAR(64) NOT NULL REFERENCES `recovery_priority_evaluations`(`evaluation_id`)
  - `sequence_name` VARCHAR(255) NOT NULL
  - `sequence_steps` JSONB NOT NULL DEFAULT '[]'
  - `bottleneck_dependencies` JSONB NOT NULL DEFAULT '[]'
  - `estimated_total_duration_hours` NUMERIC(6, 2) NOT NULL DEFAULT 4.00
  - `milestone_targets` JSONB NOT NULL DEFAULT '[]'
  - `is_validated` BOOLEAN NOT NULL DEFAULT TRUE
  - `created_by` VARCHAR(64) NOT NULL
  - `created_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `disclaimer` TEXT NOT NULL
- **Indexes**:
  - `ix_rseq_tenant_eval` (`tenant_id`, `priority_evaluation_reference`)

### 2.6 `recovery_comparison_records`
- **Columns**:
  - `comparison_id` VARCHAR(64) PRIMARY KEY
  - `tenant_id` VARCHAR(64) NOT NULL
  - `comparison_name` VARCHAR(255) NOT NULL
  - `scenario_reference` VARCHAR(64) NOT NULL
  - `strategy_reference` VARCHAR(64) NULL REFERENCES `response_strategies`(`strategy_id`)
  - `evaluated_by` VARCHAR(64) NOT NULL
  - `compared_options` JSONB NOT NULL DEFAULT '[]'
  - `trade_offs` JSONB NOT NULL DEFAULT '[]'
  - `preliminary_recommended_option_reference` VARCHAR(64) NULL
  - `comparison_summary` TEXT NOT NULL
  - `evaluated_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `disclaimer` TEXT NOT NULL
- **Indexes**:
  - `ix_rc_tenant_scen` (`tenant_id`, `scenario_reference`)

### 2.7 `recovery_resource_plans`
- **Columns**:
  - `plan_id` VARCHAR(64) PRIMARY KEY
  - `tenant_id` VARCHAR(64) NOT NULL
  - `plan_name` VARCHAR(255) NOT NULL
  - `candidate_option_reference` VARCHAR(64) NOT NULL REFERENCES `candidate_recovery_options`(`option_id`)
  - `scenario_reference` VARCHAR(64) NOT NULL
  - `planner_id` VARCHAR(64) NOT NULL
  - `required_resources` JSONB NOT NULL DEFAULT '[]'
  - `competing_resource_demands_detected` BOOLEAN NOT NULL DEFAULT FALSE
  - `competing_resource_details` JSONB NOT NULL DEFAULT '[]'
  - `resource_shortfall_risks` JSONB NOT NULL DEFAULT '[]'
  - `resource_conflict_resolution_strategy` TEXT NOT NULL
  - `is_autonomous_allocation` BOOLEAN NOT NULL DEFAULT FALSE
  - `created_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `disclaimer` TEXT NOT NULL
- **Indexes**:
  - `ix_rrp_tenant_opt` (`tenant_id`, `candidate_option_reference`)

### 2.8 `recovery_recommendations`
- **Columns**:
  - `recommendation_id` VARCHAR(64) PRIMARY KEY
  - `tenant_id` VARCHAR(64) NOT NULL
  - `recommendation_title` VARCHAR(255) NOT NULL
  - `scenario_reference` VARCHAR(64) NOT NULL
  - `recommended_option_reference` VARCHAR(64) NOT NULL REFERENCES `candidate_recovery_options`(`option_id`)
  - `alternative_option_references` JSONB NOT NULL DEFAULT '[]'
  - `feasibility_assessment_reference` VARCHAR(64) NULL REFERENCES `feasibility_assessments`(`assessment_id`)
  - `comparison_reference` VARCHAR(64) NULL REFERENCES `recovery_comparison_records`(`comparison_id`)
  - `prepared_by` VARCHAR(64) NOT NULL
  - `clinical_safety_justification` TEXT NOT NULL
  - `residual_clinical_risks` JSONB NOT NULL DEFAULT '[]'
  - `prerequisite_governance_approvals` JSONB NOT NULL DEFAULT '[]'
  - `estimated_restoration_time_hours` NUMERIC(6, 2) NOT NULL DEFAULT 4.00
  - `lifecycle_status` VARCHAR(32) NOT NULL DEFAULT 'RECOMMENDATION_PREPARED'
  - `challenge_history` JSONB NOT NULL DEFAULT '[]'
  - `management_decision` JSONB NULL
  - `created_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `updated_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `disclaimer` TEXT NOT NULL
- **Indexes**:
  - `ix_rrec_tenant_status` (`tenant_id`, `lifecycle_status`)
  - `ix_rrec_tenant_scen` (`tenant_id`, `scenario_reference`)

### 2.9 `continuity_handoffs`
- **Columns**:
  - `handoff_id` VARCHAR(64) PRIMARY KEY
  - `tenant_id` VARCHAR(64) NOT NULL
  - `recommendation_reference` VARCHAR(64) NOT NULL REFERENCES `recovery_recommendations`(`recommendation_id`)
  - `receiving_continuity_workflow_ref` VARCHAR(64) NOT NULL
  - `selected_option_reference` VARCHAR(64) NOT NULL REFERENCES `candidate_recovery_options`(`option_id`)
  - `handoff_status` VARCHAR(32) NOT NULL DEFAULT 'HANDED_OFF'
  - `operational_parameters` JSONB NOT NULL DEFAULT '{}'
  - `mandated_safeguards` JSONB NOT NULL DEFAULT '[]'
  - `handed_off_by` VARCHAR(64) NOT NULL
  - `handed_off_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `acknowledged_by` VARCHAR(64) NULL
  - `acknowledged_at` TIMESTAMPTZ NULL
  - `continuity_execution_id` VARCHAR(64) NULL
  - `disclaimer` TEXT NOT NULL
- **Indexes**:
  - `ix_ch_tenant_rec` (`tenant_id`, `recommendation_reference`)
  - `ix_ch_status` (`tenant_id`, `handoff_status`)

### 2.10 `recovery_execution_trackings`
- **Columns**:
  - `tracking_id` VARCHAR(64) PRIMARY KEY
  - `tenant_id` VARCHAR(64) NOT NULL
  - `recommendation_reference` VARCHAR(64) NOT NULL REFERENCES `recovery_recommendations`(`recommendation_id`)
  - `continuity_execution_reference` VARCHAR(64) NULL
  - `option_reference` VARCHAR(64) NOT NULL REFERENCES `candidate_recovery_options`(`option_id`)
  - `sequence_reference` VARCHAR(64) NULL REFERENCES `recovery_sequences`(`sequence_id`)
  - `execution_status` VARCHAR(32) NOT NULL DEFAULT 'PLANNED'
  - `overall_progress_percentage` NUMERIC(5, 2) NOT NULL DEFAULT 0.00
  - `elapsed_time_hours` NUMERIC(6, 2) NOT NULL DEFAULT 0.00
  - `milestones` JSONB NOT NULL DEFAULT '[]'
  - `reported_deviations` JSONB NOT NULL DEFAULT '[]'
  - `is_restoration_verified` BOOLEAN NOT NULL DEFAULT FALSE
  - `restoration_verified_by` VARCHAR(64) NULL
  - `restoration_verified_at` TIMESTAMPTZ NULL
  - `restoration_verification_evidence_ref` VARCHAR(255) NULL
  - `tracked_by` VARCHAR(64) NOT NULL
  - `started_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `disclaimer` TEXT NOT NULL
- **Indexes**:
  - `ix_ret_tenant_rec` (`tenant_id`, `recommendation_reference`)
  - `ix_ret_status` (`tenant_id`, `execution_status`)
