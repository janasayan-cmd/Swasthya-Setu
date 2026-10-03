# Phase 33: Database Dependencies & Team Ownership Boundaries

## 1. Team Ownership Boundaries

### Database Team Owns:
- Physical schema creation, table migrations, and DDL scripts.
- Relational tables: `insurance_coverages`, `eligibility_checks`, `benefit_records`, `pre_authorizations`, `claims`, `claim_items`, `claim_adjudications`, `claim_reconciliations`, `payer_webhook_events`.
- Unique indexes (`claim_number`, `authorization_number`, `idempotency_key`, `provider_claim_reference`, `provider:event_id`).
- Row-level locking primitives and database foreign key constraints.
- Financial audit trail persistence and database backup/restore strategies.

### Backend Team Owns:
- REST API contracts, FastAPI routers, and OpenAPI specifications.
- Deterministic integer minor unit calculations and line-item aggregation.
- External payer gateway adapters (HTTP clients, HMAC signature verification).
- Webhook deduplication logic and event replay protection.
- Authorization barriers (BOLA/IDOR protection, multi-tenant facility scoping).
- Notification dispatch and asynchronous job scheduling.

---

## 2. Expected Database Contract & Schema Models

### A. Insurance Coverages Table (`insurance_coverages`)
```sql
CREATE TABLE insurance_coverages (
    id VARCHAR(64) PRIMARY KEY,
    patient_id VARCHAR(128) NOT NULL,
    payer_id VARCHAR(128) NOT NULL,
    payer_name VARCHAR(255) NOT NULL,
    payer_code VARCHAR(64),
    tpa_name VARCHAR(255),
    policy_number VARCHAR(64) NOT NULL,
    member_id VARCHAR(64) NOT NULL,
    group_number VARCHAR(64),
    plan_name VARCHAR(128),
    plan_type VARCHAR(64),
    subscriber_id VARCHAR(128) NOT NULL,
    subscriber_name VARCHAR(255) NOT NULL,
    subscriber_dob DATE,
    relationship VARCHAR(32) NOT NULL DEFAULT 'SELF',
    status VARCHAR(32) NOT NULL DEFAULT 'UNVERIFIED',
    is_primary BOOLEAN NOT NULL DEFAULT TRUE,
    start_date DATE,
    end_date DATE,
    document_reference_id VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### B. Pre-Authorizations Table (`pre_authorizations`)
```sql
CREATE TABLE pre_authorizations (
    id VARCHAR(64) PRIMARY KEY,
    authorization_number VARCHAR(64) UNIQUE NOT NULL,
    patient_id VARCHAR(128) NOT NULL,
    coverage_id VARCHAR(64) NOT NULL REFERENCES insurance_coverages(id),
    payer_id VARCHAR(128) NOT NULL,
    facility_id VARCHAR(128),
    clinician_id VARCHAR(128),
    appointment_id VARCHAR(128),
    status VARCHAR(32) NOT NULL DEFAULT 'DRAFT',
    service_code VARCHAR(64) NOT NULL,
    service_description VARCHAR(255) NOT NULL,
    estimated_amount_in_minor_units BIGINT NOT NULL,
    approved_amount_in_minor_units BIGINT,
    currency VARCHAR(3) NOT NULL DEFAULT 'INR',
    valid_from DATE,
    valid_to DATE,
    payer_reference VARCHAR(255),
    denial_reason TEXT,
    denial_code VARCHAR(64),
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### C. Claims Table (`claims`)
```sql
CREATE TABLE claims (
    id VARCHAR(64) PRIMARY KEY,
    claim_number VARCHAR(64) UNIQUE NOT NULL,
    patient_id VARCHAR(128) NOT NULL,
    coverage_id VARCHAR(64) NOT NULL REFERENCES insurance_coverages(id),
    payer_id VARCHAR(128) NOT NULL,
    organization_id VARCHAR(128),
    facility_id VARCHAR(128),
    clinician_id VARCHAR(128),
    appointment_id VARCHAR(128),
    invoice_id VARCHAR(64),
    authorization_id VARCHAR(64) REFERENCES pre_authorizations(id),
    claim_type VARCHAR(32) NOT NULL DEFAULT 'INSTITUTIONAL',
    status VARCHAR(32) NOT NULL DEFAULT 'DRAFT',
    total_amount_in_minor_units BIGINT NOT NULL,
    approved_amount_in_minor_units BIGINT,
    payer_paid_amount_in_minor_units BIGINT,
    patient_responsibility_in_minor_units BIGINT,
    currency VARCHAR(3) NOT NULL DEFAULT 'INR',
    provider_claim_reference VARCHAR(255),
    idempotency_key VARCHAR(255) UNIQUE,
    submission_timestamp TIMESTAMPTZ,
    adjudication_timestamp TIMESTAMPTZ,
    denial_reason TEXT,
    denial_code VARCHAR(64),
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```
