# HealthSetu — Phase 36: Database Dependencies & Contract

## 1. Overview
The backend implementation for Phase 36 consumes existing database contracts and provides in-memory thread-safe repositories pending physical database schema deployment by the Database Teammate.

**Important Team Boundary Reminder**:
- The backend team does NOT create or modify PostgreSQL schema, tables, migrations, indexes, or constraints.
- The database teammate owns PostgreSQL schema and migrations.
- This document defines the exact database requirements and entity contracts expected by the backend service layer.

---

## 2. Required Relational Entities

### Table: `tasks`
Authoritative master record for clinical and operational tasks.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `VARCHAR(64)` | `PRIMARY KEY` | Formatted identifier (e.g. `TSK-YYYYMMDD-XXXXX`) |
| `title` | `VARCHAR(255)` | `NOT NULL` | Safe descriptive task title |
| `description` | `TEXT` | `NULL` | Contextual instructions |
| `category` | `VARCHAR(64)` | `NOT NULL` | Enum: `CLINICAL_TASK`, `DIAGNOSTIC_REVIEW_TASK`, etc. |
| `priority` | `VARCHAR(32)` | `NOT NULL`, Default `'NORMAL'` | Enum: `LOW`, `NORMAL`, `HIGH`, `URGENT` |
| `status` | `VARCHAR(32)` | `NOT NULL`, Default `'CREATED'` | Enum: `CREATED`, `ASSIGNED`, `ACCEPTED`, `IN_PROGRESS`, `BLOCKED`, `COMPLETED`, `VERIFICATION_PENDING`, `VERIFIED`, `CANCELLED`, `REJECTED`, `EXPIRED`, `FAILED` |
| `patient_id` | `VARCHAR(64)` | `NULL`, Indexed | Target patient identifier |
| `encounter_id` | `VARCHAR(64)` | `NULL`, Indexed | Associated encounter identifier |
| `organization_id` | `VARCHAR(64)` | `NULL`, Indexed | Multi-tenant organization scope |
| `facility_id` | `VARCHAR(64)` | `NULL`, Indexed | Tenant facility scope |
| `assignee_id` | `VARCHAR(64)` | `NULL`, Indexed | Assigned user or team identifier |
| `assignee_type` | `VARCHAR(32)` | `NULL` | Enum: `USER`, `TEAM`, `FACILITY`, `ORGANIZATION` |
| `team_id` | `VARCHAR(64)` | `NULL`, Indexed | Care team identifier |
| `created_by` | `VARCHAR(64)` | `NOT NULL` | User or system creator |
| `accepted_by` | `VARCHAR(64)` | `NULL` | User who accepted responsibility |
| `accepted_at` | `TIMESTAMPTZ` | `NULL` | Timestamp of acceptance |
| `started_at` | `TIMESTAMPTZ` | `NULL` | Timestamp transitioned to `IN_PROGRESS` |
| `completed_by` | `VARCHAR(64)` | `NULL` | User who completed work |
| `completed_at` | `TIMESTAMPTZ` | `NULL` | Completion timestamp |
| `completion_notes` | `TEXT` | `NULL` | Completion notes |
| `verification_required` | `BOOLEAN` | `NOT NULL`, Default `FALSE` | Require peer/supervisor review |
| `verified_by` | `VARCHAR(64)` | `NULL` | Verifier identifier |
| `verified_at` | `TIMESTAMPTZ` | `NULL` | Verification timestamp |
| `verification_notes` | `TEXT` | `NULL` | Verification remarks |
| `cancelled_by` | `VARCHAR(64)` | `NULL` | Cancellation user |
| `cancelled_at` | `TIMESTAMPTZ` | `NULL` | Cancellation timestamp |
| `cancellation_reason` | `TEXT` | `NULL` | Cancellation justification |
| `rejected_by` | `VARCHAR(64)` | `NULL` | Rejection actor |
| `rejected_at` | `TIMESTAMPTZ` | `NULL` | Rejection timestamp |
| `rejection_reason` | `TEXT` | `NULL` | Rejection explanation |
| `due_at` | `TIMESTAMPTZ` | `NULL`, Indexed | Deadline for completion |
| `start_at` | `TIMESTAMPTZ` | `NULL` | Earliest allowed start timestamp |
| `expires_at` | `TIMESTAMPTZ` | `NULL` | Auto-expiration timestamp |
| `provenance_source_type` | `VARCHAR(64)` | `NOT NULL` | Source resource type |
| `provenance_source_id` | `VARCHAR(64)` | `NOT NULL` | Source resource ID |
| `provenance_source_event_id`| `VARCHAR(64)` | `NULL` | Domain event UUID |
| `provenance_source_system` | `VARCHAR(64)` | `NOT NULL` | Origin subsystem |
| `idempotency_key` | `VARCHAR(128)` | `NULL`, Unique Index | Deduplication key |
| `escalation_level` | `INTEGER` | `NOT NULL`, Default `0` | Multi-tier escalation level |
| `escalation_deadline` | `TIMESTAMPTZ` | `NULL` | Next escalation deadline |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL`, Default `NOW()` | Creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | `NOT NULL`, Default `NOW()` | Optimistic concurrency lock |

### Table: `task_dependencies`
Represents prerequisite DAG constraints between tasks.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `VARCHAR(64)` | `PRIMARY KEY` | Dependency record UUID |
| `task_id` | `VARCHAR(64)` | `NOT NULL`, Foreign Key `tasks.id` | Target dependent task |
| `depends_on_task_id`| `VARCHAR(64)` | `NOT NULL`, Foreign Key `tasks.id` | Prerequisite task |
| `dependency_type` | `VARCHAR(64)` | `NOT NULL` | e.g. `COMPLETION_REQUIRED` |
| `status` | `VARCHAR(32)` | `NOT NULL` | Enum: `WAITING`, `READY`, `BLOCKED`, `COMPLETED` |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL`, Default `NOW()` | Creation timestamp |

### Table: `task_history`
Append-only chronological audit ledger of all status transitions and assignments.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `VARCHAR(64)` | `PRIMARY KEY` | History entry UUID |
| `task_id` | `VARCHAR(64)` | `NOT NULL`, Foreign Key `tasks.id` | Associated task |
| `action` | `VARCHAR(64)` | `NOT NULL` | Enum: `TASK_CREATED`, `TASK_ASSIGNED`, `TASK_ACCEPTED`, `TASK_STARTED`, `TASK_COMPLETED`, `TASK_VERIFIED`, etc. |
| `from_status` | `VARCHAR(32)` | `NULL` | Previous lifecycle state |
| `to_status` | `VARCHAR(32)` | `NOT NULL` | New lifecycle state |
| `actor_id` | `VARCHAR(64)` | `NOT NULL` | Mutating actor user ID |
| `actor_role` | `VARCHAR(32)` | `NOT NULL` | Actor role |
| `reason` | `TEXT` | `NULL` | Justification note |
| `metadata` | `JSONB` | `NOT NULL`, Default `'{}'` | Contextual metadata |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL`, Default `NOW()` | Immutable timestamp |

---

## 3. Recommended Indexes
- Composite index on `(organization_id, facility_id, status)` for facility queue performance.
- Index on `(assignee_id, status)` for `my_tasks` retrieval.
- Unique partial index on `(provenance_source_type, provenance_source_id, category, patient_id)` for logical task deduplication.
- Index on `(due_at)` where `status NOT IN ('COMPLETED', 'VERIFIED', 'CANCELLED')` for overdue batch processing.
