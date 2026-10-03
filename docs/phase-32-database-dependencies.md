# Phase 32: Database Dependencies & Team Ownership Boundaries

## 1. Team Ownership Boundaries

### Database Team Owns:
- Physical schema creation, table migrations, and DDL scripts.
- Relational tables: `billable_events`, `invoices`, `billing_items`, `payment_transactions`, `refunds`, `webhook_events`, `reconciliation_records`.
- Unique indexes (`idempotency_key`, `provider:event_id`, `invoice_number`, `payment_number`).
- Row-level locking primitives and database foreign key constraints.
- Financial audit trail persistence and database backup/restore strategies.

### Backend Team Owns:
- REST API contracts, FastAPI routers, and OpenAPI specifications.
- Deterministic calculation logic (integer minor units, line item aggregation).
- External payment gateway adapters (HTTP clients, HMAC signature verification).
- Webhook deduplication logic and event replay protection.
- Authorization barriers (BOLA/IDOR protection, multi-tenant facility scoping).
- Notification dispatch and asynchronous job scheduling.

---

## 2. Expected Database Contract & Schema Models

### A. Invoices Table (`invoices`)
```sql
CREATE TABLE invoices (
    id VARCHAR(64) PRIMARY KEY,
    invoice_number VARCHAR(64) UNIQUE NOT NULL,
    patient_id VARCHAR(128) NOT NULL,
    organization_id VARCHAR(128),
    facility_id VARCHAR(128),
    status VARCHAR(32) NOT NULL DEFAULT 'DRAFT',
    currency VARCHAR(3) NOT NULL DEFAULT 'INR',
    subtotal_in_minor_units BIGINT NOT NULL DEFAULT 0,
    tax_in_minor_units BIGINT NOT NULL DEFAULT 0,
    discount_in_minor_units BIGINT NOT NULL DEFAULT 0,
    total_in_minor_units BIGINT NOT NULL DEFAULT 0,
    amount_paid_in_minor_units BIGINT NOT NULL DEFAULT 0,
    amount_refunded_in_minor_units BIGINT NOT NULL DEFAULT 0,
    outstanding_amount_in_minor_units BIGINT NOT NULL DEFAULT 0,
    notes TEXT,
    issued_at TIMESTAMPTZ,
    due_at TIMESTAMPTZ,
    paid_at TIMESTAMPTZ,
    cancelled_at TIMESTAMPTZ,
    cancellation_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### B. Billing Items Table (`billing_items`)
```sql
CREATE TABLE billing_items (
    id VARCHAR(64) PRIMARY KEY,
    invoice_id VARCHAR(64) NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    description VARCHAR(255) NOT NULL,
    category VARCHAR(64) NOT NULL DEFAULT 'SERVICE',
    unit_price_in_minor_units BIGINT NOT NULL,
    quantity INT NOT NULL DEFAULT 1,
    tax_in_minor_units BIGINT NOT NULL DEFAULT 0,
    discount_in_minor_units BIGINT NOT NULL DEFAULT 0,
    total_in_minor_units BIGINT NOT NULL,
    currency VARCHAR(3) NOT NULL DEFAULT 'INR',
    billable_event_id VARCHAR(64),
    appointment_id VARCHAR(128),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### C. Payment Transactions Table (`payment_transactions`)
```sql
CREATE TABLE payment_transactions (
    id VARCHAR(64) PRIMARY KEY,
    payment_number VARCHAR(64) UNIQUE NOT NULL,
    invoice_id VARCHAR(64) NOT NULL REFERENCES invoices(id),
    patient_id VARCHAR(128) NOT NULL,
    organization_id VARCHAR(128),
    facility_id VARCHAR(128),
    amount_in_minor_units BIGINT NOT NULL,
    amount_refunded_in_minor_units BIGINT NOT NULL DEFAULT 0,
    currency VARCHAR(3) NOT NULL DEFAULT 'INR',
    status VARCHAR(32) NOT NULL DEFAULT 'PENDING',
    payment_method VARCHAR(32) NOT NULL DEFAULT 'UPI',
    provider_name VARCHAR(64) NOT NULL DEFAULT 'MOCK',
    provider_transaction_id VARCHAR(255),
    provider_order_id VARCHAR(255),
    provider_status VARCHAR(64),
    idempotency_key VARCHAR(255) UNIQUE,
    error_code VARCHAR(64),
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    failed_at TIMESTAMPTZ
);
```

### D. Refunds Table (`refunds`)
```sql
CREATE TABLE refunds (
    id VARCHAR(64) PRIMARY KEY,
    refund_number VARCHAR(64) UNIQUE NOT NULL,
    payment_id VARCHAR(64) NOT NULL REFERENCES payment_transactions(id),
    invoice_id VARCHAR(64) NOT NULL REFERENCES invoices(id),
    patient_id VARCHAR(128) NOT NULL,
    organization_id VARCHAR(128),
    facility_id VARCHAR(128),
    amount_in_minor_units BIGINT NOT NULL,
    currency VARCHAR(3) NOT NULL DEFAULT 'INR',
    status VARCHAR(32) NOT NULL DEFAULT 'REQUESTED',
    reason TEXT NOT NULL,
    provider_name VARCHAR(64) NOT NULL DEFAULT 'MOCK',
    provider_refund_id VARCHAR(255),
    provider_status VARCHAR(64),
    idempotency_key VARCHAR(255) UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    failed_at TIMESTAMPTZ
);
```
