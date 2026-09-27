# Runbook: Authentication Service & Token Failure

## 1. Overview
- **Incident Type**: Authentication Outage / Credential Rejection Spike
- **Severity**: HIGH (P1)
- **Primary Symptom**: Spike in `healthsetu_auth_failures_total` across multiple users or sudden inability for clinicians to log in.

---

## 2. Immediate Diagnostic Procedure

1. **Review Authentication Failure Metrics**:
   - Query `/api/v1/metrics?format=json` under `security.auth_failures`.
   - Inspect failure categories:
     - `invalid_credentials`
     - `token_expired`
     - `invalid_token`
     - `user_not_found`

2. **Inspect Error Logs**:
   - Filter logs by `"event": "auth_failure"`.
   - Check if failures are distributed across all users or isolated to specific IP addresses (indicating brute force / credential stuffing).

3. **Check Secret Configuration**:
   - If ALL tokens suddenly fail validation with `invalid_token`, verify whether `JWT_SECRET_KEY` was rotated or modified inadvertently during recent deployment.
   - Verify server clock synchronization (NTP drift causing immediate token expiration).

---

## 3. Mitigation Steps

### Scenario A: JWT Secret Mismatch
- If `JWT_SECRET_KEY` was accidentally modified in Railway, revert to previous secret to restore existing session validity.
- If deliberate secret rotation, inform users to re-authenticate with valid credentials.

### Scenario B: Brute Force Attack
- If high failure rate originates from specific client IPs:
  - Rate limiting middleware will automatically return `429 Too Many Requests`.
  - Block offending IP addresses at Railway / Cloudflare perimeter if traffic is severe.

### Scenario C: Password Hash Migration / Algorithm Issue
- If password authentication fails globally, verify bcrypt/passlib library dependencies and database user password hash records.

---

## 4. Verification

1. Test login flow using test credentials:
   ```bash
   pytest tests/test_production_smoke.py -k "test_smoke_auth_login" -v
   ```
2. Confirm valid tokens allow access to protected endpoints (`/api/v1/patients`, `/api/v1/prescriptions`).
3. Ensure auth failure rate returns to baseline.
