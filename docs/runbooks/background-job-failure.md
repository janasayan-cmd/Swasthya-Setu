# Runbook: Background Job Failure & Queue Backlog

## 1. Overview
- **Incident Type**: Asynchronous Task Processing Degradation
- **Severity**: MEDIUM (P2) to HIGH (P1)
- **Primary Symptom**: Spike in `healthsetu_background_jobs_total{status="failed"}` or growing unhandled queue backlog.

---

## 2. Immediate Diagnostic Procedure

1. **Inspect Background Job Metrics**:
   - Query `/api/v1/metrics?format=json` under `background_jobs`.
   - Identify which job type is failing (e.g. `document_ocr`, `audit_flush`, `notification_dispatch`).

2. **Check Dead Letter / Error Logs**:
   - Filter logs for `"event": "background_job"` and `"status": "failed"`.
   - Inspect job exception:
     - Worker timeouts
     - Transient network disconnection
     - Malformed job payload

3. **Verify Retry Invariants**:
   - Ensure jobs are **NOT** in an infinite retry loop.
   - Max retries must be capped (default: 3 attempts with exponential backoff).

---

## 3. Mitigation Steps

1. **If Caused by Downstream Dependency**:
   - If downstream OCR / external API is down, pause job workers or throttle dequeuing to avoid burning retry budgets.
2. **If Worker Thread Starvation**:
   - Check if worker threads are locked waiting on blocking synchronous I/O.
   - Restart worker processes.
3. **If Poison Pill Payload**:
   - If a specific corrupted file or payload causes repetitive worker crashes, isolate the job ID into a quarantine table for engineering review.
   - Resume processing of remaining queue.

---

## 4. Verification

1. Verify queue depth decreases monotonically.
2. Confirm job metrics show `"status": "completed"` incrementing normally.
