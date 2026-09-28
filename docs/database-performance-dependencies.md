# HealthSetu — Database Performance Dependencies & Coordination Contract

## 1. Overview & Team Boundary Contract (Section 3, 65)

This document establishes the performance expectations, connection constraints, query access patterns, and critical database indexes required by the Backend Team from the Database Team.

> **CRITICAL BOUNDARY:** The Backend Team consumes the existing database schema contract and does NOT execute DDL, create indexes, or modify database tables directly. The Database Team owns all indexing, table migrations, query plans, and PostgreSQL operations.

---

## 2. Backend Query Behavior Standards (Section 15, 16, 17)

The backend application guarantees the following operational standards to prevent database strain:

1. **Strictly Bounded Slices**: All collection endpoints apply SQL `LIMIT` (maximum 100) and `OFFSET`. Unbounded `SELECT * FROM table` queries are strictly prohibited.
2. **N+1 Prevention**: Patient workspace and clinical summaries fetch associated collections using batch filters (`WHERE patient_id = :id`) rather than looping individual row queries.
3. **Short Transaction Lifecycles**: Database transactions are committed immediately upon data validation. Transactions are NEVER held open across external HTTP API calls, AI inference, or OCR processing.
4. **Selective Column Projection**: Queries retrieve only the necessary domain attributes rather than entire unstructured payload histories.

---

## 3. Connection Pool Configuration & Expectations (Section 13, 14)

```
[ Application Container ]
       │
       ▼ (SQLAlchemy asyncpg pool)
[ Pool Size: 10 | Max Overflow: 20 | Timeout: 30s | Pre-Ping: True ]
       │
       ▼ (TLS Connection)
[ Supabase PgBouncer (Port 6543) ]
       │
       ▼ (Direct Session Pool)
[ Supabase PostgreSQL 15 Engine ]
```

- **Base Pool Size**: `DB_POOL_SIZE=10` connections per container replica.
- **Max Overflow**: `DB_MAX_OVERFLOW=20` (peak burst ceiling of 30 connections).
- **Idle Recycle**: `DB_POOL_RECYCLE=1800` (recycles connections older than 30 minutes).
- **Health Pre-Ping**: `DB_POOL_PRE_PING=true` verifies connection liveness prior to checkout to discard dropped cloud sockets.
- **Coordination Rule**: If the Backend Team scales application container count beyond 2 instances, the Database Team must verify that PgBouncer connection limits accommodate `instances * 30` maximum connections.

---

## 4. Critical Database Index Dependencies (Owned by Database Team)

To maintain P95 latency $< 100\text{ms}$ under load, the backend depends on the following composite and single-column indexes:

| Table Name | Indexed Column(s) | Primary Backend Access Pattern | Query Type |
| :--- | :--- | :--- | :--- |
| `patients` | `(user_id)` | Authenticated patient profile lookup (`/auth/me`) | Point lookup (`=`) |
| `consents` | `(patient_id, grantee_id, status)`| Real-time patient consent validation on clinician calls| Filtered join (`=`) |
| `prescriptions` | `(patient_id, created_at DESC)` | Paginated prescription history retrieval | Ordered slice |
| `prescription_items`| `(prescription_id)` | Prescription medication detail joins | Relational join |
| `patient_medications`| `(patient_id, status)` | Active medications for interaction checking | Filtered slice |
| `documents` | `(patient_id, is_archived)` | Paginated patient document listing | Filtered slice |
| `clinical_notes` | `(patient_id, is_signed, created_at DESC)`| Clinical workspace consolidated note timeline | Ordered slice |
| `clinical_assessments`| `(patient_id, status)` | Active patient clinical assessments | Filtered slice |
| `facilities` | `(status, facility_type)` | Facility capability discovery and radius search | Multi-column filter |
| `transfers` | `(patient_id, status)`<br>`(receiving_facility_id, status)`| Transfer coordination review queues | Filtered lookup |
| `audit_events` | `(patient_id, timestamp DESC)`<br>`(actor_id, timestamp DESC)`| Compliance auditing and security access logs | Append & Slice |

---

## 5. Slow-Query Investigation & Coordination Protocol

1. **Threshold**: Any database query exceeding **200 milliseconds** is flagged by the backend slow-request logger with `event=SLOW_QUERY` and recorded in Prometheus metrics.
2. **Notification**: The Backend Team forwards the query hash, parameters shape, and normalized route to the Database Team.
3. **Execution Plan Analysis**: The Database Team executes `EXPLAIN (ANALYZE, BUFFERS)` to inspect sequential scans, index scans, or join hash tables.
4. **Resolution**: The Database Team introduces missing composite indexes, updates statistics (`ANALYZE table_name`), or recommends query structure refinements without modifying business semantics.
