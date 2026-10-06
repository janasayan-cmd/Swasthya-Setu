# Database Team Dependencies — Phase 50: Clinical Safety Learning & Trend Analysis

## Document Type
Database Schema Specification & Handoff Contract

## Database Ownership
The database teammate owns all PostgreSQL schemas, indexes, foreign keys, migrations, aggregate persistence, and concurrency rules.
The backend teammate strictly consumes the agreed schema via repository abstractions and does not invent competing databases or tables.

---

## 1. Required Tables

### 1.1 `safety_learning_analysis_jobs`
Tracks execution and parameters of historical safety learning analysis jobs.

| Column | Type | Constraints / Description |
|---|---|---|
| `id` | VARCHAR(64) | PRIMARY KEY (`sl-job-...`) |
| `analysis_type` | VARCHAR(64) | NOT NULL (`INCIDENT_TREND`, `INCIDENT_RECURRENCE`, `PROVIDER_FAILURE_TREND`, etc.) |
| `scope_type` | VARCHAR(64) | NOT NULL (`GLOBAL_SYSTEM`, `ORGANIZATION`, `WORKFLOW_VERSION`, `PROVIDER`, etc.) |
| `scope_id` | VARCHAR(128) | NULLABLE |
| `start_time` | TIMESTAMPTZ | NOT NULL |
| `end_time` | TIMESTAMPTZ | NOT NULL |
| `requested_by_id` | VARCHAR(64) | NOT NULL |
| `requested_by_role` | VARCHAR(64) | NOT NULL |
| `organization_id` | VARCHAR(64) | NULLABLE (Indexed for tenant isolation) |
| `status` | VARCHAR(32) | NOT NULL DEFAULT `'REQUESTED'` (`REQUESTED`, `RUNNING`, `COMPLETED`, `FAILED`, `PARTIAL`) |
| `filters` | JSONB | NOT NULL DEFAULT `'{}'` |
| `idempotency_key` | VARCHAR(128) | NULLABLE (Unique index) |
| `error_message` | TEXT | NULLABLE |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT CURRENT_TIMESTAMP |
| `updated_at` | TIMESTAMPTZ | NOT NULL DEFAULT CURRENT_TIMESTAMP |

**Recommended Indexes**:
- `CREATE UNIQUE INDEX idx_safety_learning_jobs_idempotency ON safety_learning_analysis_jobs (idempotency_key) WHERE idempotency_key IS NOT NULL;`
- `CREATE INDEX idx_safety_learning_jobs_org ON safety_learning_analysis_jobs (organization_id);`

---

### 1.2 `safety_learning_analysis_results`
Stores authoritative analytical metrics, discovered pattern references, and limitation disclosures.

| Column | Type | Constraints / Description |
|---|---|---|
| `id` | VARCHAR(64) | PRIMARY KEY (`sl-res-...`) |
| `analysis_id` | VARCHAR(64) | NOT NULL REFERENCES `safety_learning_analysis_jobs(id)` (Unique) |
| `analysis_type` | VARCHAR(64) | NOT NULL |
| `scope_type` | VARCHAR(64) | NOT NULL |
| `scope_id` | VARCHAR(128) | NULLABLE |
| `status` | VARCHAR(32) | NOT NULL DEFAULT `'COMPLETED'` |
| `metrics` | JSONB | NOT NULL DEFAULT `'[]'` (Array of `{metric_name, count, denominator, rate, rate_available}`) |
| `detected_pattern_ids` | TEXT[] | NOT NULL DEFAULT ARRAY[]::TEXT[] |
| `generated_recommendation_ids` | TEXT[] | NOT NULL DEFAULT ARRAY[]::TEXT[] |
| `evidence_count` | INT | NOT NULL DEFAULT 0 |
| `sources_included` | TEXT[] | NOT NULL DEFAULT ARRAY[]::TEXT[] |
| `sources_unavailable` | TEXT[] | NOT NULL DEFAULT ARRAY[]::TEXT[] |
| `is_complete` | BOOLEAN | NOT NULL DEFAULT TRUE |
| `limitations` | TEXT[] | NOT NULL DEFAULT ARRAY[]::TEXT[] |
| `version` | VARCHAR(16) | NOT NULL DEFAULT `'1.0'` |
| `generated_at` | TIMESTAMPTZ | NOT NULL DEFAULT CURRENT_TIMESTAMP |

**Recommended Indexes**:
- `CREATE INDEX idx_safety_learning_results_analysis ON safety_learning_analysis_results (analysis_id);`

---

### 1.3 `safety_learning_patterns`
Tracks candidate recurring safety patterns.

| Column | Type | Constraints / Description |
|---|---|---|
| `id` | VARCHAR(64) | PRIMARY KEY (`pat-...`) |
| `title` | VARCHAR(255) | NOT NULL |
| `description` | TEXT | NOT NULL |
| `pattern_type` | VARCHAR(64) | NOT NULL |
| `state` | VARCHAR(32) | NOT NULL DEFAULT `'CANDIDATE'` (`CANDIDATE`, `UNDER_REVIEW`, `SUPPORTED`, `REJECTED`, `EXPIRED`) |
| `occurrence_count` | INT | NOT NULL |
| `evidence_references` | JSONB | NOT NULL DEFAULT `'[]'` (References to incidents/decisions/signals) |
| `affected_subsystem` | VARCHAR(64) | NOT NULL |
| `correlation_signature` | VARCHAR(255) | NULLABLE |
| `observation_window_start` | TIMESTAMPTZ | NOT NULL |
| `observation_window_end` | TIMESTAMPTZ | NOT NULL |
| `detected_at` | TIMESTAMPTZ | NOT NULL DEFAULT CURRENT_TIMESTAMP |
| `updated_at` | TIMESTAMPTZ | NOT NULL DEFAULT CURRENT_TIMESTAMP |

---

### 1.4 `safety_learning_recommendations`
Stores preventive risk improvement recommendations and human review records.

| Column | Type | Constraints / Description |
|---|---|---|
| `id` | VARCHAR(64) | PRIMARY KEY (`rec-...`) |
| `analysis_id` | VARCHAR(64) | NULLABLE REFERENCES `safety_learning_analysis_jobs(id)` |
| `pattern_id` | VARCHAR(64) | NULLABLE REFERENCES `safety_learning_patterns(id)` |
| `recommendation_type` | VARCHAR(64) | NOT NULL (`STRENGTHEN_SAFETY_GATE`, `ADD_VALIDATION_RULE`, `REQUIRE_HUMAN_REVIEW`, etc.) |
| `title` | VARCHAR(255) | NOT NULL |
| `description` | TEXT | NOT NULL |
| `rationale_summary` | TEXT | NOT NULL (Structured summary; no raw chain-of-thought) |
| `affected_subsystem` | VARCHAR(64) | NOT NULL |
| `status` | VARCHAR(32) | NOT NULL DEFAULT `'REVIEW_REQUIRED'` (`REVIEW_REQUIRED`, `UNDER_REVIEW`, `ACCEPTED`, `REJECTED`, `STALE`, `DEFERRED`) |
| `evidence_references` | JSONB | NOT NULL DEFAULT `'[]'` |
| `limitations` | TEXT[] | NOT NULL DEFAULT ARRAY[]::TEXT[] |
| `reviewed_by_id` | VARCHAR(64) | NULLABLE |
| `reviewed_by_role` | VARCHAR(64) | NULLABLE |
| `reviewed_at` | TIMESTAMPTZ | NULLABLE |
| `review_notes` | TEXT | NULLABLE |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT CURRENT_TIMESTAMP |
| `updated_at` | TIMESTAMPTZ | NOT NULL DEFAULT CURRENT_TIMESTAMP |
| `version` | VARCHAR(16) | NOT NULL DEFAULT `'1.0'` |

---

### 1.5 `corrective_action_effectiveness`
Tracks empirical post-implementation observation of Phase 49 corrective actions.

| Column | Type | Constraints / Description |
|---|---|---|
| `id` | VARCHAR(64) | PRIMARY KEY (`eff-...`) |
| `action_id` | VARCHAR(64) | NOT NULL (Phase 49 corrective action ID) |
| `incident_id` | VARCHAR(64) | NOT NULL (Phase 49 incident ID) |
| `state` | VARCHAR(32) | NOT NULL DEFAULT `'NOT_EVALUATED'` (`NOT_EVALUATED`, `PENDING_OBSERVATION`, `NO_RECURRENCE_OBSERVED`, `RECURRENCE_OBSERVED`, `PARTIAL_IMPROVEMENT`) |
| `observation_start` | TIMESTAMPTZ | NOT NULL |
| `observation_end` | TIMESTAMPTZ | NOT NULL |
| `pre_implementation_count` | INT | NOT NULL DEFAULT 1 |
| `post_implementation_count` | INT | NOT NULL DEFAULT 0 |
| `subsequent_incident_ids` | TEXT[] | NOT NULL DEFAULT ARRAY[]::TEXT[] |
| `summary` | TEXT | NOT NULL |
| `limitations` | TEXT[] | NOT NULL DEFAULT ARRAY[]::TEXT[] |
| `evaluated_at` | TIMESTAMPTZ | NOT NULL DEFAULT CURRENT_TIMESTAMP |
