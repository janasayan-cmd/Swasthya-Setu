# Runbook: External Provider Failure & Degradation

## 1. Overview
- **Incident Type**: Third-Party Integration Outage (OCR, Medication Safety, AI, Interoperability)
- **Severity**: HIGH (P1) for Medication Safety / OCR; MEDIUM (P2) for AI / Non-urgent Interoperability
- **Primary Symptom**: Spike in `healthsetu_provider_requests_total{status="error"}` or `{status="timeout"}`.

---

## 2. Clinical Safety Invariants (MANDATORY)

During an external provider outage, the following safety boundaries **MUST NEVER BE VIOLATED**:

1. **Medication Safety Provider Outage**:
   $$\text{Provider Failure} \ne \text{CLEAR}$$
   - If the medication safety validation service fails or times out, the safety status **MUST REMAIN** `UNKNOWN` or `ERROR`.
   - **NEVER** automatically mark drug interactions as `CLEAR` or `SAFE`.
   - Clinicians must be clearly alerted that automated interaction checking is unavailable and manual clinical verification is required.

2. **OCR / Document Processing Outage**:
   - Never fabricate clinical text or auto-verify unparsed extractions.
   - Mark processing state as `FAILED` or `RETRYING` according to configured policy.

3. **AI Consultation / SBAR Outage**:
   - Provide deterministic fallback where supported; otherwise return safe, graceful degradation.
   - AI output must never be treated as an authoritative clinical decision.

4. **Interoperability Import / Export Outage**:
   - Maintain source provenance.
   - Mark transmission as `FAILED_PENDING_RETRY`; do not drop message payloads silently.

---

## 3. Immediate Diagnostic Procedure

1. **Identify the Failing Provider**:
   - Review `/api/v1/metrics?format=json` under `external_providers`.
   - Check error rates for `ocr`, `medication_safety`, `ai`, and `interoperability`.

2. **Inspect Provider Error Logs**:
   - Filter logs by `"event": "provider_call"` and `"status": "error"`.
   - Determine error nature:
     - HTTP 401 / 403: Provider API key expired or revoked.
     - HTTP 429: Rate-limit quota exceeded.
     - HTTP 500 / 502 / 503 / 504: Downstream provider outage or network timeout.

3. **Check Provider Status Page**:
   - Check status dashboard for AWS Textract, OpenAI / Gemini, or designated Medication DB APIs.

---

## 4. Mitigation Steps

### Scenario A: Rate-Limiting (HTTP 429)
- Enable backoff retry policies in job queue.
- Temporarily throttle non-urgent background batch OCR processing to preserve capacity for interactive workflows.

### Scenario B: API Key Expiry / Authentication Error (HTTP 401/403)
- Rotate and update the provider API key in Railway environment variables.
- Trigger service redeployment.

### Scenario C: Complete Provider Outage (HTTP 5xx / Timeout)
- The system must fail-safe:
  - Prescriptions requiring safety check return `UNKNOWN` status with disclaimer banner.
  - Document uploads enter queue in `PENDING` state until provider recovers.
- Notify clinical staff via administrative notice banner that automated safety checks are temporarily in offline mode.

---

## 5. Verification & Recovery

1. Ensure provider test call succeeds via synthetic test endpoint.
2. Confirm `healthsetu_provider_requests_total{status="success"}` is incrementing.
3. Reprocess failed/queued background jobs according to retention policy.
