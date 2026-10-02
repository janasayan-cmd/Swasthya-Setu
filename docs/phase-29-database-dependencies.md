# HealthSetu Phase 29: Database Dependencies & Team Contracts

## 1. Ownership & Boundary Principles

In accordance with HealthSetu's architectural guidelines:
- **Backend Team Owns**: Instrumentation, event schemas, validation, template rendering, provider adapters, and repository abstractions (`NotificationRepository`, `NotificationDeliveryRepository`, `NotificationPreferenceRepository`).
- **Database Team Owns**: PostgreSQL schema definitions, table creation, indexes, foreign keys, partition strategy, and database-level retention triggers.

Backend code consumes the repository abstractions and does NOT unilaterally alter production database schemas.

---

## 2. Proposed Database Schema Contracts (For DB Team Review)

The following tables are proposed for PostgreSQL implementation to persist Phase 29 notification and communication records:

### 1. `notifications`
Stores notification records and user inbox status.

```sql
CREATE TABLE notifications (
    id VARCHAR(64) PRIMARY KEY,
    recipient_id VARCHAR(128) NOT NULL,
    notification_type VARCHAR(64) NOT NULL,
    category VARCHAR(32) NOT NULL,
    priority VARCHAR(16) NOT NULL DEFAULT 'NORMAL',
    status VARCHAR(32) NOT NULL DEFAULT 'CREATED',
    title VARCHAR(255) NOT NULL,
    body TEXT NOT NULL,
    channels JSONB NOT NULL DEFAULT '[]'::jsonb,
    resource_type VARCHAR(64),
    resource_id VARCHAR(128),
    idempotency_key VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    read_at TIMESTAMPTZ,
    dismissed_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX idx_notifications_recipient_inbox ON notifications (recipient_id, created_at DESC) WHERE dismissed_at IS NULL;
CREATE INDEX idx_notifications_idempotency ON notifications (idempotency_key);
CREATE INDEX idx_notifications_retention ON notifications (created_at);
```

### 2. `notification_deliveries`
Tracks physical dispatches and upstream gateway delivery receipts.

```sql
CREATE TABLE notification_deliveries (
    id VARCHAR(64) PRIMARY KEY,
    notification_id VARCHAR(64) NOT NULL REFERENCES notifications(id) ON DELETE CASCADE,
    channel VARCHAR(16) NOT NULL,
    recipient_target VARCHAR(255) NOT NULL,
    provider VARCHAR(64) NOT NULL,
    provider_message_id VARCHAR(128),
    status VARCHAR(32) NOT NULL DEFAULT 'QUEUED',
    retry_count INT NOT NULL DEFAULT 0,
    max_retries INT NOT NULL DEFAULT 3,
    last_error TEXT,
    error_category VARCHAR(64),
    sent_at TIMESTAMPTZ,
    delivered_at TIMESTAMPTZ,
    failed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX idx_deliveries_notification ON notification_deliveries (notification_id);
CREATE INDEX idx_deliveries_status ON notification_deliveries (status, updated_at DESC);
```

### 3. `notification_preferences`
Stores recipient communication channels, localization, and quiet hour schedules.

```sql
CREATE TABLE notification_preferences (
    user_id VARCHAR(128) PRIMARY KEY,
    email_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    sms_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    push_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    in_app_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    language VARCHAR(10) NOT NULL DEFAULT 'en',
    clinical_notifications_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    operational_notifications_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    reminders_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    quiet_hours_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    quiet_hours_start_utc VARCHAR(5) DEFAULT '22:00',
    quiet_hours_end_utc VARCHAR(5) DEFAULT '07:00',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```
