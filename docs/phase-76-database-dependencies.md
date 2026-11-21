# Phase 76: Database Persistence Requirements & Contracts

**Module**: Governance Change Portfolio Performance Assurance, Benefit Realization & Strategic Outcome Review  
**Consumer**: Database Teammate  
**Backend Layer**: In-Memory Thread-Safe Singleton Repository (`GovernanceBenefitAssuranceRepository`)  
**Strict Boundary**: Backend does **not** create or modify tables, ORM models, migrations, or indexes. All persistence models below represent the authoritative contract for the database teammate.

---

## 1. Relational Schema Architecture

```
                          ┌────────────────────────┐
                          │  governance_benefits   │
                          └───────────┬────────────┘
         ┌────────────────────────────┼────────────────────────────┐
         │                            │                            │
         ▼                            ▼                            ▼
┌──────────────────┐         ┌──────────────────┐         ┌──────────────────┐
│benefit_baselines │         │ benefit_targets  │         │benefit_indicators│
└──────────────────┘         └──────────────────┘         └─────────┬────────┘
                                                                    │
                                                                    ▼
                                                          ┌───────────────────┐
                                                          │benefit_measuremnts│
                                                          └───────────────────┘
```

---

## 2. Table Specifications

### 2.1 `governance_benefits`
Primary registry for expected operational and clinical governance benefits.
- `benefit_id`: `VARCHAR(64)` PRIMARY KEY
- `tenant_id`: `VARCHAR(64)` NOT NULL INDEX
- `title`: `VARCHAR(255)` NOT NULL
- `description`: `TEXT` NOT NULL
- `category`: `VARCHAR(64)` NOT NULL (e.g. `OPERATIONAL_EFFICIENCY`, `WORKFLOW_CONSISTENCY`, `PROCESS_RELIABILITY`, `TRAINING_READINESS`, `DOCUMENTATION_QUALITY`, `EVIDENCE_COMPLETENESS`, `OPERATIONAL_COORDINATION`, `COMPLIANCE_PROCESS_IMPROVEMENT`, `PATIENT_EXPERIENCE_AUTHORIZED`, `CLINICAL_OUTCOME_INDICATOR`)
- `expected_outcome`: `TEXT` NOT NULL
- `decision_id`: `VARCHAR(64)` NOT NULL INDEX (Ref Phase 72)
- `implementation_id`: `VARCHAR(64)` NOT NULL INDEX (Ref Phase 73)
- `portfolio_id`: `VARCHAR(64)` NULL INDEX (Ref Phase 75)
- `adoption_registration_id`: `VARCHAR(64)` NULL INDEX (Ref Phase 74)
- `responsible_benefit_owner_id`: `VARCHAR(64)` NOT NULL
- `organizational_scope`: `JSONB` NOT NULL DEFAULT `'{}'`
- `expected_realization_date`: `TIMESTAMPTZ` NOT NULL
- `measurement_period`: `VARCHAR(64)` NOT NULL
- `active_baseline_id`: `VARCHAR(64)` NULL
- `active_target_id`: `VARCHAR(64)` NULL
- `measurement_methodology`: `TEXT` NOT NULL
- `evidence_requirements`: `JSONB` NOT NULL DEFAULT `'[]'`
- `verification_requirements`: `JSONB` NOT NULL DEFAULT `'[]'`
- `status`: `VARCHAR(32)` NOT NULL DEFAULT `'DRAFT'`
- `version`: `INTEGER` NOT NULL DEFAULT 1
- `created_by`: `VARCHAR(64)` NOT NULL
- `created_at`: `TIMESTAMPTZ` NOT NULL DEFAULT NOW()
- `updated_at`: `TIMESTAMPTZ` NOT NULL DEFAULT NOW()

### 2.2 `benefit_baselines`
Versioned baseline measurements.
- `baseline_id`: `VARCHAR(64)` PRIMARY KEY
- `benefit_id`: `VARCHAR(64)` NOT NULL REFERENCES `governance_benefits(benefit_id)` ON DELETE CASCADE
- `tenant_id`: `VARCHAR(64)` NOT NULL INDEX
- `version`: `INTEGER` NOT NULL DEFAULT 1
- `measurement_definition`: `TEXT` NOT NULL
- `baseline_value`: `NUMERIC(14, 4)` NULL
- `qualitative_state`: `TEXT` NULL
- `unit`: `VARCHAR(64)` NOT NULL
- `measurement_period`: `VARCHAR(64)` NOT NULL
- `source_system`: `VARCHAR(128)` NOT NULL
- `data_collection_method`: `TEXT` NOT NULL
- `data_quality_requirements`: `JSONB` NOT NULL DEFAULT `'[]'`
- `organizational_scope`: `JSONB` NOT NULL DEFAULT `'{}'`
- `status`: `VARCHAR(32)` NOT NULL DEFAULT `'DRAFT'`
- `approval_reference`: `VARCHAR(128)` NULL
- `approved_by`: `VARCHAR(64)` NULL
- `approved_at`: `TIMESTAMPTZ` NULL
- `created_by`: `VARCHAR(64)` NOT NULL
- `created_at`: `TIMESTAMPTZ` NOT NULL DEFAULT NOW()
- *Unique Constraint*: `(benefit_id, version)`

### 2.3 `benefit_targets`
Versioned approved targets.
- `target_id`: `VARCHAR(64)` PRIMARY KEY
- `benefit_id`: `VARCHAR(64)` NOT NULL REFERENCES `governance_benefits(benefit_id)` ON DELETE CASCADE
- `tenant_id`: `VARCHAR(64)` NOT NULL INDEX
- `version`: `INTEGER` NOT NULL DEFAULT 1
- `target_value`: `NUMERIC(14, 4)` NULL
- `target_condition`: `TEXT` NULL
- `target_measurement_date`: `TIMESTAMPTZ` NOT NULL
- `unit`: `VARCHAR(64)` NOT NULL
- `measurement_method`: `TEXT` NOT NULL
- `required_evidence`: `JSONB` NOT NULL DEFAULT `'[]'`
- `organizational_scope`: `JSONB` NOT NULL DEFAULT `'{}'`
- `status`: `VARCHAR(32)` NOT NULL DEFAULT `'DRAFT'`
- `approval_reference`: `VARCHAR(128)` NULL
- `approved_by`: `VARCHAR(64)` NULL
- `approved_at`: `TIMESTAMPTZ` NULL
- `created_by`: `VARCHAR(64)` NOT NULL
- `created_at`: `TIMESTAMPTZ` NOT NULL DEFAULT NOW()
- *Unique Constraint*: `(benefit_id, version)`

### 2.4 `benefit_indicators`
Configurable metrics and indicators.
- `indicator_id`: `VARCHAR(64)` PRIMARY KEY
- `benefit_id`: `VARCHAR(64)` NOT NULL REFERENCES `governance_benefits(benefit_id)` ON DELETE CASCADE
- `tenant_id`: `VARCHAR(64)` NOT NULL INDEX
- `name`: `VARCHAR(255)` NOT NULL
- `description`: `TEXT` NOT NULL
- `indicator_type`: `VARCHAR(64)` NOT NULL
- `calculation_methodology`: `TEXT` NOT NULL
- `unit`: `VARCHAR(64)` NOT NULL
- `expected_direction`: `VARCHAR(32)` NOT NULL
- `baseline_reference`: `VARCHAR(64)` NULL
- `target_reference`: `VARCHAR(64)` NULL
- `measurement_frequency`: `VARCHAR(64)` NOT NULL
- `organizational_scope`: `JSONB` NOT NULL DEFAULT `'{}'`
- `source_system`: `VARCHAR(128)` NOT NULL
- `responsible_owner_id`: `VARCHAR(64)` NOT NULL
- `created_at`: `TIMESTAMPTZ` NOT NULL DEFAULT NOW()

### 2.5 `benefit_measurements`
Observed intake data records.
- `measurement_id`: `VARCHAR(64)` PRIMARY KEY
- `benefit_id`: `VARCHAR(64)` NOT NULL REFERENCES `governance_benefits(benefit_id)` ON DELETE CASCADE
- `indicator_id`: `VARCHAR(64)` NOT NULL REFERENCES `benefit_indicators(indicator_id)` ON DELETE CASCADE
- `tenant_id`: `VARCHAR(64)` NOT NULL INDEX
- `measurement_period`: `VARCHAR(64)` NOT NULL INDEX
- `observed_value`: `NUMERIC(14, 4)` NULL
- `qualitative_state`: `TEXT` NULL
- `unit`: `VARCHAR(64)` NOT NULL
- `source_reference`: `VARCHAR(128)` NOT NULL
- `source_system`: `VARCHAR(128)` NOT NULL
- `evidence_references`: `JSONB` NOT NULL DEFAULT `'[]'`
- `validation_status`: `VARCHAR(32)` NOT NULL DEFAULT `'SUBMITTED'`
- `reviewer_id`: `VARCHAR(64)` NULL
- `verification_timestamp`: `TIMESTAMPTZ` NULL
- `validation_notes`: `TEXT` NULL
- `created_by`: `VARCHAR(64)` NOT NULL
- `collection_timestamp`: `TIMESTAMPTZ` NOT NULL DEFAULT NOW()

### 2.6 `benefit_realization_assessments`
Authoritative evaluation comparing baseline, target, and validated observations.
- `assessment_id`: `VARCHAR(64)` PRIMARY KEY
- `benefit_id`: `VARCHAR(64)` NOT NULL REFERENCES `governance_benefits(benefit_id)` ON DELETE CASCADE
- `tenant_id`: `VARCHAR(64)` NOT NULL INDEX
- `measurement_period`: `VARCHAR(64)` NOT NULL INDEX
- `baseline_version`: `INTEGER` NOT NULL
- `target_version`: `INTEGER` NOT NULL
- `disposition`: `VARCHAR(64)` NOT NULL (e.g. `REALIZED`, `PARTIALLY_REALIZED`, `DELAYED`, `NOT_REALIZED`, `INSUFFICIENT_EVIDENCE`)
- `calculation_details`: `JSONB` NOT NULL DEFAULT `'{}'`
- `evidence_references`: `JSONB` NOT NULL DEFAULT `'[]'`
- `limitations`: `JSONB` NOT NULL DEFAULT `'[]'`
- `clinical_safety_notice`: `TEXT` NOT NULL
- `status`: `VARCHAR(32)` NOT NULL DEFAULT `'DRAFT'`
- `assessor_id`: `VARCHAR(64)` NOT NULL
- `approved_by`: `VARCHAR(64)` NULL
- `created_at`: `TIMESTAMPTZ` NOT NULL DEFAULT NOW()

### 2.7 `benefit_attributions`
Transparent attribution analyses distinguishing correlation from direct causation.
- `attribution_id`: `VARCHAR(64)` PRIMARY KEY
- `benefit_id`: `VARCHAR(64)` NOT NULL REFERENCES `governance_benefits(benefit_id)` ON DELETE CASCADE
- `tenant_id`: `VARCHAR(64)` NOT NULL INDEX
- `attribution_type`: `VARCHAR(64)` NOT NULL
- `related_initiative_ids`: `JSONB` NOT NULL DEFAULT `'[]'`
- `relevant_implementation_periods`: `JSONB` NOT NULL DEFAULT `'[]'`
- `external_influencing_factors`: `JSONB` NOT NULL DEFAULT `'[]'`
- `measurement_limitations`: `JSONB` NOT NULL DEFAULT `'[]'`
- `attribution_methodology`: `TEXT` NOT NULL
- `supporting_evidence`: `JSONB` NOT NULL DEFAULT `'[]'`
- `reviewer_id`: `VARCHAR(64)` NOT NULL
- `clinical_safety_notice`: `TEXT` NOT NULL
- `created_at`: `TIMESTAMPTZ` NOT NULL DEFAULT NOW()

### 2.8 `benefit_unintended_consequences`
Operational trade-offs and unintended side-effects.
- `consequence_id`: `VARCHAR(64)` PRIMARY KEY
- `benefit_id`: `VARCHAR(64)` NOT NULL REFERENCES `governance_benefits(benefit_id)` ON DELETE CASCADE
- `tenant_id`: `VARCHAR(64)` NOT NULL INDEX
- `description`: `TEXT` NOT NULL
- `status`: `VARCHAR(64)` NOT NULL DEFAULT `'POTENTIAL_CONSEQUENCE'`
- `routed_destination`: `VARCHAR(64)` NULL (e.g. `PHASE_49_INCIDENTS`, `PHASE_54_CAPA`, `PHASE_63_RISK_REVIEW`, `PHASE_74_ADOPTION`)
- `destination_reference`: `VARCHAR(128)` NULL
- `created_by`: `VARCHAR(64)` NOT NULL
- `created_at`: `TIMESTAMPTZ` NOT NULL DEFAULT NOW()

### 2.9 `benefit_sustainabilities`
Longitudinal trend assessments.
- `sustainability_id`: `VARCHAR(64)` PRIMARY KEY
- `benefit_id`: `VARCHAR(64)` NOT NULL REFERENCES `governance_benefits(benefit_id)` ON DELETE CASCADE
- `tenant_id`: `VARCHAR(64)` NOT NULL INDEX
- `assessment_period`: `VARCHAR(64)` NOT NULL
- `trend`: `VARCHAR(64)` NOT NULL (e.g. `SUSTAINED`, `DECLINING`, `REVERSED`)
- `consecutive_positive_periods`: `INTEGER` NOT NULL DEFAULT 1
- `performance_stability_score`: `NUMERIC(5, 4)` NOT NULL DEFAULT 1.0
- `clinical_safety_notice`: `TEXT` NOT NULL
- `assessed_by`: `VARCHAR(64)` NOT NULL
- `created_at`: `TIMESTAMPTZ` NOT NULL DEFAULT NOW()

### 2.10 `benefit_verifications`
Independent verifications enforcing separation of duties.
- `verification_id`: `VARCHAR(64)` PRIMARY KEY
- `benefit_id`: `VARCHAR(64)` NOT NULL REFERENCES `governance_benefits(benefit_id)` ON DELETE CASCADE
- `tenant_id`: `VARCHAR(64)` NOT NULL INDEX
- `verification_scope`: `TEXT` NOT NULL
- `requester_id`: `VARCHAR(64)` NOT NULL
- `assigned_verifier_id`: `VARCHAR(64)` NULL
- `conflict_of_interest_checked`: `BOOLEAN` NOT NULL DEFAULT FALSE
- `status`: `VARCHAR(64)` NOT NULL DEFAULT `'REQUESTED'`
- `findings`: `TEXT` NULL
- `verifier_comments`: `TEXT` NULL
- `recalculated_values`: `JSONB` NOT NULL DEFAULT `'{}'`
- `completed_at`: `TIMESTAMPTZ` NULL
- `created_at`: `TIMESTAMPTZ` NOT NULL DEFAULT NOW()

### 2.11 `benefit_exceptions`
Measurement exceptions and exemptions.
- `exception_id`: `VARCHAR(64)` PRIMARY KEY
- `benefit_id`: `VARCHAR(64)` NOT NULL REFERENCES `governance_benefits(benefit_id)` ON DELETE CASCADE
- `tenant_id`: `VARCHAR(64)` NOT NULL INDEX
- `exception_category`: `VARCHAR(64)` NOT NULL
- `description`: `TEXT` NOT NULL
- `impact_on_measurement`: `TEXT` NOT NULL
- `requested_duration_days`: `INTEGER` NOT NULL DEFAULT 30
- `review_date`: `TIMESTAMPTZ` NOT NULL
- `authorization_reference`: `VARCHAR(128)` NULL
- `status`: `VARCHAR(32)` NOT NULL DEFAULT `'DRAFT'`
- `created_by`: `VARCHAR(64)` NOT NULL
- `created_at`: `TIMESTAMPTZ` NOT NULL DEFAULT NOW()

### 2.12 `benefit_review_packages`
Governance review packages for Phase 72 Management Review referral.
- `review_id`: `VARCHAR(64)` PRIMARY KEY
- `portfolio_id`: `VARCHAR(64)` NOT NULL INDEX
- `tenant_id`: `VARCHAR(64)` NOT NULL INDEX
- `review_period`: `VARCHAR(64)` NOT NULL
- `title`: `VARCHAR(255)` NOT NULL
- `benefits_snapshot`: `JSONB` NOT NULL DEFAULT `'[]'`
- `recommendations`: `JSONB` NOT NULL DEFAULT `'[]'`
- `management_review_reference`: `VARCHAR(128)` NULL
- `status`: `VARCHAR(32)` NOT NULL DEFAULT `'DRAFT'`
- `created_by`: `VARCHAR(64)` NOT NULL
- `created_at`: `TIMESTAMPTZ` NOT NULL DEFAULT NOW()

---

## 3. Recommended PostgreSQL Indexes

```sql
CREATE INDEX idx_gov_benefits_tenant ON governance_benefits (tenant_id);
CREATE INDEX idx_gov_benefits_impl ON governance_benefits (tenant_id, implementation_id);
CREATE INDEX idx_gov_benefits_port ON governance_benefits (tenant_id, portfolio_id);
CREATE INDEX idx_gov_benefits_status ON governance_benefits (tenant_id, status);

CREATE INDEX idx_benefit_meas_lookup ON benefit_measurements (tenant_id, benefit_id, measurement_period);
CREATE INDEX idx_benefit_meas_valid ON benefit_measurements (tenant_id, validation_status);

CREATE INDEX idx_benefit_assess_lookup ON benefit_realization_assessments (tenant_id, benefit_id, measurement_period);
CREATE INDEX idx_benefit_sustain_lookup ON benefit_sustainabilities (tenant_id, benefit_id);
CREATE INDEX idx_benefit_verif_tenant ON benefit_verifications (tenant_id, status);
CREATE INDEX idx_benefit_exc_status ON benefit_exceptions (tenant_id, status, review_date);
```
