# HealthSetu — Phase 45 Database Contract & Schema Handover

## 1. Ownership Boundary
- **DB Teammate Owns**: Tables, migrations, indexes, constraints, foreign keys, partitions, and storage optimizations.
- **Backend Teammate Owns**: Domain services, validation, reconciliation logic, ingestion pipelines, API endpoints, and security checks.

---

## 2. Required Entities & Schema Specifications

### 2.1 Table: `external_sources`
Tracks registered external partner organizations, facilities, and interoperability endpoints.

```sql
CREATE TABLE external_sources (
    source_id VARCHAR(64) PRIMARY KEY,
    source_name VARCHAR(255) NOT NULL,
    source_type VARCHAR(64) NOT NULL, -- 'HOSPITAL', 'CLINIC', 'LABORATORY', 'HEALTHCARE_NETWORK', 'INTEROPERABILITY_PROVIDER', etc.
    trust_state VARCHAR(32) NOT NULL DEFAULT 'REGISTERED', -- 'REGISTERED', 'AUTHORIZED', 'ACTIVE', 'DEGRADED', 'SUSPENDED', 'REVOKED'
    organization_id VARCHAR(64) NOT NULL,
    facility_id VARCHAR(64),
    api_key_hash VARCHAR(128),
    allowed_resources JSONB NOT NULL DEFAULT '[]'::jsonb, -- ['Patient', 'Observation', 'MedicationRequest', etc.]
    metadata JSONB DEFAULT '{}'::jsonb,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_external_sources_org ON external_sources(organization_id);
CREATE INDEX idx_external_sources_trust ON external_sources(trust_state);
```

### 2.2 Table: `clinical_ingestions`
Master log of external data ingestion instances and processing lifecycles.

```sql
CREATE TABLE clinical_ingestions (
    ingestion_id UUID PRIMARY KEY,
    idempotency_key VARCHAR(128) UNIQUE,
    source_id VARCHAR(64) NOT NULL REFERENCES external_sources(source_id),
    resource_type VARCHAR(64) NOT NULL,
    external_resource_id VARCHAR(128) NOT NULL,
    source_version VARCHAR(32),
    patient_id VARCHAR(64), -- Nullable initially until identity resolved
    status VARCHAR(32) NOT NULL DEFAULT 'RECEIVED', -- 'RECEIVED', 'ACCEPTED', 'PROCESSING', 'MAPPED', 'IDENTITY_PENDING', 'RECONCILIATION_PENDING', 'REVIEW_REQUIRED', 'INTEGRATED', 'REJECTED', 'QUARANTINED', 'CANCELLED', 'FAILED'
    data_trust_status VARCHAR(32) NOT NULL DEFAULT 'UNVERIFIED', -- 'IMPORTED', 'UNVERIFIED', 'PENDING_REVIEW', 'VERIFIED', 'REJECTED', 'SUPERSEDED', 'CONFLICTED'
    identity_outcome VARCHAR(32), -- 'MATCH_CONFIRMED', 'MATCH_CANDIDATE', 'MULTIPLE_MATCHES', 'NO_MATCH', 'CONFLICT', 'REVIEW_REQUIRED'
    reconciliation_id VARCHAR(64),
    raw_payload_hash VARCHAR(64) NOT NULL, -- SHA-256
    mapped_data JSONB,
    quarantine_reason TEXT,
    failure_reason TEXT,
    retry_count INT NOT NULL DEFAULT 0,
    is_retryable BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_clinical_ingestions_patient ON clinical_ingestions(patient_id);
CREATE INDEX idx_clinical_ingestions_ext_res ON clinical_ingestions(source_id, external_resource_id);
CREATE INDEX idx_clinical_ingestions_status ON clinical_ingestions(status);
CREATE INDEX idx_clinical_ingestions_trust ON clinical_ingestions(data_trust_status);
```

### 2.3 Table: `ingestion_provenance`
Immutable record of data origins, transformation pipelines, and cryptographic signatures.

```sql
CREATE TABLE ingestion_provenance (
    provenance_id UUID PRIMARY KEY,
    ingestion_id UUID NOT NULL REFERENCES clinical_ingestions(ingestion_id) ON DELETE CASCADE,
    source_organization VARCHAR(128) NOT NULL,
    source_facility VARCHAR(128),
    source_system VARCHAR(128),
    source_resource_id VARCHAR(128) NOT NULL,
    source_version VARCHAR(32),
    source_timestamp TIMESTAMPTZ,
    received_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    raw_payload_hash VARCHAR(64) NOT NULL,
    mapper_version VARCHAR(32) NOT NULL,
    transformations JSONB NOT NULL DEFAULT '[]'::jsonb,
    verification_state VARCHAR(32) NOT NULL DEFAULT 'UNVERIFIED',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_ingestion_provenance_ingestion ON ingestion_provenance(ingestion_id);
CREATE INDEX idx_ingestion_provenance_source_res ON ingestion_provenance(source_resource_id);
```

### 2.4 Table: `webhook_delivery_logs`
Replay-protection ledger and audit record for provider webhook invocations.

```sql
CREATE TABLE webhook_delivery_logs (
    event_id VARCHAR(128) PRIMARY KEY,
    provider VARCHAR(64) NOT NULL,
    timestamp BIGINT NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    signature VARCHAR(256),
    payload_hash VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL
);

CREATE INDEX idx_webhook_logs_provider ON webhook_delivery_logs(provider);
CREATE INDEX idx_webhook_logs_received ON webhook_delivery_logs(received_at);
```

---

## 3. Database Constraints & Foreign Key Rules
1. `clinical_ingestions.idempotency_key` must be strictly unique to prevent concurrent double-processing of provider payloads.
2. `clinical_ingestions.data_trust_status` defaults to `UNVERIFIED` and cannot be modified to `VERIFIED` by ingestion services alone.
3. No foreign key cascading deletes on patient clinical records; supersession or deletion notices from external systems must create historical audit entries rather than hard deletes.
