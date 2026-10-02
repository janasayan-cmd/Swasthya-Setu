# HealthSetu — Phase 31 Scheduling & Clinical Access Architecture

## 1. Architectural Overview

Phase 31 implements the backend scheduling and appointment-management layer for HealthSetu. It establishes a strictly governed, authorization-aware operational layer connecting patients, clinicians, facilities, and healthcare organizations.

```
                      Client Request
                            │
                            ▼
                      ┌───────────┐
                      │  FastAPI  │
                      └─────┬─────┘
                            │
                            ▼
             Authentication & Rate Limiting
                            │
                            ▼
             Authorization / Scope Boundary
                            │
                            ▼
                 Scheduling Service
                            │
             ┌──────────────┴──────────────┐
             ▼                             ▼
      Availability Service          Appointment Service
             │                             │
             ▼                             ▼
      Schedule Repository          Appointment Repository
             │                             │
             └──────────────┬──────────────┘
                            ▼
                   Authoritative Database
                            │
            ┌───────────────┼────────────────┐
            ▼               ▼                ▼
     Centralized Audit   Phase 29 Notif   Phase 28 Analytics
```

---

## 2. Core Clinical Boundaries & Invariants

```
SCHEDULING ≠ CLINICAL DECISION
SCHEDULING ≠ DIAGNOSIS
SCHEDULING ≠ TRIAGE
SCHEDULING ≠ TREATMENT RECOMMENDATION
AVAILABLE SLOT ≠ CLINICAL RECOMMENDATION
APPOINTMENT ≠ CLINICAL ENCOUNTER
APPOINTMENT BOOKED ≠ PATIENT SEEN
APPOINTMENT CANCELLED ≠ CLINICAL CANCELLATION
APPOINTMENT REMINDER ≠ MEDICAL ADVICE
APPOINTMENT ≠ EMERGENCY RESPONSE
FACILITY DISCOVERY ≠ APPOINTMENT AVAILABILITY
CLINICIAN PROFILE ≠ CLINICIAN AVAILABILITY
```

1. **No Autonomous Clinical Prioritization**: The scheduling engine manages calendar slots; it does not decide who is medically sicker or override clinical urgency. Phase 8 retains clinical triage responsibility.
2. **Appointment vs. Encounter Distinction**: Booking an appointment reserves clinician/facility availability. A clinical encounter is created only when a clinician starts an examination or clinical interaction (Phase 4 / Phase 10).
3. **No Automatic Facility Selection**: The backend exposes factual availability; it never ranks or automatically forces a doctor or hospital onto the patient.
4. **Emergency Guardrail**: If an active emergency triage condition exists, patients are guided to emergency pathways; normal scheduling is never substituted for acute emergency intervention.

---

## 3. Appointment Lifecycle State Machine

```
                   REQUESTED
                  /    │    \
                 /     │     \
                ▼      ▼      ▼
            CONFIRMED PENDING REJECTED
             /   │   \
            /    │    \
           /     ▼     \
          /   CHECKED_IN \
         /       │        \
        ▼        ▼         ▼
   RESCHEDULED IN_PROGRESS CANCELLED
                 │
                 ▼
             COMPLETED (Terminal)
             NO_SHOW   (Terminal)
             EXPIRED   (Terminal)
             FAILED    (Terminal)
```

- Transitions are validated deterministically by `AppointmentValidationService`.
- Terminal states cannot transition to any other status.
- Patients can only transition their own appointments to `CANCELLED` or `RESCHEDULED`.
- Status transitions like `CHECKED_IN`, `IN_PROGRESS`, and `COMPLETED` require clinician or operational staff permissions.

---

## 4. Concurrency Control & Double-Booking Prevention

### The Race Condition Problem
When two concurrent requests hit the booking endpoint for the exact same slot:
```
User A ──┐
         ├──> [Slot X Check: Available] ──> [Both Book] ──> DOUBLE BOOKING BUG!
User B ──┘
```

### The HealthSetu Solution
1. **Transactional Row Lock**:
   - In-memory / provider uses a thread-safe mutex (`threading.RLock`) surrounding slot checks and reservations.
   - In PostgreSQL, queries use `SELECT ... FOR UPDATE` on `availability_slots`.
2. **Atomic Counter & State**:
   - `booked_count` is incremented atomically.
   - If `booked_count >= capacity`, state switches immediately to `BOOKED`.
   - The first request succeeds (`HTTP 201 Created`).
   - The second request immediately receives `APPOINTMENT_SLOT_UNAVAILABLE` (`HTTP 409 Conflict`).

---

## 5. Idempotent Booking

- Supported via the `Idempotency-Key` HTTP header.
- Scoped to user context.
- If a duplicate request with the identical key arrives within the retry window:
  - No new appointment is created.
  - The previously created appointment record is returned idempotently.
  - Slot capacity is not deducted twice.

---

## 6. Timezone Handling

- All timestamps are stored and manipulated using explicit timezone offsets (`TIMESTAMPTZ` / `datetime` with `tzinfo`).
- Naive datetime comparisons are strictly prohibited.
- Timezones in requests and schedule definitions must be valid IANA timezone identifiers (e.g. `UTC`, `Asia/Kolkata`).
- Validation fails fast with `INVALID_TIMEZONE` (HTTP 400) if an unknown timezone is supplied.

---

## 7. Downstream Integrations

1. **Phase 29 Notifications**:
   - Emits `APPOINTMENT_CONFIRMED`, `APPOINTMENT_RESCHEDULED`, `APPOINTMENT_CANCELLED`, and `APPOINTMENT_CHECK_IN`.
   - Notification content contains operational schedule reminders only; it NEVER generates new medical advice or medication instructions.
2. **Centralized Audit (Phase 3)**:
   - Emits structured non-PHI audit logs for all creations, status changes, and searches.
3. **Phase 28 Analytics**:
   - Tracks operational metrics (`appointment_creation_total`, `booking_conflicts_total`, `availability_query_latency`) without exposing PHI.
4. **Phase 30 Search**:
   - Appointments are indexed into search with `resource_type=appointment` under strict caller authorization constraints.
