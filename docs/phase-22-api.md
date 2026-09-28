# Phase 22 — Asynchronous Job Orchestration API Reference

Base URL: `/api/v1/jobs`

All endpoints enforce Bearer JWT authentication, authorization, and audit trail recording.

---

### 1. Enqueue Job
`POST /api/v1/jobs`

Enqueues an asynchronous operation with optional client idempotency key.

**Request Headers**:
- `Authorization: Bearer <token>`
- `X-Request-ID: <uuid>` (optional)

**Request Body**:
```json
{
  "job_type": "DOCUMENT_PROCESSING",
  "patient_id": "pat-001",
  "resource_type": "document",
  "resource_id": "doc-994",
  "operation_type": "ocr_extraction",
  "payload": {
    "engine": "tesseract_v5"
  },
  "idempotency_key": "idemp-doc-994-v1",
  "max_retries": 3
}
```

**Response (HTTP 202 Accepted)**:
```json
{
  "id": "job-4c90e0b3-909d-478e-9d0b-d249f7e7f1b2",
  "job_type": "DOCUMENT_PROCESSING",
  "status": "QUEUED",
  "patient_id": "pat-001",
  "resource_type": "document",
  "resource_id": "doc-994",
  "operation_type": "ocr_extraction",
  "attempt": 0,
  "max_retries": 3,
  "created_at": "2026-09-28T10:15:00Z",
  "started_at": null,
  "completed_at": null,
  "failed_at": null,
  "error_message": null,
  "error_category": null,
  "result": null
}
```

---

### 2. Poll Job Status
`GET /api/v1/jobs/{job_id}/status`

Lightweight polling endpoint to verify progress without returning heavy payloads.

**Response (HTTP 200 OK)**:
```json
{
  "job_id": "job-4c90e0b3-909d-478e-9d0b-d249f7e7f1b2",
  "status": "COMPLETED",
  "attempt": 1,
  "created_at": "2026-09-28T10:15:00Z",
  "completed_at": "2026-09-28T10:15:03Z",
  "failed_at": null,
  "is_terminal": true
}
```

---

### 3. Retrieve Full Job Details
`GET /api/v1/jobs/{job_id}`

Retrieves complete metadata and non-PHI output payload.

**Response (HTTP 200 OK)**:
```json
{
  "id": "job-4c90e0b3-909d-478e-9d0b-d249f7e7f1b2",
  "job_type": "DOCUMENT_PROCESSING",
  "status": "COMPLETED",
  "patient_id": "pat-001",
  "resource_type": "document",
  "resource_id": "doc-994",
  "operation_type": "ocr_extraction",
  "attempt": 1,
  "max_retries": 3,
  "created_at": "2026-09-28T10:15:00Z",
  "started_at": "2026-09-28T10:15:01Z",
  "completed_at": "2026-09-28T10:15:03Z",
  "failed_at": null,
  "error_message": null,
  "error_category": null,
  "result": {
    "document_id": "doc-994",
    "confidence_score": 0.96,
    "status": "COMPLETED"
  }
}
```

---

### 4. Cancel Pending Job
`POST /api/v1/jobs/{job_id}/cancel`

Cancels a queued task before it enters execution.

**Response (HTTP 200 OK)**:
```json
{
  "job_id": "job-4c90e0b3-909d-478e-9d0b-d249f7e7f1b2",
  "status": "CANCELLED",
  "message": "Job 'job-4c90e0b3-909d-478e-9d0b-d249f7e7f1b2' has been cancelled."
}
```

---

### 5. Retry Failed Job
`POST /api/v1/jobs/{job_id}/retry`

Manually schedules a failed job for retry.

**Response (HTTP 200 OK)**:
```json
{
  "job_id": "job-4c90e0b3-909d-478e-9d0b-d249f7e7f1b2",
  "status": "QUEUED",
  "attempt": 1,
  "message": "Job 'job-4c90e0b3-909d-478e-9d0b-d249f7e7f1b2' scheduled for retry."
}
```
