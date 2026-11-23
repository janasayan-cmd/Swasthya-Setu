# Phase 85: Database Dependencies & Relational Persistence Specification

## Notice for Database Engineering Teammate

In compliance with the **Strict Database Ownership Boundary**, this document specifies the proposed persistence structures required for **Phase 85: Clinical Safety Governance Resilience Role-Coverage Continuity, Succession Readiness & Authorized Backup Coordination**.

The backend layer does **not** create or modify database tables, ORM models, schemas, migrations, indexes, constraints, foreign keys, triggers, or functions. All Phase 85 backend logic is currently backed by an isolated, thread-safe in-memory repository (`GovernanceRoleCoverageRepository`).

This document details the complete relational specification for the 7 primary entities when database migration is scheduled.

---

## 1. Entities Overview

| Entity Name | Primary Key | Business Purpose | Upstream Reference |
|---|---|---|---|
| `critical_governance_responsibilities` | `responsibility_id` (VARCHAR(64)) | Stores inventory of critical clinical safety governance roles and responsibilities | Core Users, Phase 84 Frameworks |
| `role_coverage_arrangements` | `coverage_id` (VARCHAR(64)) | Manages primary-backup coverage mappings, activation rules, and lifecycle states | `critical_governance_responsibilities` |
| `backup_verification_records` | `verification_id` (VARCHAR(64)) | Records independent verification of backup capability, administrative authorization, and availability | `role_coverage_arrangements`, Phase 84 Assessments |
| `coverage_scenario_evaluations` | `evaluation_id` (VARCHAR(64)) | Stores results of simulated disruption stress tests and coverage resilience percentages | Core Users, `critical_governance_responsibilities` |
| `governance_succession_plans` | `succession_plan_id` (VARCHAR(64)) | Coordinates succession pipelines, candidate readiness tiers, and development milestones | `critical_governance_responsibilities`, Phase 84 Proposals |
| `role_handover_records` | `handover_id` (VARCHAR(64)) | Tracks structured governance responsibility transitions, open safety items, and acknowledgements | `critical_governance_responsibilities`, Phases 54/63/67/72 |
| `role_coverage_gaps` | `gap_id` (VARCHAR(64)) | Tracks identified coverage deficits, remedial assignments, and authoritative escalations | `critical_governance_responsibilities`, Phases 54/63/67/72 |

---

## 2. Table Specifications

### 2.1 `critical_governance_responsibilities`
- **Columns**:
  - `responsibility_id` VARCHAR(64) PRIMARY KEY
  - `tenant_id` VARCHAR(64) NOT NULL
  - `role_title` VARCHAR(255) NOT NULL
  - `responsibility_name` VARCHAR(255) NOT NULL
  - `description` TEXT NOT NULL
  - `criticality_tier` VARCHAR(32) NOT NULL DEFAULT 'TIER_1_ESSENTIAL' -- TIER_1_ESSENTIAL, TIER_2_CRITICAL, TIER_3_IMPORTANT, TIER_4_SUPPORTING
  - `coverage_scope` VARCHAR(32) NOT NULL DEFAULT 'ORGANIZATION' -- ORGANIZATION, FACILITY, DEPARTMENT, SERVICE, CROSS_FUNCTIONAL
  - `max_acceptable_outage_hours` NUMERIC(6, 2) NOT NULL DEFAULT 4.00
  - `primary_owner_id` VARCHAR(64) NOT NULL
  - `primary_owner_name` VARCHAR(255) NOT NULL
  - `required_capability_framework_id` VARCHAR(64) NULL
  - `required_capability_ids` JSONB NOT NULL DEFAULT '[]'
  - `status` VARCHAR(32) NOT NULL DEFAULT 'ACTIVE'
  - `review_cycle_days` INT NOT NULL DEFAULT 90
  - `last_reviewed_at` TIMESTAMPTZ NULL
  - `next_review_due` TIMESTAMPTZ NULL
  - `created_by` VARCHAR(64) NOT NULL
  - `created_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `updated_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `disclaimer` TEXT NOT NULL
- **Indexes**:
  - `ix_cgr_tenant_tier` (`tenant_id`, `criticality_tier`)
  - `ix_cgr_primary_owner` (`tenant_id`, `primary_owner_id`)
  - `ix_cgr_next_review` (`tenant_id`, `next_review_due`)

### 2.2 `role_coverage_arrangements`
- **Columns**:
  - `coverage_id` VARCHAR(64) PRIMARY KEY
  - `tenant_id` VARCHAR(64) NOT NULL
  - `responsibility_id` VARCHAR(64) NOT NULL REFERENCES `critical_governance_responsibilities`(`responsibility_id`)
  - `status` VARCHAR(32) NOT NULL DEFAULT 'DRAFT' -- DRAFT, UNDER_REVIEW, EVIDENCE_PENDING, AUTHORIZATION_PENDING, APPROVED, ACTIVE, TEMPORARILY_UNAVAILABLE, EXPIRED, SUSPENDED, REVOKED, SUPERSEDED, CLOSED
  - `designated_backups` JSONB NOT NULL DEFAULT '[]' -- List of designated backup objects with precedence, verification flags, delegation refs
  - `effective_start_date` TIMESTAMPTZ NULL
  - `effective_end_date` TIMESTAMPTZ NULL
  - `activation_condition` TEXT NULL
  - `created_by` VARCHAR(64) NOT NULL
  - `reviewed_by` VARCHAR(64) NULL
  - `approved_by` VARCHAR(64) NULL
  - `approved_at` TIMESTAMPTZ NULL
  - `activation_notes` TEXT NULL
  - `created_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `updated_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `disclaimer` TEXT NOT NULL
- **Indexes**:
  - `ix_rca_tenant_status` (`tenant_id`, `status`)
  - `ix_rca_responsibility` (`tenant_id`, `responsibility_id`)
  - `ix_rca_effective_end` (`tenant_id`, `effective_end_date`)

### 2.3 `backup_verification_records`
- **Columns**:
  - `verification_id` VARCHAR(64) PRIMARY KEY
  - `tenant_id` VARCHAR(64) NOT NULL
  - `coverage_id` VARCHAR(64) NOT NULL REFERENCES `role_coverage_arrangements`(`coverage_id`)
  - `responsibility_id` VARCHAR(64) NOT NULL REFERENCES `critical_governance_responsibilities`(`responsibility_id`)
  - `backup_user_id` VARCHAR(64) NOT NULL
  - `status` VARCHAR(32) NOT NULL DEFAULT 'PENDING_REVIEW' -- VERIFIED, DEFICIENT, EXPIRED, PENDING_REVIEW
  - `capability_verified` BOOLEAN NOT NULL DEFAULT FALSE
  - `capability_assessment_ref` VARCHAR(64) NULL
  - `capability_assessment_date` TIMESTAMPTZ NULL
  - `authorization_verified` BOOLEAN NOT NULL DEFAULT FALSE
  - `authorization_ref` VARCHAR(128) NULL
  - `authorization_expires_at` TIMESTAMPTZ NULL
  - `concurrent_tier1_roles_count` INT NOT NULL DEFAULT 0
  - `availability_confirmed` BOOLEAN NOT NULL DEFAULT TRUE
  - `deficiencies` JSONB NOT NULL DEFAULT '[]'
  - `verified_by` VARCHAR(64) NOT NULL
  - `verified_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `next_verification_due` TIMESTAMPTZ NULL
  - `disclaimer` TEXT NOT NULL
- **Indexes**:
  - `ix_bvr_tenant_backup` (`tenant_id`, `backup_user_id`)
  - `ix_bvr_coverage_status` (`tenant_id`, `coverage_id`, `status`)
  - `ix_bvr_next_verification` (`tenant_id`, `next_verification_due`)

### 2.4 `coverage_scenario_evaluations`
- **Columns**:
  - `evaluation_id` VARCHAR(64) PRIMARY KEY
  - `tenant_id` VARCHAR(64) NOT NULL
  - `scenario_type` VARCHAR(32) NOT NULL -- PRIMARY_ABSENT, CONCURRENT_ABSENCE, EXTENDED_DISRUPTION, MASS_UNAVAILABILITY
  - `scenario_name` VARCHAR(255) NOT NULL
  - `simulated_unavailable_user_ids` JSONB NOT NULL DEFAULT '[]'
  - `total_critical_responsibilities_evaluated` INT NOT NULL DEFAULT 0
  - `fully_covered_count` INT NOT NULL DEFAULT 0
  - `partially_covered_count` INT NOT NULL DEFAULT 0
  - `uncovered_count` INT NOT NULL DEFAULT 0
  - `overall_coverage_resilience_percentage` NUMERIC(5, 2) NOT NULL DEFAULT 0.00
  - `uncovered_responsibility_ids` JSONB NOT NULL DEFAULT '[]'
  - `single_points_of_failure_revealed` JSONB NOT NULL DEFAULT '[]'
  - `evaluated_by` VARCHAR(64) NOT NULL
  - `evaluated_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `advisory_recommendations` JSONB NOT NULL DEFAULT '[]'
  - `disclaimer` TEXT NOT NULL
- **Indexes**:
  - `ix_cse_tenant_type` (`tenant_id`, `scenario_type`)
  - `ix_cse_evaluated_at` (`tenant_id`, `evaluated_at`)

### 2.5 `governance_succession_plans`
- **Columns**:
  - `succession_plan_id` VARCHAR(64) PRIMARY KEY
  - `tenant_id` VARCHAR(64) NOT NULL
  - `responsibility_id` VARCHAR(64) NOT NULL REFERENCES `critical_governance_responsibilities`(`responsibility_id`)
  - `role_title` VARCHAR(255) NOT NULL
  - `status` VARCHAR(32) NOT NULL DEFAULT 'DRAFT' -- DRAFT, UNDER_REVIEW, APPROVED, ACTIVE, ARCHIVED
  - `candidates` JSONB NOT NULL DEFAULT '[]' -- List of successor candidate objects with readiness tier and development refs
  - `review_cycle_days` INT NOT NULL DEFAULT 180
  - `last_reviewed_at` TIMESTAMPTZ NULL
  - `next_review_due` TIMESTAMPTZ NULL
  - `created_by` VARCHAR(64) NOT NULL
  - `approved_by` VARCHAR(64) NULL
  - `created_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `updated_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `disclaimer` TEXT NOT NULL
- **Indexes**:
  - `ix_gsp_tenant_resp` (`tenant_id`, `responsibility_id`)
  - `ix_gsp_status` (`tenant_id`, `status`)
  - `ix_gsp_next_review` (`tenant_id`, `next_review_due`)

### 2.6 `role_handover_records`
- **Columns**:
  - `handover_id` VARCHAR(64) PRIMARY KEY
  - `tenant_id` VARCHAR(64) NOT NULL
  - `responsibility_id` VARCHAR(64) NOT NULL REFERENCES `critical_governance_responsibilities`(`responsibility_id`)
  - `outgoing_user_id` VARCHAR(64) NOT NULL
  - `incoming_user_id` VARCHAR(64) NOT NULL
  - `handover_reason` TEXT NOT NULL
  - `effective_from` TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `expected_to` TIMESTAMPTZ NULL
  - `status` VARCHAR(32) NOT NULL DEFAULT 'INITIATED' -- INITIATED, PENDING_INCOMING_ACKNOWLEDGEMENT, ACKNOWLEDGED, COMPLETED, REJECTED, CANCELLED
  - `open_governance_items` JSONB NOT NULL DEFAULT '[]' -- List of open items with type, source phase, ref ID, urgency
  - `outgoing_checklist_completed` BOOLEAN NOT NULL DEFAULT FALSE
  - `outgoing_signoff_notes` TEXT NULL
  - `incoming_acknowledged_at` TIMESTAMPTZ NULL
  - `incoming_acknowledgement_notes` TEXT NULL
  - `supervisor_reviewed_by` VARCHAR(64) NULL
  - `created_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `updated_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `disclaimer` TEXT NOT NULL
- **Indexes**:
  - `ix_rhr_tenant_users` (`tenant_id`, `outgoing_user_id`, `incoming_user_id`)
  - `ix_rhr_responsibility_status` (`tenant_id`, `responsibility_id`, `status`)

### 2.7 `role_coverage_gaps`
- **Columns**:
  - `gap_id` VARCHAR(64) PRIMARY KEY
  - `tenant_id` VARCHAR(64) NOT NULL
  - `responsibility_id` VARCHAR(64) NOT NULL REFERENCES `critical_governance_responsibilities`(`responsibility_id`)
  - `category` VARCHAR(64) NOT NULL -- NO_BACKUP_DESIGNATED, UNVERIFIED_BACKUP_CAPABILITY, EXPIRED_DELEGATION, SINGLE_PERSON_BOTTLENECK, CONCURRENT_ALLOCATION_CONFLICT, SUCCESSION_DEFICIT
  - `severity` VARCHAR(32) NOT NULL DEFAULT 'HIGH' -- LOW, MEDIUM, HIGH, CRITICAL
  - `status` VARCHAR(32) NOT NULL DEFAULT 'IDENTIFIED' -- IDENTIFIED, ASSIGNED, REMEDIATION_IN_PROGRESS, VERIFIED_RESOLVED, ESCALATED, WAIVED_WITH_JUSTIFICATION
  - `title` VARCHAR(255) NOT NULL
  - `description` TEXT NOT NULL
  - `identified_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `assigned_to` VARCHAR(64) NULL
  - `escalated_to_phase` VARCHAR(64) NULL
  - `escalation_reference_id` VARCHAR(128) NULL
  - `remediation_notes` TEXT NULL
  - `resolved_at` TIMESTAMPTZ NULL
  - `resolution_verified_by` VARCHAR(64) NULL
  - `created_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `updated_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `disclaimer` TEXT NOT NULL
- **Indexes**:
  - `ix_rcg_tenant_status` (`tenant_id`, `status`, `severity`)
  - `ix_rcg_responsibility` (`tenant_id`, `responsibility_id`)

---

## 3. Separation of Duties and Integrity Rules
1. **Self-Approval Prohibition**: Coverage arrangements cannot be approved by the proposer (`created_by == approver_id`) or by any designated backup (`backup_user_id == approver_id`).
2. **Succession Plan Separation**: Succession plans cannot be approved by their creator or by any nominated successor candidate.
3. **Handover Self-Transition Prohibition**: Incoming user must be distinct from outgoing user. Incoming user must independently acknowledge the handover before it can be marked completed.
4. **Evidence-Backed Gap Resolution**: Gaps cannot transition to `VERIFIED_RESOLVED` without referencing either an active verified coverage mapping or an approved succession plan.
