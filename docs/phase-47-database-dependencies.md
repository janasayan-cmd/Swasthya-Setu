# HealthSetu — Phase 47: Database Dependencies & Shared Architecture Contract

## 1. Division of Ownership

### DB Teammate Owns:
- Tables: `clinical_decisions`, `decision_inputs`, `decision_reviews`, `decision_actions`
- Schema constraints, foreign keys, indexes, migrations
- Uniqueness constraints and temporal indexes
- Database-level concurrency and query optimization for decision trace lookups

### Backend Teammate Owns:
- Decision lifecycle orchestration, validation, and staleness detection
- Human review gates, approval/rejection logic, and oversight enforcement
- Audience-tailored explanation generation (patient vs clinician)
- Audit event emission (Phase 15/47 `AuditEventType`) and error handling
- Concurrency and idempotency handling on decision mutations

---

## 2. Table Contracts & Schemas

### A. Clinical Decisions Table (`clinical_decisions`)
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | VARCHAR(64) | PRIMARY KEY | Unique decision ID (`dec-...`) |
| `decision_type` | VARCHAR(64) | NOT NULL | Type e.g. `TRIAGE_CLASSIFICATION`, `MEDICATION_SAFETY_WARNING` |
| `patient_id` | UUID | NOT NULL | Foreign key to `patients(id)` |
| `resource_type` | VARCHAR(64) | NULL | Target resource type e.g. `medication` |
| `resource_id` | UUID | NULL | Target resource ID |
| `resource_version` | INTEGER | NULL | Version evaluated at decision time (Phase 46) |
| `status` | VARCHAR(32) | NOT NULL | Lifecycle state (`GENERATED`, `REVIEW_REQUIRED`, `APPROVED`, etc.) |
| `initiating_actor_id` | VARCHAR(64) | NOT NULL | Initiator ID |
| `initiating_actor_role` | VARCHAR(64) | NOT NULL | Role of initiator |
| `initiating_actor_type` | VARCHAR(32) | NOT NULL | Enum: `SYSTEM`, `RULE_ENGINE`, `AI_MODEL`, etc. |
| `source_service` | VARCHAR(64) | NOT NULL | Producing subsystem |
| `output_payload` | JSONB | NOT NULL | Recommendation or classification payload |
| `rule_metadata` | JSONB | NULL | Rule set, version, and matched rule IDs |
| `model_metadata` | JSONB | NULL | Provider, model, prompt/schema versions, confidence |
| `requires_human_oversight` | BOOLEAN | NOT NULL, DEFAULT FALSE | Gate requirement flag |
| `is_current` | BOOLEAN | NOT NULL, DEFAULT TRUE | False if superseded or cancelled |
| `superseded_by_id` | VARCHAR(64) | NULL | Replacement decision ID |
| `supersedes_id` | VARCHAR(64) | NULL | Prior decision ID replaced |
| `downstream_action_type` | VARCHAR(64) | NULL | Triggered action type |
| `downstream_action_id` | VARCHAR(64) | NULL | Triggered action ID |
| `applied_at` | TIMESTAMPTZ | NULL | Application timestamp |
| `expires_at` | TIMESTAMPTZ | NULL | Expiration timestamp |
| `idempotency_key` | VARCHAR(128) | NULL | Client idempotency key |
| `created_at` | TIMESTAMPTZ | NOT NULL | Creation timestamp |
| `updated_at` | TIMESTAMPTZ | NOT NULL | Last update timestamp |

### B. Decision Reviews Table (`decision_reviews`)
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | VARCHAR(64) | PRIMARY KEY | Review record ID (`rev-...`) |
| `decision_id` | VARCHAR(64) | NOT NULL | Reference to `clinical_decisions(id)` |
| `reviewer_id` | VARCHAR(64) | NOT NULL | Clinician user ID |
| `reviewer_role` | VARCHAR(64) | NOT NULL | Clinician role |
| `action` | VARCHAR(32) | NOT NULL | `APPROVED`, `REJECTED`, `MODIFIED`, etc. |
| `review_reason` | TEXT | NOT NULL | Clinical justification |
| `previous_status` | VARCHAR(32) | NOT NULL | Prior status |
| `resulting_status` | VARCHAR(32) | NOT NULL | New status |
| `modifications` | JSONB | NULL | Applied modifications if modified |
| `reviewed_at` | TIMESTAMPTZ | NOT NULL | Review timestamp |

### C. Indexes & Constraints
```sql
CREATE INDEX idx_decisions_patient 
ON clinical_decisions(patient_id, created_at DESC);

CREATE INDEX idx_decisions_resource 
ON clinical_decisions(resource_type, resource_id, created_at DESC);

CREATE INDEX idx_decisions_status 
ON clinical_decisions(status) WHERE is_current = TRUE;

CREATE INDEX idx_decision_reviews_decision 
ON decision_reviews(decision_id, reviewed_at ASC);
```
