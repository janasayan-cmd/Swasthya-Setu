# Phase 75: Database Teammate Dependencies & Persistence Contracts

**Phase:** Phase 75 — Governance Change Portfolio Oversight, Cross-Initiative Dependency Management & Cumulative Impact Coordination  
**Target Persistence Layer:** PostgreSQL 16+ / SQLAlchemy 2.x  
**Database Ownership Notice:**  
The backend implementation strictly respects the database ownership boundary. The backend does not define new database migrations, raw SQL DDL, or independent ORM entities directly. This document specifies the exact persistence contracts, schemas, foreign keys, constraints, indexes, and audit triggers required from the database teammate for Phase 75.

---

## 1. Persistence Tables Overview

Phase 75 introduces nine structured entities for governance change portfolio oversight and cross-initiative coordination:

1. `governance_change_portfolios`
2. `portfolio_initiatives`
3. `cross_initiative_dependencies`
4. `portfolio_conflicts`
5. `portfolio_schedule_assessments`
6. `cumulative_impact_assessments`
7. `portfolio_resource_dependencies`
8. `portfolio_issues`
9. `portfolio_reviews`

---

## 2. Table Specifications

### 2.1 `governance_change_portfolios`
Authoritative register of governance change portfolios coordinating related initiatives.

```sql
CREATE TABLE governance_change_portfolios (
    portfolio_id VARCHAR(64) PRIMARY KEY,
    tenant_id VARCHAR(64) NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    governance_purpose TEXT NOT NULL,
    portfolio_owner_id VARCHAR(64) NOT NULL,
    executive_sponsor_id VARCHAR(64),
    participating_organizations JSONB NOT NULL DEFAULT '[]'::jsonb,
    participating_facilities JSONB NOT NULL DEFAULT '[]'::jsonb,
    participating_departments JSONB NOT NULL DEFAULT '[]'::jsonb,
    participating_teams JSONB NOT NULL DEFAULT '[]'::jsonb,
    priority VARCHAR(32) NOT NULL DEFAULT 'MEDIUM',
    planned_start_date TIMESTAMPTZ NOT NULL,
    target_review_date TIMESTAMPTZ NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'DRAFT',
    inclusion_criteria JSONB NOT NULL DEFAULT '[]'::jsonb,
    exclusion_criteria JSONB NOT NULL DEFAULT '[]'::jsonb,
    related_management_review_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    version INT NOT NULL DEFAULT 1,
    created_by VARCHAR(64) NOT NULL,
    submitted_by VARCHAR(64),
    submitted_at TIMESTAMPTZ,
    approved_by VARCHAR(64),
    approved_at TIMESTAMPTZ,
    approval_comments TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_portfolios_tenant ON governance_change_portfolios(tenant_id);
CREATE INDEX idx_portfolios_status ON governance_change_portfolios(status);
```

### 2.2 `portfolio_initiatives`
Initiatives coordinated under a portfolio, referencing Phase 72 decisions, Phase 73 implementations, and Phase 74 adoptions.

```sql
CREATE TABLE portfolio_initiatives (
    initiative_id VARCHAR(64) PRIMARY KEY,
    portfolio_id VARCHAR(64) NOT NULL REFERENCES governance_change_portfolios(portfolio_id) ON DELETE RESTRICT,
    tenant_id VARCHAR(64) NOT NULL,
    decision_id VARCHAR(64) NOT NULL,
    implementation_id VARCHAR(64) NOT NULL,
    adoption_registration_id VARCHAR(64),
    title VARCHAR(255) NOT NULL,
    initiative_description TEXT NOT NULL,
    intended_operational_change TEXT NOT NULL,
    participating_facilities JSONB NOT NULL DEFAULT '[]'::jsonb,
    participating_departments JSONB NOT NULL DEFAULT '[]'::jsonb,
    participating_teams JSONB NOT NULL DEFAULT '[]'::jsonb,
    accountable_owner_id VARCHAR(64) NOT NULL,
    planned_start_date TIMESTAMPTZ NOT NULL,
    planned_target_date TIMESTAMPTZ NOT NULL,
    priority VARCHAR(32) NOT NULL DEFAULT 'MEDIUM',
    coordination_status VARCHAR(32) NOT NULL DEFAULT 'PROPOSED',
    source_implementation_status VARCHAR(64),
    source_adoption_status VARCHAR(64),
    is_blocked BOOLEAN NOT NULL DEFAULT FALSE,
    blocked_reason TEXT,
    created_by VARCHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_portfolio_implementation UNIQUE (portfolio_id, implementation_id)
);

CREATE INDEX idx_portfolio_inits_portfolio ON portfolio_initiatives(portfolio_id);
CREATE INDEX idx_portfolio_inits_impl ON portfolio_initiatives(implementation_id);
CREATE INDEX idx_portfolio_inits_status ON portfolio_initiatives(coordination_status);
```

### 2.3 `cross_initiative_dependencies`
Explicit dependencies between initiatives within a portfolio.

```sql
CREATE TABLE cross_initiative_dependencies (
    dependency_id VARCHAR(64) PRIMARY KEY,
    portfolio_id VARCHAR(64) NOT NULL REFERENCES governance_change_portfolios(portfolio_id) ON DELETE RESTRICT,
    tenant_id VARCHAR(64) NOT NULL,
    source_initiative_id VARCHAR(64) NOT NULL REFERENCES portfolio_initiatives(initiative_id) ON DELETE RESTRICT,
    target_initiative_id VARCHAR(64) NOT NULL REFERENCES portfolio_initiatives(initiative_id) ON DELETE RESTRICT,
    dependency_type VARCHAR(64) NOT NULL,
    description TEXT NOT NULL,
    dependency_owner_id VARCHAR(64) NOT NULL,
    required_condition TEXT NOT NULL,
    expected_resolution_date TIMESTAMPTZ,
    status VARCHAR(32) NOT NULL DEFAULT 'PROPOSED',
    supporting_evidence_reference VARCHAR(255),
    dispute_reason TEXT,
    verified_by VARCHAR(64),
    verified_at TIMESTAMPTZ,
    created_by VARCHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_cross_deps_portfolio ON cross_initiative_dependencies(portfolio_id);
CREATE INDEX idx_cross_deps_source ON cross_initiative_dependencies(source_initiative_id);
CREATE INDEX idx_cross_deps_target ON cross_initiative_dependencies(target_initiative_id);
CREATE INDEX idx_cross_deps_status ON cross_initiative_dependencies(status);
```

### 2.4 `portfolio_conflicts`
Identified conflicts between concurrent initiatives (schedule overlaps, resource competition, workflow clashes).

```sql
CREATE TABLE portfolio_conflicts (
    conflict_id VARCHAR(64) PRIMARY KEY,
    portfolio_id VARCHAR(64) NOT NULL REFERENCES governance_change_portfolios(portfolio_id) ON DELETE RESTRICT,
    tenant_id VARCHAR(64) NOT NULL,
    initiative_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    classification VARCHAR(64) NOT NULL,
    description TEXT NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'POTENTIAL_CONFLICT',
    detected_by VARCHAR(64) NOT NULL DEFAULT 'AUTOMATED_SCAN',
    detected_at TIMESTAMPTZ NOT NULL,
    reviewed_by VARCHAR(64),
    reviewed_at TIMESTAMPTZ,
    review_notes TEXT,
    disposition VARCHAR(64),
    disposed_by VARCHAR(64),
    disposed_at TIMESTAMPTZ,
    disposition_notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_portfolio_conflicts_portfolio ON portfolio_conflicts(portfolio_id);
CREATE INDEX idx_portfolio_conflicts_status ON portfolio_conflicts(status);
```

### 2.5 `portfolio_schedule_assessments`
Cross-initiative schedule assessments and advisory sequencing recommendations.

```sql
CREATE TABLE portfolio_schedule_assessments (
    assessment_id VARCHAR(64) PRIMARY KEY,
    portfolio_id VARCHAR(64) NOT NULL REFERENCES governance_change_portfolios(portfolio_id) ON DELETE RESTRICT,
    tenant_id VARCHAR(64) NOT NULL,
    assessment_date TIMESTAMPTZ NOT NULL,
    overlapping_initiatives JSONB NOT NULL DEFAULT '[]'::jsonb,
    sequencing_recommendations JSONB NOT NULL DEFAULT '[]'::jsonb,
    assessed_by VARCHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_schedule_assessments_portfolio ON portfolio_schedule_assessments(portfolio_id);
```

### 2.6 `cumulative_impact_assessments`
Cumulative operational disruption and burden evaluations across concurrent initiatives.

```sql
CREATE TABLE cumulative_impact_assessments (
    assessment_id VARCHAR(64) PRIMARY KEY,
    portfolio_id VARCHAR(64) NOT NULL REFERENCES governance_change_portfolios(portfolio_id) ON DELETE RESTRICT,
    tenant_id VARCHAR(64) NOT NULL,
    assessment_period VARCHAR(128) NOT NULL,
    included_initiative_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    affected_facilities JSONB NOT NULL DEFAULT '[]'::jsonb,
    affected_departments JSONB NOT NULL DEFAULT '[]'::jsonb,
    shared_workflows JSONB NOT NULL DEFAULT '[]'::jsonb,
    concurrent_changes_count INT NOT NULL DEFAULT 0,
    estimated_training_workload_hours FLOAT NOT NULL DEFAULT 0.0,
    procedure_update_count INT NOT NULL DEFAULT 0,
    disruption_risk_level VARCHAR(32) NOT NULL DEFAULT 'MEDIUM',
    data_coverage_percentage FLOAT NOT NULL DEFAULT 100.0,
    limitations_disclosed JSONB NOT NULL DEFAULT '[]'::jsonb,
    assumptions_noted JSONB NOT NULL DEFAULT '[]'::jsonb,
    clinical_safety_notice TEXT NOT NULL DEFAULT 'Operational burden assessment only. Does not predict or evaluate clinical safety outcomes.',
    assessor_id VARCHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_impact_assessments_portfolio ON cumulative_impact_assessments(portfolio_id);
```

### 2.7 `portfolio_resource_dependencies`
Visibility into shared subject-matter experts, clinical trainers, and facility availability windows.

```sql
CREATE TABLE portfolio_resource_dependencies (
    resource_dependency_id VARCHAR(64) PRIMARY KEY,
    portfolio_id VARCHAR(64) NOT NULL REFERENCES governance_change_portfolios(portfolio_id) ON DELETE RESTRICT,
    tenant_id VARCHAR(64) NOT NULL,
    initiative_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    resource_name VARCHAR(255) NOT NULL,
    resource_category VARCHAR(64) NOT NULL,
    capacity_status VARCHAR(32) NOT NULL DEFAULT 'UNKNOWN',
    notes TEXT,
    created_by VARCHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_resource_deps_portfolio ON portfolio_resource_dependencies(portfolio_id);
```

### 2.8 `portfolio_issues`
Cross-initiative issues routed to authoritative destination workflows (Phases 49, 54, 63, 67, 72, 74).

```sql
CREATE TABLE portfolio_issues (
    issue_id VARCHAR(64) PRIMARY KEY,
    portfolio_id VARCHAR(64) NOT NULL REFERENCES governance_change_portfolios(portfolio_id) ON DELETE RESTRICT,
    tenant_id VARCHAR(64) NOT NULL,
    related_initiative_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    category VARCHAR(64) NOT NULL,
    severity VARCHAR(32) NOT NULL DEFAULT 'MEDIUM',
    owner_id VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'OPEN',
    routed_destination VARCHAR(64),
    destination_reference VARCHAR(128),
    routing_notes TEXT,
    escalated_by VARCHAR(64),
    escalated_at TIMESTAMPTZ,
    created_by VARCHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_portfolio_issues_portfolio ON portfolio_issues(portfolio_id);
CREATE INDEX idx_portfolio_issues_status ON portfolio_issues(status);
```

### 2.9 `portfolio_reviews`
Structured review packages prepared for governance review and referred to Phase 72 Management Review.

```sql
CREATE TABLE portfolio_reviews (
    review_id VARCHAR(64) PRIMARY KEY,
    portfolio_id VARCHAR(64) NOT NULL REFERENCES governance_change_portfolios(portfolio_id) ON DELETE RESTRICT,
    tenant_id VARCHAR(64) NOT NULL,
    review_title VARCHAR(255) NOT NULL,
    review_period VARCHAR(128) NOT NULL,
    participants JSONB NOT NULL DEFAULT '[]'::jsonb,
    summary_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    recommendations JSONB NOT NULL DEFAULT '[]'::jsonb,
    referred_to_management_review BOOLEAN NOT NULL DEFAULT FALSE,
    management_review_reference VARCHAR(128),
    referral_notes TEXT,
    status VARCHAR(32) NOT NULL DEFAULT 'DRAFT',
    chair_id VARCHAR(64) NOT NULL,
    submitted_by VARCHAR(64),
    approved_by VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_portfolio_reviews_portfolio ON portfolio_reviews(portfolio_id);
CREATE INDEX idx_portfolio_reviews_status ON portfolio_reviews(status);
```

---

## 3. Strict Clinical Safety & Governance Invariants
1. **Separation of Duties:**
   - Portfolio creator or owner cannot approve the portfolio (`created_by != approved_by` and `portfolio_owner_id != approved_by`).
2. **Clinical Safety Boundary Notice:**
   - `cumulative_impact_assessments.clinical_safety_notice` is immutable and explicitly confirms that operational burden evaluations do not predict or evaluate clinical safety outcomes.
3. **Traceability Preservation:**
   - Every portfolio initiative references an authorized Phase 72 decision and Phase 73 implementation record.
