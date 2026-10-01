# HealthSetu Phase 28: Database Dependencies & Team Contracts

## 1. Ownership & Boundary Principles

In accordance with HealthSetu's architectural guidelines:
- **Backend Team Owns**: Instrumentation, event schemas, validation, aggregation logic, anomaly evaluation, and repository abstractions.
- **Database Team Owns**: PostgreSQL schema definitions, table creation, indexes, foreign keys, partition strategy, and database-level retention triggers.

Backend code consumes the repository abstraction (`AnalyticsRepository`) and does NOT unilaterally alter production database schemas.

---

## 2. Proposed Database Schema Contracts (For DB Team Review)

The following tables are proposed for PostgreSQL implementation to persist Phase 28 analytics data efficiently at scale:

### 1. `analytics_events` (Partitioned by Month)
Stores sanitized raw telemetry events for the duration of the retention window.

```sql
CREATE TABLE analytics_events (
    event_id UUID PRIMARY KEY,
    event_type VARCHAR(64) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    environment VARCHAR(32) NOT NULL,
    service VARCHAR(64) NOT NULL,
    api_version VARCHAR(16) NOT NULL DEFAULT 'v1',
    endpoint_template VARCHAR(255),
    http_method VARCHAR(16),
    status_code INT,
    duration_ms DOUBLE PRECISION,
    request_id VARCHAR(64),
    correlation_id VARCHAR(64),
    user_category VARCHAR(32),
    organization_id VARCHAR(64),
    facility_id VARCHAR(64),
    feature_name VARCHAR(64),
    provider_name VARCHAR(64),
    job_type VARCHAR(64),
    job_status VARCHAR(32),
    resource_type VARCHAR(64),
    result_category VARCHAR(32),
    error_category VARCHAR(64),
    metadata JSONB DEFAULT '{}'::jsonb
) PARTITION BY RANGE (timestamp);

CREATE INDEX idx_analytics_events_query ON analytics_events (timestamp DESC, endpoint_template, status_code);
CREATE INDEX idx_analytics_events_org ON analytics_events (organization_id, facility_id, timestamp DESC);
```

### 2. `operational_anomalies`
Stores lifecycle records of detected operational anomalies.

```sql
CREATE TABLE operational_anomalies (
    anomaly_id UUID PRIMARY KEY,
    anomaly_type VARCHAR(64) NOT NULL,
    severity VARCHAR(32) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'DETECTED',
    title VARCHAR(255) NOT NULL,
    description TEXT,
    detected_at TIMESTAMPTZ NOT NULL,
    acknowledged_at TIMESTAMPTZ,
    acknowledged_by VARCHAR(64),
    resolved_at TIMESTAMPTZ,
    resolution_notes TEXT,
    metric_name VARCHAR(64),
    current_value DOUBLE PRECISION,
    threshold_value DOUBLE PRECISION,
    baseline_value DOUBLE PRECISION,
    deviation_percent DOUBLE PRECISION,
    endpoint VARCHAR(255),
    provider_name VARCHAR(64),
    metrics JSONB DEFAULT '{}'::jsonb,
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX idx_anomalies_status ON operational_anomalies (status, detected_at DESC);
```
