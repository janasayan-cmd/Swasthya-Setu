# HealthSetu — Phase 31 Database Dependencies & Entity Contract

**Document Purpose**: Outlines the consumed database contract, schema requirements, index specifications, and transaction/concurrency constraints expected from the Database Team for Phase 31: Scheduling, Appointment & Clinical Access Management.

**Team Boundary**:
- The **Backend Team** consumes this schema via repositories and domain services.
- The **Database Team** owns all tables, DDL migrations, PostgreSQL constraints, exclusion locks, and database-level optimization.
- The backend does NOT create competing tables or independently manage database migrations.

---

## 1. Entities Consumed

### 1.1 Appointments Entity (`appointments`)
Canonical persistence entity representing authorized patient appointments.

| Column | Type | Nullable | Constraints & References | Description |
|---|---|---|---|---|
| `id` | `VARCHAR(64)` | NO | PRIMARY KEY | Canonical appointment ID (`appt-...`) |
| `patient_id` | `VARCHAR(64)` | NO | REFERENCES `patients(id)` | Clinical subject identity |
| `facility_id` | `VARCHAR(64)` | NO | REFERENCES `facilities(id)` | Physical/telecom healthcare facility |
| `clinician_id` | `VARCHAR(64)` | YES | REFERENCES `users(id)` | Assigned clinician/practitioner |
| `organization_id` | `VARCHAR(64)` | YES | REFERENCES `organizations(id)` | Healthcare organization boundary |
| `appointment_type`| `VARCHAR(32)` | NO | ENUM/Reference table | Type (CONSULTATION, FOLLOW_UP, etc.) |
| `slot_id` | `VARCHAR(64)` | YES | REFERENCES `availability_slots(id)` | Associated reservation slot |
| `start_time` | `TIMESTAMPTZ` | NO | | Appointment start with timezone offset |
| `end_time` | `TIMESTAMPTZ` | NO | | Appointment end with timezone offset |
| `status` | `VARCHAR(32)` | NO | ENUM/Check constraint | Approved lifecycle state |
| `reason` | `VARCHAR(500)` | YES | | Patient non-diagnostic input |
| `encounter_id` | `VARCHAR(64)` | YES | REFERENCES `encounters(id)` | Clinical encounter if established |
| `idempotency_key` | `VARCHAR(128)`| YES | UNIQUE | Client-supplied deduplication key |
| `created_by` | `VARCHAR(64)` | NO | REFERENCES `users(id)` | Creator actor identity |
| `created_at` | `TIMESTAMPTZ` | NO | DEFAULT `NOW()` | Audit creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | NO | DEFAULT `NOW()` | Audit update timestamp |
| `cancelled_at` | `TIMESTAMPTZ` | YES | | Explicit cancellation timestamp |
| `cancellation_reason` | `VARCHAR(500)` | YES | | Explicit reason for cancellation |
| `checked_in_at`| `TIMESTAMPTZ` | YES | | Front desk arrival timestamp |
| `completed_at` | `TIMESTAMPTZ` | YES | | Clinical completion timestamp |
| `metadata` | `JSONB` | NO | DEFAULT `'{}'::jsonb` | Extensible operational metadata |

---

### 1.2 Availability Slots Entity (`availability_slots`)
Authoritative discrete schedulable slots.

| Column | Type | Nullable | Constraints & References | Description |
|---|---|---|---|---|
| `slot_id` | `VARCHAR(64)` | NO | PRIMARY KEY | Unique slot ID (`slot-...`) |
| `facility_id` | `VARCHAR(64)` | NO | REFERENCES `facilities(id)` | Facility where slot is hosted |
| `clinician_id` | `VARCHAR(64)` | YES | REFERENCES `users(id)` | Clinician assigned to slot |
| `appointment_type`| `VARCHAR(32)` | NO | | Schedulable appointment type |
| `start_time` | `TIMESTAMPTZ` | NO | | Slot window start |
| `end_time` | `TIMESTAMPTZ` | NO | | Slot window end |
| `status` | `VARCHAR(32)` | NO | ENUM | AVAILABLE, RESERVED, BOOKED, BLOCKED |
| `capacity` | `INTEGER` | NO | DEFAULT 1, CHECK (`capacity` >= 1) | Max simultaneous bookings |
| `booked_count` | `INTEGER` | NO | DEFAULT 0, CHECK (`booked_count` >= 0) | Currently confirmed bookings |
| `metadata` | `JSONB` | NO | DEFAULT `'{}'::jsonb` | Schedule template reference |

---

### 1.3 Schedule Configurations (`schedules`)
Weekly recurring working hours and blocked date templates.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | `VARCHAR(64)` | NO (PK) | Unique schedule ID |
| `facility_id` | `VARCHAR(64)` | NO | Associated facility |
| `clinician_id` | `VARCHAR(64)` | YES | Associated clinician |
| `timezone` | `VARCHAR(64)` | NO (DEFAULT 'UTC') | Operating IANA timezone |
| `working_hours` | `JSONB` | NO | Array of day_of_week, start_time, end_time, slot_duration |
| `blocked_dates` | `JSONB` | NO | Array of YYYY-MM-DD blocked/holiday dates |
| `is_active` | `BOOLEAN` | NO | Active rule flag |

---

## 2. Approved Reference Values & Enums

### 2.1 Appointment Types
- `CONSULTATION`
- `FOLLOW_UP`
- `GENERAL_VISIT`
- `SPECIALIST_VISIT`
- `DIAGNOSTIC_VISIT`
- `PROCEDURE`
- `VACCINATION`
- `TELECONSULTATION`
- `OTHER`

### 2.2 Appointment Lifecycle States
- `REQUESTED`
- `PENDING`
- `CONFIRMED`
- `RESCHEDULE_REQUESTED`
- `RESCHEDULED`
- `CHECKED_IN`
- `IN_PROGRESS`
- `COMPLETED`
- `CANCELLED`
- `NO_SHOW`
- `REJECTED`
- `EXPIRED`
- `FAILED`

---

## 3. Concurrency, Locking & Double-Booking Prevention

1. **Slot Capacity Lock**:
   - Single-capacity slots (`capacity = 1`): Must enforce `CHECK (booked_count <= capacity)`.
   - In PostgreSQL, slot reservation must execute within a `SERIALIZABLE` or `READ COMMITTED` transaction using:
     ```sql
     SELECT * FROM availability_slots WHERE slot_id = :id FOR UPDATE;
     ```
   - If `booked_count >= capacity` or `status != 'AVAILABLE'`, rollback and emit `APPOINTMENT_SLOT_UNAVAILABLE` (HTTP 409).

2. **Clinician Overlap Exclusion Constraint**:
   - Clinicians cannot be booked in overlapping active appointments:
     ```sql
     ALTER TABLE appointments ADD CONSTRAINT prevent_clinician_double_booking
     EXCLUDE USING gist (
       clinician_id WITH =,
       tstzrange(start_time, end_time) WITH &&
     ) WHERE (status IN ('CONFIRMED', 'RESCHEDULED', 'CHECKED_IN', 'IN_PROGRESS'));
     ```

3. **Idempotency Key Uniqueness**:
   - Unique index on `idempotency_key WHERE idempotency_key IS NOT NULL`.

---

## 4. Required Database Indexes

```sql
-- Fast patient history lookup
CREATE INDEX idx_appointments_patient_start ON appointments(patient_id, start_time DESC);

-- Fast clinician daily schedule lookup
CREATE INDEX idx_appointments_clinician_time ON appointments(clinician_id, start_time);

-- Fast facility appointment monitoring
CREATE INDEX idx_appointments_facility_time ON appointments(facility_id, start_time);

-- Fast slot availability querying
CREATE INDEX idx_availability_slots_query ON availability_slots(facility_id, clinician_id, appointment_type, start_time, status);

-- Fast lookup by idempotency
CREATE UNIQUE INDEX idx_appointments_idempotency ON appointments(idempotency_key) WHERE idempotency_key IS NOT NULL;
```
