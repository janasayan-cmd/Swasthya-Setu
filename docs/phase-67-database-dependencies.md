# Phase 67: Governance Escalation, Exception Resolution & Decision Coordination
## Database Dependencies Specification

**Document Version:** 1.0.0  
**Phase:** 67 (Governance Escalation & Decision Coordination)  
**Boundary:** Backend application layer contract requirements for the database team.  
**Notice:** Backend does NOT create migrations, alter schemas, or manage DDL. This document defines the exact PostgreSQL entities, fields, constraints, and indexes required by HealthSetu backend services.

---

### 1. Conceptual Architecture & Isolation Boundary

Phase 67 coordinates cross-workflow safety governance exceptions, priority routing, assignment, conflict resolution, and controlled closures.
- Entities are tenant-isolated via `organization_id` and optionally `facility_id`.
- The database schema must preserve complete provenance: source phase, source record ID, source version, and immutable audit history.
- Historical closure records must never be overwritten; reopening must increment `reopen_count` while preserving historical timestamps and deciders.

---

### 2. Required Database Entities

#### 2.1 Table: `governance_escalations`
Stores the central governance escalation workflow entities.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `escalation_id` | VARCHAR(64) | PRIMARY KEY | Unique identifier (e.g. `gesc-uuid`) |
| `title` | VARCHAR(255) | NOT NULL | Human-readable escalation title |
| `summary` | TEXT | NOT NULL | Context and summary of governance exception |
| `primary_category` | VARCHAR(64) | NOT NULL, INDEXED | Exception category enum |
| `governance_priority` | VARCHAR(32) | NOT NULL, INDEXED | Priority enum (`ROUTINE`, `ELEVATED`, `HIGH`, `URGENT`, `CRITICAL`, `UNCLASSIFIED`) |
| `lifecycle_state` | VARCHAR(64) | NOT NULL, INDEXED | Escalation state enum |
| `organization_id` | VARCHAR(64) | NOT NULL, INDEXED | Multi-tenant organization scope |
| `facility_id` | VARCHAR(64) | NOT NULL, INDEXED | Associated facility scope |
| `patient_id` | VARCHAR(64) | NULLABLE, INDEXED | Associated patient scope (if applicable) |
| `routing_domain` | VARCHAR(64) | NOT NULL, INDEXED | Routing domain enum |
| `escalation_level` | INTEGER | NOT NULL DEFAULT 1 | Governance hierarchy level (1, 2, 3...) |
| `assigned_owner_id` | VARCHAR(64) | NULLABLE, INDEXED | User ID of designated owner |
| `assigned_owner_role` | VARCHAR(64) | NULLABLE | Role of designated owner |
| `assigned_at` | TIMESTAMPTZ | NULLABLE | Timestamp ownership was assigned |
| `assigned_by` | VARCHAR(64) | NULLABLE | User ID who assigned ownership |
| `secondary_reviewer_id`| VARCHAR(64) | NULLABLE | Optional secondary reviewer |
| `governance_committee_ref`| VARCHAR(128)| NULLABLE | Committee reference if routed |
| `specialist_role_required`| VARCHAR(64) | NULLABLE | Required clinical/specialist role |
| `is_acknowledged` | BOOLEAN | NOT NULL DEFAULT FALSE | Whether owner acknowledged assignment |
| `acknowledged_by` | VARCHAR(64) | NULLABLE | User ID who acknowledged |
| `acknowledged_at` | TIMESTAMPTZ | NULLABLE | Timestamp of acknowledgement |
| `acknowledgement_deadline`| TIMESTAMPTZ | NULLABLE | Policy deadline for acknowledgement |
| `initial_review_deadline`| TIMESTAMPTZ | NULLABLE | Policy deadline for initial review |
| `decision_deadline` | TIMESTAMPTZ | NULLABLE | Policy deadline for governance decision |
| `resolution_deadline` | TIMESTAMPTZ | NULLABLE | Policy deadline for resolution |
| `is_overdue` | BOOLEAN | NOT NULL DEFAULT FALSE | Flag indicating overdue status |
| `overdue_duration_seconds`| INTEGER | NULLABLE | Overdue duration |
| `extensions_count` | INTEGER | NOT NULL DEFAULT 0 | Count of deadline extensions granted |
| `aggregated_exception_ids`| JSONB | NOT NULL DEFAULT '[]' | List of associated exception IDs |
| `related_workflow_ids` | JSONB | NOT NULL DEFAULT '[]' | Cross-phase linked workflow IDs |
| `conflicting_decision_ids`| JSONB | NOT NULL DEFAULT '[]' | Conflict record references |
| `dependency_refs` | JSONB | NOT NULL DEFAULT '[]' | Explicit dependency references |
| `resolution_rationale` | TEXT | NULLABLE | Rationale when resolved |
| `resolved_at` | TIMESTAMPTZ | NULLABLE | Timestamp resolved |
| `resolved_by` | VARCHAR(64) | NULLABLE | User ID who resolved |
| `closure_rationale` | TEXT | NULLABLE | Administrative closure rationale |
| `closed_at` | TIMESTAMPTZ | NULLABLE | Timestamp closed |
| `closed_by` | VARCHAR(64) | NULLABLE | User ID who closed |
| `is_reopened` | BOOLEAN | NOT NULL DEFAULT FALSE | Reopening flag |
| `reopen_count` | INTEGER | NOT NULL DEFAULT 0 | Number of times reopened |
| `reopened_at` | TIMESTAMPTZ | NULLABLE | Timestamp last reopened |
| `reopened_by` | VARCHAR(64) | NULLABLE | User ID who reopened |
| `reopen_trigger_source`| VARCHAR(128)| NULLABLE | Phase and ID triggering reopening |
| `reopen_rationale` | TEXT | NULLABLE | Justification for reopening |
| `policy_reference` | VARCHAR(128)| NOT NULL | Governance policy identifier |
| `policy_version` | VARCHAR(32) | NOT NULL | Governance policy version |
| `idempotency_key` | VARCHAR(128)| NULLABLE, UNIQUE | Key to prevent duplicate execution |
| `correlation_id` | VARCHAR(128)| NULLABLE, INDEXED | Tracing correlation identifier |
| `metadata` | JSONB | NOT NULL DEFAULT '{}' | Additional context |
| `created_by` | VARCHAR(64) | NOT NULL | User ID who created record |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Timestamp created |
| `updated_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Timestamp updated |

---

#### 2.2 Table: `governance_exceptions`
Stores normalized exceptions ingested from authoritative source workflows.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `exception_id` | VARCHAR(64) | PRIMARY KEY | Unique exception identifier (e.g. `gex-uuid`) |
| `escalation_id` | VARCHAR(64) | NULLABLE, INDEXED | Foreign key reference to `governance_escalations` |
| `category` | VARCHAR(64) | NOT NULL, INDEXED | Exception category enum |
| `source_phase` | VARCHAR(64) | NOT NULL, INDEXED | Authoritative originating phase |
| `source_record_id` | VARCHAR(64) | NOT NULL, INDEXED | Originating record identifier |
| `source_version` | VARCHAR(32) | NOT NULL | Originating record version |
| `organization_id` | VARCHAR(64) | NOT NULL, INDEXED | Multi-tenant organization scope |
| `facility_id` | VARCHAR(64) | NOT NULL, INDEXED | Associated facility scope |
| `patient_id` | VARCHAR(64) | NULLABLE, INDEXED | Associated patient scope |
| `source_severity` | VARCHAR(32) | NOT NULL | Originating severity rating |
| `governance_priority` | VARCHAR(32) | NOT NULL | Evaluated governance priority |
| `lifecycle_state` | VARCHAR(32) | NOT NULL, INDEXED | Exception status (`ACTIVE`, `UNDER_REVIEW`, etc.) |
| `title` | VARCHAR(255) | NOT NULL | Short description |
| `description` | TEXT | NOT NULL | Detailed finding context |
| `is_material` | BOOLEAN | NOT NULL DEFAULT TRUE | Materiality flag |
| `materiality_rationale` | TEXT | NULLABLE | Materiality evaluation explanation |
| `policy_reference` | VARCHAR(128)| NOT NULL | Policy identifier |
| `policy_version` | VARCHAR(32) | NOT NULL | Policy version |
| `related_workflow_ids` | JSONB | NOT NULL DEFAULT '[]' | Cross-phase linked IDs |
| `dependency_refs` | JSONB | NOT NULL DEFAULT '[]' | Dependency references |
| `evidence_refs` | JSONB | NOT NULL DEFAULT '[]' | Evidence artifact references |
| `resolution_status` | VARCHAR(32) | NOT NULL DEFAULT 'UNRESOLVED' | Status of resolution |
| `resolved_at` | TIMESTAMPTZ | NULLABLE | Timestamp resolved |
| `resolution_rationale` | TEXT | NULLABLE | Explanation of resolution |
| `created_by` | VARCHAR(64) | NOT NULL | Originating actor |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Timestamp created |
| `updated_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Timestamp updated |
| `metadata` | JSONB | NOT NULL DEFAULT '{}' | Metadata |

---

#### 2.3 Table: `governance_reviews`
Records formal reviews conducted on escalations.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `review_id` | VARCHAR(64) | PRIMARY KEY | Unique review identifier (e.g. `grev-uuid`) |
| `escalation_id` | VARCHAR(64) | NOT NULL, INDEXED | Foreign key reference to `governance_escalations` |
| `reviewer_id` | VARCHAR(64) | NOT NULL, INDEXED | User ID who conducted review |
| `reviewer_role` | VARCHAR(64) | NOT NULL | Role of reviewer |
| `outcome` | VARCHAR(64) | NOT NULL, INDEXED | Review outcome enum |
| `rationale` | TEXT | NOT NULL | Evaluative findings and rationale |
| `policy_version` | VARCHAR(32) | NOT NULL | Policy version under which reviewed |
| `reviewed_exception_ids`| JSONB | NOT NULL DEFAULT '[]' | Specific exceptions reviewed |
| `evidence_refs` | JSONB | NOT NULL DEFAULT '[]' | Supporting evidence examined |
| `required_follow_up_actions`| JSONB | NOT NULL DEFAULT '[]' | Required actions identified |
| `required_downstream_workflows`| JSONB| NOT NULL DEFAULT '[]' | Target workflows needing engagement |
| `reviewed_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Timestamp review conducted |
| `metadata` | JSONB | NOT NULL DEFAULT '{}' | Context metadata |

---

#### 2.4 Table: `governance_decisions`
Records authorized governance decisions issued for escalations.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `decision_id` | VARCHAR(64) | PRIMARY KEY | Unique decision identifier (e.g. `gdec-uuid`) |
| `escalation_id` | VARCHAR(64) | NOT NULL, INDEXED | Foreign key reference to `governance_escalations` |
| `decided_by` | VARCHAR(64) | NOT NULL, INDEXED | Authoritative decider user ID |
| `decided_by_role` | VARCHAR(64) | NOT NULL | Role of decider |
| `decision_type` | VARCHAR(64) | NOT NULL | Decision type descriptor |
| `decision_title` | VARCHAR(255) | NOT NULL | Human-readable decision title |
| `rationale` | TEXT | NOT NULL | Formal governance rationale |
| `policy_reference` | VARCHAR(128)| NOT NULL | Governing policy reference |
| `policy_version` | VARCHAR(32) | NOT NULL | Governing policy version |
| `approved_actions` | JSONB | NOT NULL DEFAULT '[]' | Actions formally authorized |
| `required_resolution_requirements`| JSONB | NOT NULL DEFAULT '[]'| Spawned resolution requirements |
| `target_workflow_instructions`| JSONB | NOT NULL DEFAULT '{}' | Cross-phase instructions |
| `decided_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Timestamp decision recorded |
| `metadata` | JSONB | NOT NULL DEFAULT '{}' | Context metadata |

---

#### 2.5 Table: `resolution_requirements`
Tracks individual conditions required to achieve escalation resolution.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `requirement_id` | VARCHAR(64) | PRIMARY KEY | Unique requirement identifier (e.g. `greq-uuid`) |
| `escalation_id` | VARCHAR(64) | NOT NULL, INDEXED | Foreign key reference to `governance_escalations` |
| `title` | VARCHAR(255) | NOT NULL | Description of requirement |
| `category` | VARCHAR(64) | NOT NULL, INDEXED | Requirement category enum |
| `is_mandatory` | BOOLEAN | NOT NULL DEFAULT TRUE | Mandatory vs optional flag |
| `status` | VARCHAR(32) | NOT NULL, INDEXED | Requirement status enum |
| `responsible_phase` | VARCHAR(64) | NOT NULL | Upstream/downstream phase responsible |
| `responsible_owner` | VARCHAR(64) | NULLABLE | Specific owner assigned |
| `target_record_id` | VARCHAR(64) | NULLABLE | Downstream target record |
| `target_version` | VARCHAR(32) | NULLABLE | Target record version |
| `completion_evidence_refs`| JSONB | NOT NULL DEFAULT '[]' | Evidence references satisfying requirement |
| `blocking_reason` | TEXT | NULLABLE | Explanation if blocked |
| `waiver_rationale` | TEXT | NULLABLE | Justification if authorized waived |
| `waived_by` | VARCHAR(64) | NULLABLE | Administrator who waived |
| `due_date` | TIMESTAMPTZ | NULLABLE | Due date from policy |
| `reconciled_at` | TIMESTAMPTZ | NULLABLE | Timestamp reconciled |
| `reconciled_by` | VARCHAR(64) | NULLABLE | User ID who reconciled |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Timestamp created |
| `updated_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Timestamp updated |
| `metadata` | JSONB | NOT NULL DEFAULT '{}' | Context metadata |

---

#### 2.6 Table: `cross_workflow_conflicts`
Records contradictory authoritative decisions detected across safety workflows.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `conflict_id` | VARCHAR(64) | PRIMARY KEY | Unique conflict identifier (e.g. `gconf-uuid`) |
| `escalation_id` | VARCHAR(64) | NOT NULL, INDEXED | Foreign key reference to `governance_escalations` |
| `conflict_type` | VARCHAR(64) | NOT NULL | Type descriptor |
| `severity` | VARCHAR(32) | NOT NULL | Severity rating |
| `is_material` | BOOLEAN | NOT NULL DEFAULT TRUE | Materiality flag |
| `source_phase_a` | VARCHAR(64) | NOT NULL | First source phase |
| `source_record_id_a`| VARCHAR(64) | NOT NULL | First source record ID |
| `source_state_a` | VARCHAR(64) | NOT NULL | First source state |
| `source_version_a` | VARCHAR(32) | NOT NULL | First source version |
| `source_phase_b` | VARCHAR(64) | NOT NULL | Second source phase |
| `source_record_id_b`| VARCHAR(64) | NOT NULL | Second source record ID |
| `source_state_b` | VARCHAR(64) | NOT NULL | Second source state |
| `source_version_b` | VARCHAR(32) | NOT NULL | Second source version |
| `description` | TEXT | NOT NULL | Detailed explanation of conflict |
| `is_resolved` | BOOLEAN | NOT NULL DEFAULT FALSE | Resolution flag |
| `resolution_rationale`| TEXT | NULLABLE | Rationale when resolved |
| `resolved_by` | VARCHAR(64) | NULLABLE | User ID who reconciled conflict |
| `resolved_at` | TIMESTAMPTZ | NULLABLE | Timestamp resolved |
| `detected_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Timestamp detected |
| `metadata` | JSONB | NOT NULL DEFAULT '{}' | Context metadata |

---

#### 2.7 Table: `escalation_history`
Stores non-repudiable audit transitions for every escalation state change.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `history_id` | VARCHAR(64) | PRIMARY KEY | Unique history identifier (e.g. `ghist-uuid`) |
| `escalation_id` | VARCHAR(64) | NOT NULL, INDEXED | Foreign key reference to `governance_escalations` |
| `from_state` | VARCHAR(64) | NOT NULL | Previous lifecycle state |
| `to_state` | VARCHAR(64) | NOT NULL | New lifecycle state |
| `action` | VARCHAR(64) | NOT NULL | Action performed |
| `performed_by` | VARCHAR(64) | NOT NULL, INDEXED | User ID who performed action |
| `performed_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Timestamp action performed |
| `rationale` | TEXT | NULLABLE | Rationale for transition |
| `details` | JSONB | NOT NULL DEFAULT '{}' | Structured context |
