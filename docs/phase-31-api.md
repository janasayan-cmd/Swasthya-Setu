# HealthSetu — Phase 31 API Specification

**Module**: Scheduling, Appointment & Clinical Access Management  
**API Version**: v1  
**Base Path**: `/api/v1`

---

## 1. Safety & Architecture Principles

- **SCHEDULING ≠ CLINICAL DECISION**: Scheduling manages operational access, not diagnosis or clinical triage.
- **APPOINTMENT ≠ ENCOUNTER**: An appointment is a reserved calendar time slot; an encounter is an active clinical interaction.
- **AVAILABLE SLOT ≠ CLINICAL RECOMMENDATION**: Display of availability is factual capacity, never medical advice.
- **DOUBLE BOOKING PREVENTION**: Two concurrent booking requests for a single slot will result in exactly ONE success and ONE conflict (HTTP 409).
- **IDEMPOTENCY**: Safe retries using `Idempotency-Key` header return the original appointment without duplicates.

---

## 2. Endpoints Overview

| Method | Path | Auth Required | Description |
|---|---|---|---|
| `GET` | `/api/v1/availability` | Yes (`AVAILABILITY_READ`) | Query available appointment slots |
| `POST` | `/api/v1/appointments` | Yes (`APPOINTMENT_CREATE`) | Book a new appointment |
| `GET` | `/api/v1/appointments/{id}` | Yes (`APPOINTMENT_READ`) | Get appointment details |
| `POST` | `/api/v1/appointments/{id}/reschedule` | Yes (`APPOINTMENT_RESCHEDULE`) | Reschedule to a new slot |
| `POST` | `/api/v1/appointments/{id}/cancel` | Yes (`APPOINTMENT_CANCEL`) | Cancel an appointment |
| `POST` | `/api/v1/appointments/{id}/status` | Yes (`APPOINTMENT_UPDATE`) | Update lifecycle status |
| `GET` | `/api/v1/patients/{patient_id}/appointments` | Yes (`APPOINTMENT_READ`) | List appointments for patient |
| `GET` | `/api/v1/clinicians/me/appointments` | Yes (`APPOINTMENT_READ`) | List doctor's assigned appointments |
| `GET` | `/api/v1/facilities/{facility_id}/appointments` | Yes (`APPOINTMENT_READ`) | List appointments at facility |
| `GET` | `/api/v1/organizations/{org_id}/appointments` | Yes (`APPOINTMENT_READ`) | List appointments under organization |
| `GET` | `/api/v1/admin/scheduling/status` | Yes (`ADMIN_SCHEDULING_VIEW`) | View scheduling health and flags |
| `GET` | `/api/v1/admin/scheduling/providers` | Yes (`ADMIN_SCHEDULING_VIEW`) | View configured provider adapters |
| `GET` | `/api/v1/admin/scheduling/provider-status`| Yes (`ADMIN_SCHEDULING_VIEW`) | Health check on providers |
| `POST` | `/api/v1/admin/scheduling/providers/{p}/test`| Yes (`ADMIN_SCHEDULING_MANAGE`) | Probe synthetic test on provider |

---

## 3. Detailed Request & Response Examples

### 3.1 Slot Availability Retrieval
`GET /api/v1/availability?facility_id=fac-123&clinician_id=doc-456&date=2026-10-10`

**Response (HTTP 200)**:
```json
{
  "success": true,
  "data": {
    "slots": [
      {
        "slot_id": "slot-9821abc",
        "facility_id": "fac-123",
        "clinician_id": "doc-456",
        "appointment_type": "CONSULTATION",
        "start_time": "2026-10-10T10:00:00+00:00",
        "end_time": "2026-10-10T10:30:00+00:00",
        "status": "AVAILABLE",
        "capacity": 1,
        "booked_count": 0
      }
    ],
    "total": 1
  }
}
```

---

### 3.2 Appointment Booking
`POST /api/v1/appointments`  
Header: `Idempotency-Key: 9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d`

**Request Body**:
```json
{
  "patient_id": "pat-123",
  "facility_id": "fac-123",
  "clinician_id": "doc-456",
  "appointment_type": "CONSULTATION",
  "slot_id": "slot-9821abc",
  "start_time": "2026-10-10T10:00:00+00:00",
  "end_time": "2026-10-10T10:30:00+00:00",
  "reason": "Follow-up consultation after lab tests"
}
```

**Response (HTTP 201 Created)**:
```json
{
  "success": true,
  "data": {
    "appointment": {
      "id": "appt-48f9382103ab",
      "patient_id": "pat-123",
      "facility_id": "fac-123",
      "clinician_id": "doc-456",
      "appointment_type": "CONSULTATION",
      "slot_id": "slot-9821abc",
      "start_time": "2026-10-10T10:00:00+00:00",
      "end_time": "2026-10-10T10:30:00+00:00",
      "status": "CONFIRMED",
      "reason": "Follow-up consultation after lab tests",
      "created_by": "user-patient-1",
      "created_at": "2026-10-02T18:00:00+00:00",
      "updated_at": "2026-10-02T18:00:00+00:00"
    }
  }
}
```

---

### 3.3 Conflict Response (Double-Booking Prevention)
**Response (HTTP 409 Conflict)**:
```json
{
  "success": false,
  "error": {
    "code": "APPOINTMENT_SLOT_UNAVAILABLE",
    "message": "The selected appointment slot is no longer available.",
    "request_id": "req-98210a"
  }
}
```

---

### 3.4 Rescheduling
`POST /api/v1/appointments/appt-48f9382103ab/reschedule`

**Request Body**:
```json
{
  "slot_id": "slot-new-456",
  "reason": "Patient requested earlier timing"
}
```

**Response (HTTP 200 OK)**:
```json
{
  "success": true,
  "data": {
    "appointment": {
      "id": "appt-48f9382103ab",
      "status": "RESCHEDULED",
      "slot_id": "slot-new-456",
      "updated_at": "2026-10-02T18:05:00+00:00"
    }
  }
}
```

---

### 3.5 Cancellation
`POST /api/v1/appointments/appt-48f9382103ab/cancel`

**Request Body**:
```json
{
  "reason": "Patient conflict with travel"
}
```

**Response (HTTP 200 OK)**:
```json
{
  "success": true,
  "data": {
    "appointment": {
      "id": "appt-48f9382103ab",
      "status": "CANCELLED",
      "cancelled_at": "2026-10-02T18:10:00+00:00",
      "cancellation_reason": "Patient conflict with travel"
    }
  }
}
```

---

## 4. Standard Error Codes

- `APPOINTMENTS_DISABLED` (HTTP 503)
- `APPOINTMENT_NOT_FOUND` (HTTP 404)
- `APPOINTMENT_NOT_AUTHORIZED` (HTTP 403)
- `APPOINTMENT_SLOT_NOT_FOUND` (HTTP 404)
- `APPOINTMENT_SLOT_UNAVAILABLE` (HTTP 409)
- `APPOINTMENT_DOUBLE_BOOKING` (HTTP 409)
- `APPOINTMENT_BOOKING_CONFLICT` (HTTP 409)
- `APPOINTMENT_INVALID_STATE` (HTTP 409)
- `INVALID_APPOINTMENT_TIME` (HTTP 400)
- `INVALID_TIMEZONE` (HTTP 400)
- `SCHEDULING_PROVIDER_UNAVAILABLE` (HTTP 503)
- `SCHEDULING_PROVIDER_TIMEOUT` (HTTP 504)
