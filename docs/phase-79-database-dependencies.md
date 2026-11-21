# Phase 79: Database Persistence Requirements & Contracts

**Module**: Clinical Safety Governance Strategic Execution Monitoring, Cross-Roadmap Coordination & Long-Term Strategy Adaptation  
**Consumer**: Database Teammate  
**Backend Layer**: In-Memory Thread-Safe Singleton Repository (`GovernanceStrategyExecutionRepository`)  
**Strict Boundary**: Backend does **not** create or modify tables, ORM models, migrations, or indexes. All persistence models below represent the authoritative contract for the database teammate.

---

## 1. Relational Schema Architecture

```
                                  ┌───────────────────────────────────────────┐
                                  │      governance_strategy_roadmaps         │
                                  │               (Phase 78)                  │
                                  └─────────────────────┬─────────────────────┘
                                                        │
                      ┌─────────────────────────────────┼─────────────────────────────────┐
                      ▼                                 ▼                                 ▼
┌───────────────────────────────────────┐ ┌───────────────────────────────────────┐ ┌───────────────────────────────────────┐
│ strategic_execution_monitoring        │ │ cross_roadmap_dependencies            │ │ strategic_alignment_findings          │
└───────────────────────────────────────┘ └───────────────────────────────────────┘ └───────────────────────────────────────┘
                      │                                 │                                 │
                      ▼                                 ▼                                 ▼
┌───────────────────────────────────────┐ ┌───────────────────────────────────────┐ ┌───────────────────────────────────────┐
│ strategic_assumptions                 │ │ strategic_change_signals              │ │ strategic_execution_exceptions        │
└───────────────────────────────────────┘ └───────────────────────────────────────┘ └───────────────────────────────────────┘
                      │                                 │                                 │
                      └─────────────────────────────────┼─────────────────────────────────┘
                                                        │
                                                        ▼
                                          ┌───────────────────────────┐
                                          │   adaptation_proposals    │
                                          └─────────────┬─────────────┘
                                                        │
                                                        ▼
                                          ┌───────────────────────────┐
                                          │ adaptation_followthroughs │
                                          └───────────────────────────┘
                                                        │
                                                        ▼
                                          ┌───────────────────────────┐
                                          │  strategic_review_packages│
                                          └───────────────────────────┘
```

---

## 2. Table Specifications

### 2.1 `governance_strategic_execution_monitoring`
Stores monitored workflow items across Phase 78 roadmaps, objectives, milestones, Phase 75 portfolios, Phase 73 implementations, Phase 74 adoptions, Phase 76 benefits, and Phase 77 maturity.
- `monitoring_id`: `VARCHAR(64)` PRIMARY KEY
- `tenant_id`: `VARCHAR(64)` NOT NULL INDEX
- `roadmap_id`: `VARCHAR(64)` NOT NULL INDEX
- `monitored_item_type`: `VARCHAR(48)` NOT NULL (`PHASE_78_ROADMAP`, `PHASE_78_OBJECTIVE`, `PHASE_78_MILESTONE`, `PHASE_78_CAPABILITY_TARGET`, `PHASE_75_PORTFOLIO`, `PHASE_73_IMPLEMENTATION`, `PHASE_74_ADOPTION`, `PHASE_76_BENEFIT`, `PHASE_77_MATURITY`)
- `monitored_item_id`: `VARCHAR(64)` NOT NULL INDEX
- `source_status`: `VARCHAR(64)` NOT NULL
- `health_status`: `VARCHAR(32)` NOT NULL (`ON_TRACK`, `AT_RISK`, `OFF_TRACK`, `BLOCKED`, `STALE_EVIDENCE`, `UNAVAILABLE`)
- `evidence_freshness_timestamp`: `TIMESTAMPTZ` NOT NULL
- `is_stale`: `BOOLEAN` NOT NULL DEFAULT FALSE
- `analytical_observation`: `TEXT` NOT NULL DEFAULT ''
- `detected_issue_count`: `INTEGER` NOT NULL DEFAULT 0
- `last_synchronized_at`: `TIMESTAMPTZ` NOT NULL
- `disclaimer`: `TEXT` NOT NULL
- **Constraints & Indexes**:
  - `idx_sem_tenant_roadmap`: `(tenant_id, roadmap_id)`
  - `idx_sem_item`: `(tenant_id, monitored_item_type, monitored_item_id)`
  - `idx_sem_health`: `(tenant_id, health_status)`

### 2.2 `governance_cross_roadmap_dependencies`
Tracks inter-roadmap dependencies, sequencing constraints, and conflict reviews.
- `dependency_id`: `VARCHAR(64)` PRIMARY KEY
- `tenant_id`: `VARCHAR(64)` NOT NULL INDEX
- `source_roadmap_id`: `VARCHAR(64)` NOT NULL INDEX
- `target_roadmap_id`: `VARCHAR(64)` NOT NULL INDEX
- `source_objective_id`: `VARCHAR(64)` NULL
- `target_objective_id`: `VARCHAR(64)` NULL
- `source_milestone_id`: `VARCHAR(64)` NULL
- `target_milestone_id`: `VARCHAR(64)` NULL
- `category`: `VARCHAR(48)` NOT NULL (`SHARED_CAPABILITY`, `SHARED_WORKFORCE`, `SHARED_TECHNOLOGY`, `SHARED_APPROVAL`, `READINESS_REQUIREMENT`, `IMPLEMENTATION_ACTIVITY`, `EXTERNAL_SERVICE`)
- `rationale`: `TEXT` NOT NULL
- `planned_dependency_date`: `TIMESTAMPTZ` NOT NULL
- `status`: `VARCHAR(32)` NOT NULL DEFAULT `'IDENTIFIED'` (`IDENTIFIED`, `CONFIRMED`, `RESOLVED`, `CONFLICT_DETECTED`, `WAIVED`)
- `responsible_owner_id`: `VARCHAR(64)` NOT NULL
- `evidence_references`: `JSONB` NOT NULL DEFAULT `'[]'`
- `conflict_description`: `TEXT` NULL
- `review_outcome`: `TEXT` NULL
- `disclaimer`: `TEXT` NOT NULL
- `created_at`: `TIMESTAMPTZ` NOT NULL
- `updated_at`: `TIMESTAMPTZ` NOT NULL
- **Constraints & Indexes**:
  - `idx_crd_source`: `(tenant_id, source_roadmap_id)`
  - `idx_crd_target`: `(tenant_id, target_roadmap_id)`
  - `idx_crd_status`: `(tenant_id, status)`

### 2.3 `governance_strategic_alignment_findings`
Captures explainable alignment findings (orphan objectives, disconnected portfolios, conflicting target states, etc.).
- `finding_id`: `VARCHAR(64)` PRIMARY KEY
- `tenant_id`: `VARCHAR(64)` NOT NULL INDEX
- `category`: `VARCHAR(48)` NOT NULL (`ORPHAN_OBJECTIVE`, `ORPHAN_MILESTONE`, `DISCONNECTED_PORTFOLIO`, `DUPLICATE_INITIATIVE`, `CONFLICTING_TARGET_STATE`, `COMPETING_RESOURCES`, `CONTRADICTORY_TIMELINE`, `UNOWNED_COMMITMENT`, `CHANGED_ASSUMPTION`)
- `affected_roadmap_ids`: `JSONB` NOT NULL DEFAULT `'[]'`
- `affected_record_references`: `JSONB` NOT NULL DEFAULT `'[]'`
- `detection_method`: `VARCHAR(128)` NOT NULL
- `rule_version`: `VARCHAR(32)` NOT NULL DEFAULT `'1.0'`
- `explanation`: `TEXT` NOT NULL
- `confidence_score`: `NUMERIC(4,3)` NOT NULL DEFAULT 1.000
- `evidence_limitations`: `TEXT` NOT NULL DEFAULT ''
- `status`: `VARCHAR(32)` NOT NULL DEFAULT `'DETECTED'` (`DETECTED`, `UNDER_REVIEW`, `ACCEPTED_FOR_ADAPTATION`, `DISMISSED`)
- `reviewed_by`: `VARCHAR(64)` NULL
- `review_notes`: `TEXT` NULL
- `suggested_review_destination`: `VARCHAR(64)` NOT NULL
- `disclaimer`: `TEXT` NOT NULL
- `detected_at`: `TIMESTAMPTZ` NOT NULL
- **Constraints & Indexes**:
  - `idx_saf_tenant_cat`: `(tenant_id, category)`
  - `idx_saf_status`: `(tenant_id, status)`

### 2.4 `governance_strategic_assumptions`
Records and monitors operational and strategic assumptions supporting roadmaps.
- `assumption_id`: `VARCHAR(64)` PRIMARY KEY
- `tenant_id`: `VARCHAR(64)` NOT NULL INDEX
- `roadmap_id`: `VARCHAR(64)` NOT NULL INDEX
- `category`: `VARCHAR(48)` NOT NULL (`WORKFORCE_AVAILABILITY`, `ORGANIZATIONAL_CAPACITY`, `TECHNOLOGY_READINESS`, `INTEGRATION_AVAILABILITY`, `FUNDING_ASSUMPTION`, `OPERATIONAL_READINESS`, `TRAINING_CAPACITY`, `EXTERNAL_SERVICE`)
- `description`: `TEXT` NOT NULL
- `source_rationale`: `TEXT` NOT NULL
- `owner_id`: `VARCHAR(64)` NOT NULL
- `validation_method`: `VARCHAR(128)` NOT NULL
- `last_validated_date`: `TIMESTAMPTZ` NULL
- `expected_review_date`: `TIMESTAMPTZ` NOT NULL
- `status`: `VARCHAR(32)` NOT NULL DEFAULT `'PROPOSED'` (`PROPOSED`, `UNDER_REVIEW`, `VALIDATED`, `PARTIALLY_VALIDATED`, `INVALIDATED`, `EXPIRED`, `SUPERSEDED`)
- `impact_if_invalidated`: `TEXT` NOT NULL
- `supporting_evidence_reference`: `VARCHAR(128)` NULL
- `disclaimer`: `TEXT` NOT NULL
- `created_at`: `TIMESTAMPTZ` NOT NULL
- `updated_at`: `TIMESTAMPTZ` NOT NULL
- **Constraints & Indexes**:
  - `idx_gsa_tenant_roadmap`: `(tenant_id, roadmap_id)`
  - `idx_gsa_status`: `(tenant_id, status)`

### 2.5 `governance_strategic_change_signals`
Tracks change signals detected from recurring delays, dependency failures, or adoption drift.
- `signal_id`: `VARCHAR(64)` PRIMARY KEY
- `tenant_id`: `VARCHAR(64)` NOT NULL INDEX
- `category`: `VARCHAR(48)` NOT NULL (`REPEATED_MILESTONE_DELAYS`, `PERSISTENT_DEPENDENCY_FAILURES`, `UNRESOLVED_APPROVAL_REQUESTS`, `RECURRING_RESOURCE_CONSTRAINTS`, `DECLINING_CAPABILITY_INDICATORS`, `OPERATIONAL_ADOPTION_FAILURES`, `BENEFIT_REALIZATION_GAPS`, `MATERIAL_MATURITY_CHANGES`, `INCREASING_EXCEPTIONS`)
- `affected_roadmap_ids`: `JSONB` NOT NULL DEFAULT `'[]'`
- `source_references`: `JSONB` NOT NULL DEFAULT `'[]'`
- `detection_rule`: `VARCHAR(128)` NOT NULL
- `observation_period`: `VARCHAR(64)` NOT NULL
- `severity`: `VARCHAR(16)` NOT NULL (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`)
- `evidence_limitations`: `TEXT` NOT NULL DEFAULT ''
- `strategic_implication`: `TEXT` NOT NULL
- `recommended_destination`: `VARCHAR(64)` NOT NULL
- `disposition`: `VARCHAR(32)` NOT NULL DEFAULT `'ACTIVE'` (`ACTIVE`, `INVESTIGATING`, `ESCALATED_PHASE_63`, `ESCALATED_PHASE_49`, `RESOLVED`, `CLOSED`)
- `reviewed_by`: `VARCHAR(64)` NULL
- `review_notes`: `TEXT` NULL
- `disclaimer`: `TEXT` NOT NULL
- `detected_at`: `TIMESTAMPTZ` NOT NULL
- **Constraints & Indexes**:
  - `idx_gscs_tenant_sev`: `(tenant_id, severity)`
  - `idx_gscs_disp`: `(tenant_id, disposition)`

### 2.6 `governance_strategic_adaptation_proposals`
Stores evidence-backed proposals for strategic roadmaps and objectives adjustments.
- `proposal_id`: `VARCHAR(64)` PRIMARY KEY
- `tenant_id`: `VARCHAR(64)` NOT NULL INDEX
- `source_roadmap_id`: `VARCHAR(64)` NOT NULL INDEX
- `proposal_type`: `VARCHAR(48)` NOT NULL (`REVISE_MILESTONE`, `REORDER_MILESTONES`, `REVISIT_CAPABILITY_PRIORITY`, `REVISE_OBJECTIVE`, `REVIEW_TARGET_STATE`, `REVISIT_INVESTMENT_ASSUMPTION`, `RESOLVE_CROSS_DEPENDENCY`, `REVISE_PLANNING_HORIZON`, `PROPOSE_NEW_OBJECTIVE`)
- `affected_objective_ids`: `JSONB` NOT NULL DEFAULT `'[]'`
- `affected_milestone_ids`: `JSONB` NOT NULL DEFAULT `'[]'`
- `supporting_signal_ids`: `JSONB` NOT NULL DEFAULT `'[]'`
- `proposed_change_description`: `TEXT` NOT NULL
- `rationale`: `TEXT` NOT NULL
- `expected_benefits`: `TEXT` NOT NULL
- `potential_negative_consequences`: `TEXT` NOT NULL
- `resource_implications`: `TEXT` NOT NULL
- `uncertainty_limitations`: `TEXT` NOT NULL DEFAULT ''
- `requesting_owner_id`: `VARCHAR(64)` NOT NULL
- `status`: `VARCHAR(32)` NOT NULL DEFAULT `'DRAFT'` (`DRAFT`, `SUBMITTED`, `UNDER_REVIEW`, `ACCEPTED_FOR_CONSIDERATION`, `REJECTED`, `APPROVED_AUTHORITATIVE`, `IMPLEMENTED_AUTHORITATIVE`, `SUPERSEDED`, `WITHDRAWN`)
- `review_notes`: `TEXT` NULL
- `authoritative_decision_reference`: `VARCHAR(128)` NULL (Phase 72 decision reference)
- `authoritative_roadmap_revision_id`: `VARCHAR(128)` NULL (Phase 78 revision reference)
- `disclaimer`: `TEXT` NOT NULL
- `created_at`: `TIMESTAMPTZ` NOT NULL
- `updated_at`: `TIMESTAMPTZ` NOT NULL
- **Constraints & Indexes**:
  - `idx_gsap_tenant_roadmap`: `(tenant_id, source_roadmap_id)`
  - `idx_gsap_status`: `(tenant_id, status)`

### 2.7 `governance_adaptation_followthroughs`
Tracks downstream realization and phase linkages for approved strategic adaptations.
- `followthrough_id`: `VARCHAR(64)` PRIMARY KEY
- `tenant_id`: `VARCHAR(64)` NOT NULL INDEX
- `proposal_id`: `VARCHAR(64)` NOT NULL UNIQUE INDEX
- `phase72_decision_reference`: `VARCHAR(128)` NULL
- `phase78_revision_reference`: `VARCHAR(128)` NULL
- `phase73_implementation_reference`: `VARCHAR(128)` NULL
- `phase75_portfolio_reference`: `VARCHAR(128)` NULL
- `phase74_adoption_reference`: `VARCHAR(128)` NULL
- `phase76_benefit_reference`: `VARCHAR(128)` NULL
- `phase77_maturity_reference`: `VARCHAR(128)` NULL
- `status`: `VARCHAR(32)` NOT NULL DEFAULT `'IN_PROGRESS'`
- `verification_notes`: `TEXT` NULL
- `disclaimer`: `TEXT` NOT NULL
- `updated_at`: `TIMESTAMPTZ` NOT NULL

### 2.8 `governance_strategic_scenarios`
Stores advisory what-if simulation records.
- `scenario_id`: `VARCHAR(64)` PRIMARY KEY
- `tenant_id`: `VARCHAR(64)` NOT NULL INDEX
- `title`: `VARCHAR(255)` NOT NULL
- `scenario_type`: `VARCHAR(32)` NOT NULL (`DELAYED_EXECUTION`, `REDUCED_RESOURCES`, `INCREASED_CAPACITY`, `CHANGED_TECHNOLOGY`, `DEPENDENCY_RESOLUTION`, `CHANGED_SEQUENCE`, `REVISED_HORIZON`)
- `description`: `TEXT` NOT NULL
- `input_roadmap_id`: `VARCHAR(64)` NOT NULL INDEX
- `assumptions`: `JSONB` NOT NULL DEFAULT `'[]'`
- `variables`: `JSONB` NOT NULL DEFAULT `'{}'`
- `calculation_method`: `TEXT` NOT NULL
- `projected_milestone_impacts`: `JSONB` NOT NULL DEFAULT `'[]'`
- `projected_dependency_impacts`: `JSONB` NOT NULL DEFAULT `'[]'`
- `projected_resource_implications`: `TEXT` NOT NULL DEFAULT ''
- `expected_strategic_consequences`: `TEXT` NOT NULL DEFAULT ''
- `uncertainty_range`: `VARCHAR(128)` NOT NULL DEFAULT ''
- `limitations`: `TEXT` NOT NULL DEFAULT ''
- `created_by`: `VARCHAR(64)` NOT NULL
- `disclaimer`: `TEXT` NOT NULL
- `created_at`: `TIMESTAMPTZ` NOT NULL

### 2.9 `governance_strategic_execution_exceptions`
Maintains exceptions requiring authoritative routing to Phase 67, Phase 63, Phase 49, Phase 54, or Phase 72.
- `exception_id`: `VARCHAR(64)` PRIMARY KEY
- `tenant_id`: `VARCHAR(64)` NOT NULL INDEX
- `category`: `VARCHAR(48)` NOT NULL (`CROSS_ROADMAP_CONFLICT`, `DEPENDENCY_FAILURE`, `OBJECTIVE_MISALIGNMENT`, `DELAYED_APPROVAL`, `INVALIDATED_ASSUMPTION`, `RESOURCE_CONSTRAINT`, `STALE_EXECUTION_EVIDENCE`, `UNOWNED_COMMITMENT`, `REPEATED_MILESTONE_SLIPPAGE`)
- `affected_roadmap_ids`: `JSONB` NOT NULL DEFAULT `'[]'`
- `affected_objective_ids`: `JSONB` NOT NULL DEFAULT `'[]'`
- `evidence_references`: `JSONB` NOT NULL DEFAULT `'[]'`
- `detection_source`: `VARCHAR(128)` NOT NULL
- `impact_description`: `TEXT` NOT NULL
- `responsible_owner_id`: `VARCHAR(64)` NOT NULL
- `escalation_destination`: `VARCHAR(64)` NULL
- `escalation_reference`: `VARCHAR(128)` NULL
- `status`: `VARCHAR(32)` NOT NULL DEFAULT `'OPEN'` (`OPEN`, `UNDER_REVIEW`, `ESCALATED_PHASE_67`, `ESCALATED_PHASE_63`, `ESCALATED_PHASE_49`, `ESCALATED_PHASE_54`, `RESOLVED`, `CLOSED`)
- `resolution_evidence`: `TEXT` NULL
- `disclaimer`: `TEXT` NOT NULL
- `created_at`: `TIMESTAMPTZ` NOT NULL
- `updated_at`: `TIMESTAMPTZ` NOT NULL

### 2.10 `governance_strategic_review_packages`
Authoritative dossiers consolidating strategic execution oversight intelligence for executive leadership and Phase 72 referral.
- `package_id`: `VARCHAR(64)` PRIMARY KEY
- `tenant_id`: `VARCHAR(64)` NOT NULL INDEX
- `title`: `VARCHAR(255)` NOT NULL
- `reporting_period`: `VARCHAR(64)` NOT NULL
- `organizational_scope`: `JSONB` NOT NULL DEFAULT `'{}'`
- `included_roadmap_ids`: `JSONB` NOT NULL DEFAULT `'[]'`
- `executive_summary`: `TEXT` NOT NULL
- `monitored_status_summary`: `JSONB` NOT NULL DEFAULT `'{}'`
- `cross_roadmap_dependency_summary`: `JSONB` NOT NULL DEFAULT `'{}'`
- `alignment_findings`: `JSONB` NOT NULL DEFAULT `'[]'`
- `invalidated_assumptions`: `JSONB` NOT NULL DEFAULT `'[]'`
- `active_signals`: `JSONB` NOT NULL DEFAULT `'[]'`
- `open_exceptions`: `JSONB` NOT NULL DEFAULT `'[]'`
- `adaptation_proposals`: `JSONB` NOT NULL DEFAULT `'[]'`
- `evidence_coverage`: `NUMERIC(4,3)` NOT NULL DEFAULT 1.000
- `known_limitations`: `TEXT` NOT NULL DEFAULT ''
- `prepared_by`: `VARCHAR(64)` NOT NULL
- `phase_72_referral_reference`: `VARCHAR(128)` NULL
- `disclaimer`: `TEXT` NOT NULL
- `created_at`: `TIMESTAMPTZ` NOT NULL
