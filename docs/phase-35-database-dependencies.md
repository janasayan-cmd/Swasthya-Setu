# HealthSetu — Phase 35: Database Dependencies & Contracts

## 1. Ownership Boundary
The database schema, constraints, migrations, partitioning, and indexing strategies are strictly owned by the **Database Team**. The Backend Team relies on standardized contracts and repository interfaces without executing runtime DDL.

---

## 2. Expected Database Tables & Relations

### `alerts`
- `id` (PK, varchar(64), e.g. `ALT-YYYYMMDD-XXXX`)
- `title` (varchar(255), not null)
- `summary` (text, not null)
- `category` (varchar(64), enum `AlertCategory`)
- `severity` (varchar(32), enum `AlertSeverity`)
- `status` (varchar(32), enum `AlertStatus`, default `CREATED`)
- `patient_id` (varchar(64), nullable, indexed, FK to `patients`)
- `encounter_id` (varchar(64), nullable, FK to `encounters`)
- `organization_id` (varchar(64), nullable, indexed, FK to `organizations`)
- `facility_id` (varchar(64), nullable, indexed, FK to `facilities`)
- `responsible_clinician_id` (varchar(64), nullable, indexed, FK to `users`)
- `requires_acknowledgement` (boolean, default false)
- `escalation_enabled` (boolean, default false)
- `escalation_level` (integer, default 0)
- `next_escalation_deadline` (timestamptz, nullable, indexed)
- `acknowledged_at` (timestamptz, nullable)
- `acknowledged_by` (varchar(64), nullable)
- `resolved_at` (timestamptz, nullable)
- `resolved_by` (varchar(64), nullable)
- `resolution_reason` (text, nullable)
- `dismissed_at` (timestamptz, nullable)
- `dismissed_by` (varchar(64), nullable)
- `dismissal_reason` (text, nullable)
- `source_system` (varchar(128), not null)
- `source_event_type` (varchar(128), not null)
- `source_event_id` (varchar(128), not null)
- `source_resource_type` (varchar(128), not null)
- `source_resource_id` (varchar(128), not null)
- `policy_id` (varchar(128), not null)
- `idempotency_key` (varchar(128), not null, unique)
- `created_at` (timestamptz, not null)
- `updated_at` (timestamptz, not null)

### `alert_policies`
- `policy_id` (PK, varchar(128))
- `name` (varchar(255), not null)
- `version` (varchar(32), not null)
- `event_type` (varchar(128), not null, indexed)
- `category` (varchar(64), not null)
- `severity` (varchar(32), not null)
- `requires_acknowledgement` (boolean, default false)
- `escalation_enabled` (boolean, default false)
- `escalation_timeout_minutes` (integer, default 30)
- `cooldown_period_minutes` (integer, default 0)
- `is_active` (boolean, default true)
- `conditions` (jsonb, nullable)
- `created_at` (timestamptz, not null)

### `alert_recipients`
- `id` (PK, bigserial)
- `alert_id` (varchar(64), not null, indexed, FK to `alerts`)
- `recipient_id` (varchar(64), not null, indexed)
- `recipient_type` (varchar(64), not null)
- `channel` (varchar(32), not null)
- `delivered_at` (timestamptz, nullable)
- `read_at` (timestamptz, nullable)
- `status` (varchar(32), default `PENDING`)

### `alert_history`
- `id` (PK, bigserial)
- `alert_id` (varchar(64), not null, indexed, FK to `alerts`)
- `action` (varchar(64), not null)
- `from_status` (varchar(32), nullable)
- `to_status` (varchar(32), not null)
- `actor_id` (varchar(64), not null)
- `actor_role` (varchar(64), not null)
- `reason` (text, nullable)
- `metadata` (jsonb, nullable)
- `timestamp` (timestamptz, not null)

### `alert_escalations`
- `id` (PK, bigserial)
- `alert_id` (varchar(64), not null, indexed, FK to `alerts`)
- `from_level` (integer, not null)
- `to_level` (integer, not null)
- `escalated_to_recipient_id` (varchar(64), not null)
- `escalated_to_recipient_type` (varchar(64), not null)
- `escalation_reason` (text, not null)
- `status` (varchar(32), not null)
- `stop_reason` (varchar(64), nullable)
- `timestamp` (timestamptz, not null)

---

## 3. Required Indexes & Performance Guarantees
- `idx_alerts_status_severity`: Composite index on `(status, severity)` for triage prioritization.
- `idx_alerts_clinician_status`: Composite index on `(responsible_clinician_id, status)` for instant inbox loading.
- `idx_alerts_patient_id`: Index on `patient_id` for patient portal views.
- `idx_alerts_escalation_deadline`: Partial index on `next_escalation_deadline WHERE status = 'CREATED' AND escalation_enabled = true` for worker polling.
- `idx_alerts_idempotency_key`: Unique index on `idempotency_key` ensuring zero duplicate alert records.
