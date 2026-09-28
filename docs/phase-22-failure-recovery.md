# Phase 22 — Failure Recovery & Safety Runbook

## 1. Safety Invariants Under Failure

1. **Provider Outage $\neq$ Clinical Clearance**:
   - An external medication safety provider timeout or 5xx response MUST NOT synthesize a `CLEAR` interaction assessment. The assessment status is marked `UNKNOWN` with an explicit flag requiring pharmacist verification.
2. **AI Model Failure $\neq$ Success**:
   - An LLM provider outage or prompt injection detection aborts the AI task or routes to deterministic rule templates. Unverified drafts are never presented as clinician-verified.
3. **Partial Workflow Preservation**:
   - In a multi-step pipeline (e.g. Document Upload $\rightarrow$ OCR $\rightarrow$ Medication Normalization $\rightarrow$ Safety Check), if step 4 fails, earlier stages remain available. The workflow transitions to `PARTIALLY_FAILED`, not catastrophic data loss.

## 2. Failure Scenarios and Recovery Procedures

### Scenario A: Broker / Queue Provider Outage
- **Symptom**: `InMemoryJobQueueProvider` or broker returns 503; HTTP clients receive `SERVICE_UNAVAILABLE`.
- **Behavior**: Jobs already persisted in `async_jobs` retain `status="QUEUED"`.
- **Recovery**: Once broker connectivity is restored, the `flush_outbox` / reconciliation routine re-populates the in-memory lease queue without creating duplicate database rows.

### Scenario B: Worker Process Unexpected Crash (SIGKILL)
- **Symptom**: Job was in state `PROCESSING`, but worker container was terminated abruptly.
- **Behavior**: Leased job times out according to visibility timeout or queue expiration.
- **Recovery**: Background supervisor queries jobs stuck in `PROCESSING` longer than `JOB_DEFAULT_TIMEOUT_SECONDS` and schedules them for retry (`RETRY_PENDING` $\rightarrow$ `QUEUED`).

### Scenario C: Duplicate Webhook / Event Delivery
- **Symptom**: External broker delivers identical `DomainEvent` multiple times.
- **Behavior**: `EventService` checks `(event_id, consumer_name)` in `consumed_events`. If present, skips re-execution and logs `EVENT_DUPLICATE_IGNORED` in the immutable audit trail.
