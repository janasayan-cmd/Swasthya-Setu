# Phase 22 — Database Performance & Schema Dependencies (Database Team Handover)

## 1. Required Table Contracts (DB Team Owned)

The Backend Team has implemented repository adapters for the following required PostgreSQL table schemas:

### A. `async_jobs`
```sql
CREATE TABLE IF NOT EXISTS async_jobs (
    id VARCHAR(36) PRIMARY KEY,
    job_type VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'CREATED',
    patient_id VARCHAR(36) REFERENCES patients(id) ON DELETE SET NULL,
    resource_type VARCHAR(64) NOT NULL,
    resource_id VARCHAR(128) NOT NULL,
    operation_type VARCHAR(64) NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    result JSONB DEFAULT NULL,
    initiating_user_id VARCHAR(36) REFERENCES users(id) ON DELETE SET NULL,
    idempotency_key VARCHAR(128) UNIQUE,
    correlation_id VARCHAR(128),
    attempt INT NOT NULL DEFAULT 0,
    max_retries INT NOT NULL DEFAULT 3,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    queued_at TIMESTAMPTZ,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    failed_at TIMESTAMPTZ,
    error_message TEXT,
    error_category VARCHAR(64)
);

CREATE INDEX IF NOT EXISTS idx_async_jobs_patient_id ON async_jobs(patient_id);
CREATE INDEX IF NOT EXISTS idx_async_jobs_status_created ON async_jobs(status, created_at);
CREATE INDEX IF NOT EXISTS idx_async_jobs_idempotency_key ON async_jobs(idempotency_key);
```

### B. `async_workflows`
```sql
CREATE TABLE IF NOT EXISTS async_workflows (
    id VARCHAR(36) PRIMARY KEY,
    workflow_type VARCHAR(64) NOT NULL,
    patient_id VARCHAR(36) REFERENCES patients(id) ON DELETE SET NULL,
    initiating_user_id VARCHAR(36) REFERENCES users(id) ON DELETE SET NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'PENDING',
    current_step_index INT NOT NULL DEFAULT 0,
    steps JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_async_workflows_patient_id ON async_workflows(patient_id);
CREATE INDEX IF NOT EXISTS idx_async_workflows_status ON async_workflows(status);
```

### C. `event_outbox`
```sql
CREATE TABLE IF NOT EXISTS event_outbox (
    id VARCHAR(36) PRIMARY KEY,
    event_id VARCHAR(36) NOT NULL UNIQUE,
    event_type VARCHAR(64) NOT NULL,
    payload JSONB NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'PENDING',
    attempts INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    published_at TIMESTAMPTZ,
    last_error TEXT
);

CREATE INDEX IF NOT EXISTS idx_event_outbox_pending ON event_outbox(status, created_at) WHERE status = 'PENDING';
```

### D. `consumed_events`
```sql
CREATE TABLE IF NOT EXISTS consumed_events (
    event_id VARCHAR(36) NOT NULL,
    consumer_name VARCHAR(128) NOT NULL,
    consumed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (event_id, consumer_name)
);
```

### E. `idempotency_records`
```sql
CREATE TABLE IF NOT EXISTS idempotency_records (
    key VARCHAR(128) PRIMARY KEY,
    operation_type VARCHAR(64) NOT NULL,
    resource_id VARCHAR(128) NOT NULL,
    state VARCHAR(32) NOT NULL DEFAULT 'PROCESSING',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    result_payload JSONB DEFAULT NULL,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_idempotency_expires_at ON idempotency_records(expires_at);
```

## 2. Retention & Housekeeping Recommendations

- `event_outbox`: Records with `status = 'PUBLISHED'` and `created_at < NOW() - INTERVAL '7 days'` can be purged via pg_cron or archived.
- `idempotency_records`: Expired keys (`expires_at < NOW()`) should be periodically deleted.
