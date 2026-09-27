# Runbook: High HTTP 5xx Error Rate

## 1. Overview
- **Incident Type**: Internal Server Error Spike
- **Severity**: HIGH (P1)
- **Primary Symptom**: `healthsetu_http_errors_total{status_class="5xx"}` exceeding 5% of total requests or sustained rate of > 10 errors/min.

---

## 2. Immediate Diagnostic Procedure

1. **Identify Failing Routes**:
   - Query metrics summary endpoint:
     ```bash
     curl -s https://api.healthsetu.com/api/v1/metrics?format=json | jq '.http_requests'
     ```
   - Identify which normalized routes (e.g. `/api/v1/prescriptions`, `/api/v1/auth/login`) are producing 500 status codes.

2. **Inspect Error Logs by Correlation ID**:
   - Filter Railway logs by `"level": "ERROR"`.
   - Inspect the `request_id`, `route`, and sanitized `error` message.
   - Confirm whether the error is:
     - Uncaught Python exception (`AttributeError`, `KeyError`, `ValueError`)
     - Database query failure (`OperationalError`, `IntegrityError`)
     - External provider timeout (`httpx.TimeoutException`)

3. **Check Recent Deployment**:
   - Check if a new version was deployed right before the error spike.
   - If error is correlated with a recent release, prepare for rollback.

---

## 3. Mitigation Steps

1. **If Root Cause is New Code Regression**:
   - Perform an immediate rollback in Railway to the last known healthy deployment.
   - Follow `docs/rollback.md`.

2. **If Root Cause is Downstream Service Failure**:
   - If Supabase PostgreSQL is failing, refer to `docs/runbooks/database-unavailable.md`.
   - If external service (OCR / AI) is failing, refer to `docs/runbooks/external-provider-failure.md`.

3. **If Root Cause is Memory / Concurrency Pressure**:
   - Restart the Railway instance to clear transient state.
   - Scale horizontally if request volume exceeds container capacity.

---

## 4. Verification

1. Monitor `GET /api/v1/metrics?format=json` for 10 minutes.
2. Confirm 5xx error rate drops to < 0.1%.
3. Run smoke test suite to confirm end-to-end functionality:
   ```bash
   pytest tests/test_production_smoke.py -v
   ```
