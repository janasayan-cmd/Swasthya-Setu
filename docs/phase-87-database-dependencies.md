# Phase 87: Database Dependencies & Relational Persistence Specification

## Notice for Database Engineering Teammate

In compliance with the **Strict Database Ownership Boundary**, this document specifies the proposed persistence structures required for **Phase 87: Clinical Safety Governance Resilience Disruption Impact Analysis, Cascading Failure Assessment & Cross-Dependency Scenario Intelligence**.

The backend layer does **not** create or modify database tables, ORM models, schemas, migrations, indexes, constraints, foreign keys, triggers, or functions. All Phase 87 backend logic is currently backed by an isolated, thread-safe in-memory repository (`GovernanceDisruptionImpactRepository`).

This document details the complete relational specification for the 6 primary entities when database migration is scheduled.

---

## 1. Entities Overview

| Entity Name | Primary Key | Business Purpose | Upstream Reference |
|---|---|---|---|
| `disruption_scenarios` | `scenario_id` (VARCHAR(64)) | Stores configurable disruption scenarios, categories, severity assumptions, and constraints | Core Organization, Phase 49 Incidents |
| `disruption_impact_assessments` | `assessment_id` (VARCHAR(64)) | Stores evaluated direct and indirect impacts, MTPD calculations, and human review status | `disruption_scenarios`, Phase 86 Mappings |
| `cascading_failure_analyses` | `analysis_id` (VARCHAR(64)) | Stores multi-level propagation paths, shared upstream findings, and common provider risks | `disruption_impact_assessments`, Phase 86 Graphs |
| `compound_disruption_scenarios` | `compound_scenario_id` (VARCHAR(64)) | Stores multi-resource simultaneous disruption evaluations and non-independent fallback findings | `disruption_scenarios`, Phase 86 Resources |
| `fallback_comparison_records` | `comparison_id` (VARCHAR(64)) | Stores baseline vs. fallback readiness tier comparisons and mitigation evaluations | `disruption_impact_assessments`, Phase 86 Alternatives |
| `impact_remediation_follow_ups` | `follow_up_id` (VARCHAR(64)) | Coordinates handoffs to authoritative workflows (Phase 63, 67, 49, 54, 72, 80) | `disruption_impact_assessments` |

---

## 2. Table Specifications

### 2.1 `disruption_scenarios`
- **Columns**:
  - `scenario_id` VARCHAR(64) PRIMARY KEY
  - `tenant_id` VARCHAR(64) NOT NULL
  - `scenario_name` VARCHAR(255) NOT NULL
  - `description` TEXT NOT NULL
  - `category` VARCHAR(64) NOT NULL -- APPLICATION_UNAVAILABILITY, INFRASTRUCTURE_FAILURE, NETWORK_DISRUPTION, CLOUD_INTERRUPTION, DATA_STORAGE_UNAVAILABILITY, IDENTITY_AUTHENTICATION_DISRUPTION, EXTERNAL_PROVIDER_OUTAGE, etc.
  - `organizational_scope` VARCHAR(255) NOT NULL DEFAULT 'ORGANIZATION'
  - `affected_resource_refs` JSONB NOT NULL DEFAULT '[]'
  - `affected_capability_refs` JSONB NOT NULL DEFAULT '[]'
  - `affected_responsibility_refs` JSONB NOT NULL DEFAULT '[]'
  - `initial_disruption_conditions` TEXT NOT NULL
  - `duration_type` VARCHAR(64) NOT NULL DEFAULT 'EXTENDED_INTERRUPTION'
  - `assumed_duration_hours` NUMERIC(6, 2) NOT NULL DEFAULT 4.00
  - `severity_assumption` VARCHAR(32) NOT NULL DEFAULT 'HIGH'
  - `expected_operating_constraints` JSONB NOT NULL DEFAULT '[]'
  - `potential_recovery_conditions` TEXT NULL
  - `evidence_refs` JSONB NOT NULL DEFAULT '[]'
  - `live_incident_ref` VARCHAR(64) NULL
  - `scenario_version` VARCHAR(32) NOT NULL DEFAULT '1.0'
  - `scenario_owner` VARCHAR(64) NOT NULL
  - `review_status` VARCHAR(32) NOT NULL DEFAULT 'DRAFT' -- DRAFT, SUBMITTED, APPROVED, REJECTED, SUPERSEDED, ARCHIVED
  - `approval_ref` VARCHAR(255) NULL
  - `approved_by` VARCHAR(64) NULL
  - `approved_at` TIMESTAMPTZ NULL
  - `created_by` VARCHAR(64) NOT NULL
  - `created_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `updated_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `disclaimer` TEXT NOT NULL
- **Indexes**:
  - `ix_ds_tenant_cat` (`tenant_id`, `category`)
  - `ix_ds_tenant_status` (`tenant_id`, `review_status`)
  - `ix_ds_owner` (`tenant_id`, `scenario_owner`)

### 2.2 `disruption_impact_assessments`
- **Columns**:
  - `assessment_id` VARCHAR(64) PRIMARY KEY
  - `tenant_id` VARCHAR(64) NOT NULL
  - `scenario_id` VARCHAR(64) NOT NULL REFERENCES `disruption_scenarios`(`scenario_id`)
  - `assessment_name` VARCHAR(255) NOT NULL
  - `dependency_graph_version` VARCHAR(32) NOT NULL DEFAULT '1.0'
  - `assessment_timestamp` TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `affected_capability_refs` JSONB NOT NULL DEFAULT '[]'
  - `affected_responsibility_refs` JSONB NOT NULL DEFAULT '[]'
  - `affected_resource_refs` JSONB NOT NULL DEFAULT '[]'
  - `direct_findings` JSONB NOT NULL DEFAULT '[]'
  - `indirect_findings` JSONB NOT NULL DEFAULT '[]'
  - `potential_operational_consequences` JSONB NOT NULL DEFAULT '[]'
  - `available_fallback_refs` JSONB NOT NULL DEFAULT '[]'
  - `remaining_limitations` JSONB NOT NULL DEFAULT '[]'
  - `uncertainty_indicators` JSONB NOT NULL DEFAULT '[]'
  - `evidence_freshness_hours` NUMERIC(6, 2) NULL
  - `mtpd_exceeded` BOOLEAN NOT NULL DEFAULT FALSE
  - `rto_exceeded` BOOLEAN NOT NULL DEFAULT FALSE
  - `evidence_refs` JSONB NOT NULL DEFAULT '[]'
  - `overall_impact_severity` VARCHAR(32) NOT NULL DEFAULT 'HIGH'
  - `review_status` VARCHAR(64) NOT NULL DEFAULT 'DRAFT' -- DRAFT, AUTOMATED_ANALYSIS_COMPLETED, EVIDENCE_REVIEW_PENDING, HUMAN_REVIEW, CHALLENGED, ADDITIONAL_EVIDENCE_REQUESTED, APPROVED, SUPERSEDED, CLOSED
  - `assessment_version` INT NOT NULL DEFAULT 1
  - `assessed_by` VARCHAR(64) NOT NULL
  - `reviewed_by` VARCHAR(64) NULL
  - `review_notes` TEXT NULL
  - `reviewed_at` TIMESTAMPTZ NULL
  - `challenge_notes` TEXT NULL
  - `challenged_by` VARCHAR(64) NULL
  - `created_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `updated_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `disclaimer` TEXT NOT NULL
- **Indexes**:
  - `ix_dia_tenant_scen` (`tenant_id`, `scenario_id`)
  - `ix_dia_tenant_status` (`tenant_id`, `review_status`)
  - `ix_dia_tenant_sev` (`tenant_id`, `overall_impact_severity`)

### 2.3 `cascading_failure_analyses`
- **Columns**:
  - `analysis_id` VARCHAR(64) PRIMARY KEY
  - `tenant_id` VARCHAR(64) NOT NULL
  - `assessment_id` VARCHAR(64) NULL REFERENCES `disruption_impact_assessments`(`assessment_id`)
  - `scenario_id` VARCHAR(64) NULL REFERENCES `disruption_scenarios`(`scenario_id`)
  - `total_paths_identified` INT NOT NULL DEFAULT 0
  - `max_depth_traversed` INT NOT NULL DEFAULT 0
  - `cascading_findings` JSONB NOT NULL DEFAULT '[]'
  - `propagation_paths` JSONB NOT NULL DEFAULT '[]'
  - `shared_upstream_resources` JSONB NOT NULL DEFAULT '[]'
  - `common_provider_risks` JSONB NOT NULL DEFAULT '[]'
  - `analyzed_by` VARCHAR(64) NOT NULL
  - `analyzed_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `disclaimer` TEXT NOT NULL
- **Indexes**:
  - `ix_cfa_tenant_assess` (`tenant_id`, `assessment_id`)
  - `ix_cfa_tenant_ts` (`tenant_id`, `analyzed_at` DESC)

### 2.4 `compound_disruption_scenarios`
- **Columns**:
  - `compound_scenario_id` VARCHAR(64) PRIMARY KEY
  - `tenant_id` VARCHAR(64) NOT NULL
  - `scenario_name` VARCHAR(255) NOT NULL
  - `description` TEXT NOT NULL
  - `component_scenario_ids` JSONB NOT NULL DEFAULT '[]'
  - `simultaneous_resource_ids` JSONB NOT NULL DEFAULT '[]'
  - `shared_dependencies_identified` JSONB NOT NULL DEFAULT '[]'
  - `combined_affected_capabilities` JSONB NOT NULL DEFAULT '[]'
  - `combined_affected_responsibilities` JSONB NOT NULL DEFAULT '[]'
  - `available_fallback_arrangements` JSONB NOT NULL DEFAULT '[]'
  - `non_independent_fallbacks` JSONB NOT NULL DEFAULT '[]'
  - `capacity_limitations` JSONB NOT NULL DEFAULT '[]'
  - `unresolved_assumptions` JSONB NOT NULL DEFAULT '[]'
  - `compound_severity` VARCHAR(32) NOT NULL DEFAULT 'CRITICAL'
  - `evaluated_at` TIMESTAMPTZ NULL
  - `evaluated_by` VARCHAR(64) NULL
  - `created_by` VARCHAR(64) NOT NULL
  - `created_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `updated_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `disclaimer` TEXT NOT NULL
- **Indexes**:
  - `ix_cds_tenant_sev` (`tenant_id`, `compound_severity`)

### 2.5 `fallback_comparison_records`
- **Columns**:
  - `comparison_id` VARCHAR(64) PRIMARY KEY
  - `tenant_id` VARCHAR(64) NOT NULL
  - `assessment_id` VARCHAR(64) NOT NULL REFERENCES `disruption_impact_assessments`(`assessment_id`)
  - `resource_id` VARCHAR(64) NOT NULL
  - `baseline_severity_without_fallback` VARCHAR(32) NOT NULL DEFAULT 'CRITICAL'
  - `comparison_items` JSONB NOT NULL DEFAULT '[]'
  - `optimal_fallback_id` VARCHAR(64) NULL
  - `recommendations` JSONB NOT NULL DEFAULT '[]'
  - `compared_by` VARCHAR(64) NOT NULL
  - `compared_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `disclaimer` TEXT NOT NULL
- **Indexes**:
  - `ix_fcr_tenant_assess` (`tenant_id`, `assessment_id`)
  - `ix_fcr_tenant_res` (`tenant_id`, `resource_id`)

### 2.6 `impact_remediation_follow_ups`
- **Columns**:
  - `follow_up_id` VARCHAR(64) PRIMARY KEY
  - `tenant_id` VARCHAR(64) NOT NULL
  - `assessment_id` VARCHAR(64) NOT NULL REFERENCES `disruption_impact_assessments`(`assessment_id`)
  - `finding_reference_id` VARCHAR(64) NULL
  - `affected_capability_ref` VARCHAR(255) NOT NULL
  - `responsible_owner_ref` VARCHAR(64) NOT NULL
  - `destination_workflow` VARCHAR(64) NOT NULL -- PHASE_63_RISK_MANAGEMENT, PHASE_67_GOVERNANCE_EXCEPTION, PHASE_49_INCIDENT, PHASE_54_CORRECTIVE_ACTION, PHASE_72_MANAGEMENT_REVIEW, PHASE_80_CONTINUITY_PLANNING
  - `priority_severity` VARCHAR(32) NOT NULL DEFAULT 'HIGH'
  - `status` VARCHAR(32) NOT NULL DEFAULT 'PROPOSED' -- PROPOSED, SUBMITTED, ACKNOWLEDGED, IN_PROGRESS, COMPLETED, REJECTED
  - `proposal_description` TEXT NOT NULL
  - `external_workflow_reference_id` VARCHAR(64) NULL
  - `handoff_timestamp` TIMESTAMPTZ NULL
  - `acknowledgement_timestamp` TIMESTAMPTZ NULL
  - `acknowledged_by` VARCHAR(64) NULL
  - `outcome_notes` TEXT NULL
  - `created_by` VARCHAR(64) NOT NULL
  - `created_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `updated_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `disclaimer` TEXT NOT NULL
- **Indexes**:
  - `ix_irfu_tenant_assess` (`tenant_id`, `assessment_id`)
  - `ix_irfu_dest_status` (`tenant_id`, `destination_workflow`, `status`)
