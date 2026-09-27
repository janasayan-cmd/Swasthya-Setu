# Runbook: Backend Down / Unreachable

## 1. Overview
- **Incident Type**: Total Application Outage
- **Severity**: CRITICAL (P0)
- **Primary Symptom**: `https://api.healthsetu.com/api/v1/health` returns HTTP 5xx, connection refused, or timed out.

---

## 2. Immediate Diagnostic Procedure

Execute in strict sequential order:

1. **Check Railway Deployment Status**:
   - Access the Railway project dashboard.
   - Verify container status (is container `CRASHED`, `RESTARTING`, or `DEPLOY_FAILED`?).
   - Check if a new deployment was triggered in the last 15 minutes.

2. **Inspect Container Logs**:
   - View recent standard output / standard error streams in Railway.
   - Search for fatal startup errors:
     - Uncaught Python syntax / import error
     - Configuration parsing error (`pydantic.ValidationError`)
     - Port binding failure (must listen on `0.0.0.0:$PORT`)

3. **Check Direct Container Health Endpoint**:
   ```bash
   curl -I -sS https://api.healthsetu.com/api/v1/health
   curl -I -sS https://api.healthsetu.com/health
   ```
   If root returns 200 but `/api/v1/` returns 404/500, verify FastAPI routing configuration.

4. **Check Resource Exhaustion**:
   - In Railway metrics, check Container Memory (RAM) and CPU graphs.
   - If Memory is at 100% (OOMKilled), container was terminated by the Linux kernel.

---

## 3. Mitigation & Recovery Steps

### Scenario A: Container Crashed Following a Deployment
1. Identify the previous stable deployment commit hash or release ID.
2. In Railway dashboard, click on the last known healthy deployment and select **Rollback**.
3. Alternatively, trigger rollback via git:
   ```bash
   git revert HEAD
   git push origin main
   ```
4. Follow `docs/rollback.md` for complete rollback guidance.

### Scenario B: Container Out of Memory (OOM) or Hung Process
1. Trigger a manual restart of the Railway deployment service.
2. Monitor memory growth as traffic resumes.
3. If memory grows monotonically, scale container memory allotment or inspect recent changes for memory leaks.

### Scenario C: Environment Configuration Missing
1. Confirm Railway environment variables match `.env.example`:
   - `ENVIRONMENT=production`
   - `DATABASE_URL` (Supabase pooled URL)
   - `JWT_SECRET_KEY`
   - `CORS_ORIGINS`

---

## 4. Verification

After performing mitigation:
1. Verify `/api/v1/health` returns HTTP 200:
   ```bash
   curl https://api.healthsetu.com/api/v1/health
   ```
2. Verify `/api/v1/ready` returns HTTP 200:
   ```bash
   curl https://api.healthsetu.com/api/v1/ready
   ```
3. Run automated smoke tests:
   ```bash
   pytest tests/test_production_smoke.py -v
   ```
4. Ensure error rate returns to normal baseline in `/metrics`.
