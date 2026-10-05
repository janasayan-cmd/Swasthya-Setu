# Phase 41: Clinical Communication Database Dependencies & Schema Contract

## Database Team Ownership Boundary

In accordance with HealthSetu system architecture:
- The **Database Team** owns all database tables, schemas, migrations, indexes, constraints, and foreign key relationships.
- The **Backend Team** provides this dependency contract and consumes the persistence interface via repositories.
- The backend does NOT create competing SQLAlchemy models in `app/models/`.

---

## 1. Entities & Schema Specification

### 1.1 `conversations` Table
| Column Name | PostgreSQL Type | Nullable | Description & Constraints |
| :--- | :--- | :--- | :--- |
| `id` | `VARCHAR(64)` | `NOT NULL` | Primary Key (e.g. `conv-uuid`) |
| `patient_id` | `VARCHAR(64)` | `NOT NULL` | Foreign Key → `patients(id)` |
| `category` | `VARCHAR(50)` | `NOT NULL` | Enum: `PATIENT_CLINICIAN`, `PATIENT_CARE_TEAM`, `CLINICIAN_CARE_TEAM`, `CLINICAL_FOLLOW_UP`, etc. |
| `subject` | `VARCHAR(255)` | `NOT NULL` | Brief subject title |
| `status` | `VARCHAR(32)` | `NOT NULL` | Enum: `CREATED`, `ACTIVE`, `PAUSED`, `CLOSED`, `ARCHIVED`, `LOCKED` |
| `organization_id`| `VARCHAR(64)` | `NULL` | Foreign Key → `organizations(id)` |
| `facility_id` | `VARCHAR(64)` | `NULL` | Foreign Key → `facilities(id)` |
| `encounter_id` | `VARCHAR(64)` | `NULL` | Optional link to encounter |
| `created_by` | `VARCHAR(64)` | `NOT NULL` | User ID of creator |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL` | Defaults to `NOW()` |
| `updated_at` | `TIMESTAMPTZ` | `NOT NULL` | Defaults to `NOW()` |
| `closed_at` | `TIMESTAMPTZ` | `NULL` | Timestamp of closure |
| `closed_by` | `VARCHAR(64)` | `NULL` | User ID who closed |
| `close_reason` | `TEXT` | `NULL` | Operational reason |
| `total_messages`| `INTEGER` | `NOT NULL` | Default 0 |
| `last_message_at`| `TIMESTAMPTZ` | `NULL` | Timestamp of last message |
| `metadata` | `JSONB` | `NULL` | Supplementary non-PHI metadata |

**Indexes**:
- `idx_conversations_patient_id` on `(patient_id)`
- `idx_conversations_org_fac` on `(organization_id, facility_id)`
- `idx_conversations_status` on `(status)`
- `idx_conversations_updated_at` on `(updated_at DESC)`

---

### 1.2 `conversation_participants` Table
| Column Name | PostgreSQL Type | Nullable | Description & Constraints |
| :--- | :--- | :--- | :--- |
| `participant_id` | `VARCHAR(64)` | `NOT NULL` | Primary Key |
| `conversation_id`| `VARCHAR(64)` | `NOT NULL` | Foreign Key → `conversations(id)` ON DELETE CASCADE |
| `user_id` | `VARCHAR(64)` | `NOT NULL` | Foreign Key → `users(id)` |
| `role` | `VARCHAR(32)` | `NOT NULL` | `PATIENT`, `CLINICIAN`, `CARE_TEAM_MEMBER`, `ORGANIZATION_ADMIN`, `SUPPORT_AGENT`, `SYSTEM` |
| `organization_id`| `VARCHAR(64)` | `NULL` | Organization boundary |
| `facility_id` | `VARCHAR(64)` | `NULL` | Facility boundary |
| `display_name` | `VARCHAR(255)` | `NULL` | Safe display name |
| `joined_at` | `TIMESTAMPTZ` | `NOT NULL` | Default `NOW()` |
| `left_at` | `TIMESTAMPTZ` | `NULL` | Timestamp when user left |
| `is_active` | `BOOLEAN` | `NOT NULL` | Default `TRUE` |

**Constraints & Indexes**:
- `UNIQUE(conversation_id, user_id)` (where `is_active = TRUE`)
- `idx_conv_participants_user` on `(user_id, is_active)`
- `idx_conv_participants_conv` on `(conversation_id)`

---

### 1.3 `messages` Table
| Column Name | PostgreSQL Type | Nullable | Description & Constraints |
| :--- | :--- | :--- | :--- |
| `id` | `VARCHAR(64)` | `NOT NULL` | Primary Key |
| `conversation_id`| `VARCHAR(64)` | `NOT NULL` | Foreign Key → `conversations(id)` ON DELETE CASCADE |
| `sender_id` | `VARCHAR(64)` | `NOT NULL` | Foreign Key → `users(id)` |
| `sender_role` | `VARCHAR(32)` | `NOT NULL` | Role of sender |
| `message_type` | `VARCHAR(32)` | `NOT NULL` | `TEXT`, `DOCUMENT_REFERENCE`, `TASK_REFERENCE`, etc. |
| `content` | `TEXT` | `NOT NULL` | Raw text content (max 10,000 characters) |
| `reply_to_id` | `VARCHAR(64)` | `NULL` | Foreign Key → `messages(id)` |
| `attachments` | `JSONB` | `NULL` | Array of attachment reference objects |
| `status` | `VARCHAR(32)` | `NOT NULL` | `CREATED`, `QUEUED`, `PROCESSING`, `SENT`, `DELIVERED`, `READ`, `ACKNOWLEDGED`, `FAILED` |
| `idempotency_key`| `VARCHAR(128)` | `NULL` | Unique per conversation / sender |
| `provider` | `VARCHAR(64)` | `NULL` | Provider adapter name |
| `provider_msg_id`| `VARCHAR(128)` | `NULL` | Provider external message ID |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL` | Default `NOW()` |
| `sent_at` | `TIMESTAMPTZ` | `NULL` | Time accepted by provider |
| `delivered_at` | `TIMESTAMPTZ` | `NULL` | Time confirmed delivered to device |
| `read_at` | `TIMESTAMPTZ` | `NULL` | Time read |
| `read_by` | `JSONB` | `NOT NULL` | Array of user IDs who opened message |
| `acknowledged_at`| `TIMESTAMPTZ` | `NULL` | Clinician formal acknowledgment |
| `acknowledged_by`| `VARCHAR(64)` | `NULL` | Clinician user ID |
| `retry_count` | `INTEGER` | `NOT NULL` | Default 0 |
| `failure_reason` | `TEXT` | `NULL` | Provider error message |
| `is_ai_draft` | `BOOLEAN` | `NOT NULL` | Default `FALSE` |
| `ai_approved` | `BOOLEAN` | `NOT NULL` | Default `FALSE` |
| `translations` | `JSONB` | `NULL` | Keyed by language code |
| `metadata` | `JSONB` | `NULL` | Non-PHI operational metadata |

**Constraints & Indexes**:
- `UNIQUE(idempotency_key)` (where `idempotency_key IS NOT NULL`)
- `idx_messages_conversation_created` on `(conversation_id, created_at ASC)`
- `idx_messages_sender_id` on `(sender_id)`
- `idx_messages_status` on `(status)`

---

### 1.4 `message_delivery_history` Table
| Column Name | PostgreSQL Type | Nullable | Description & Constraints |
| :--- | :--- | :--- | :--- |
| `id` | `VARCHAR(64)` | `NOT NULL` | Primary Key |
| `message_id` | `VARCHAR(64)` | `NOT NULL` | Foreign Key → `messages(id)` ON DELETE CASCADE |
| `provider` | `VARCHAR(64)` | `NULL` | Provider name |
| `previous_status`| `VARCHAR(32)` | `NULL` | Status prior to transition |
| `new_status` | `VARCHAR(32)` | `NOT NULL` | Status post transition |
| `reason` | `TEXT` | `NULL` | Description / error reason |
| `event_id` | `VARCHAR(128)` | `NULL` | External webhook event ID |
| `timestamp` | `TIMESTAMPTZ` | `NOT NULL` | Default `NOW()` |

**Indexes**:
- `idx_del_history_message` on `(message_id, timestamp ASC)`
- `idx_del_history_event_id` on `(event_id)` (Replay prevention)
