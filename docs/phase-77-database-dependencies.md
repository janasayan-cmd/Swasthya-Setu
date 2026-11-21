# Phase 77: Database Persistence Requirements & Contracts

**Module**: Clinical Safety Governance Strategic Assurance, Organizational Maturity Assessment & Continuous Governance Improvement  
**Consumer**: Database Teammate  
**Backend Layer**: In-Memory Thread-Safe Singleton Repository (`GovernanceStrategicAssuranceRepository`)  
**Strict Boundary**: Backend does **not** create or modify tables, ORM models, migrations, or indexes. All persistence models below represent the authoritative contract for the database teammate.

---

## 1. Relational Schema Architecture

```
                               ┌────────────────────────────────┐
                               │ governance_maturity_frameworks │
                               └───────────────┬────────────────┘
                                               │
                                               ▼
                               ┌────────────────────────────────┐
                               │  governance_maturity_criteria  │
                               └───────────────┬────────────────┘
                                               │
                                               ▼
                               ┌────────────────────────────────┐
                               │ governance_maturity_assessment │
                               └───────┬────────────────┬───────┘
                                       │                │
            ┌──────────────────────────┘                └──────────────────────────┐
            ▼                                                                      ▼
┌───────────────────────┐                                              ┌───────────────────────┐
│  assurance_evidence   │                                              │   assurance_reviews   │
└───────────────────────┘                                              └───────────────────────┘
            │                                                                      │
            ▼                                                                      ▼
┌───────────────────────┐                                              ┌───────────────────────┐
│governance_systemic_gap│                                              │strat_mgmt_review_pkgs │
└───────────┬───────────┘                                              └───────────────────────┘
            │
            ▼
┌───────────────────────┐
│  gov_improvement_plan │
└───────────────────────┘
```

---

## 2. Table Specifications

### 2.1 `governance_maturity_frameworks`
Authoritative storage for clinical safety governance maturity framework definitions and lifecycle states.
- `framework_id`: `VARCHAR(64)` PRIMARY KEY
- `tenant_id`: `VARCHAR(64)` NOT NULL INDEX
- `framework_code`: `VARCHAR(64)` NOT NULL
- `name`: `VARCHAR(255)` NOT NULL
- `version`: `VARCHAR(32)` NOT NULL
- `status`: `VARCHAR(32)` NOT NULL DEFAULT `'DRAFT'` (`DRAFT`, `SUBMITTED`, `APPROVED`, `ACTIVE`, `SUPERSEDED`, `ARCHIVED`)
- `description`: `TEXT` NOT NULL
- `dimensions`: `JSONB` NOT NULL DEFAULT `'[]'`
- `author_id`: `VARCHAR(64)` NOT NULL
- `approved_by`: `VARCHAR(64)` NULL
- `approval_date`: `TIMESTAMPTZ` NULL
- `activated_at`: `TIMESTAMPTZ` NULL
- `superseded_by_framework_id`: `VARCHAR(64)` NULL
- `metadata`: `JSONB` NOT NULL DEFAULT `'{}'`
- `disclaimer`: `TEXT` NOT NULL
- `created_at`: `TIMESTAMPTZ` NOT NULL DEFAULT NOW()
- `updated_at`: `TIMESTAMPTZ` NOT NULL DEFAULT NOW()
- **Unique Constraint**: `UNIQUE(tenant_id, framework_code, version)`

### 2.2 `governance_maturity_assessments`
Authoritative records of conducted organizational maturity evaluations.
- `assessment_id`: `VARCHAR(64)` PRIMARY KEY
- `tenant_id`: `VARCHAR(64)` NOT NULL INDEX
- `framework_id`: `VARCHAR(64)` NOT NULL REFERENCES `governance_maturity_frameworks(framework_id)`
- `framework_version`: `VARCHAR(32)` NOT NULL
- `scope_type`: `VARCHAR(64)` NOT NULL (`ORGANIZATION`, `BUSINESS_UNIT`, `FACILITY`, `DEPARTMENT`, `TEAM`, `WORKFLOW`, `CROSS_FUNCTIONAL`)
- `scope_id`: `VARCHAR(64)` NOT NULL INDEX
- `scope_name`: `VARCHAR(255)` NOT NULL
- `parent_scope_id`: `VARCHAR(64)` NULL
- `status`: `VARCHAR(32)` NOT NULL DEFAULT `'DRAFT'` (`DRAFT`, `IN_PROGRESS`, `SUBMITTED`, `UNDER_REVIEW`, `APPROVED`, `SUPERSEDED`, `ARCHIVED`)
- `assessor_id`: `VARCHAR(64)` NOT NULL
- `assessment_date`: `TIMESTAMPTZ` NOT NULL
- `dimension_results`: `JSONB` NOT NULL DEFAULT `'{}'`
- `overall_maturity_level`: `VARCHAR(64)` NOT NULL DEFAULT `'NOT_ASSESSED'`
- `summary_findings`: `TEXT` NOT NULL DEFAULT `''`
- `evidence_coverage_percentage`: `NUMERIC(5, 2)` NOT NULL DEFAULT 0.0
- `independent_review_id`: `VARCHAR(64)` NULL
- `disclaimer`: `TEXT` NOT NULL
- `created_at`: `TIMESTAMPTZ` NOT NULL DEFAULT NOW()
- `updated_at`: `TIMESTAMPTZ` NOT NULL DEFAULT NOW()

### 2.3 `governance_assurance_evidence`
Lineage-tracked evidence items submitted to substantiate criteria compliance.
- `evidence_id`: `VARCHAR(64)` PRIMARY KEY
- `tenant_id`: `VARCHAR(64)` NOT NULL INDEX
- `assessment_id`: `VARCHAR(64)` NOT NULL REFERENCES `governance_maturity_assessments(assessment_id)` ON DELETE CASCADE
- `dimension`: `VARCHAR(64)` NOT NULL
- `criterion_id`: `VARCHAR(64)` NOT NULL
- `source_workflow`: `VARCHAR(64)` NOT NULL (e.g. `PHASE_49_INCIDENT`, `PHASE_54_CAPA`, `PHASE_63_RISK`, `PHASE_70_AUDIT`, `PHASE_72_MANAGEMENT_REVIEW`, `PHASE_73_IMPLEMENTATION`, `PHASE_74_ADOPTION`, `PHASE_75_PORTFOLIO`, `PHASE_76_BENEFIT`)
- `source_record_id`: `VARCHAR(64)` NOT NULL
- `title`: `VARCHAR(255)` NOT NULL
- `description`: `TEXT` NOT NULL
- `artifact_uri`: `VARCHAR(512)` NULL
- `verification_status`: `VARCHAR(32)` NOT NULL DEFAULT `'PENDING_VERIFICATION'` (`PENDING_VERIFICATION`, `VERIFIED`, `REJECTED`, `EXPIRED`, `UNVERIFIED`)
- `verified_by`: `VARCHAR(64)` NULL
- `verified_at`: `TIMESTAMPTZ` NULL
- `verification_notes`: `TEXT` NULL
- `collected_by`: `VARCHAR(64)` NOT NULL
- `collected_at`: `TIMESTAMPTZ` NOT NULL DEFAULT NOW()
- `freshness_timestamp`: `TIMESTAMPTZ` NOT NULL DEFAULT NOW()
- `is_stale`: `BOOLEAN` NOT NULL DEFAULT FALSE
- `disclaimer`: `TEXT` NOT NULL

### 2.4 `governance_systemic_gaps`
Cross-dimensional and cross-facility governance capability deficits.
- `gap_id`: `VARCHAR(64)` PRIMARY KEY
- `tenant_id`: `VARCHAR(64)` NOT NULL INDEX
- `title`: `VARCHAR(255)` NOT NULL
- `description`: `TEXT` NOT NULL
- `classification`: `VARCHAR(64)` NOT NULL (`CAPABILITY_DEFICIT`, `COVERAGE_DEFICIT`, `RELIABILITY_DRIFT`, `EVIDENCE_DEFICIENCY`, `CONTROL_ABSENCE`)
- `status`: `VARCHAR(32)` NOT NULL DEFAULT `'POTENTIAL_GAP'` (`POTENTIAL_GAP`, `CONFIRMED_GAP`, `ADDRESSED_IN_PLAN`, `RESOLVED`, `ACCEPTED_EXCEPTION`)
- `impacted_dimensions`: `JSONB` NOT NULL DEFAULT `'[]'`
- `impacted_scopes`: `JSONB` NOT NULL DEFAULT `'[]'`
- `originating_assessment_ids`: `JSONB` NOT NULL DEFAULT `'[]'`
- `identified_by`: `VARCHAR(64)` NOT NULL
- `identified_at`: `TIMESTAMPTZ` NOT NULL DEFAULT NOW()
- `confirmed_by`: `VARCHAR(64)` NULL
- `confirmed_at`: `TIMESTAMPTZ` NULL
- `confirmation_notes`: `TEXT` NULL
- `improvement_plan_id`: `VARCHAR(64)` NULL
- `disclaimer`: `TEXT` NOT NULL

### 2.5 `governance_improvement_plans`
Continuous capability improvement plans and milestone progression.
- `plan_id`: `VARCHAR(64)` PRIMARY KEY
- `tenant_id`: `VARCHAR(64)` NOT NULL INDEX
- `title`: `VARCHAR(255)` NOT NULL
- `description`: `TEXT` NOT NULL
- `target_dimensions`: `JSONB` NOT NULL DEFAULT `'[]'`
- `baseline_level`: `VARCHAR(64)` NOT NULL
- `target_level`: `VARCHAR(64)` NOT NULL
- `scope`: `JSONB` NOT NULL DEFAULT `'{}'`
- `status`: `VARCHAR(32)` NOT NULL DEFAULT `'ACTIVE'` (`DRAFT`, `ACTIVE`, `MONITORING`, `COMPLETED`, `CANCELLED`)
- `accountable_owner_id`: `VARCHAR(64)` NOT NULL
- `milestones`: `JSONB` NOT NULL DEFAULT `'[]'`
- `linked_gap_ids`: `JSONB` NOT NULL DEFAULT `'[]'`
- `external_handoffs`: `JSONB` NOT NULL DEFAULT `'[]'`
- `created_by`: `VARCHAR(64)` NOT NULL
- `target_completion_date`: `TIMESTAMPTZ` NOT NULL
- `disclaimer`: `TEXT` NOT NULL
- `created_at`: `TIMESTAMPTZ` NOT NULL DEFAULT NOW()
- `updated_at`: `TIMESTAMPTZ` NOT NULL DEFAULT NOW()

### 2.6 `governance_assurance_reviews`
Independent verification and assessment approval reviews.
- `review_id`: `VARCHAR(64)` PRIMARY KEY
- `tenant_id`: `VARCHAR(64)` NOT NULL INDEX
- `assessment_id`: `VARCHAR(64)` NOT NULL REFERENCES `governance_maturity_assessments(assessment_id)`
- `assigned_reviewer_id`: `VARCHAR(64)` NOT NULL
- `assigned_by`: `VARCHAR(64)` NOT NULL
- `assigned_at`: `TIMESTAMPTZ` NOT NULL DEFAULT NOW()
- `status`: `VARCHAR(32)` NOT NULL DEFAULT `'IN_REVIEW'` (`PENDING_REVIEW`, `IN_REVIEW`, `ACCEPTED`, `REJECTED`, `CHANGES_REQUESTED`)
- `conflict_of_interest_cleared`: `BOOLEAN` NOT NULL DEFAULT TRUE
- `review_notes`: `TEXT` NULL
- `completed_at`: `TIMESTAMPTZ` NULL
- `disclaimer`: `TEXT` NOT NULL

### 2.7 `strategic_management_review_packages`
Dossiers compiled for executive oversight and Phase 72 Management Review referral.
- `package_id`: `VARCHAR(64)` PRIMARY KEY
- `tenant_id`: `VARCHAR(64)` NOT NULL INDEX
- `title`: `VARCHAR(255)` NOT NULL
- `reporting_period`: `VARCHAR(64)` NOT NULL
- `executive_summary`: `TEXT` NOT NULL
- `included_assessment_ids`: `JSONB` NOT NULL DEFAULT `'[]'`
- `systemic_gaps`: `JSONB` NOT NULL DEFAULT `'[]'`
- `proposed_improvement_plans`: `JSONB` NOT NULL DEFAULT `'[]'`
- `prepared_by`: `VARCHAR(64)` NOT NULL
- `phase_72_referral_id`: `VARCHAR(64)` NULL
- `disclaimer`: `TEXT` NOT NULL
- `created_at`: `TIMESTAMPTZ` NOT NULL DEFAULT NOW()

---

## 3. Recommended PostgreSQL Indexes

```sql
CREATE INDEX idx_framework_tenant_status ON governance_maturity_frameworks(tenant_id, status);
CREATE INDEX idx_assessment_tenant_scope ON governance_maturity_assessments(tenant_id, scope_id, scope_type);
CREATE INDEX idx_evidence_tenant_assessment ON governance_assurance_evidence(tenant_id, assessment_id);
CREATE INDEX idx_gaps_tenant_status ON governance_systemic_gaps(tenant_id, status);
CREATE INDEX idx_plans_tenant_status ON governance_improvement_plans(tenant_id, status);
CREATE INDEX idx_reviews_tenant_reviewer ON governance_assurance_reviews(tenant_id, assigned_reviewer_id);
CREATE INDEX idx_packages_tenant ON strategic_management_review_packages(tenant_id);
```
