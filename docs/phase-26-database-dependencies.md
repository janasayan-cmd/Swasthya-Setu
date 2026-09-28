# Phase 26: Database Dependencies & Contract Alignment

## 1. Architecture Alignment
Backend implementation strictly avoids creating competing database tables or executing uncoordinated migrations.
Until the Database Team provisions migration scripts for persistent tables, the backend operates via thread-safe, in-memory repository abstractions (`DataQualityRepository`, `ReconciliationRepository`) that exactly mirror the intended database contract.

## 2. Expected Database Contract

### Table 1: `data_quality_findings`
- `id`: VARCHAR(64) PRIMARY KEY
- `patient_id`: VARCHAR(64) NOT NULL REFERENCES patients(id)
- `resource_type`: VARCHAR(64) NOT NULL
- `resource_id`: VARCHAR(64) NOT NULL
- `finding_type`: VARCHAR(64) NOT NULL (Enum matching DataQualityFindingType)
- `severity`: VARCHAR(32) NOT NULL (Enum matching DataQualitySeverity)
- `status`: VARCHAR(32) NOT NULL (Enum matching DataQualityFindingStatus)
- `description`: TEXT NOT NULL
- `rule_id`: VARCHAR(64) NOT NULL
- `rule_version`: VARCHAR(32) NOT NULL
- `source_references`: JSONB DEFAULT '[]'
- `conflicting_references`: JSONB DEFAULT '[]'
- `context_data`: JSONB DEFAULT '{}'
- `detected_at`: TIMESTAMPTZ NOT NULL
- `reviewer_notes`: TEXT NULL
- `resolved_at`: TIMESTAMPTZ NULL
- `resolved_by`: VARCHAR(64) NULL REFERENCES users(id)
- `resolution_action`: VARCHAR(64) NULL
- `resolution_notes`: TEXT NULL
- `version`: INTEGER DEFAULT 1 NOT NULL

### Table 2: `clinical_reconciliations`
- `id`: VARCHAR(64) PRIMARY KEY
- `patient_id`: VARCHAR(64) NOT NULL REFERENCES patients(id)
- `scope`: VARCHAR(32) NOT NULL (Enum matching ReconciliationScope)
- `status`: VARCHAR(32) NOT NULL (Enum matching ReconciliationStatus)
- `sources`: JSONB DEFAULT '[]'
- `conflicts`: JSONB DEFAULT '[]'
- `summary`: TEXT NOT NULL
- `created_at`: TIMESTAMPTZ NOT NULL
- `resolved_at`: TIMESTAMPTZ NULL
- `resolved_by`: VARCHAR(64) NULL REFERENCES users(id)
- `resolution_action`: VARCHAR(64) NULL
- `resolution_notes`: TEXT NULL
- `version`: INTEGER DEFAULT 1 NOT NULL
