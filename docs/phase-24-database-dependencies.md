# HealthSetu — Phase 24 Database Dependencies & Schema Coordination

## 1. Team Boundary & Governance

- **Backend Team**: Owns services, policies, retention evaluation logic, export assembly, and repository interfaces. Does NOT create competing database schemas, ad-hoc tables, or direct production migrations.
- **Database Team**: Owns production tables, indexes, constraints, partitions, foreign keys, and migration execution.

---

## 2. Recommended Database Schema Additions for Database Team

The Database Team is requested to deliver the following tables and columns in upcoming schema migrations:

### A. Retention Policies Table (`retention_policies`)
```sql
CREATE TABLE IF NOT EXISTS retention_policies (
    policy_id VARCHAR(64) PRIMARY KEY,
    data_type VARCHAR(64) NOT NULL UNIQUE,
    purpose VARCHAR(64),
    retention_period_days INTEGER,
    retention_start_event VARCHAR(64) NOT NULL DEFAULT 'creation',
    archive_behavior VARCHAR(32) NOT NULL DEFAULT 'ARCHIVE',
    deletion_behavior VARCHAR(32) NOT NULL DEFAULT 'SOFT_DELETE',
    description TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### B. Legal & Preservation Holds Table (`legal_holds`)
```sql
CREATE TABLE IF NOT EXISTS legal_holds (
    hold_id VARCHAR(64) PRIMARY KEY,
    resource_type VARCHAR(64) NOT NULL,
    resource_id VARCHAR(64) NOT NULL,
    patient_id VARCHAR(64) REFERENCES patients(id) ON DELETE RESTRICT,
    hold_type VARCHAR(32) NOT NULL,
    reason TEXT NOT NULL,
    placed_by VARCHAR(64) NOT NULL,
    placed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    expires_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_legal_holds_target ON legal_holds(resource_id, is_active);
```

### C. Patient Data Exports Table (`patient_data_exports`)
```sql
CREATE TABLE IF NOT EXISTS patient_data_exports (
    export_id VARCHAR(64) PRIMARY KEY,
    patient_id VARCHAR(64) NOT NULL REFERENCES patients(id) ON DELETE RESTRICT,
    requester_id VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'PENDING',
    scopes JSONB NOT NULL DEFAULT '[]',
    format VARCHAR(16) NOT NULL DEFAULT 'JSON',
    storage_key VARCHAR(255),
    file_size_bytes BIGINT,
    checksum_sha256 VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    download_count INTEGER NOT NULL DEFAULT 0,
    error_message TEXT
);
CREATE INDEX IF NOT EXISTS idx_exports_patient_exp ON patient_data_exports(patient_id, expires_at);
```

### D. Data Transformation Lineage Table (`data_lineage`)
```sql
CREATE TABLE IF NOT EXISTS data_lineage (
    lineage_id VARCHAR(64) PRIMARY KEY,
    patient_id VARCHAR(64) REFERENCES patients(id) ON DELETE SET NULL,
    resource_type VARCHAR(64) NOT NULL,
    resource_id VARCHAR(64) NOT NULL,
    source_type VARCHAR(64) NOT NULL,
    transformation_type VARCHAR(64),
    verifier_id VARCHAR(64),
    stage VARCHAR(32) NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_lineage_resource ON data_lineage(resource_id);
```

### E. Entity Lifecycle Columns
The Database Team should add to `patients`, `medical_documents`, `prescriptions`, and `care_plans`:
- `lifecycle_status VARCHAR(32) DEFAULT 'ACTIVE'`
- `archived_at TIMESTAMPTZ NULL`
- `deleted_at TIMESTAMPTZ NULL`
