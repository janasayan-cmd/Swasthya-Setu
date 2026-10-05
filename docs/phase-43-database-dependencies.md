# Phase 43 — Database Dependencies & Schema Contract

## 1. Database Teammate Ownership

As defined in Section 4 of the Phase 43 Specification:
- The **DB Teammate** owns:
  - Table definitions, columns, primary and foreign keys.
  - Data types, constraints (e.g. check constraints, uniqueness).
  - Migration scripts (Alembic / PostgreSQL DDL).
  - Indexes and database-level optimization.
- The **Backend Layer** owns:
  - In-memory repository contracts and fallbacks.
  - Domain models, Pydantic schemas, and validation.
  - Centralized access evaluation engine and service logic.
  - Endpoints, workers, and background re-evaluation.

---

## 2. Recommended Relational Schema

### Table: `consents`
Extends Phase 3 `consents` table:
```sql
CREATE TABLE IF NOT EXISTS consents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE RESTRICT,
    grantee_id VARCHAR(255) NOT NULL,
    recipient_type VARCHAR(50) NOT NULL DEFAULT 'CLINICIAN',
    purpose VARCHAR(100) NOT NULL,
    scope VARCHAR(100) NOT NULL,
    resource_scopes JSONB NOT NULL DEFAULT '[]'::jsonb,
    action_scopes JSONB NOT NULL DEFAULT '["READ"]'::jsonb,
    status VARCHAR(50) NOT NULL DEFAULT 'ACTIVE',
    version INT NOT NULL DEFAULT 1,
    granted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    effective_from TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ NULL,
    withdrawal_reason TEXT NULL,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    history JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_consents_patient_status ON consents(patient_id, status);
CREATE INDEX idx_consents_grantee_patient ON consents(grantee_id, patient_id);
CREATE INDEX idx_consents_expires_at ON consents(expires_at) WHERE status = 'ACTIVE';
```

### Table: `consent_requests`
```sql
CREATE TABLE IF NOT EXISTS consent_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE RESTRICT,
    requester_id VARCHAR(255) NOT NULL,
    requester_role VARCHAR(50) NOT NULL,
    grantee_id VARCHAR(255) NOT NULL,
    recipient_type VARCHAR(50) NOT NULL DEFAULT 'CLINICIAN',
    purpose VARCHAR(100) NOT NULL,
    resource_scopes JSONB NOT NULL DEFAULT '[]'::jsonb,
    action_scopes JSONB NOT NULL DEFAULT '["READ"]'::jsonb,
    requested_duration_days INT NOT NULL DEFAULT 90,
    status VARCHAR(50) NOT NULL DEFAULT 'REQUESTED',
    notes TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    decided_at TIMESTAMPTZ NULL,
    decided_by VARCHAR(255) NULL,
    decision_reason TEXT NULL
);

CREATE INDEX idx_consent_requests_patient ON consent_requests(patient_id, status);
CREATE INDEX idx_consent_requests_requester ON consent_requests(requester_id, status);
```

---

## 3. Data Integrity & Retention Rules

1. **No Silent Cascade Deletion:**
   - Consents MUST NOT be deleted via `CASCADE` when a patient record is archived.
   - Deletions are governed by Phase 24 legal hold and retention policies.
2. **Immutability of Version History:**
   - When a consent is renewed or superseded, the existing record or audit trail must preserve the original timestamps, scopes, and grantor identity.
