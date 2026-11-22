# Phase 83: Database Dependencies & Relational Persistence Specification

## Notice for Database Engineering Teammate

In compliance with the **Strict Database Ownership Boundary**, this document specifies the proposed persistence structures required for **Phase 83: Clinical Safety Governance Resilience Knowledge Management, Organizational Learning & Continuous Preparedness Capability Development**.

The backend layer does **not** create or modify database tables, ORM models, schemas, migrations, indexes, constraints, foreign keys, triggers, or functions. All Phase 83 backend logic is currently backed by an isolated, thread-safe in-memory repository (`GovernanceResilienceKnowledgeRepository`).

This document details the complete relational specification for the 8 entities when database migration is scheduled.

---

## 1. Entities Overview

| Entity Name | Primary Key | Business Purpose | Upstream Reference |
|---|---|---|---|
| `governance_resilience_knowledge_records` | `knowledge_id` (VARCHAR(64)) | Stores validated resilience guidance, operational lessons, material versions, and lifecycle status | Phase 80 Continuity, Phase 81 Exercises, Phase 82 Intelligence |
| `knowledge_distribution_campaigns` | `campaign_id` (VARCHAR(64)) | Stores targeted distribution campaigns, audience scopes, and delivery governance gates | `governance_resilience_knowledge_records` |
| `knowledge_acknowledgement_records` | `acknowledgement_id` (VARCHAR(64)) | Tracks recipient delivery, view timestamps, and formal acknowledgements | `knowledge_distribution_campaigns`, Core Users |
| `knowledge_application_evidence` | `evidence_id` (VARCHAR(64)) | Stores observed operational application evidence in exercises/real incidents and Phase 55 link | `governance_resilience_knowledge_records`, Phase 55 Assessment |
| `organizational_learning_gaps` | `gap_id` (VARCHAR(64)) | Tracks systemic resilience learning gaps, human review validation, and Phase 54 CAPA referral | Phase 80 Disruption, Phase 81 Exercises, Phase 54 CAPA |
| `resilience_capability_recommendations` | `recommendation_id` (VARCHAR(64)) | Stores advisory continuous preparedness capability recommendations and target milestones | `organizational_learning_gaps`, `governance_resilience_knowledge_records` |
| `knowledge_transfer_records` | `transfer_id` (VARCHAR(64)) | Governs knowledge succession handoffs, checklists, and independent verification | `governance_resilience_knowledge_records`, Core Users |
| `knowledge_conflict_records` | `conflict_id` (VARCHAR(64)) | Records contradictory/obsolete guidance across silos and resolution decisions | `governance_resilience_knowledge_records` |

---

## 2. Table Specifications

### 2.1 `governance_resilience_knowledge_records`
- **Columns**:
  - `knowledge_id` VARCHAR(64) PRIMARY KEY
  - `tenant_id` VARCHAR(64) NOT NULL
  - `title` VARCHAR(255) NOT NULL
  - `category` VARCHAR(64) NOT NULL -- VALIDATED_LESSONS_LEARNED, CONTINUITY_OPERATING_GUIDANCE, etc.
  - `summary` TEXT NOT NULL
  - `content` TEXT NOT NULL
  - `source_phase` VARCHAR(32) NULL
  - `source_reference_id` VARCHAR(64) NULL
  - `tags` JSONB NOT NULL DEFAULT '[]'
  - `confidentiality_level` VARCHAR(32) NOT NULL DEFAULT 'INTERNAL' -- PUBLIC, INTERNAL, RESTRICTED, CONFIDENTIAL
  - `owner_id` VARCHAR(64) NOT NULL
  - `author_id` VARCHAR(64) NOT NULL
  - `current_state` VARCHAR(32) NOT NULL DEFAULT 'DRAFT' -- DRAFT, SUBMITTED_FOR_REVIEW, UNDER_REVIEW, CHANGES_REQUESTED, VALIDATED, APPROVED_FOR_PUBLICATION, PUBLISHED, UNDER_SCHEDULED_REVIEW, SUPERSEDED, WITHDRAWN, ARCHIVED
  - `version` INT NOT NULL DEFAULT 1
  - `previous_version_id` VARCHAR(64) NULL
  - `review_due_date` TIMESTAMPTZ NULL
  - `published_at` TIMESTAMPTZ NULL
  - `validated_by` VARCHAR(64) NULL
  - `approved_by` VARCHAR(64) NULL
  - `withdrawn_reason` TEXT NULL
  - `superseded_by_id` VARCHAR(64) NULL
  - `disclaimer` TEXT NOT NULL
  - `created_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `updated_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
- **Indexes**:
  - `ix_rkm_tenant_category` (`tenant_id`, `category`)
  - `ix_rkm_tenant_state` (`tenant_id`, `current_state`)
  - `ix_rkm_tenant_owner` (`tenant_id`, `owner_id`)
  - `ix_rkm_review_due` (`tenant_id`, `review_due_date`)

### 2.2 `knowledge_distribution_campaigns`
- **Columns**:
  - `campaign_id` VARCHAR(64) PRIMARY KEY
  - `tenant_id` VARCHAR(64) NOT NULL
  - `knowledge_id` VARCHAR(64) NOT NULL REFERENCES `governance_resilience_knowledge_records`(`knowledge_id`)
  - `knowledge_version` INT NOT NULL DEFAULT 1
  - `title` VARCHAR(255) NOT NULL
  - `description` TEXT NULL
  - `target_audiences` JSONB NOT NULL DEFAULT '[]'
  - `acknowledgement_required` BOOLEAN NOT NULL DEFAULT TRUE
  - `due_date` TIMESTAMPTZ NULL
  - `status` VARCHAR(32) NOT NULL DEFAULT 'DRAFT' -- DRAFT, APPROVED, DISPATCHED, COMPLETED, CANCELLED
  - `created_by` VARCHAR(64) NOT NULL
  - `approved_by` VARCHAR(64) NULL
  - `dispatched_at` TIMESTAMPTZ NULL
  - `completed_at` TIMESTAMPTZ NULL
  - `dispatch_notes` TEXT NULL
  - `disclaimer` TEXT NOT NULL
  - `created_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `updated_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
- **Indexes**:
  - `ix_kdc_tenant_knowledge` (`tenant_id`, `knowledge_id`)
  - `ix_kdc_tenant_status` (`tenant_id`, `status`)

### 2.3 `knowledge_acknowledgement_records`
- **Columns**:
  - `acknowledgement_id` VARCHAR(64) PRIMARY KEY
  - `tenant_id` VARCHAR(64) NOT NULL
  - `campaign_id` VARCHAR(64) NOT NULL REFERENCES `knowledge_distribution_campaigns`(`campaign_id`)
  - `knowledge_id` VARCHAR(64) NOT NULL REFERENCES `governance_resilience_knowledge_records`(`knowledge_id`)
  - `user_id` VARCHAR(64) NOT NULL
  - `user_role` VARCHAR(64) NULL
  - `facility_id` VARCHAR(64) NULL
  - `department_id` VARCHAR(64) NULL
  - `status` VARCHAR(32) NOT NULL DEFAULT 'DELIVERED' -- DELIVERED, VIEWED, ACKNOWLEDGED
  - `delivered_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `viewed_at` TIMESTAMPTZ NULL
  - `acknowledged_at` TIMESTAMPTZ NULL
  - `acknowledgement_notes` TEXT NULL
  - `disclaimer` TEXT NOT NULL
- **Indexes**:
  - `ix_kar_tenant_campaign_user` (`tenant_id`, `campaign_id`, `user_id`)
  - `ix_kar_user_status` (`tenant_id`, `user_id`, `status`)

### 2.4 `knowledge_application_evidence`
- **Columns**:
  - `evidence_id` VARCHAR(64) PRIMARY KEY
  - `tenant_id` VARCHAR(64) NOT NULL
  - `knowledge_id` VARCHAR(64) NOT NULL REFERENCES `governance_resilience_knowledge_records`(`knowledge_id`)
  - `operational_context` VARCHAR(64) NOT NULL -- CONTINUITY_EXERCISE, REAL_DISRUPTION_RESPONSE, etc.
  - `operational_reference_id` VARCHAR(64) NULL
  - `description` TEXT NOT NULL
  - `observed_effectiveness_rating` INT NOT NULL -- 1 to 5
  - `phase55_assessment_id` VARCHAR(64) NULL
  - `submitted_by` VARCHAR(64) NOT NULL
  - `verified_by` VARCHAR(64) NULL
  - `status` VARCHAR(32) NOT NULL DEFAULT 'RECORDED' -- RECORDED, VERIFIED, REJECTED
  - `rejection_notes` TEXT NULL
  - `disclaimer` TEXT NOT NULL
  - `created_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `verified_at` TIMESTAMPTZ NULL
- **Indexes**:
  - `ix_kae_tenant_knowledge` (`tenant_id`, `knowledge_id`)
  - `ix_kae_context` (`tenant_id`, `operational_context`)

### 2.5 `organizational_learning_gaps`
- **Columns**:
  - `gap_id` VARCHAR(64) PRIMARY KEY
  - `tenant_id` VARCHAR(64) NOT NULL
  - `gap_type` VARCHAR(64) NOT NULL -- UNADDRESSED_EXERCISE_FINDING, REPEATED_DISRUPTION_FAILURE, etc.
  - `severity` VARCHAR(32) NOT NULL DEFAULT 'MEDIUM' -- LOW, MEDIUM, HIGH, CRITICAL
  - `title` VARCHAR(255) NOT NULL
  - `description` TEXT NOT NULL
  - `affected_capabilities` JSONB NOT NULL DEFAULT '[]'
  - `affected_roles` JSONB NOT NULL DEFAULT '[]'
  - `affected_facilities` JSONB NOT NULL DEFAULT '[]'
  - `source_exercise_id` VARCHAR(64) NULL
  - `source_disruption_id` VARCHAR(64) NULL
  - `identified_by` VARCHAR(64) NOT NULL
  - `validated_by` VARCHAR(64) NULL
  - `status` VARCHAR(32) NOT NULL DEFAULT 'IDENTIFIED' -- IDENTIFIED, VALIDATED, CAPA_REFERRED, RESOLVED, CLOSED
  - `capa_referral_id` VARCHAR(64) NULL
  - `resolution_notes` TEXT NULL
  - `disclaimer` TEXT NOT NULL
  - `identified_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `validated_at` TIMESTAMPTZ NULL
  - `resolved_at` TIMESTAMPTZ NULL
- **Indexes**:
  - `ix_olg_tenant_status` (`tenant_id`, `status`)
  - `ix_olg_type_severity` (`tenant_id`, `gap_type`, `severity`)

### 2.6 `resilience_capability_recommendations`
- **Columns**:
  - `recommendation_id` VARCHAR(64) PRIMARY KEY
  - `tenant_id` VARCHAR(64) NOT NULL
  - `activity_type` VARCHAR(64) NOT NULL -- TARGETED_TRAINING, SIMULATION_DRILL, etc.
  - `priority` VARCHAR(32) NOT NULL DEFAULT 'MEDIUM' -- LOW, MEDIUM, HIGH, CRITICAL
  - `title` VARCHAR(255) NOT NULL
  - `rationalization` TEXT NOT NULL
  - `target_capabilities` JSONB NOT NULL DEFAULT '[]'
  - `target_roles` JSONB NOT NULL DEFAULT '[]'
  - `target_facilities` JSONB NOT NULL DEFAULT '[]'
  - `linked_learning_gap_ids` JSONB NOT NULL DEFAULT '[]'
  - `linked_knowledge_ids` JSONB NOT NULL DEFAULT '[]'
  - `status` VARCHAR(32) NOT NULL DEFAULT 'PROPOSED' -- PROPOSED, ACCEPTED, SCHEDULED, COMPLETED, DEFERRED, REJECTED
  - `proposed_by` VARCHAR(64) NOT NULL
  - `approved_by` VARCHAR(64) NULL
  - `completion_notes` TEXT NULL
  - `scheduled_date` TIMESTAMPTZ NULL
  - `completed_at` TIMESTAMPTZ NULL
  - `disclaimer` TEXT NOT NULL
  - `created_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
- **Indexes**:
  - `ix_rcr_tenant_status` (`tenant_id`, `status`)
  - `ix_rcr_priority` (`tenant_id`, `priority`)

### 2.7 `knowledge_transfer_records`
- **Columns**:
  - `transfer_id` VARCHAR(64) PRIMARY KEY
  - `tenant_id` VARCHAR(64) NOT NULL
  - `knowledge_ids` JSONB NOT NULL DEFAULT '[]'
  - `transferring_owner_id` VARCHAR(64) NOT NULL
  - `successor_owner_id` VARCHAR(64) NOT NULL
  - `reason` TEXT NOT NULL
  - `handoff_checklist` JSONB NOT NULL DEFAULT '{}'
  - `status` VARCHAR(32) NOT NULL DEFAULT 'INITIATED' -- INITIATED, IN_PROGRESS, COMPLETED, VERIFIED, REJECTED
  - `initiated_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `completed_at` TIMESTAMPTZ NULL
  - `verified_by` VARCHAR(64) NULL
  - `verified_at` TIMESTAMPTZ NULL
  - `rejection_notes` TEXT NULL
  - `disclaimer` TEXT NOT NULL
- **Indexes**:
  - `ix_ktr_tenant_transferring` (`tenant_id`, `transferring_owner_id`)
  - `ix_ktr_tenant_successor` (`tenant_id`, `successor_owner_id`)
  - `ix_ktr_tenant_status` (`tenant_id`, `status`)

### 2.8 `knowledge_conflict_records`
- **Columns**:
  - `conflict_id` VARCHAR(64) PRIMARY KEY
  - `tenant_id` VARCHAR(64) NOT NULL
  - `conflict_type` VARCHAR(64) NOT NULL -- DIRECT_CONTRADICTION, VERSION_AMBIGUITY, etc.
  - `description` TEXT NOT NULL
  - `primary_knowledge_id` VARCHAR(64) NOT NULL REFERENCES `governance_resilience_knowledge_records`(`knowledge_id`)
  - `conflicting_knowledge_id` VARCHAR(64) NOT NULL REFERENCES `governance_resilience_knowledge_records`(`knowledge_id`)
  - `detected_by` VARCHAR(64) NOT NULL
  - `status` VARCHAR(32) NOT NULL DEFAULT 'DETECTED' -- DETECTED, UNDER_EVALUATION, RESOLVED, DISMISSED
  - `resolution_strategy` TEXT NULL
  - `resolution_rationale` TEXT NULL
  - `resolved_by` VARCHAR(64) NULL
  - `detected_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - `resolved_at` TIMESTAMPTZ NULL
  - `disclaimer` TEXT NOT NULL
- **Indexes**:
  - `ix_kcr_tenant_status` (`tenant_id`, `status`)
  - `ix_kcr_conflict_type` (`tenant_id`, `conflict_type`)

---

## 3. Migration Sequence Guidance

When the database team applies these tables:
1. Create `governance_resilience_knowledge_records` first.
2. Create `knowledge_distribution_campaigns` with FK to `governance_resilience_knowledge_records`.
3. Create `knowledge_acknowledgement_records` with FKs to campaigns and knowledge records.
4. Create `knowledge_application_evidence` with FK to `governance_resilience_knowledge_records`.
5. Create `organizational_learning_gaps`.
6. Create `resilience_capability_recommendations`.
7. Create `knowledge_transfer_records`.
8. Create `knowledge_conflict_records` with self-referencing FKs to `governance_resilience_knowledge_records`.
