# Phase 37: Clinical Workflow Orchestration & Order Management
## Database Dependencies & Schema Contract Specification

**Document Type:** Architecture & Teammate Hand-off  
**Audience:** Database Teammate & Backend Engineering  
**Scope:** PostgreSQL Schema, Tables, Constraints, and Indices required for Phase 37.

---

### 1. Executive Summary & Boundaries

Per the HealthSetu team boundary rules, the **backend does NOT create or alter PostgreSQL schemas, tables, migrations, constraints, or seeds**. The database teammate owns PostgreSQL schema design and migrations.

The backend implementation consumes the existing schema where available and utilizes an in-memory repository layer (`app/repositories/workflow_repository.py` and `app/repositories/workflow_step_repository.py`) as an operational bridge. This document formalizes the exact schema contracts required for persistence.

---

### 2. Required Database Entities

#### 2.1 Table: `workflow_definitions`
Stores approved, versioned clinical and operational workflow templates.

```sql
CREATE TABLE IF NOT EXISTS workflow_definitions (
    definition_id VARCHAR(64) NOT NULL,
    version VARCHAR(32) NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    category VARCHAR(64) NOT NULL, -- e.g., 'DIAGNOSTIC', 'MEDICATION', 'DISCHARGE', 'TRANSFER'
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    trigger_type VARCHAR(64) NOT NULL, -- e.g., 'DIAGNOSTIC_RESULT', 'MEDICATION_SAFETY', etc.
    timeout_minutes INT NOT NULL DEFAULT 1440,
    escalation_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    steps_config JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (definition_id, version)
);

CREATE INDEX idx_workflow_defs_category ON workflow_definitions (category, enabled);
```

#### 2.2 Table: `workflow_instances`
Represents single runtime executions of a workflow definition.

```sql
CREATE TABLE IF NOT EXISTS workflow_instances (
    workflow_id VARCHAR(64) PRIMARY KEY,
    definition_id VARCHAR(64) NOT NULL,
    definition_version VARCHAR(32) NOT NULL,
    name VARCHAR(255) NOT NULL,
    category VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL, -- 'CREATED', 'READY', 'RUNNING', 'WAITING', 'PAUSED', 'BLOCKED', 'AWAITING_APPROVAL', 'COMPLETED', 'FAILED', 'CANCELLED', 'EXPIRED'
    current_step_id VARCHAR(64),
    patient_id VARCHAR(64),
    encounter_id VARCHAR(64),
    resource_id VARCHAR(64),
    facility_id VARCHAR(64),
    correlation_id VARCHAR(128) NOT NULL,
    source_event_id VARCHAR(128),
    source_event_type VARCHAR(64),
    idempotency_key VARCHAR(128),
    context JSONB NOT NULL DEFAULT '{}'::jsonb,
    failure_reason TEXT,
    error_code VARCHAR(64),
    retry_count INT NOT NULL DEFAULT 0,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_wf_definition FOREIGN KEY (definition_id, definition_version)
        REFERENCES workflow_definitions (definition_id, version)
);

-- Idempotency and Deduplication Unique Indices
CREATE UNIQUE INDEX idx_workflow_idempotency_key 
    ON workflow_instances (idempotency_key) 
    WHERE idempotency_key IS NOT NULL;

CREATE UNIQUE INDEX idx_workflow_logical_identity 
    ON workflow_instances (source_event_type, source_event_id, definition_id, definition_version, patient_id)
    WHERE source_event_type IS NOT NULL AND source_event_id IS NOT NULL;

-- Query & Scoping Indices
CREATE INDEX idx_workflow_patient ON workflow_instances (patient_id, status);
CREATE INDEX idx_workflow_facility ON workflow_instances (facility_id, status);
CREATE INDEX idx_workflow_status ON workflow_instances (status);
CREATE INDEX idx_workflow_correlation ON workflow_instances (correlation_id);
```

#### 2.3 Table: `workflow_step_instances`
Runtime step records tracking execution, action type, linked tasks, and prerequisite dependencies.

```sql
CREATE TABLE IF NOT EXISTS workflow_step_instances (
    step_instance_id VARCHAR(64) PRIMARY KEY,
    workflow_id VARCHAR(64) NOT NULL REFERENCES workflow_instances(workflow_id) ON DELETE CASCADE,
    step_id VARCHAR(64) NOT NULL,
    name VARCHAR(255) NOT NULL,
    order_index INT NOT NULL DEFAULT 1,
    action_type VARCHAR(64) NOT NULL, -- 'CREATE_TASK', 'SEND_NOTIFICATION', 'WAIT_FOR_EVENT', 'HUMAN_APPROVAL', etc.
    action_config JSONB NOT NULL DEFAULT '{}'::jsonb,
    status VARCHAR(32) NOT NULL, -- 'PENDING', 'READY', 'RUNNING', 'WAITING', 'AWAITING_APPROVAL', 'COMPLETED', 'FAILED', 'SKIPPED', 'CANCELLED', 'BLOCKED'
    dependencies JSONB NOT NULL DEFAULT '[]'::jsonb,
    approval_required BOOLEAN NOT NULL DEFAULT FALSE,
    required_approval_role VARCHAR(64),
    related_task_id VARCHAR(64), -- Foreign reference to Phase 36 tasks.id
    related_alert_id VARCHAR(64), -- Foreign reference to Phase 35 alerts.id
    waiting_for_event VARCHAR(128),
    retry_count INT NOT NULL DEFAULT 0,
    max_retries INT NOT NULL DEFAULT 3,
    error_message TEXT,
    error_code VARCHAR(64),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_workflow_step UNIQUE (workflow_id, step_id)
);

CREATE INDEX idx_step_workflow ON workflow_step_instances (workflow_id, order_index);
CREATE INDEX idx_step_related_task ON workflow_step_instances (related_task_id) WHERE related_task_id IS NOT NULL;
CREATE INDEX idx_step_waiting_event ON workflow_step_instances (waiting_for_event, status) WHERE status = 'WAITING';
```

#### 2.4 Table: `workflow_approvals`
Audit records capturing human authorization decisions at approval gates.

```sql
CREATE TABLE IF NOT EXISTS workflow_approvals (
    approval_id VARCHAR(64) PRIMARY KEY,
    workflow_id VARCHAR(64) NOT NULL REFERENCES workflow_instances(workflow_id) ON DELETE CASCADE,
    step_id VARCHAR(64) NOT NULL,
    step_instance_id VARCHAR(64) NOT NULL REFERENCES workflow_step_instances(step_instance_id),
    approver_id VARCHAR(64) NOT NULL,
    approver_role VARCHAR(64) NOT NULL,
    decision VARCHAR(32) NOT NULL, -- 'APPROVED', 'REJECTED'
    comments TEXT,
    policy_version VARCHAR(32) NOT NULL DEFAULT '1.0',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_approvals_workflow ON workflow_approvals (workflow_id);
CREATE INDEX idx_approvals_approver ON workflow_approvals (approver_id);
```

#### 2.5 Table: `workflow_history`
Append-only immutable audit trail capturing every state machine progression.

```sql
CREATE TABLE IF NOT EXISTS workflow_history (
    history_id VARCHAR(64) PRIMARY KEY,
    workflow_id VARCHAR(64) NOT NULL REFERENCES workflow_instances(workflow_id) ON DELETE CASCADE,
    step_id VARCHAR(64),
    action VARCHAR(64) NOT NULL,
    from_status VARCHAR(32),
    to_status VARCHAR(32) NOT NULL,
    actor_id VARCHAR(64),
    actor_role VARCHAR(64),
    reason TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_wf_history_workflow ON workflow_history (workflow_id, created_at ASC);
```

---

### 3. Data Governance & PHI Safeguards

1. **Reference-Only Architecture**: Workflow tables store foreign keys (`patient_id`, `encounter_id`, `resource_id`) and avoid storing raw PHI clinical text, prescriptions, or notes.
2. **Append-Only History**: Deleting a workflow instance must NOT erase `workflow_history` or `workflow_approvals` without governance justification.
3. **No Autonomous Mutations**: Workflow records represent operational coordination; no tables grant autonomous prescription or diagnostic authority.
