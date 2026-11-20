# Phase 72: Clinical Safety Governance Management Review, Executive Oversight & Decision Follow-Through
## Database Dependencies Specification

**Document Version:** 1.0.0  
**Phase:** 72 (Clinical Safety Governance Management Review, Executive Oversight & Decision Follow-Through)  
**Boundary:** Backend application layer contract requirements for the database team.  
**Notice:** Backend does NOT create migrations, alter schemas, or manage DDL. This document defines the exact PostgreSQL entities, fields, constraints, and indexes required by HealthSetu backend services.

---

### 1. Conceptual Architecture & Isolation Boundary

Phase 72 formalizes management review meetings, executive decision recording, follow-through commitments, and review reports.
- All entities are strictly isolated by `organization_id` and optionally `facility_id`.
- Complete traceability and history are preserved (no hard deletions of decisions or commitments).
- Foreign key linkages connect management commitments to upstream workflow engines (Phase 54 CAPA, Phase 55 effectiveness, Phase 63 risk review, Phase 67 escalation).

---

### 2. Required Database Entities

#### 2.1 Table: `management_review_programmes`
Stores governance review programme definitions and approvals.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `programme_id` | VARCHAR(64) | PRIMARY KEY | Unique identifier (`gmrp-uuid`) |
| `name` | VARCHAR(255) | NOT NULL | Programme title |
| `description` | TEXT | NOT NULL | Programme description |
| `objectives` | JSONB | NOT NULL DEFAULT '[]' | Programme goals and objectives |
| `category` | VARCHAR(64) | NOT NULL, INDEXED | Programme category enum |
| `frequency` | VARCHAR(32) | NOT NULL, INDEXED | Interval frequency enum |
| `status` | VARCHAR(32) | NOT NULL, INDEXED | Status enum (`DRAFT`, `APPROVED`, etc.) |
| `responsible_owner_id` | VARCHAR(64) | NOT NULL | Programme owner |
| `responsible_owner_role` | VARCHAR(64) | NOT NULL | Role of owner |
| `participating_units` | JSONB | NOT NULL DEFAULT '[]' | Participating clinical departments |
| `applicable_domains` | JSONB | NOT NULL DEFAULT '[]' | Applicable clinical safety domains |
| `approved_by` | VARCHAR(64) | NULLABLE | Approver user ID |
| `approved_at` | TIMESTAMPTZ | NULLABLE | Approval timestamp |
| `approval_policy_ref` | VARCHAR(255) | NULLABLE | Governance policy reference |
| `organization_id` | VARCHAR(64) | NOT NULL, INDEXED | Tenant isolation |
| `facility_id` | VARCHAR(64) | NULLABLE, INDEXED | Facility identifier |
| `created_by` | VARCHAR(64) | NOT NULL | Creator user ID |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Creation timestamp |
| `updated_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Last update timestamp |
| `metadata` | JSONB | NOT NULL DEFAULT '{}' | Extensible attributes |

#### 2.2 Table: `management_reviews`
Stores individual review meetings and their lifecycle state machine.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `review_id` | VARCHAR(64) | PRIMARY KEY | Unique identifier (`gmrv-uuid`) |
| `programme_id` | VARCHAR(64) | NOT NULL, INDEXED | Foreign key to `management_review_programmes` |
| `title` | VARCHAR(255) | NOT NULL | Review meeting title |
| `objectives` | JSONB | NOT NULL DEFAULT '[]' | Meeting objectives |
| `status` | VARCHAR(32) | NOT NULL, INDEXED | Meeting lifecycle status |
| `planned_date` | TIMESTAMPTZ | NOT NULL, INDEXED | Scheduled meeting date |
| `time_zone` | VARCHAR(64) | NOT NULL DEFAULT 'UTC' | Meeting timezone |
| `duration_minutes` | INTEGER | NOT NULL DEFAULT 60 | Planned duration |
| `actual_start_time` | TIMESTAMPTZ | NULLABLE | Meeting commencement timestamp |
| `actual_end_time` | TIMESTAMPTZ | NULLABLE | Meeting completion timestamp |
| `chairperson_id` | VARCHAR(64) | NULLABLE, INDEXED | Assigned chairperson user ID |
| `meeting_owner_id` | VARCHAR(64) | NOT NULL | Meeting organizer user ID |
| `agenda_preparation_deadline` | TIMESTAMPTZ | NULLABLE | Agenda freeze deadline |
| `evidence_preparation_deadline` | TIMESTAMPTZ | NULLABLE | Evidence compilation deadline |
| `decision_recording_deadline` | TIMESTAMPTZ | NULLABLE | Decision recording deadline |
| `follow_up_deadline` | TIMESTAMPTZ | NULLABLE | Target completion for actions |
| `organization_id` | VARCHAR(64) | NOT NULL, INDEXED | Tenant isolation |
| `facility_id` | VARCHAR(64) | NULLABLE, INDEXED | Facility isolation |
| `cancellation_reason` | TEXT | NULLABLE | Reason if cancelled |
| `rescheduled_reason` | TEXT | NULLABLE | Reason if rescheduled |
| `created_by` | VARCHAR(64) | NOT NULL | Creator user ID |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Creation timestamp |
| `updated_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Last update timestamp |
| `metadata` | JSONB | NOT NULL DEFAULT '{}' | Extensible attributes |

#### 2.3 Table: `review_participants`
Stores participant rosters, attendance records, authority flags, and conflict declarations.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `participant_id` | VARCHAR(64) | PRIMARY KEY | Unique identifier (`gmpt-uuid`) |
| `review_id` | VARCHAR(64) | NOT NULL, INDEXED | Foreign key to `management_reviews` |
| `user_id` | VARCHAR(64) | NOT NULL, INDEXED | Participant user ID |
| `user_name` | VARCHAR(255) | NULLABLE | Display name of participant |
| `role` | VARCHAR(64) | NOT NULL | Functional participant role |
| `attendance_status` | VARCHAR(32) | NOT NULL | Attendance status enum |
| `has_decision_authority` | BOOLEAN | NOT NULL DEFAULT FALSE | Explicit decision authority flag |
| `delegated_from_id` | VARCHAR(64) | NULLABLE | Delegation source user ID |
| `conflict_declared` | BOOLEAN | NOT NULL DEFAULT FALSE | Conflict flag |
| `conflict_details` | TEXT | NULLABLE | Conflict details |
| `attendance_confirmed_at` | TIMESTAMPTZ | NULLABLE | Confirmation timestamp |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Creation timestamp |
| `metadata` | JSONB | NOT NULL DEFAULT '{}' | Extensible attributes |

#### 2.4 Table: `review_agenda_items`
Stores structured review agenda topics.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `agenda_item_id` | VARCHAR(64) | PRIMARY KEY | Unique identifier (`gmai-uuid`) |
| `review_id` | VARCHAR(64) | NOT NULL, INDEXED | Foreign key to `management_reviews` |
| `title` | VARCHAR(255) | NOT NULL | Topic title |
| `description` | TEXT | NOT NULL | Topic description |
| `category` | VARCHAR(64) | NOT NULL, INDEXED | Agenda category enum |
| `priority` | VARCHAR(32) | NOT NULL | Urgency/priority enum |
| `discussion_status` | VARCHAR(32) | NOT NULL | Discussion progression enum |
| `presenter_id` | VARCHAR(64) | NULLABLE | Presenter user ID |
| `presenter_name` | VARCHAR(255) | NULLABLE | Presenter name |
| `allocated_minutes` | INTEGER | NOT NULL DEFAULT 15 | Allocated discussion time |
| `order` | INTEGER | NOT NULL DEFAULT 1 | Display/discussion order |
| `linked_sources` | JSONB | NOT NULL DEFAULT '[]' | Referenced evidence from Phases 49-71 |
| `metadata` | JSONB | NOT NULL DEFAULT '{}' | Extensible attributes |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Creation timestamp |
| `updated_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Last update timestamp |

#### 2.5 Table: `consolidated_review_inputs`
Indexes cross-phase evidence gathered for executive review.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `input_id` | VARCHAR(64) | PRIMARY KEY | Unique identifier (`gmin-uuid`) |
| `review_id` | VARCHAR(64) | NOT NULL, INDEXED | Foreign key to `management_reviews` |
| `source_phase` | VARCHAR(32) | NOT NULL, INDEXED | Originating phase (`PHASE_71`, etc.) |
| `source_id` | VARCHAR(64) | NOT NULL, INDEXED | Source record identifier |
| `source_type` | VARCHAR(64) | NOT NULL | Type of evidence |
| `summary` | TEXT | NOT NULL | Executive input summary |
| `details` | JSONB | NOT NULL DEFAULT '{}' | Raw input payload |
| `collected_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Indexing timestamp |
| `collected_by` | VARCHAR(64) | NOT NULL | Collector user ID |

#### 2.6 Table: `review_packages`
Stores reproducible, versioned review packages.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `package_id` | VARCHAR(64) | PRIMARY KEY | Unique identifier (`gmpk-uuid`) |
| `review_id` | VARCHAR(64) | NOT NULL, INDEXED | Foreign key to `management_reviews` |
| `version` | INTEGER | NOT NULL | Monotonically increasing version |
| `package_title` | VARCHAR(255) | NOT NULL | Review package title |
| `executive_summary` | TEXT | NOT NULL | Executive brief |
| `agenda_item_ids` | JSONB | NOT NULL DEFAULT '[]' | List of included agenda item IDs |
| `input_ids` | JSONB | NOT NULL DEFAULT '[]' | List of included input IDs |
| `status` | VARCHAR(32) | NOT NULL | `COMPILED` or `LOCKED` |
| `compiled_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Compilation timestamp |
| `compiled_by` | VARCHAR(64) | NOT NULL | Compiler user ID |
| `locked_at` | TIMESTAMPTZ | NULLABLE | Lock timestamp |
| `locked_by` | VARCHAR(64) | NULLABLE | Locker user ID |
| `metadata` | JSONB | NOT NULL DEFAULT '{}' | Extensible attributes |

#### 2.7 Table: `review_discussions`
Stores meeting discussion minutes and key discussion points.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `discussion_id` | VARCHAR(64) | PRIMARY KEY | Unique identifier (`gmds-uuid`) |
| `review_id` | VARCHAR(64) | NOT NULL, INDEXED | Foreign key to `management_reviews` |
| `agenda_item_id` | VARCHAR(64) | NULLABLE, INDEXED | Optional link to agenda topic |
| `speaker_id` | VARCHAR(64) | NOT NULL | Speaker user ID |
| `speaker_name` | VARCHAR(255) | NULLABLE | Speaker name |
| `topic` | VARCHAR(255) | NOT NULL | Discussion subject |
| `discussion_notes` | TEXT | NOT NULL | Recorded minutes |
| `key_points` | JSONB | NOT NULL DEFAULT '[]' | Bullet points/takeaways |
| `recorded_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Recording timestamp |
| `metadata` | JSONB | NOT NULL DEFAULT '{}' | Extensible attributes |

#### 2.8 Table: `management_decisions`
Stores authoritative executive governance decisions.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `decision_id` | VARCHAR(64) | PRIMARY KEY | Unique identifier (`gmdc-uuid`) |
| `review_id` | VARCHAR(64) | NOT NULL, INDEXED | Foreign key to `management_reviews` |
| `agenda_item_id` | VARCHAR(64) | NULLABLE, INDEXED | Link to agenda topic |
| `title` | VARCHAR(255) | NOT NULL | Decision title |
| `category` | VARCHAR(64) | NOT NULL, INDEXED | Decision category enum |
| `status` | VARCHAR(32) | NOT NULL, INDEXED | Status enum (`APPROVED`, `DEFERRED`, etc.) |
| `rationale` | TEXT | NOT NULL | Executive justification |
| `decided_by_id` | VARCHAR(64) | NOT NULL | Authoritative decider user ID |
| `decided_by_role` | VARCHAR(64) | NOT NULL | Role conferring authority |
| `decided_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Decision timestamp |
| `supporting_evidence_refs` | JSONB | NOT NULL DEFAULT '[]' | Supporting artifact references |
| `supersedes_decision_id` | VARCHAR(64) | NULLABLE, INDEXED | Prior decision being superseded |
| `superseded_by_id` | VARCHAR(64) | NULLABLE, INDEXED | Newer superseding decision ID |
| `superseded_reason` | TEXT | NULLABLE | Explanation of supersession |
| `commitments_count` | INTEGER | NOT NULL DEFAULT 0 | Count of assigned commitments |
| `organization_id` | VARCHAR(64) | NOT NULL, INDEXED | Tenant isolation |
| `facility_id` | VARCHAR(64) | NULLABLE, INDEXED | Facility isolation |
| `metadata` | JSONB | NOT NULL DEFAULT '{}' | Extensible attributes |

#### 2.9 Table: `management_commitments`
Stores actionable follow-through commitments.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `commitment_id` | VARCHAR(64) | PRIMARY KEY | Unique identifier (`gmcm-uuid`) |
| `decision_id` | VARCHAR(64) | NOT NULL, INDEXED | Foreign key to `management_decisions` |
| `review_id` | VARCHAR(64) | NOT NULL, INDEXED | Foreign key to `management_reviews` |
| `title` | VARCHAR(255) | NOT NULL | Action commitment title |
| `description` | TEXT | NOT NULL | Action description |
| `responsible_owner_id` | VARCHAR(64) | NOT NULL, INDEXED | Assigned executor user ID |
| `accountable_lead_id` | VARCHAR(64) | NOT NULL, INDEXED | Executive accountable lead |
| `status` | VARCHAR(32) | NOT NULL, INDEXED | Lifecycle status enum |
| `priority` | VARCHAR(32) | NOT NULL | Priority level enum |
| `due_date` | TIMESTAMPTZ | NOT NULL, INDEXED | Commitment due date |
| `progress_percentage` | INTEGER | NOT NULL DEFAULT 0 | Implementation completion percentage |
| `progress_notes` | JSONB | NOT NULL DEFAULT '[]' | History of progress updates |
| `completion_evidence_refs` | JSONB | NOT NULL DEFAULT '[]' | Evidence artifact references |
| `verified_by` | VARCHAR(64) | NULLABLE | Verifier user ID |
| `verified_at` | TIMESTAMPTZ | NULLABLE | Verification timestamp |
| `verification_notes` | TEXT | NULLABLE | Notes from formal verification |
| `linked_capa_id` | VARCHAR(64) | NULLABLE, INDEXED | Phase 54 CAPA link |
| `linked_effectiveness_id` | VARCHAR(64) | NULLABLE, INDEXED | Phase 55 effectiveness check link |
| `linked_risk_review_id` | VARCHAR(64) | NULLABLE, INDEXED | Phase 63 risk review link |
| `linked_escalation_id` | VARCHAR(64) | NULLABLE, INDEXED | Phase 67 exception escalation link |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Creation timestamp |
| `updated_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Last update timestamp |
| `metadata` | JSONB | NOT NULL DEFAULT '{}' | Extensible attributes |

#### 2.10 Table: `commitment_escalations`
Stores escalations of overdue or blocked commitments.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `escalation_id` | VARCHAR(64) | PRIMARY KEY | Unique identifier (`gmes-uuid`) |
| `commitment_id` | VARCHAR(64) | NOT NULL, INDEXED | Foreign key to `management_commitments` |
| `review_id` | VARCHAR(64) | NOT NULL, INDEXED | Foreign key to `management_reviews` |
| `escalated_by` | VARCHAR(64) | NOT NULL | Escalating user ID |
| `escalated_to` | VARCHAR(64) | NOT NULL | Target executive user ID |
| `escalation_reason` | TEXT | NOT NULL | Justification for escalation |
| `urgency` | VARCHAR(32) | NOT NULL DEFAULT 'HIGH' | Urgency tier |
| `escalated_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Escalation timestamp |
| `resolved_at` | TIMESTAMPTZ | NULLABLE | Resolution timestamp |
| `resolution_notes` | TEXT | NULLABLE | Resolution details |

#### 2.11 Table: `management_review_reports`
Stores executive summary reports and formal sign-offs.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `report_id` | VARCHAR(64) | PRIMARY KEY | Unique identifier (`gmrp-uuid`) |
| `review_id` | VARCHAR(64) | NOT NULL, INDEXED | Foreign key to `management_reviews` |
| `programme_id` | VARCHAR(64) | NOT NULL, INDEXED | Foreign key to `management_review_programmes` |
| `version` | INTEGER | NOT NULL DEFAULT 1 | Report version |
| `status` | VARCHAR(32) | NOT NULL, INDEXED | Report lifecycle status enum |
| `title` | VARCHAR(255) | NOT NULL | Report title |
| `executive_summary` | TEXT | NOT NULL | Executive brief |
| `attendees_summary` | JSONB | NOT NULL DEFAULT '[]' | Summary of attendees and roles |
| `agenda_summary` | JSONB | NOT NULL DEFAULT '[]' | Summary of agenda items |
| `key_decisions` | JSONB | NOT NULL DEFAULT '[]' | Summary of approved decisions |
| `commitments_assigned` | JSONB | NOT NULL DEFAULT '[]' | Summary of assigned commitments |
| `previous_actions_reconciliation` | JSONB | NOT NULL DEFAULT '[]' | Prior action reconciliation results |
| `prepared_by` | VARCHAR(64) | NOT NULL | Preparer user ID |
| `prepared_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Preparation timestamp |
| `approved_by` | VARCHAR(64) | NULLABLE | Approver user ID |
| `approved_at` | TIMESTAMPTZ | NULLABLE | Approval timestamp |
| `approval_notes` | TEXT | NULLABLE | Governance approval notes |
| `finalized_by` | VARCHAR(64) | NULLABLE | Finalizer user ID |
| `finalized_at` | TIMESTAMPTZ | NULLABLE | Finalization timestamp |
| `distribution_list` | JSONB | NOT NULL DEFAULT '[]' | Distribution recipients |
| `metadata` | JSONB | NOT NULL DEFAULT '{}' | Extensible attributes |
