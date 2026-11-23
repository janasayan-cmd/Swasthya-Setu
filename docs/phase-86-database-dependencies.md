# Phase 86: Database Dependencies & Relational Persistence Specification

## Notice for Database Engineering Teammate

In compliance with the **Strict Database Ownership Boundary**, this document specifies the proposed persistence structures required for **Phase 86: Clinical Safety Governance Resilience Resource Dependency Mapping, Critical Resource Availability & Continuity Capacity Assurance**.

The backend layer does **not** create or modify database tables, ORM models, schemas, migrations, indexes, constraints, foreign keys, triggers, or functions. All Phase 86 backend logic is currently backed by an isolated, thread-safe in-memory repository (`GovernanceResourceDependencyRepository`).

This document details the complete relational specification for the 7 primary entities when database migration is scheduled.

---

## 1. Entities Overview

| Entity Name | Primary Key | Business Purpose | Upstream Reference |
|---|---|---|---|
| `critical_governance_resources` | `resource_id` (VARCHAR(64)) | Stores inventory of critical clinical safety governance operational resources, services, and dependencies | Core Facilities, Phase 80 Continuity Ops |
| `capability_resource_dependency_mappings` | `dependency_id` (VARCHAR(64)) | Manages capability-to-resource dependency linkages, criticality, and formal approvals | `critical_governance_resources`, Phase 80/85 |
| `resource_availability_observations` | `observation_id` (VARCHAR(64)) | Records timestamped operational telemetry, status observations, and source reliability | `critical_governance_resources` |
| `alternative_resource_records` | `alternative_id` (VARCHAR(64)) | Defines validated alternative resources, compatibility rules, and fallback readiness assessments | `critical_governance_resources` |
| `resource_capacity_requirements` | `requirement_id` (VARCHAR(64)) | Stores minimum capacity thresholds, disruption tolerances, and verified evaluations | `critical_governance_resources` |
| `dependency_graph_analyses` | `analysis_id` (VARCHAR(64)) | Records dependency graph evaluations, SPOF discoveries, circular dependencies, and critical paths | `critical_governance_resources`, `capability_resource_dependency_mappings` |
| `resource_dependency_gaps` | `gap_id` (VARCHAR(64)) | Tracks identified resource shortfalls, single points of failure, remedial assignments, and escalations | `critical_governance_resources`, Phases 54/63/67/72 |

---

## 2. Table Specifications

### 2.1 `critical_governance_resources`
- **Columns**:
  - `resource_id` VARCHAR(64) PRIMARY KEY
  - `tenant_id` VARCHAR(64) NOT NULL
  - `resource_name` VARCHAR(255) NOT NULL
  - `category` VARCHAR(64) NOT NULL -- CLINICAL_INFORMATION_SYSTEM, INFRASTRUCTURE, COMMUNICATION_NETWORK, PHYSICAL_FACILITY, THIRD_PARTY_SERVICE, GOVERNANCE_RECORDS_REPOSITORY, SPECIALIZED_EQUIPMENT, EXTERNAL_REGULATORY_PORTAL
  - `description` TEXT NOT NULL
  - `owning_organization` VARCHAR(255) NOT NULL
  - `responsible_department` VARCHAR(255) NOT NULL
  - `resource_owner_ref` VARCHAR(64) NOT NULL
  - `criticality` VARCHAR(32) NOT NULL DEFAULT 'TIER_1_ESSENTIAL' -- TIER_1_ESSENTIAL, TIER_2_CRITICAL, TIER_3_IMPORTANT, TIER_4_SUPPORTING
  - `associated_governance_capability` VARCHAR(255) NOT NULL
  - `availability_requirement_hours` NUMERIC(6, 2) NOT NULL DEFAULT 4.00
  - `dependency_refs` JSONB NOT NULL DEFAULT '[]'
  - `alternative_resource_refs` JSONB NOT NULL DEFAULT '[]'
  - `external_provider_ref` VARCHAR(255) NULL
  - `source_system_ref` VARCHAR(255) NULL
  - `verification_status` VARCHAR(64) NOT NULL DEFAULT 'UNVERIFIED'
  - `last_verified_at` TIMESTAMPTZ NULL
  - `review_cycle_days` INT NOT NULL DEFAULT 90
  - `next_review_due` TIMESTAMPTZ NULL
  - `lifecycle_status` VARCHAR(32) NOT NULL DEFAULT 'ACTIVE' -- DRAFT, ACTIVE, DEGRADED, UNDER_MAINTENANCE, RETIRED, DEPRECATED
  - `created_by` VARCHAR(64) NOT NULL
  - `created_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `updated_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `disclaimer` TEXT NOT NULL
- **Indexes**:
  - `ix_cgr_tenant_cat` (`tenant_id`, `category`)
  - `ix_cgr_tenant_crit` (`tenant_id`, `criticality`)
  - `ix_cgr_lifecycle` (`tenant_id`, `lifecycle_status`)

### 2.2 `capability_resource_dependency_mappings`
- **Columns**:
  - `dependency_id` VARCHAR(64) PRIMARY KEY
  - `tenant_id` VARCHAR(64) NOT NULL
  - `governance_capability_ref` VARCHAR(255) NOT NULL
  - `responsibility_ref` VARCHAR(64) NULL
  - `resource_id` VARCHAR(64) NOT NULL REFERENCES `critical_governance_resources`(`resource_id`)
  - `resource_criticality` VARCHAR(32) NOT NULL DEFAULT 'TIER_1_ESSENTIAL'
  - `dependency_type` VARCHAR(64) NOT NULL DEFAULT 'PRIMARY' -- PRIMARY, SECONDARY, CONTINGENCY, PREREQUISITE, UPSTREAM_FEED
  - `minimum_availability_pct` NUMERIC(5, 2) NOT NULL DEFAULT 99.00
  - `required_operating_capacity` VARCHAR(255) NOT NULL DEFAULT 'Full operational capability'
  - `organizational_scope` VARCHAR(255) NOT NULL DEFAULT 'ORGANIZATION'
  - `dependency_owner` VARCHAR(64) NOT NULL
  - `evidence_refs` JSONB NOT NULL DEFAULT '[]'
  - `status` VARCHAR(32) NOT NULL DEFAULT 'DRAFT' -- DRAFT, UNDER_REVIEW, APPROVED, REJECTED, SUSPENDED, SUPERSEDED
  - `effective_start` TIMESTAMPTZ NULL
  - `effective_end` TIMESTAMPTZ NULL
  - `created_by` VARCHAR(64) NOT NULL
  - `approved_by` VARCHAR(64) NULL
  - `approved_at` TIMESTAMPTZ NULL
  - `created_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `updated_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
- **Indexes**:
  - `ix_crdm_tenant_cap` (`tenant_id`, `governance_capability_ref`)
  - `ix_crdm_tenant_res` (`tenant_id`, `resource_id`)
  - `ix_crdm_status` (`tenant_id`, `status`)

### 2.3 `resource_availability_observations`
- **Columns**:
  - `observation_id` VARCHAR(64) PRIMARY KEY
  - `tenant_id` VARCHAR(64) NOT NULL
  - `resource_id` VARCHAR(64) NOT NULL REFERENCES `critical_governance_resources`(`resource_id`)
  - `source_system` VARCHAR(255) NOT NULL
  - `observed_status` VARCHAR(64) NOT NULL -- AVAILABLE_VERIFIED, AVAILABLE_UNVERIFIED, DEGRADED, UNAVAILABLE, SCHEDULED_DOWNTIME, UNKNOWN
  - `observation_timestamp` TIMESTAMPTZ NOT NULL
  - `verification_timestamp` TIMESTAMPTZ NULL
  - `data_freshness_minutes` INT NOT NULL DEFAULT 0
  - `evidence_ref` VARCHAR(255) NULL
  - `organizational_scope` VARCHAR(255) NOT NULL DEFAULT 'ORGANIZATION'
  - `source_reliability` VARCHAR(32) NOT NULL DEFAULT 'MEDIUM' -- HIGH, MEDIUM, LOW, UNCONFIRMED
  - `failure_details` TEXT NULL
  - `limitation_details` TEXT NULL
  - `recorded_by` VARCHAR(64) NOT NULL
  - `created_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
- **Indexes**:
  - `ix_rao_tenant_res_ts` (`tenant_id`, `resource_id`, `observation_timestamp` DESC)

### 2.4 `alternative_resource_records`
- **Columns**:
  - `alternative_id` VARCHAR(64) PRIMARY KEY
  - `tenant_id` VARCHAR(64) NOT NULL
  - `primary_resource_id` VARCHAR(64) NOT NULL REFERENCES `critical_governance_resources`(`resource_id`)
  - `alternative_resource_id` VARCHAR(64) NOT NULL REFERENCES `critical_governance_resources`(`resource_id`)
  - `substitution_conditions` TEXT NOT NULL
  - `dependency_compatibility` TEXT NOT NULL
  - `required_configuration_ref` VARCHAR(255) NULL
  - `access_prerequisites` JSONB NOT NULL DEFAULT '[]'
  - `organizational_scope` VARCHAR(255) NOT NULL DEFAULT 'ORGANIZATION'
  - `capacity_constraints` TEXT NULL
  - `known_limitations` TEXT NULL
  - `verification_evidence_ref` VARCHAR(255) NULL
  - `last_successful_validation` TIMESTAMPTZ NULL
  - `approval_ref` VARCHAR(255) NULL
  - `expiry_date` TIMESTAMPTZ NULL
  - `fallback_readiness` VARCHAR(64) NOT NULL DEFAULT 'NOT_ASSESSED' -- READY_VERIFIED, READY_UNVERIFIED, DEGRADED_FALLBACK, INSUFFICIENT_EVIDENCE, EXPIRED, NOT_ASSESSED
  - `readiness_assessed_by` VARCHAR(64) NULL
  - `readiness_assessed_at` TIMESTAMPTZ NULL
  - `readiness_notes` TEXT NULL
  - `created_by` VARCHAR(64) NOT NULL
  - `created_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `updated_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
- **Indexes**:
  - `ix_arr_tenant_primary` (`tenant_id`, `primary_resource_id`)
  - `ix_arr_readiness` (`tenant_id`, `fallback_readiness`)

### 2.5 `resource_capacity_requirements`
- **Columns**:
  - `requirement_id` VARCHAR(64) PRIMARY KEY
  - `tenant_id` VARCHAR(64) NOT NULL
  - `governance_capability_ref` VARCHAR(255) NOT NULL
  - `resource_id` VARCHAR(64) NOT NULL REFERENCES `critical_governance_resources`(`resource_id`)
  - `minimum_availability_pct` NUMERIC(5, 2) NOT NULL DEFAULT 99.00
  - `max_acceptable_interruption_minutes` INT NOT NULL DEFAULT 60
  - `min_service_capacity_pct` NUMERIC(5, 2) NOT NULL DEFAULT 80.00
  - `min_information_accessibility_pct` NUMERIC(5, 2) NOT NULL DEFAULT 90.00
  - `required_communication_capacity` VARCHAR(255) NOT NULL DEFAULT 'Standard secure channels'
  - `max_acceptable_dependency_concentration` INT NOT NULL DEFAULT 3
  - `continuity_requirement_ref` VARCHAR(255) NULL
  - `required_capacity_note` TEXT NULL
  - `reported_capacity_pct` NUMERIC(5, 2) NULL
  - `verified_capacity_pct` NUMERIC(5, 2) NULL
  - `capacity_shortfall_pct` NUMERIC(5, 2) NULL
  - `evidence_freshness_hours` NUMERIC(6, 2) NULL
  - `applicable_scenario` VARCHAR(255) NOT NULL DEFAULT 'NORMAL_OPERATIONS'
  - `evaluation_status` VARCHAR(64) NOT NULL DEFAULT 'UNEVALUATED' -- CAPACITY_ADEQUATE, CAPACITY_SHORTFALL_DETECTED, UNVERIFIED_ESTIMATE_ONLY, INSUFFICIENT_EVIDENCE, UNEVALUATED
  - `last_evaluated_at` TIMESTAMPTZ NULL
  - `created_by` VARCHAR(64) NOT NULL
  - `created_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `updated_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
- **Indexes**:
  - `ix_rcr_tenant_cap` (`tenant_id`, `governance_capability_ref`)
  - `ix_rcr_tenant_eval` (`tenant_id`, `evaluation_status`)

### 2.6 `dependency_graph_analyses`
- **Columns**:
  - `analysis_id` VARCHAR(64) PRIMARY KEY
  - `tenant_id` VARCHAR(64) NOT NULL
  - `analysis_scope` VARCHAR(255) NOT NULL DEFAULT 'ALL'
  - `total_resources_analyzed` INT NOT NULL DEFAULT 0
  - `total_dependencies_analyzed` INT NOT NULL DEFAULT 0
  - `spof_findings` JSONB NOT NULL DEFAULT '[]'
  - `circular_dependencies_detected` JSONB NOT NULL DEFAULT '[]'
  - `shared_dependencies` JSONB NOT NULL DEFAULT '[]'
  - `critical_path_resource_ids` JSONB NOT NULL DEFAULT '[]'
  - `capabilities_without_resource_mapping` JSONB NOT NULL DEFAULT '[]'
  - `resources_without_verified_availability` JSONB NOT NULL DEFAULT '[]'
  - `resources_without_fallback` JSONB NOT NULL DEFAULT '[]'
  - `analyzed_by` VARCHAR(64) NOT NULL
  - `analyzed_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `advisory_notes` JSONB NOT NULL DEFAULT '[]'
  - `disclaimer` TEXT NOT NULL
- **Indexes**:
  - `ix_dga_tenant_ts` (`tenant_id`, `analyzed_at` DESC)

### 2.7 `resource_dependency_gaps`
- **Columns**:
  - `gap_id` VARCHAR(64) PRIMARY KEY
  - `tenant_id` VARCHAR(64) NOT NULL
  - `governance_capability_ref` VARCHAR(255) NOT NULL
  - `resource_id` VARCHAR(64) NULL REFERENCES `critical_governance_resources`(`resource_id`)
  - `dependency_id` VARCHAR(64) NULL REFERENCES `capability_resource_dependency_mappings`(`dependency_id`)
  - `category` VARCHAR(64) NOT NULL -- UNMAPPED_DEPENDENCY, SINGLE_POINT_OF_FAILURE, ABSENT_FALLBACK, UNVERIFIED_FALLBACK, CAPACITY_SHORTFALL, STALE_MONITORING_DATA, CONCENTRATION_RISK, CIRCULAR_DEPENDENCY
  - `severity` VARCHAR(32) NOT NULL DEFAULT 'HIGH' -- CRITICAL, HIGH, MEDIUM, LOW
  - `status` VARCHAR(32) NOT NULL DEFAULT 'IDENTIFIED' -- IDENTIFIED, ASSIGNED, REMEDIATION_IN_PROGRESS, ESCALATED, RESOLVED, VERIFIED_RESOLVED, ACCEPTED_RISK
  - `title` VARCHAR(255) NOT NULL
  - `description` TEXT NOT NULL
  - `identified_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `assigned_to` VARCHAR(64) NULL
  - `remediation_proposal` TEXT NULL
  - `target_resolution_date` TIMESTAMPTZ NULL
  - `escalated_to_phase` VARCHAR(32) NULL
  - `escalation_reference_id` VARCHAR(64) NULL
  - `resolution_evidence_ref` VARCHAR(255) NULL
  - `resolved_at` TIMESTAMPTZ NULL
  - `resolution_verified_by` VARCHAR(64) NULL
  - `created_by` VARCHAR(64) NOT NULL
  - `created_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `updated_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `disclaimer` TEXT NOT NULL
- **Indexes**:
  - `ix_rdg_tenant_status` (`tenant_id`, `status`)
  - `ix_rdg_tenant_sev` (`tenant_id`, `severity`)
  - `ix_rdg_tenant_cap` (`tenant_id`, `governance_capability_ref`)

---

## 3. Migration Considerations & Constraints
- Cross-database constraints: Foreign keys reference existing tenant and organizational boundaries.
- No direct database mutation is performed by the application layer.
- All JSONB arrays default to valid JSON empty arrays `[]`.
- Audit timestamps (`created_at`, `updated_at`) must be preserved upon migration.
