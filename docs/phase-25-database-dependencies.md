# HealthSetu — Phase 25: Database Dependencies & Team Boundaries

## 1. Architectural Boundary (Backend vs. Database Team)

In accordance with HealthSetu architectural principles, the backend team owns runtime configuration validation, feature flag evaluation, rollout algorithms, and API contracts.

The database team owns persistent database schemas, migrations, indexes, and historical change tables.

**The backend team does NOT create database-owned migrations or duplicate competing schemas.**

---

## 2. Requirements for the Database Team

If persistent configuration storage is selected for multi-node synchronization, the database team will maintain the following relational schema:

### Table: `feature_flags`
- `id` (UUID, Primary Key)
- `name` (VARCHAR(128), Unique, Indexed)
- `category` (VARCHAR(64), Indexed)
- `state` (VARCHAR(32), Default 'ENABLED')
- `lifecycle` (VARCHAR(32), Default 'ACTIVE')
- `default_enabled` (BOOLEAN, Default TRUE)
- `owner` (VARCHAR(128))
- `percentage` (INT, Nullable, CHECK 0 <= percentage <= 100)
- `allowlist_users` (JSONB / ARRAY)
- `allowlist_organizations` (JSONB / ARRAY)
- `allowlist_facilities` (JSONB / ARRAY)
- `environments` (JSONB / ARRAY)
- `dependencies` (JSONB / ARRAY)
- `created_at` (TIMESTAMPTZ, Default NOW())
- `updated_at` (TIMESTAMPTZ, Default NOW())

### Table: `feature_flag_audit_history`
- `id` (UUID, Primary Key)
- `flag_name` (VARCHAR(128), Indexed)
- `actor_id` (UUID, Indexed)
- `action` (VARCHAR(64))
- `previous_state` (VARCHAR(32))
- `new_state` (VARCHAR(32))
- `reason` (TEXT)
- `metadata` (JSONB)
- `created_at` (TIMESTAMPTZ, Default NOW())

### Table: `kill_switches`
- `name` (VARCHAR(128), Primary Key)
- `is_active` (BOOLEAN, Default FALSE, Indexed)
- `category` (VARCHAR(64))
- `activated_by` (UUID, Nullable)
- `activated_at` (TIMESTAMPTZ, Nullable)
- `reason` (TEXT, Nullable)
- `updated_at` (TIMESTAMPTZ, Default NOW())

---

## 3. Recommended Indexes
- `idx_feature_flags_name`: Unique B-Tree index on `feature_flags(name)`.
- `idx_feature_flags_category`: B-Tree index on `feature_flags(category)`.
- `idx_kill_switches_active`: Filtered index on `kill_switches(name) WHERE is_active = TRUE`.
