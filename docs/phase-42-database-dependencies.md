# Phase 42: Database Dependencies & Contracts

> **OWNERSHIP NOTICE**:
> The Database Teammate owns all database schema, tables, migrations, constraints, foreign keys, and indexes.
> The Backend Teammate consumes these contracts through `app/repositories/patient_action_repository.py` and `app/repositories/questionnaire_repository.py`.

---

## 1. Required Database Entities

### 1. `action_definitions`
Reusable catalog of patient-facing operational actions.

```sql
CREATE TABLE action_definitions (
    id VARCHAR(64) PRIMARY KEY,
    code VARCHAR(64) NOT NULL UNIQUE,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    action_type VARCHAR(64) NOT NULL,
    default_expiration_hours INT NOT NULL DEFAULT 72,
    requires_consent BOOLEAN NOT NULL DEFAULT FALSE,
    required_consent_type VARCHAR(64),
    questionnaire_id VARCHAR(64),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_action_def_code ON action_definitions(code);
CREATE INDEX idx_action_def_active ON action_definitions(is_active);
```

---

### 2. `patient_actions`
Individual action instances assigned to a specific patient.

```sql
CREATE TABLE patient_actions (
    id VARCHAR(64) PRIMARY KEY,
    definition_id VARCHAR(64) REFERENCES action_definitions(id) ON DELETE SET NULL,
    patient_id VARCHAR(64) NOT NULL,
    organization_id VARCHAR(64),
    facility_id VARCHAR(64),
    care_team_id VARCHAR(64),
    encounter_id VARCHAR(64),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    action_type VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'AVAILABLE',
    priority VARCHAR(16) NOT NULL DEFAULT 'NORMAL',
    target_resource_type VARCHAR(64),
    target_resource_id VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    available_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    started_at TIMESTAMPTZ,
    submitted_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    cancelled_at TIMESTAMPTZ,
    cancellation_reason TEXT,
    created_by VARCHAR(64),
    is_refusal BOOLEAN NOT NULL DEFAULT FALSE,
    refusal_reason TEXT,
    reminder_count INT NOT NULL DEFAULT 0,
    last_reminder_at TIMESTAMPTZ,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX idx_patient_actions_patient_id ON patient_actions(patient_id);
CREATE INDEX idx_patient_actions_status ON patient_actions(status);
CREATE INDEX idx_patient_actions_expires_at ON patient_actions(expires_at) WHERE status IN ('AVAILABLE', 'STARTED');
CREATE INDEX idx_patient_actions_org_fac ON patient_actions(organization_id, facility_id);
```

---

### 3. `patient_action_history`
Chronological state transition log for audits and provenance.

```sql
CREATE TABLE patient_action_history (
    id VARCHAR(64) PRIMARY KEY,
    action_id VARCHAR(64) NOT NULL REFERENCES patient_actions(id) ON DELETE CASCADE,
    from_status VARCHAR(32),
    to_status VARCHAR(32) NOT NULL,
    actor_id VARCHAR(64),
    actor_role VARCHAR(64),
    reason TEXT,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_action_history_action_id ON patient_action_history(action_id);
```

---

### 4. `patient_submissions`
Submissions and corrections submitted by the patient.

```sql
CREATE TABLE patient_submissions (
    id VARCHAR(64) PRIMARY KEY,
    action_id VARCHAR(64) NOT NULL REFERENCES patient_actions(id) ON DELETE CASCADE,
    patient_id VARCHAR(64) NOT NULL,
    submission_version INT NOT NULL DEFAULT 1,
    submission_type VARCHAR(64) NOT NULL,
    responses JSONB NOT NULL DEFAULT '{}'::jsonb,
    document_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    notes TEXT,
    idempotency_key VARCHAR(128) UNIQUE,
    is_correction BOOLEAN NOT NULL DEFAULT FALSE,
    correction_reason TEXT,
    prior_submission_id VARCHAR(64) REFERENCES patient_submissions(id),
    provenance JSONB NOT NULL,
    clinical_verification_status VARCHAR(64) NOT NULL DEFAULT 'PATIENT_REPORTED_UNVERIFIED',
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_submissions_action ON patient_submissions(action_id);
CREATE INDEX idx_submissions_patient ON patient_submissions(patient_id);
CREATE UNIQUE INDEX idx_submissions_idempotency ON patient_submissions(idempotency_key) WHERE idempotency_key IS NOT NULL;
```

---

### 5. `questionnaire_definitions` & `questionnaire_responses`
Structured templates and responses.

```sql
CREATE TABLE questionnaire_definitions (
    id VARCHAR(64) PRIMARY KEY,
    code VARCHAR(64) NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    version VARCHAR(32) NOT NULL DEFAULT '1.0.0',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    questions JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_questionnaire_code_version UNIQUE (code, version)
);

CREATE TABLE questionnaire_responses (
    id VARCHAR(64) PRIMARY KEY,
    questionnaire_id VARCHAR(64) NOT NULL REFERENCES questionnaire_definitions(id),
    questionnaire_version VARCHAR(32) NOT NULL,
    action_id VARCHAR(64) NOT NULL REFERENCES patient_actions(id) ON DELETE CASCADE,
    patient_id VARCHAR(64) NOT NULL,
    answers JSONB NOT NULL DEFAULT '[]'::jsonb,
    submitted_by VARCHAR(64),
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_qres_action ON questionnaire_responses(action_id);
CREATE INDEX idx_qres_patient ON questionnaire_responses(patient_id);
```

---

### 6. `patient_action_documents`
Links to documents securely stored in Phase 5.

```sql
CREATE TABLE patient_action_documents (
    id VARCHAR(64) PRIMARY KEY,
    action_id VARCHAR(64) NOT NULL REFERENCES patient_actions(id) ON DELETE CASCADE,
    patient_id VARCHAR(64) NOT NULL,
    document_id VARCHAR(64) NOT NULL,
    document_type VARCHAR(64),
    description TEXT,
    submitted_by VARCHAR(64) NOT NULL,
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_pact_doc_action ON patient_action_documents(action_id);
CREATE INDEX idx_pact_doc_patient ON patient_action_documents(patient_id);
```
