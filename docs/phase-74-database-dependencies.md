# Phase 74: Database Teammate Dependencies & Persistence Contracts

**Phase:** Phase 74 — Governance Change Adoption, Operational Sustainability & Implementation Drift Monitoring  
**Target Persistence Layer:** PostgreSQL 16+ / SQLAlchemy 2.x  
**Database Ownership Notice:**  
The backend implementation strictly respects the database ownership boundary. The backend does not define new database migrations, raw SQL DDL, or independent ORM entities directly. This document specifies the exact persistence contracts, schemas, foreign keys, constraints, indexes, and audit triggers required from the database teammate for Phase 74.

---

## 1. Persistence Tables Overview

Phase 74 introduces ten structured entities for governance change adoption and operational drift tracking:

1. `governance_change_adoption_registrations`
2. `operational_adoption_baselines`
3. `adoption_monitoring_plans`
4. `adoption_evidence`
5. `adoption_indicators`
6. `implementation_drift_signals`
7. `sustainability_assessments`
8. `adoption_exceptions`
9. `operational_consequences`
10. `adoption_escalations`

---

## 2. Table Specifications

### 2.1 `governance_change_adoption_registrations`
Authoritative register of governance changes that have completed or entered Phase 73 implementation and require operational adoption monitoring.

```sql
CREATE TABLE governance_change_adoption_registrations (
    registration_id VARCHAR(64) PRIMARY KEY,
    tenant_id VARCHAR(64) NOT NULL,
    management_review_id VARCHAR(64) NOT NULL,
    decision_id VARCHAR(64) NOT NULL,
    implementation_id VARCHAR(64) NOT NULL, -- references Phase 73 decision_implementations
    title VARCHAR(255) NOT NULL,
    change_description TEXT NOT NULL,
    operational_scope JSONB NOT NULL DEFAULT '{}'::jsonb,
    accountable_operational_owner_id VARCHAR(64) NOT NULL,
    adoption_monitoring_owner_id VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'PENDING_BASELINE',
    monitoring_start_date TIMESTAMPTZ NOT NULL,
    expected_monitoring_duration_days INT NOT NULL DEFAULT 90,
    current_baseline_version VARCHAR(32),
    active_baseline_id VARCHAR(64),
    adoption_milestones JSONB NOT NULL DEFAULT '[]'::jsonb,
    required_evidence_categories JSONB NOT NULL DEFAULT '[]'::jsonb,
    limitations_disclosed JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_by VARCHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    version INT NOT NULL DEFAULT 1
);

CREATE INDEX idx_change_adoption_reg_tenant ON governance_change_adoption_registrations(tenant_id);
CREATE INDEX idx_change_adoption_reg_status ON governance_change_adoption_registrations(status);
CREATE INDEX idx_change_adoption_reg_impl ON governance_change_adoption_registrations(implementation_id);
```

### 2.2 `operational_adoption_baselines`
Version-controlled operational adoption baselines defining expected workflows, practices, readiness criteria, and limitations.

```sql
CREATE TABLE operational_adoption_baselines (
    baseline_id VARCHAR(64) PRIMARY KEY,
    registration_id VARCHAR(64) NOT NULL REFERENCES governance_change_adoption_registrations(registration_id) ON DELETE RESTRICT,
    tenant_id VARCHAR(64) NOT NULL,
    version VARCHAR(32) NOT NULL,
    previous_version_id VARCHAR(64),
    change_reason TEXT,
    intended_operational_process TEXT NOT NULL,
    expected_workflow_behavior TEXT NOT NULL,
    required_operational_practices JSONB NOT NULL DEFAULT '[]'::jsonb,
    operational_scope JSONB NOT NULL DEFAULT '{}'::jsonb,
    responsible_roles JSONB NOT NULL DEFAULT '[]'::jsonb,
    required_training_programmes JSONB NOT NULL DEFAULT '[]'::jsonb,
    required_procedural_docs JSONB NOT NULL DEFAULT '[]'::jsonb,
    operational_readiness_criteria JSONB NOT NULL DEFAULT '[]'::jsonb,
    required_evidence_types JSONB NOT NULL DEFAULT '[]'::jsonb,
    monitoring_frequency VARCHAR(32) NOT NULL DEFAULT 'WEEKLY',
    known_limitations JSONB NOT NULL DEFAULT '[]'::jsonb,
    system_dependencies JSONB NOT NULL DEFAULT '[]'::jsonb,
    approved_exceptions_summary JSONB NOT NULL DEFAULT '[]'::jsonb,
    status VARCHAR(32) NOT NULL DEFAULT 'DRAFT',
    author_id VARCHAR(64) NOT NULL,
    submitted_by VARCHAR(64),
    submitted_at TIMESTAMPTZ,
    approved_by VARCHAR(64),
    approved_at TIMESTAMPTZ,
    approval_authority_role VARCHAR(64),
    rejection_reason TEXT,
    effective_date TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_baseline_registration_version UNIQUE (registration_id, version)
);

CREATE INDEX idx_baseline_reg ON operational_adoption_baselines(registration_id);
CREATE INDEX idx_baseline_tenant_status ON operational_adoption_baselines(tenant_id, status);
```

### 2.3 `adoption_monitoring_plans`
Structured monitoring plans defining objectives, multi-level organizational scopes, thresholds, and end criteria.

```sql
CREATE TABLE adoption_monitoring_plans (
    plan_id VARCHAR(64) PRIMARY KEY,
    registration_id VARCHAR(64) NOT NULL REFERENCES governance_change_adoption_registrations(registration_id) ON DELETE RESTRICT,
    tenant_id VARCHAR(64) NOT NULL,
    title VARCHAR(255) NOT NULL,
    monitoring_objectives JSONB NOT NULL DEFAULT '[]'::jsonb,
    organizational_scope JSONB NOT NULL DEFAULT '{}'::jsonb,
    baseline_id VARCHAR(64) NOT NULL REFERENCES operational_adoption_baselines(baseline_id),
    baseline_version VARCHAR(32) NOT NULL,
    monitoring_schedule_start TIMESTAMPTZ NOT NULL,
    monitoring_schedule_end TIMESTAMPTZ,
    monitoring_frequency VARCHAR(32) NOT NULL DEFAULT 'WEEKLY',
    responsible_operational_owner_id VARCHAR(64) NOT NULL,
    independent_verifier_role VARCHAR(64),
    escalation_thresholds JSONB NOT NULL DEFAULT '{}'::jsonb,
    reporting_cadence VARCHAR(32) NOT NULL DEFAULT 'MONTHLY',
    monitoring_end_criteria JSONB NOT NULL DEFAULT '[]'::jsonb,
    known_limitations JSONB NOT NULL DEFAULT '[]'::jsonb,
    status VARCHAR(32) NOT NULL DEFAULT 'DRAFT',
    created_by VARCHAR(64) NOT NULL,
    activated_by VARCHAR(64),
    activated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_monitoring_plans_reg ON adoption_monitoring_plans(registration_id);
CREATE INDEX idx_monitoring_plans_status ON adoption_monitoring_plans(status);
```

### 2.4 `adoption_evidence`
Operational evidence artifacts verifying workflow integration, procedure updates, training completion, and checklist executions.

```sql
CREATE TABLE adoption_evidence (
    evidence_id VARCHAR(64) PRIMARY KEY,
    registration_id VARCHAR(64) NOT NULL REFERENCES governance_change_adoption_registrations(registration_id) ON DELETE RESTRICT,
    tenant_id VARCHAR(64) NOT NULL,
    baseline_version VARCHAR(32) NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    category VARCHAR(64) NOT NULL,
    organizational_scope JSONB NOT NULL DEFAULT '{}'::jsonb,
    source_system VARCHAR(128) NOT NULL,
    source_reference VARCHAR(255) NOT NULL,
    collected_at TIMESTAMPTZ NOT NULL,
    submitted_at TIMESTAMPTZ NOT NULL,
    submitting_actor_id VARCHAR(64) NOT NULL,
    verification_status VARCHAR(32) NOT NULL DEFAULT 'SUBMITTED',
    reviewer_id VARCHAR(64),
    verified_at TIMESTAMPTZ,
    rejection_reason TEXT,
    valid_until TIMESTAMPTZ,
    integrity_hash VARCHAR(128),
    provenance_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_adoption_evidence_reg ON adoption_evidence(registration_id);
CREATE INDEX idx_adoption_evidence_status ON adoption_evidence(verification_status);
CREATE INDEX idx_adoption_evidence_expiry ON adoption_evidence(valid_until);
```

### 2.5 `adoption_indicators`
Configurable operational adoption indicators evaluated strictly against verified evidence.

```sql
CREATE TABLE adoption_indicators (
    indicator_id VARCHAR(64) PRIMARY KEY,
    registration_id VARCHAR(64) NOT NULL REFERENCES governance_change_adoption_registrations(registration_id) ON DELETE RESTRICT,
    tenant_id VARCHAR(64) NOT NULL,
    indicator_key VARCHAR(100) NOT NULL,
    title VARCHAR(255) NOT NULL,
    category VARCHAR(64) NOT NULL,
    measurement_criteria TEXT NOT NULL,
    target_threshold VARCHAR(128) NOT NULL,
    current_value VARCHAR(128),
    outcome VARCHAR(32) NOT NULL DEFAULT 'NOT_ASSESSED',
    evidence_ids_used JSONB NOT NULL DEFAULT '[]'::jsonb,
    confidence VARCHAR(32) NOT NULL DEFAULT 'UNKNOWN',
    assessed_by VARCHAR(64),
    assessed_at TIMESTAMPTZ,
    rationale TEXT,
    limitations_noted JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_indicator_reg_key UNIQUE (registration_id, indicator_key)
);

CREATE INDEX idx_adoption_indicator_reg ON adoption_indicators(registration_id);
CREATE INDEX idx_adoption_indicator_outcome ON adoption_indicators(outcome);
```

### 2.6 `implementation_drift_signals`
Signals detecting divergence between current operational practices and approved baseline requirements.

```sql
CREATE TABLE implementation_drift_signals (
    signal_id VARCHAR(64) PRIMARY KEY,
    registration_id VARCHAR(64) NOT NULL REFERENCES governance_change_adoption_registrations(registration_id) ON DELETE RESTRICT,
    tenant_id VARCHAR(64) NOT NULL,
    baseline_version VARCHAR(32) NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    classification VARCHAR(64) NOT NULL DEFAULT 'POTENTIAL_DRIFT',
    source_type VARCHAR(64) NOT NULL DEFAULT 'MANUAL_OBSERVATION',
    observed_at TIMESTAMPTZ NOT NULL,
    evidence_reference VARCHAR(255),
    operational_scope JSONB NOT NULL DEFAULT '{}'::jsonb,
    status VARCHAR(32) NOT NULL DEFAULT 'OPEN',
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

CREATE INDEX idx_drift_signals_reg ON implementation_drift_signals(registration_id);
CREATE INDEX idx_drift_signals_status ON implementation_drift_signals(status);
```

### 2.7 `sustainability_assessments`
Multi-dimensional evaluations of whether changes remain integrated over routine operations.

```sql
CREATE TABLE sustainability_assessments (
    assessment_id VARCHAR(64) PRIMARY KEY,
    registration_id VARCHAR(64) NOT NULL REFERENCES governance_change_adoption_registrations(registration_id) ON DELETE RESTRICT,
    tenant_id VARCHAR(64) NOT NULL,
    baseline_version VARCHAR(32) NOT NULL,
    monitoring_period VARCHAR(128) NOT NULL,
    operational_scope JSONB NOT NULL DEFAULT '{}'::jsonb,
    dimension_scores JSONB NOT NULL DEFAULT '{}'::jsonb,
    evidence_references JSONB NOT NULL DEFAULT '[]'::jsonb,
    unresolved_limitations JSONB NOT NULL DEFAULT '[]'::jsonb,
    disposition VARCHAR(64) NOT NULL DEFAULT 'PENDING',
    status VARCHAR(32) NOT NULL DEFAULT 'DRAFT',
    assessor_id VARCHAR(64) NOT NULL,
    submitted_by VARCHAR(64),
    submitted_at TIMESTAMPTZ,
    approved_by VARCHAR(64),
    approved_at TIMESTAMPTZ,
    approval_comments TEXT,
    follow_up_requirements JSONB NOT NULL DEFAULT '[]'::jsonb,
    clinical_safety_notice TEXT NOT NULL DEFAULT 'Operational sustainability assessment only. Does not replace Phase 55 clinical effectiveness.',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_sustainability_reg ON sustainability_assessments(registration_id);
CREATE INDEX idx_sustainability_status ON sustainability_assessments(status);
```

### 2.8 `adoption_exceptions`
Operational adoption exceptions with explicit authorization references and expiry tracking.

```sql
CREATE TABLE adoption_exceptions (
    exception_id VARCHAR(64) PRIMARY KEY,
    registration_id VARCHAR(64) NOT NULL REFERENCES governance_change_adoption_registrations(registration_id) ON DELETE RESTRICT,
    tenant_id VARCHAR(64) NOT NULL,
    baseline_version VARCHAR(32) NOT NULL,
    category VARCHAR(64) NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    supporting_evidence_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    risk_reference VARCHAR(128),
    operational_scope JSONB NOT NULL DEFAULT '{}'::jsonb,
    responsible_owner_id VARCHAR(64) NOT NULL,
    requested_duration_days INT NOT NULL DEFAULT 30,
    review_date TIMESTAMPTZ NOT NULL,
    expiry_date TIMESTAMPTZ,
    authorization_reference VARCHAR(128),
    status VARCHAR(32) NOT NULL DEFAULT 'DRAFT',
    reviewed_by VARCHAR(64),
    reviewed_at TIMESTAMPTZ,
    resolution_requirements JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_adoption_exceptions_reg ON adoption_exceptions(registration_id);
CREATE INDEX idx_adoption_exceptions_status ON adoption_exceptions(status);
CREATE INDEX idx_adoption_exceptions_expiry ON adoption_exceptions(expiry_date);
```

### 2.9 `operational_consequences`
Unintended operational consequences recorded and routed to authoritative workflows (Phases 49, 54, 59, 63, 67, 72).

```sql
CREATE TABLE operational_consequences (
    consequence_id VARCHAR(64) PRIMARY KEY,
    registration_id VARCHAR(64) NOT NULL REFERENCES governance_change_adoption_registrations(registration_id) ON DELETE RESTRICT,
    tenant_id VARCHAR(64) NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    severity VARCHAR(32) NOT NULL DEFAULT 'MEDIUM',
    operational_scope JSONB NOT NULL DEFAULT '{}'::jsonb,
    reported_by VARCHAR(64) NOT NULL,
    reported_at TIMESTAMPTZ NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'REPORTED',
    routed_destination VARCHAR(64),
    destination_reference VARCHAR(128),
    routing_notes TEXT,
    routed_by VARCHAR(64),
    routed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_consequences_reg ON operational_consequences(registration_id);
CREATE INDEX idx_consequences_dest ON operational_consequences(routed_destination);
```

### 2.10 `adoption_escalations`
Adoption escalations triggered by unaddressed drift, expired exceptions, or sustained adoption failures.

```sql
CREATE TABLE adoption_escalations (
    escalation_id VARCHAR(64) PRIMARY KEY,
    registration_id VARCHAR(64) NOT NULL REFERENCES governance_change_adoption_registrations(registration_id) ON DELETE RESTRICT,
    tenant_id VARCHAR(64) NOT NULL,
    title VARCHAR(255) NOT NULL,
    reason TEXT NOT NULL,
    urgency VARCHAR(32) NOT NULL DEFAULT 'PRIORITY',
    escalated_to_destination VARCHAR(128) NOT NULL DEFAULT 'MANAGEMENT_REVIEW',
    escalated_by VARCHAR(64) NOT NULL,
    escalated_at TIMESTAMPTZ NOT NULL,
    acknowledged_by VARCHAR(64),
    acknowledged_at TIMESTAMPTZ,
    resolution_notes TEXT,
    resolved BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_adoption_escalations_reg ON adoption_escalations(registration_id);
CREATE INDEX idx_adoption_escalations_resolved ON adoption_escalations(resolved);
```

---

## 3. Strict Clinical Safety & Governance Invariants
1. **Separation of Duties:**
   - Baseline author cannot approve the baseline (`author_id != approved_by`).
   - Evidence submitting actor cannot verify their own evidence (`submitting_actor_id != reviewer_id`).
2. **Clinical Safety Boundary Notice:**
   - `sustainability_assessments.clinical_safety_notice` is immutable and explicitly confirms that operational sustainability evaluations do not replace Phase 55 clinical effectiveness verification.
3. **Evidence Integrity:**
   - Indicators cannot be marked `ACHIEVED` without valid, verified supporting evidence references.
