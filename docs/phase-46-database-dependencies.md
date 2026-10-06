# HealthSetu — Phase 46: Database Dependencies & Shared Architecture Contract

## 1. Division of Ownership

### DB Teammate Owns:
- Database schema, tables, relationships, indexes, constraints, enums, migrations
- Version columns, historical record tables/structures
- Temporal columns (`event_time`, `recorded_time`, `effective_time`, `supersession_time`, etc.)
- Database-level concurrency triggers and check constraints
- History indexes (e.g. `(resource_type, resource_id, version_number)`)
- Performance optimization for temporal range queries

### Backend Teammate Owns:
- Version-aware domain services and APIs
- Optimistic concurrency control (`expected_version` validation)
- Historical state retrieval and pagination
- Cryptographic provenance and Phase 26 reconciliation coordination
- Audit trail logging (Phase 15/46 `AuditEventType`)
- AI boundary enforcement and clinical safety regression tests

---

## 2. Table Contracts & Schemas

### A. Current Resource Table (`clinical_records`)
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PRIMARY KEY | Canonical entity ID |
| `resource_type` | VARCHAR(64) | NOT NULL | Resource discriminator e.g. medication, allergy |
| `patient_id` | UUID | NOT NULL | Foreign key to `patients(id)` |
| `current_version_number` | INTEGER | NOT NULL, DEFAULT 1 | Current active version number |
| `is_deleted` | BOOLEAN | NOT NULL, DEFAULT FALSE | Logical soft-deletion flag |
| `created_at` | TIMESTAMPTZ | NOT NULL | Record creation timestamp |
| `updated_at` | TIMESTAMPTZ | NOT NULL | Last modification timestamp |

### B. Version History Table (`clinical_record_versions`)
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | VARCHAR(64) | PRIMARY KEY | Unique version identifier (`ver-...`) |
| `resource_id` | UUID | NOT NULL | Reference to `clinical_records(id)` |
| `resource_type` | VARCHAR(64) | NOT NULL | Domain resource type |
| `patient_id` | UUID | NOT NULL | Foreign key to `patients(id)` |
| `version_number` | INTEGER | NOT NULL | Monotonically increasing revision counter |
| `previous_version_number` | INTEGER | NULL | Predecessor version counter |
| `version_type` | VARCHAR(32) | NOT NULL | Enum: CREATED, UPDATED, CORRECTED, SUPERSEDED, RESTORED |
| `is_current` | BOOLEAN | NOT NULL, DEFAULT FALSE | True only for the active current version |
| `state_data` | JSONB | NOT NULL | Immutable snapshot of resource fields |
| `event_time` | TIMESTAMPTZ | NULL | Clinical event occurrence time |
| `recorded_time` | TIMESTAMPTZ | NOT NULL | Intake timestamp |
| `effective_time` | TIMESTAMPTZ | NOT NULL | Applicable start time |
| `supersession_time` | TIMESTAMPTZ | NULL | Replacement timestamp |
| `actor_id` | VARCHAR(64) | NOT NULL | User or provider applying change |
| `actor_role` | VARCHAR(64) | NOT NULL | Role of actor |
| `change_reason` | TEXT | NOT NULL | Mandatory clinical justification |
| `provenance_id` | VARCHAR(64) | NULL | Reference to provenance audit |
| `created_at` | TIMESTAMPTZ | NOT NULL | Audit insertion timestamp |

### C. Unique Constraints & Indexes
```sql
-- Ensure version numbers are strictly unique per resource
CREATE UNIQUE INDEX uq_resource_version 
ON clinical_record_versions(resource_type, resource_id, version_number);

-- Ensure at most ONE active current version per resource
CREATE UNIQUE INDEX uq_resource_current_version 
ON clinical_record_versions(resource_type, resource_id) 
WHERE is_current = TRUE;

-- High-performance chronological query index
CREATE INDEX idx_resource_history 
ON clinical_record_versions(resource_type, resource_id, version_number DESC);
```
