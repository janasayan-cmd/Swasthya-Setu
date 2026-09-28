# HealthSetu Runbook — Application Recovery & Rollback

================================================================================
ALERT IDENTIFIERS & SYMPTOMS
================================================================================
- **Alert**: `RailwayApplicationDown`, `ContainerCrashLoopBackOff`, `DeploymentFailed`
- **Symptoms**:
  - `GET /api/v1/health` times out or returns HTTP 502/503.
  - Railway deployment dashboard indicates `CRASHED`, `FAILED`, or `UNHEALTHY`.
  - Upstream reverse proxy / Cloudflare returns `502 Bad Gateway`.
- **Severity**: **SEV-1 (Critical)**

================================================================================
1. INCIDENT TRIAGE & INITIAL INSPECTION
================================================================================

Do NOT immediately modify application source code during an active production outage.
First determine whether the failure was caused by:
1. A new bad release deployment
2. A container runtime issue (OOM / memory spike)
3. An environment variable or secret misconfiguration
4. An external infrastructure or database failure

### Step 1.1: Inspect Deployment Status & Recent Commits
Using the Railway CLI or dashboard:
```bash
# Check status of the latest deployment
railway status

# View the last 100 deployment build and runtime logs
railway logs -n 100
```

### Step 1.2: Identify Last Known-Good Release
- Check the Git repository releases or Railway deployment history.
- Locate the previous successful deployment SHA (e.g. commit `a1b2c3d` tagged `v1.18.2`).

================================================================================
2. ROLLBACK PROCEDURE (FASTEST RECOVERY)
================================================================================

If the outage began immediately following a new deployment rollout:

### Step 2.1: Halt Active Rollout
- In Railway Dashboard: Navigate to Project -> `healthsetu-backend` -> Deployments -> Click **Cancel** on active build.

### Step 2.2: Execute Deployment Rollback
```bash
# Via Railway CLI: Roll back to previous stable deployment
railway rollback

# OR via Railway Dashboard:
# 1. Click 'Deployments' tab
# 2. Find the last deployment with green 'ACTIVE' state prior to incident
# 3. Click '...' -> Select 'Redeploy'
```

### Step 2.3: Verify Rollback Startup
Watch container initialization logs:
```bash
railway logs
```
Verify that the log outputs:
```
INFO: Starting HealthSetu [env=production, version=...]
INFO: Database connection established and verified on startup.
INFO: Application startup complete. Uvicorn running on http://0.0.0.0:8000
```

================================================================================
3. CONTAINER CRASH / OOM RECOVERY
================================================================================

If the container crashed due to Out-Of-Memory (OOM) or unhandled runtime signal:

1. **Check Railway Metrics**:
   - Inspect CPU & RAM graphs in Railway Dashboard.
   - If memory reached 100% (e.g., 512MB limit), container was terminated by OS kernel (`SIGKILL`).
2. **Immediate Remediation**:
   - In Railway Settings -> Service Settings -> Resources:
   - Increase container memory allocation (e.g. from 512MB to 1024MB or 2048MB).
   - Trigger restart: `railway restart`.
3. **Record Incident**:
   - Track memory leak investigation in post-recovery task list.

================================================================================
4. POST-RECOVERY VALIDATION GATES
================================================================================

Before declaring the application recovered, execute the following probes sequentially:

### Step 4.1: Probe Liveness Endpoint
```bash
curl -f -s https://api.healthsetu.com/api/v1/health | jq .
# Expected: {"status": "ok", "service": "healthsetu-backend", "version": "..."}
```

### Step 4.2: Probe Readiness Endpoint
```bash
curl -f -s https://api.healthsetu.com/api/v1/ready | jq .
# Expected HTTP 200: {"status": "ready", "checks": {"database": "available"}}
```

### Step 4.3: Execute Backend Integration Smoke Tests
Run the comprehensive smoke test suite from a secure terminal:
```bash
python scripts/verify_integration.py
```
Expected output:
```
[OK] GET /api/v1/health -> Status: 200
[OK] GET /api/v1/ready  -> Status: 200
[OK] POST /api/v1/auth/login -> 200 OK
[OK] GET /clinical-workspace -> 200 OK
[OK] POST /medication-safety/check-medications -> 200 OK
================== ALL SMOKE TESTS PASSED ==================
```

### Step 4.4: Record Telemetry Metrics
In the backend telemetry registry:
- `metrics.record_recovery_attempt("application")`
- `metrics.record_deployment_rollback()`
- `metrics.record_recovery_result("application", success=True)`

### Step 4.5: Monitor for 30 Minutes
Observe Prometheus metrics (`/metrics`) and error rates. If 5xx error rate remains < 0.1%, close the active SEV-1 incident.
