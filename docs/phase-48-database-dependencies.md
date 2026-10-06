# Phase 48: Database Dependencies & Schema Contract

## Handoff Document for Database Teammate

### 1. Database Ownership Principle
As established in the Phase 48 TRD, the database teammate owns all database schema, tables, relationships, indexes, constraints, enums, migrations, and database-level optimization. The backend teammate consumes the agreed schema and does NOT invent competing persistence subsystems.

### 2. Required Entities & Tables

#### 1. `safety_checks`
Tracks every evaluation executed by the central safety gate:
- `id`: VARCHAR(64) PRIMARY KEY (e.g. `chk-...`)
- `operation`: VARCHAR(128) NOT NULL (e.g. `medication:apply`)
- `allowed`: BOOLEAN NOT NULL
- `status`: VARCHAR(32) NOT NULL (e.g. `ALLOWED`, `BLOCKED`, `REVIEW_REQUIRED`, `INSUFFICIENT_INFORMATION`, `CONFLICTED`, `STALE`, `EXPIRED`, `UNAVAILABLE`)
- `policy_type`: VARCHAR(64) NOT NULL
- `policy_version`: VARCHAR(32) NOT NULL
- `reason_codes`: JSONB / TEXT[] DEFAULT '[]'
- `warnings`: JSONB / TEXT[] DEFAULT '[]'
- `required_actions`: JSONB / TEXT[] DEFAULT '[]'
- `decision_id`: VARCHAR(64) REFERENCES `decisions(id)` ON DELETE SET NULL
- `patient_id`: VARCHAR(64) REFERENCES `patients(id)` ON DELETE SET NULL
- `resource_type`: VARCHAR(64)
- `resource_id`: VARCHAR(64)
- `actor_id`: VARCHAR(64)
- `actor_role`: VARCHAR(32)
- `details`: JSONB DEFAULT '{}'
- `timestamp`: TIMESTAMPTZ NOT NULL DEFAULT NOW()

Indexes:
- `CREATE INDEX idx_safety_checks_decision_id ON safety_checks(decision_id);`
- `CREATE INDEX idx_safety_checks_resource ON safety_checks(resource_type, resource_id);`
- `CREATE INDEX idx_safety_checks_patient_id ON safety_checks(patient_id);`
- `CREATE INDEX idx_safety_checks_timestamp ON safety_checks(timestamp DESC);`

#### 2. `safety_policies`
Versioned registry of clinical safety policies:
- `policy_id`: VARCHAR(64) PRIMARY KEY
- `policy_type`: VARCHAR(64) NOT NULL
- `policy_version`: VARCHAR(32) NOT NULL
- `name`: VARCHAR(128) NOT NULL
- `description`: TEXT
- `mandatory_controls`: JSONB NOT NULL DEFAULT '[]'
- `prohibited_actions`: JSONB NOT NULL DEFAULT '[]'
- `fail_safe_status`: VARCHAR(32) NOT NULL DEFAULT 'BLOCKED'
- `effective_timestamp`: TIMESTAMPTZ NOT NULL DEFAULT NOW()
- `is_active`: BOOLEAN NOT NULL DEFAULT TRUE
- `metadata`: JSONB DEFAULT '{}'

Constraints:
- `UNIQUE (policy_type, policy_version)`

#### 3. `provider_circuit_breakers`
Circuit breaker tracking for external clinical safety providers:
- `provider_name`: VARCHAR(64) PRIMARY KEY
- `state`: VARCHAR(16) NOT NULL DEFAULT 'CLOSED' -- CLOSED, OPEN, HALF_OPEN
- `failure_count`: INT NOT NULL DEFAULT 0
- `last_failure_at`: TIMESTAMPTZ
- `opened_at`: TIMESTAMPTZ
- `updated_at`: TIMESTAMPTZ NOT NULL DEFAULT NOW()

#### 4. `safety_operation_executions`
Operational execution log for sensitive actions to prevent unsafe retries:
- `op_key`: VARCHAR(128) PRIMARY KEY
- `status`: VARCHAR(32) NOT NULL -- SUCCESS, FAILED, UNKNOWN
- `check_id`: VARCHAR(64) REFERENCES `safety_checks(id)`
- `executed_at`: TIMESTAMPTZ NOT NULL DEFAULT NOW()
