# Phase 27: Database Dependencies & Contract Handoff

## 1. Overview for Database Team

Backend Phase 27 introduces persistent administrative concepts including:
- Operational Incidents (`operational_incidents`)
- Administrative Audit Events (`audit_events` integration)
- Specialized Administrative Role Mappings

In accordance with team responsibilities:
- **Backend Team**: Owns services, validation, security enforcement, and consumed data models.
- **Database Team**: Owns schema creation, tables, migrations, constraints, indexes, triggers, and SQL optimizations.

The backend repository `IncidentRepository` provides a thread-safe in-memory implementation that conforms strictly to the expected schema contract below.

---

## 2. Table: `operational_incidents`

Stores operational incidents, outages, degraded dependencies, and administrative triages.

### Proposed Schema

```sql
CREATE TYPE incident_status_enum AS ENUM (
    'OPEN',
    'INVESTIGATING',
    'MITIGATED',
    'RESOLVED',
    'CLOSED'
);

CREATE TYPE incident_severity_enum AS ENUM (
    'CRITICAL',
    'HIGH',
    'MEDIUM',
    'LOW'
);

CREATE TYPE incident_category_enum AS ENUM (
    'API_OUTAGE',
    'DATABASE_FAILURE',
    'QUEUE_FAILURE',
    'OCR_FAILURE',
    'MEDICATION_PROVIDER_OUTAGE',
    'AI_PROVIDER_OUTAGE',
    'INTEROPERABILITY_FAILURE',
    'SECURITY_INCIDENT',
    'DATA_QUALITY_INCIDENT',
    'PERFORMANCE_INCIDENT',
    'DEPLOYMENT_INCIDENT',
    'OTHER'
);

CREATE TABLE operational_incidents (
    id VARCHAR(64) PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    description TEXT NOT NULL,
    category incident_category_enum NOT NULL DEFAULT 'OTHER',
    severity incident_severity_enum NOT NULL DEFAULT 'MEDIUM',
    status incident_status_enum NOT NULL DEFAULT 'OPEN',
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    acknowledged_at TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ,
    closed_at TIMESTAMPTZ,
    owner VARCHAR(64),
    correlation_id VARCHAR(128),
    resolution_summary TEXT,
    created_by VARCHAR(64) NOT NULL,
    updated_by VARCHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX idx_incidents_status ON operational_incidents(status);
CREATE INDEX idx_incidents_severity ON operational_incidents(severity);
CREATE INDEX idx_incidents_category ON operational_incidents(category);
CREATE INDEX idx_incidents_created_at ON operational_incidents(created_at DESC);
```

### Constraints & Lifecycle Triggers
1. **Transition Rules**:
   - `OPEN` -> `INVESTIGATING` sets `acknowledged_at`.
   - `INVESTIGATING` -> `RESOLVED` / `CLOSED` requires `resolution_summary IS NOT NULL`.
   - `CLOSED` records are immutable (modifications rejected).
2. **Audit Trigger**: Any status transition emits a row to `audit_events`.

---

## 3. Administrative Audit Events Contract

Administrative events emit to the existing append-only `audit_events` table (Phase 15):
- `ADMIN_SYSTEM_STATUS_VIEWED`
- `ADMIN_JOB_VIEWED`
- `ADMIN_JOB_RETRIED`
- `ADMIN_JOB_CANCELLED`
- `ADMIN_INTEGRATION_VIEWED`
- `ADMIN_INTEGRATION_TESTED`
- `ADMIN_INCIDENT_CREATED`
- `ADMIN_INCIDENT_UPDATED`
- `ADMIN_INCIDENT_RESOLVED`
- `ADMIN_AUDIT_VIEWED`
- `ADMIN_SECURITY_EVENT_VIEWED`
- `ADMIN_DATA_QUALITY_VIEWED`
- `ADMIN_SUPPORT_LOOKUP`
- `ADMIN_CONFIGURATION_VIEWED`
- `ADMIN_CONFIGURATION_CHANGED`

**Append-Only Invariant**: Normal admin APIs have NO delete or update routes for audit records.
