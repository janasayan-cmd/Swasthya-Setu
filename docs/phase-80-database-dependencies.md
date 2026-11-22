# Phase 80: Database Persistence Requirements & Contracts

**Module**: Clinical Safety Governance Strategic Resilience, Continuity Planning & Recovery Assurance  
**Consumer**: Database Teammate  
**Backend Layer**: In-Memory Thread-Safe Singleton Repository (`GovernanceContinuityRepository`)  
**Strict Boundary**: Backend does **not** create or modify tables, ORM models, migrations, or indexes. All persistence models below represent the authoritative contract for the database teammate.

---

## 1. Relational Schema Architecture

```
                               ┌──────────────────────────────────────────────┐
                               │     governance_continuity_capabilities       │
                               └──────────────────────┬───────────────────────┘
                                                      │
                       ┌──────────────────────────────┼──────────────────────────────┐
                       ▼                              ▼                              ▼
┌──────────────────────────────┐ ┌──────────────────────────────┐ ┌──────────────────────────────┐
│  continuity_requirements     │ │  continuity_dependencies     │ │   continuity_plans           │
└──────────────────────────────┘ └──────────────────────────────┘ └──────────────┬───────────────┘
                                                                                 │
                                                                                 ▼
                                                                  ┌──────────────────────────────┐
                                                                  │    continuity_activations    │
                                                                  └──────────────┬───────────────┘
                                                                                 │
                       ┌─────────────────────────────────────────────────────────┼─────────────────────────────────────────┐
                       ▼                                                         ▼                                         ▼
┌──────────────────────────────┐                          ┌──────────────────────────────┐          ┌──────────────────────────────┐
│  alternative_arrangements    │                          │     temporary_decisions      │          │    continuity_recoveries     │
└──────────────────────────────┘                          └──────────────────────────────┘          └──────────────────────────────┘
                       │                                                         │                                         │
                       └─────────────────────────────────────────────────────────┼─────────────────────────────────────────┘
                                                                                 │
                                                                                 ▼
                                                                  ┌──────────────────────────────┐
                                                                  │       continuity_gaps        │
                                                                  └──────────────────────────────┘
```

---

## 2. Table Specifications

### 2.1 `governance_continuity_capabilities`
Stores critical clinical safety governance capabilities, classifications, and continuity attributes.
- `capability_id`: `VARCHAR(64)` PRIMARY KEY
- `tenant_id`: `VARCHAR(64)` NOT NULL INDEX
- `name`: `VARCHAR(255)` NOT NULL
- `description`: `TEXT` NOT NULL
- `organizational_scope`: `JSONB` NOT NULL DEFAULT `'{}'`
- `responsible_department`: `VARCHAR(128)` NOT NULL
- `accountable_owner_id`: `VARCHAR(64)` NOT NULL
- `supporting_roles`: `JSONB` NOT NULL DEFAULT `'[]'`
- `related_workflow`: `VARCHAR(128)` NOT NULL
- `criticality`: `VARCHAR(32)` NOT NULL (`TIER_1_CRITICAL`, `TIER_2_ESSENTIAL`, `TIER_3_IMPORTANT`, `TIER_4_SUPPORTING`)
- `continuity_requirement_id`: `VARCHAR(64)` NULL
- `required_supporting_systems`: `JSONB` NOT NULL DEFAULT `'[]'`
- `required_integrations`: `JSONB` NOT NULL DEFAULT `'[]'`
- `required_information_sources`: `JSONB` NOT NULL DEFAULT `'[]'`
- `minimum_operational_requirements`: `TEXT` NOT NULL
- `max_acceptable_interruption_hours`: `NUMERIC(6,2)` NOT NULL DEFAULT 4.00
- `recovery_priority`: `INTEGER` NOT NULL DEFAULT 1
- `status`: `VARCHAR(32)` NOT NULL DEFAULT `'DRAFT'` (`DRAFT`, `SUBMITTED`, `APPROVED`, `ACTIVE`, `RETIRED`)
- `approved_by`: `VARCHAR(64)` NULL
- `approval_reference`: `VARCHAR(128)` NULL
- `review_date`: `TIMESTAMPTZ` NOT NULL
- `version`: `INTEGER` NOT NULL DEFAULT 1
- `disclaimer`: `TEXT` NOT NULL
- `created_at`: `TIMESTAMPTZ` NOT NULL
- `updated_at`: `TIMESTAMPTZ` NOT NULL
- **Constraints & Indexes**:
  - `idx_gcc_tenant_crit`: `(tenant_id, criticality)`
  - `idx_gcc_status`: `(tenant_id, status)`

### 2.2 `governance_continuity_requirements`
Stores formal continuity targets and recovery metrics (RTO, RPO, MTPD, MBCO).
- `requirement_id`: `VARCHAR(64)` PRIMARY KEY
- `tenant_id`: `VARCHAR(64)` NOT NULL INDEX
- `capability_id`: `VARCHAR(64)` NOT NULL INDEX
- `required_operating_hours`: `VARCHAR(128)` NOT NULL
- `max_acceptable_interruption_hours`: `NUMERIC(6,2)` NOT NULL
- `recovery_time_objective_hours`: `NUMERIC(6,2)` NOT NULL (RTO)
- `recovery_point_objective_hours`: `NUMERIC(6,2)` NOT NULL (RPO)
- `maximum_tolerable_period_disruption_hours`: `NUMERIC(6,2)` NOT NULL (MTPD)
- `minimum_continuity_objective`: `TEXT` NOT NULL (MBCO)
- `required_staffing_coverage`: `TEXT` NOT NULL
- `required_role_availability`: `JSONB` NOT NULL DEFAULT `'[]'`
- `required_communication_channels`: `JSONB` NOT NULL DEFAULT `'[]'`
- `required_supporting_systems`: `JSONB` NOT NULL DEFAULT `'[]'`
- `required_escalation_arrangements`: `TEXT` NOT NULL
- `required_manual_alternatives`: `TEXT` NOT NULL
- `evidence_required_to_verify`: `TEXT` NOT NULL
- `status`: `VARCHAR(32)` NOT NULL DEFAULT `'DRAFT'` (`DRAFT`, `SUBMITTED`, `APPROVED`, `SUPERSEDED`)
- `approved_by`: `VARCHAR(64)` NULL
- `approval_reference`: `VARCHAR(128)` NULL
- `version`: `INTEGER` NOT NULL DEFAULT 1
- `disclaimer`: `TEXT` NOT NULL
- `created_at`: `TIMESTAMPTZ` NOT NULL
- `updated_at`: `TIMESTAMPTZ` NOT NULL

### 2.3 `governance_continuity_dependencies`
Maps inter-domain dependencies across personnel, systems, information, and external partners.
- `dependency_id`: `VARCHAR(64)` PRIMARY KEY
- `tenant_id`: `VARCHAR(64)` NOT NULL INDEX
- `source_capability_id`: `VARCHAR(64)` NOT NULL INDEX
- `dependency_type`: `VARCHAR(32)` NOT NULL (`PERSONNEL`, `SYSTEM`, `INFORMATION`, `EXTERNAL`)
- `target_reference`: `VARCHAR(255)` NOT NULL
- `criticality`: `VARCHAR(16)` NOT NULL (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`)
- `responsible_owner_id`: `VARCHAR(64)` NOT NULL
- `availability_requirements`: `TEXT` NOT NULL
- `has_validated_alternative`: `BOOLEAN` NOT NULL DEFAULT FALSE
- `alternative_arrangement_description`: `TEXT` NOT NULL DEFAULT ''
- `is_single_point_of_failure`: `BOOLEAN` NOT NULL DEFAULT FALSE
- `last_validation_date`: `TIMESTAMPTZ` NULL
- `status`: `VARCHAR(32)` NOT NULL DEFAULT `'IDENTIFIED'` (`IDENTIFIED`, `VALIDATED`, `UNVALIDATED`, `CONFLICT_DETECTED`, `WAIVED`)
- `evidence_references`: `JSONB` NOT NULL DEFAULT `'[]'`
- `disclaimer`: `TEXT` NOT NULL
- `created_at`: `TIMESTAMPTZ` NOT NULL
- `updated_at`: `TIMESTAMPTZ` NOT NULL
- **Constraints & Indexes**:
  - `idx_gcd_spof`: `(tenant_id, is_single_point_of_failure)`
  - `idx_gcd_status`: `(tenant_id, status)`

### 2.4 `governance_continuity_plans`
Stores version-controlled continuity plans covering critical governance capabilities.
- `plan_id`: `VARCHAR(64)` PRIMARY KEY
- `tenant_id`: `VARCHAR(64)` NOT NULL INDEX
- `title`: `VARCHAR(255)` NOT NULL
- `organizational_scope`: `JSONB` NOT NULL DEFAULT `'{}'`
- `covered_capability_ids`: `JSONB` NOT NULL DEFAULT `'[]'`
- `plan_owner_id`: `VARCHAR(64)` NOT NULL
- `authorized_approver_id`: `VARCHAR(64)` NULL
- `activation_conditions`: `TEXT` NOT NULL
- `disruption_categories`: `JSONB` NOT NULL DEFAULT `'[]'`
- `escalation_procedures`: `TEXT` NOT NULL
- `communication_arrangements`: `TEXT` NOT NULL
- `alternative_operating_procedures`: `TEXT` NOT NULL
- `delegation_arrangements`: `TEXT` NOT NULL
- `required_resources`: `TEXT` NOT NULL
- `recovery_priorities`: `TEXT` NOT NULL
- `restoration_criteria`: `TEXT` NOT NULL
- `verification_requirements`: `TEXT` NOT NULL
- `testing_schedule`: `VARCHAR(255)` NOT NULL
- `review_schedule`: `VARCHAR(255)` NOT NULL
- `status`: `VARCHAR(32)` NOT NULL DEFAULT `'DRAFT'` (`DRAFT`, `UNDER_REVIEW`, `SUBMITTED`, `APPROVED`, `ACTIVE`, `UNDER_REVISION`, `SUPERSEDED`, `RETIRED`)
- `version`: `INTEGER` NOT NULL DEFAULT 1
- `approval_reference`: `VARCHAR(128)` NULL
- `approval_history`: `JSONB` NOT NULL DEFAULT `'[]'`
- `version_history`: `JSONB` NOT NULL DEFAULT `'[]'`
- `disclaimer`: `TEXT` NOT NULL
- `created_at`: `TIMESTAMPTZ` NOT NULL
- `updated_at`: `TIMESTAMPTZ` NOT NULL

### 2.5 `governance_continuity_disruptions`
Captures operational disruptions affecting clinical safety governance.
- `disruption_id`: `VARCHAR(64)` PRIMARY KEY
- `tenant_id`: `VARCHAR(64)` NOT NULL INDEX
- `category`: `VARCHAR(48)` NOT NULL
- `description`: `TEXT` NOT NULL
- `affected_organizational_scope`: `JSONB` NOT NULL DEFAULT `'{}'`
- `affected_capability_ids`: `JSONB` NOT NULL DEFAULT `'[]'`
- `source_incident_reference`: `VARCHAR(128)` NULL
- `detection_timestamp`: `TIMESTAMPTZ` NOT NULL
- `reported_impact`: `TEXT` NOT NULL
- `evidence_references`: `JSONB` NOT NULL DEFAULT `'[]'`
- `status`: `VARCHAR(32)` NOT NULL DEFAULT `'ACTIVE'` (`ACTIVE`, `INVESTIGATING`, `CONTAINED`, `RESOLVED`, `CLOSED`)
- `responsible_coordinator_id`: `VARCHAR(64)` NOT NULL
- `escalation_destination`: `VARCHAR(64)` NOT NULL DEFAULT `'PHASE_67_ESCALATION'`
- `related_plan_id`: `VARCHAR(64)` NULL
- `recovery_status`: `VARCHAR(32)` NOT NULL DEFAULT `'NOT_STARTED'`
- `disclaimer`: `TEXT` NOT NULL
- `created_at`: `TIMESTAMPTZ` NOT NULL
- `updated_at`: `TIMESTAMPTZ` NOT NULL

### 2.6 `governance_continuity_activations`
Maintains authorized continuity plan activations and decision audit trails.
- `activation_id`: `VARCHAR(64)` PRIMARY KEY
- `tenant_id`: `VARCHAR(64)` NOT NULL INDEX
- `triggering_disruption_id`: `VARCHAR(64)` NOT NULL INDEX
- `affected_capability_ids`: `JSONB` NOT NULL DEFAULT `'[]'`
- `applicable_plan_id`: `VARCHAR(64)` NOT NULL INDEX
- `plan_version`: `INTEGER` NOT NULL
- `activation_requestor_id`: `VARCHAR(64)` NOT NULL
- `authorized_decision_maker_id`: `VARCHAR(64)` NULL
- `decision_timestamp`: `TIMESTAMPTZ` NULL
- `status`: `VARCHAR(32)` NOT NULL DEFAULT `'PROPOSED'` (`PROPOSED`, `UNDER_ASSESSMENT`, `APPROVED`, `ACTIVATED`, `PARTIALLY_ACTIVATED`, `REJECTED`, `DEACTIVATED`, `CLOSED`)
- `decision_rationale`: `TEXT` NULL
- `alternative_operating_arrangements`: `JSONB` NOT NULL DEFAULT `'[]'`
- `responsible_coordinator_id`: `VARCHAR(64)` NOT NULL
- `acknowledgement_timestamp`: `TIMESTAMPTZ` NULL
- `communication_references`: `JSONB` NOT NULL DEFAULT `'[]'`
- `disclaimer`: `TEXT` NOT NULL
- `created_at`: `TIMESTAMPTZ` NOT NULL
- `updated_at`: `TIMESTAMPTZ` NOT NULL

### 2.7 `governance_alternative_arrangements`
Tracks authorized temporary operating arrangements during disruptions.
- `arrangement_id`: `VARCHAR(64)` PRIMARY KEY
- `tenant_id`: `VARCHAR(64)` NOT NULL INDEX
- `activation_id`: `VARCHAR(64)` NOT NULL INDEX
- `affected_capability_id`: `VARCHAR(64)` NOT NULL INDEX
- `description`: `TEXT` NOT NULL
- `authorized_procedure_reference`: `VARCHAR(128)` NOT NULL
- `responsible_owner_id`: `VARCHAR(64)` NOT NULL
- `activation_time`: `TIMESTAMPTZ` NOT NULL
- `expiry_or_review_time`: `TIMESTAMPTZ` NOT NULL
- `evidence_capture_requirements`: `TEXT` NOT NULL
- `data_reconciliation_requirements`: `TEXT` NOT NULL
- `security_restrictions`: `TEXT` NOT NULL
- `deactivation_conditions`: `TEXT` NOT NULL
- `verification_status`: `VARCHAR(32)` NOT NULL DEFAULT `'ACTIVE'` (`ACTIVE`, `REVIEW_DUE`, `RECONCILIATION_PENDING`, `DEACTIVATED`, `VERIFIED_CLOSED`)
- `disclaimer`: `TEXT` NOT NULL
- `created_at`: `TIMESTAMPTZ` NOT NULL
- `updated_at`: `TIMESTAMPTZ` NOT NULL

### 2.8 `governance_temporary_decisions`
Maintains decisions made under continuity arrangements for controlled reconciliation into authoritative workflows.
- `temporary_decision_id`: `VARCHAR(64)` PRIMARY KEY
- `tenant_id`: `VARCHAR(64)` NOT NULL INDEX
- `activation_id`: `VARCHAR(64)` NOT NULL INDEX
- `decision_title`: `VARCHAR(255)` NOT NULL
- `decision_summary`: `TEXT` NOT NULL
- `decision_authority_role`: `VARCHAR(128)` NOT NULL
- `authorized_decision_maker_id`: `VARCHAR(64)` NOT NULL
- `delegation_reference`: `VARCHAR(128)` NULL
- `decision_timestamp`: `TIMESTAMPTZ` NOT NULL
- `supporting_evidence_references`: `JSONB` NOT NULL DEFAULT `'[]'`
- `temporary_documentation_reference`: `VARCHAR(128)` NOT NULL
- `reconciliation_status`: `VARCHAR(32)` NOT NULL DEFAULT `'PENDING'` (`PENDING`, `UNDER_RECONCILIATION`, `RECONCILED`, `CONFLICT_DETECTED`, `REJECTED`)
- `reconciliation_timestamp`: `TIMESTAMPTZ` NULL
- `receiving_authoritative_record_id`: `VARCHAR(128)` NULL (Phase 72, 63, 54, or 49 reference)
- `reconciled_by`: `VARCHAR(64)` NULL
- `conflict_description`: `TEXT` NULL
- `disclaimer`: `TEXT` NOT NULL
- `created_at`: `TIMESTAMPTZ` NOT NULL
- `updated_at`: `TIMESTAMPTZ` NOT NULL

### 2.9 `governance_continuity_recoveries`
Tracks recovery progress, technical vs. operational restoration, and independent verification.
- `recovery_id`: `VARCHAR(64)` PRIMARY KEY
- `tenant_id`: `VARCHAR(64)` NOT NULL INDEX
- `disruption_id`: `VARCHAR(64)` NOT NULL INDEX
- `capability_id`: `VARCHAR(64)` NOT NULL INDEX
- `pre_disruption_operating_state`: `TEXT` NOT NULL
- `recovery_start_time`: `TIMESTAMPTZ` NOT NULL
- `recovery_milestones`: `JSONB` NOT NULL DEFAULT `'[]'`
- `recovery_status`: `VARCHAR(32)` NOT NULL DEFAULT `'IN_PROGRESS'`
- `evidence_of_restored_functionality`: `TEXT` NOT NULL DEFAULT ''
- `responsible_verifier_id`: `VARCHAR(64)` NULL
- `verification_timestamp`: `TIMESTAMPTZ` NULL
- `verification_notes`: `TEXT` NULL
- `outstanding_limitations`: `TEXT` NOT NULL DEFAULT ''
- `disclaimer`: `TEXT` NOT NULL
- `created_at`: `TIMESTAMPTZ` NOT NULL
- `updated_at`: `TIMESTAMPTZ` NOT NULL

### 2.10 `governance_continuity_exercises`
Stores continuity exercises, simulations, observed results, and weakness evaluations.
- `exercise_id`: `VARCHAR(64)` PRIMARY KEY
- `tenant_id`: `VARCHAR(64)` NOT NULL INDEX
- `title`: `VARCHAR(255)` NOT NULL
- `exercise_type`: `VARCHAR(48)` NOT NULL
- `scope`: `TEXT` NOT NULL
- `objectives`: `TEXT` NOT NULL
- `applicable_plan_id`: `VARCHAR(64)` NOT NULL INDEX
- `plan_version`: `INTEGER` NOT NULL
- `participating_departments`: `JSONB` NOT NULL DEFAULT `'[]'`
- `coordinator_id`: `VARCHAR(64)` NOT NULL
- `planned_date`: `TIMESTAMPTZ` NOT NULL
- `actual_date`: `TIMESTAMPTZ` NULL
- `scenario`: `TEXT` NOT NULL
- `expected_results`: `TEXT` NOT NULL
- `observed_results`: `TEXT` NOT NULL DEFAULT ''
- `status`: `VARCHAR(32)` NOT NULL DEFAULT `'PLANNED'`
- `identified_weaknesses`: `JSONB` NOT NULL DEFAULT `'[]'`
- `corrective_action_references`: `JSONB` NOT NULL DEFAULT `'[]'`
- `evidence_references`: `JSONB` NOT NULL DEFAULT `'[]'`
- `disclaimer`: `TEXT` NOT NULL
- `created_at`: `TIMESTAMPTZ` NOT NULL
- `updated_at`: `TIMESTAMPTZ` NOT NULL

### 2.11 `governance_continuity_gaps`
Stores continuity gaps and resilience weaknesses routed to corrective action.
- `gap_id`: `VARCHAR(64)` PRIMARY KEY
- `tenant_id`: `VARCHAR(64)` NOT NULL INDEX
- `category`: `VARCHAR(48)` NOT NULL
- `affected_capability_ids`: `JSONB` NOT NULL DEFAULT `'[]'`
- `detection_method`: `VARCHAR(128)` NOT NULL
- `explanation`: `TEXT` NOT NULL
- `severity`: `VARCHAR(16)` NOT NULL (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`)
- `recommended_action`: `TEXT` NOT NULL
- `status`: `VARCHAR(32)` NOT NULL DEFAULT `'DETECTED'` (`DETECTED`, `UNDER_REVIEW`, `ACTION_REFERRED`, `RESOLVED`, `DISMISSED`)
- `escalation_destination`: `VARCHAR(64)` NOT NULL DEFAULT `'PHASE_54_CAPA'`
- `reviewed_by`: `VARCHAR(64)` NULL
- `review_notes`: `TEXT` NULL
- `corrective_action_reference`: `VARCHAR(128)` NULL
- `disclaimer`: `TEXT` NOT NULL
- `detected_at`: `TIMESTAMPTZ` NOT NULL
