# HealthSetu — Phase 44: Database Team Dependencies

## Database Schema Contract for Clinical Data Sharing & Controlled Exchange

The database team owns all migrations, tables, constraints, relationships, and indexing.
The backend layer relies on the following schema structures:

---

### 1. `sharing_requests` Table

```sql
CREATE TABLE IF NOT EXISTS sharing_requests (
    id VARCHAR(64) PRIMARY KEY,
    patient_id VARCHAR(64) NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    requester_id VARCHAR(64) NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    requester_role VARCHAR(32) NOT NULL,
    sharing_type VARCHAR(64) NOT NULL,
    recipient_id VARCHAR(64) NOT NULL,
    recipient_type VARCHAR(64) NOT NULL,
    destination_url VARCHAR(512),
    resource_scopes JSONB NOT NULL,
    action VARCHAR(32) NOT NULL DEFAULT 'SHARE',
    purpose VARCHAR(128) NOT NULL DEFAULT 'CARE_DELIVERY',
    delivery_method VARCHAR(64) NOT NULL DEFAULT 'DIRECT_API',
    requested_format VARCHAR(32) NOT NULL DEFAULT 'JSON',
    status VARCHAR(32) NOT NULL DEFAULT 'REQUESTED',
    consent_id VARCHAR(64) REFERENCES consents(id) ON DELETE SET NULL,
    idempotency_key VARCHAR(128) UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    approved_at TIMESTAMPTZ,
    executed_at TIMESTAMPTZ,
    delivered_at TIMESTAMPTZ,
    denial_reason TEXT,
    delivery_status VARCHAR(64),
    provider_reference VARCHAR(128),
    retry_count INTEGER NOT NULL DEFAULT 0,
    provenance_id VARCHAR(64),
    history JSONB DEFAULT '[]'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_sharing_requests_patient_status ON sharing_requests(patient_id, status);
CREATE INDEX IF NOT EXISTS idx_sharing_requests_requester_status ON sharing_requests(requester_id, status);
CREATE INDEX IF NOT EXISTS idx_sharing_requests_expires_at ON sharing_requests(expires_at, status);
```

---

### 2. `clinical_exports` Table

```sql
CREATE TABLE IF NOT EXISTS clinical_exports (
    id VARCHAR(64) PRIMARY KEY,
    patient_id VARCHAR(64) NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    requester_id VARCHAR(64) NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    requester_role VARCHAR(32) NOT NULL,
    export_scope VARCHAR(64) NOT NULL,
    format VARCHAR(32) NOT NULL DEFAULT 'JSON',
    purpose VARCHAR(128) NOT NULL DEFAULT 'CARE_CONTINUITY',
    status VARCHAR(32) NOT NULL DEFAULT 'REQUESTED',
    consent_id VARCHAR(64) REFERENCES consents(id) ON DELETE SET NULL,
    idempotency_key VARCHAR(128) UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    download_url VARCHAR(512),
    payload JSONB,
    file_size_bytes INTEGER,
    error_message TEXT,
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_clinical_exports_patient_id ON clinical_exports(patient_id);
CREATE INDEX IF NOT EXISTS idx_clinical_exports_expires_at ON clinical_exports(expires_at, status);
```

---

### 3. `sharing_provenance` Table

```sql
CREATE TABLE IF NOT EXISTS sharing_provenance (
    provenance_id VARCHAR(64) PRIMARY KEY,
    share_or_export_id VARCHAR(64) NOT NULL,
    source_system VARCHAR(64) NOT NULL DEFAULT 'HealthSetu',
    patient_id VARCHAR(64) NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    requester_id VARCHAR(64) NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    recipient_id VARCHAR(64) NOT NULL,
    destination VARCHAR(512),
    resource_scopes JSONB NOT NULL,
    action VARCHAR(32) NOT NULL,
    format VARCHAR(32) NOT NULL,
    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    payload_hash VARCHAR(128),
    is_external_inbound BOOLEAN NOT NULL DEFAULT FALSE,
    is_verified_clinical_truth BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_sharing_provenance_share_id ON sharing_provenance(share_or_export_id);
```
