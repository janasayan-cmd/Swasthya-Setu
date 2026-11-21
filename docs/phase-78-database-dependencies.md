# Phase 78: Database Persistence Requirements & Contracts

**Module**: Clinical Safety Governance Strategy, Multi-Year Roadmap & Strategic Capability Development Planning  
**Consumer**: Database Teammate  
**Backend Layer**: In-Memory Thread-Safe Singleton Repository (`GovernanceStrategyRepository`)  
**Strict Boundary**: Backend does **not** create or modify tables, ORM models, migrations, or indexes. All persistence models below represent the authoritative contract for the database teammate.

---

## 1. Relational Schema Architecture

```
                               ┌─────────────────────────────────┐
                               │  governance_strategy_roadmaps   │
                               └───────────────┬─────────────────┘
                                               │
                                               ▼
                               ┌─────────────────────────────────┐
                               │ governance_strategy_objectives  │
                               └───────┬─────────────────┬───────┘
                                       │                 │
            ┌──────────────────────────┘                 └──────────────────────────┐
            ▼                                                                       ▼
┌───────────────────────┐                                               ┌───────────────────────┐
│ strategy_priorities   │                                               │ strategy_milestones   │
└───────────────────────┘                                               └───────────┬───────────┘
            │                                                                       │
            ▼                                                                       ▼
┌───────────────────────┐                                               ┌───────────────────────┐
│ capability_targets    │                                               │ milestone_dependencies│
└───────────────────────┘                                               └───────────────────────┘
            │                                                                       │
            ▼                                                                       ▼
┌───────────────────────┐                                               ┌───────────────────────┐
│  resource_proposals   │                                               │ strategy_coordination │
└───────────────────────┘                                               └───────────────────────┘
```

---

## 2. Table Specifications

### 2.1 `governance_strategy_roadmaps`
Primary multi-year strategic roadmap storage.
- `roadmap_id`: `VARCHAR(64)` PRIMARY KEY
- `tenant_id`: `VARCHAR(64)` NOT NULL INDEX
- `title`: `VARCHAR(255)` NOT NULL
- `description`: `TEXT` NOT NULL
- `organizational_scope`: `JSONB` NOT NULL DEFAULT `'{}'`
- `planning_horizon`: `VARCHAR(32)` NOT NULL (`ONE_YEAR`, `THREE_YEAR`, `FIVE_YEAR`)
- `start_date`: `TIMESTAMPTZ` NOT NULL
- `end_date`: `TIMESTAMPTZ` NOT NULL
- `strategic_objective_ids`: `JSONB` NOT NULL DEFAULT `'[]'`
- `strategic_priority_ids`: `JSONB` NOT NULL DEFAULT `'[]'`
- `milestone_ids`: `JSONB` NOT NULL DEFAULT `'[]'`
- `resource_proposal_ids`: `JSONB` NOT NULL DEFAULT `'[]'`
- `status`: `VARCHAR(32)` NOT NULL DEFAULT `'DRAFT'` (`DRAFT`, `UNDER_REVIEW`, `SUBMITTED`, `APPROVED`, `ACTIVE`, `PAUSED`, `SUPERSEDED`, `COMPLETED`, `CANCELLED`)
- `owner_id`: `VARCHAR(64)` NOT NULL
- `current_version`: `INTEGER` NOT NULL DEFAULT 1
- `approved_version`: `INTEGER` NULL
- `approved_by`: `VARCHAR(64)` NULL
- `approval_date`: `TIMESTAMPTZ` NULL
- `approval_reference`: `VARCHAR(64)` NULL
- `change_history`: `JSONB` NOT NULL DEFAULT `'[]'`
- `disclaimer`: `TEXT` NOT NULL
- `created_at`: `TIMESTAMPTZ` NOT NULL DEFAULT NOW()
- `updated_at`: `TIMESTAMPTZ` NOT NULL DEFAULT NOW()

### 2.2 `governance_strategy_objectives`
Authoritative records of strategic governance objectives.
- `objective_id`: `VARCHAR(64)` PRIMARY KEY
- `tenant_id`: `VARCHAR(64)` NOT NULL INDEX
- `title`: `VARCHAR(255)` NOT NULL
- `description`: `TEXT` NOT NULL
- `rationale`: `TEXT` NOT NULL
- `category`: `VARCHAR(64)` NOT NULL (`LEADERSHIP_OVERSIGHT`, `RISK_GOVERNANCE`, `INCIDENT_PREVENTION`, `CLINICAL_ASSURANCE`, `CAPABILITY_DEVELOPMENT`, `SYSTEMIC_TRANSFORMATION`)
- `organizational_scope`: `JSONB` NOT NULL DEFAULT `'{}'`
- `source_reference`: `VARCHAR(255)` NULL
- `related_phase77_gap_ids`: `JSONB` NOT NULL DEFAULT `'[]'`
- `related_governance_risk_ids`: `JSONB` NOT NULL DEFAULT `'[]'`
- `related_audit_finding_ids`: `JSONB` NOT NULL DEFAULT `'[]'`
- `related_management_decision_ids`: `JSONB` NOT NULL DEFAULT `'[]'`
- `intended_target_state`: `TEXT` NOT NULL
- `priority`: `VARCHAR(32)` NOT NULL DEFAULT `'HIGH'` (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`)
- `planning_horizon`: `VARCHAR(32)` NOT NULL DEFAULT `'THREE_YEAR'`
- `responsible_governance_owner_id`: `VARCHAR(64)` NOT NULL
- `supporting_stakeholders`: `JSONB` NOT NULL DEFAULT `'[]'`
- `dependencies`: `JSONB` NOT NULL DEFAULT `'[]'`
- `success_indicators`: `JSONB` NOT NULL DEFAULT `'[]'`
- `measurement_methodology`: `TEXT` NOT NULL
- `baseline_reference`: `VARCHAR(255)` NULL
- `target_condition`: `TEXT` NOT NULL
- `status`: `VARCHAR(32)` NOT NULL DEFAULT `'DRAFT'` (`DRAFT`, `UNDER_REVIEW`, `SUBMITTED`, `APPROVED`, `ACTIVE`, `ON_HOLD`, `SUPERSEDED`, `COMPLETED`, `CANCELLED`)
- `created_by`: `VARCHAR(64)` NOT NULL
- `approved_by`: `VARCHAR(64)` NULL
- `approval_date`: `TIMESTAMPTZ` NULL
- `approval_reference`: `VARCHAR(64)` NULL
- `version`: `INTEGER` NOT NULL DEFAULT 1
- `disclaimer`: `TEXT` NOT NULL
- `created_at`: `TIMESTAMPTZ` NOT NULL DEFAULT NOW()
- `updated_at`: `TIMESTAMPTZ` NOT NULL DEFAULT NOW()

### 2.3 `governance_strategy_priorities`
Evidence-linked strategic capability development priorities.
- `priority_id`: `VARCHAR(64)` PRIMARY KEY
- `tenant_id`: `VARCHAR(64)` NOT NULL INDEX
- `title`: `VARCHAR(255)` NOT NULL
- `strategic_rationale`: `TEXT` NOT NULL
- `potential_impact`: `TEXT` NOT NULL
- `urgency`: `VARCHAR(64)` NOT NULL
- `evidence_references`: `JSONB` NOT NULL DEFAULT `'[]'`
- `proposed_priority_level`: `VARCHAR(32)` NOT NULL (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`)
- `status`: `VARCHAR(32)` NOT NULL DEFAULT `'PROPOSED'` (`PROPOSED`, `REVIEWED`, `ACCEPTED`, `REJECTED`)
- `proposed_by`: `VARCHAR(64)` NOT NULL
- `reviewed_by`: `VARCHAR(64)` NULL
- `review_outcome`: `VARCHAR(32)` NULL
- `review_notes`: `TEXT` NULL
- `linked_objective_id`: `VARCHAR(64)` NULL
- `disclaimer`: `TEXT` NOT NULL
- `created_at`: `TIMESTAMPTZ` NOT NULL DEFAULT NOW()
- `updated_at`: `TIMESTAMPTZ` NOT NULL DEFAULT NOW()

### 2.4 `governance_capability_targets`
Target operating state definitions referencing Phase 77 baselines.
- `target_id`: `VARCHAR(64)` PRIMARY KEY
- `tenant_id`: `VARCHAR(64)` NOT NULL INDEX
- `capability_domain`: `VARCHAR(64)` NOT NULL
- `title`: `VARCHAR(255)` NOT NULL
- `current_state_description`: `TEXT` NOT NULL
- `current_maturity_reference`: `VARCHAR(64)` NULL
- `desired_future_state_description`: `TEXT` NOT NULL
- `target_maturity_level`: `VARCHAR(64)` NULL
- `organizational_scope`: `JSONB` NOT NULL DEFAULT `'{}'`
- `planned_milestone_id`: `VARCHAR(64)` NULL
- `responsible_owner_id`: `VARCHAR(64)` NOT NULL
- `evidence_required`: `JSONB` NOT NULL DEFAULT `'[]'`
- `review_criteria`: `TEXT` NOT NULL
- `status`: `VARCHAR(32)` NOT NULL DEFAULT `'PROPOSED'` (`PROPOSED`, `ACCEPTED`, `IN_PROGRESS`, `MET`, `DEFERRED`)
- `disclaimer`: `TEXT` NOT NULL
- `created_at`: `TIMESTAMPTZ` NOT NULL DEFAULT NOW()
- `updated_at`: `TIMESTAMPTZ` NOT NULL DEFAULT NOW()

### 2.5 `governance_strategy_milestones`
Strategic roadmap delivery milestones and evidence verification.
- `milestone_id`: `VARCHAR(64)` PRIMARY KEY
- `tenant_id`: `VARCHAR(64)` NOT NULL INDEX
- `roadmap_id`: `VARCHAR(64)` NOT NULL REFERENCES `governance_strategy_roadmaps(roadmap_id)` ON DELETE CASCADE
- `related_objective_id`: `VARCHAR(64)` NULL
- `title`: `VARCHAR(255)` NOT NULL
- `description`: `TEXT` NOT NULL
- `planned_start_date`: `TIMESTAMPTZ` NOT NULL
- `planned_completion_date`: `TIMESTAMPTZ` NOT NULL
- `actual_start_date`: `TIMESTAMPTZ` NULL
- `actual_completion_date`: `TIMESTAMPTZ` NULL
- `responsible_owner_id`: `VARCHAR(64)` NOT NULL
- `expected_deliverables`: `JSONB` NOT NULL DEFAULT `'[]'`
- `evidence_requirements`: `JSONB` NOT NULL DEFAULT `'[]'`
- `completion_evidence_reference`: `VARCHAR(255)` NULL
- `related_portfolio_id`: `VARCHAR(64)` NULL
- `related_implementation_id`: `VARCHAR(64)` NULL
- `status`: `VARCHAR(32)` NOT NULL DEFAULT `'PENDING'` (`PENDING`, `IN_PROGRESS`, `COMPLETED`, `DELAYED`, `BLOCKED`, `CANCELLED`)
- `delay_reason`: `TEXT` NULL
- `dependencies`: `JSONB` NOT NULL DEFAULT `'[]'`
- `verified_by`: `VARCHAR(64)` NULL
- `verified_at`: `TIMESTAMPTZ` NULL
- `disclaimer`: `TEXT` NOT NULL
- `created_at`: `TIMESTAMPTZ` NOT NULL DEFAULT NOW()
- `updated_at`: `TIMESTAMPTZ` NOT NULL DEFAULT NOW()

### 2.6 `governance_resource_proposals`
Estimated resource and financial requirements without autonomous budget allocation.
- `proposal_id`: `VARCHAR(64)` PRIMARY KEY
- `tenant_id`: `VARCHAR(64)` NOT NULL INDEX
- `roadmap_id`: `VARCHAR(64)` NOT NULL REFERENCES `governance_strategy_roadmaps(roadmap_id)`
- `related_objective_id`: `VARCHAR(64)` NULL
- `title`: `VARCHAR(255)` NOT NULL
- `rationale`: `TEXT` NOT NULL
- `proposed_financial_investment`: `NUMERIC(15, 2)` NOT NULL DEFAULT 0.0
- `currency`: `VARCHAR(8)` NOT NULL DEFAULT `'INR'`
- `staffing_requirements`: `TEXT` NOT NULL DEFAULT `''`
- `technology_requirements`: `TEXT` NOT NULL DEFAULT `''`
- `training_requirements`: `TEXT` NOT NULL DEFAULT `''`
- `external_service_dependencies`: `TEXT` NOT NULL DEFAULT `''`
- `funding_assumptions`: `TEXT` NOT NULL DEFAULT `''`
- `expected_strategic_contribution`: `TEXT` NOT NULL DEFAULT `''`
- `status`: `VARCHAR(32)` NOT NULL DEFAULT `'PROPOSED'` (`PROPOSED`, `REVIEWED`, `APPROVED`, `FUNDED`, `COMMITTED`)
- `proposed_by`: `VARCHAR(64)` NOT NULL
- `reviewed_by`: `VARCHAR(64)` NULL
- `approval_reference`: `VARCHAR(64)` NULL
- `disclaimer`: `TEXT` NOT NULL
- `created_at`: `TIMESTAMPTZ` NOT NULL DEFAULT NOW()
- `updated_at`: `TIMESTAMPTZ` NOT NULL DEFAULT NOW()

### 2.7 `governance_strategy_coordination`
Linkages to Phase 75 portfolios, Phase 73 implementations, and strategic issues.
- `link_id`: `VARCHAR(64)` PRIMARY KEY
- `tenant_id`: `VARCHAR(64)` NOT NULL INDEX
- `roadmap_id`: `VARCHAR(64)` NOT NULL
- `link_type`: `VARCHAR(32)` NOT NULL (`PORTFOLIO`, `IMPLEMENTATION`)
- `source_id`: `VARCHAR(64)` NOT NULL
- `target_id`: `VARCHAR(64)` NOT NULL
- `status`: `VARCHAR(32)` NOT NULL DEFAULT `'ACTIVE'`
- `linked_at`: `TIMESTAMPTZ` NOT NULL DEFAULT NOW()

### 2.8 `governance_strategy_issues`
Strategic risks, delivery conflicts, and cross-phase escalations.
- `issue_id`: `VARCHAR(64)` PRIMARY KEY
- `tenant_id`: `VARCHAR(64)` NOT NULL INDEX
- `roadmap_id`: `VARCHAR(64)` NOT NULL REFERENCES `governance_strategy_roadmaps(roadmap_id)`
- `affected_objective_ids`: `JSONB` NOT NULL DEFAULT `'[]'`
- `affected_milestone_ids`: `JSONB` NOT NULL DEFAULT `'[]'`
- `classification`: `VARCHAR(64)` NOT NULL (`ROADMAP_DELAY`, `DEPENDENCY_FAILURE`, `UNFUNDED_COMMITMENT`, `RESOURCE_CONFLICT`, `READINESS_GAP`, `STALE_EVIDENCE`, `GOVERNANCE_EXCEPTION`, `CLINICAL_SAFETY_RISK`)
- `title`: `VARCHAR(255)` NOT NULL
- `description`: `TEXT` NOT NULL
- `impact_description`: `TEXT` NOT NULL
- `status`: `VARCHAR(32)` NOT NULL DEFAULT `'OPEN'` (`OPEN`, `INVESTIGATING`, `ESCALATED`, `RESOLVED`, `CLOSED`)
- `detected_by`: `VARCHAR(64)` NOT NULL
- `detection_timestamp`: `TIMESTAMPTZ` NOT NULL DEFAULT NOW()
- `escalation_target`: `VARCHAR(64)` NULL
- `escalation_reference`: `VARCHAR(64)` NULL
- `resolution_notes`: `TEXT` NULL
- `disclaimer`: `TEXT` NOT NULL

---

## 3. Recommended PostgreSQL Indexes

```sql
CREATE INDEX idx_strategy_roadmap_tenant ON governance_strategy_roadmaps(tenant_id, status);
CREATE INDEX idx_strategy_objective_tenant ON governance_strategy_objectives(tenant_id, category, status);
CREATE INDEX idx_strategy_priority_tenant ON governance_strategy_priorities(tenant_id, status);
CREATE INDEX idx_capability_target_tenant ON governance_capability_targets(tenant_id, capability_domain);
CREATE INDEX idx_strategy_milestone_roadmap ON governance_strategy_milestones(tenant_id, roadmap_id, status);
CREATE INDEX idx_strategy_resource_roadmap ON governance_resource_proposals(tenant_id, roadmap_id, status);
CREATE INDEX idx_strategy_issue_roadmap ON governance_strategy_issues(tenant_id, roadmap_id, status);
```
