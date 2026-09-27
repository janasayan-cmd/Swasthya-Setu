# HealthSetu — Production Rollback Procedure (Phase 17)

## 1. Overview & Policy

A predictable, well-rehearsed rollback procedure is mandatory for healthcare applications. If a production release exhibits unexpected exceptions, broken clinical workflows, or connection failures, the backend must be restored to the previous known-good deployment immediately.

**Key Rule**: The backend team **must not** independently attempt automated database schema rollbacks. Any database rollbacks must be strictly coordinated with the Database Team.

---

## 2. Trigger Criteria for Rollback

Initiate rollback immediately if any of the following occur during or immediately following deployment:
1. `GET /api/v1/health` fails to return `200 OK`.
2. `GET /api/v1/ready` reports `"status": "not_ready"` or `"database": "unavailable"`.
3. Application startup logs show fatal security violations (`RuntimeError: Application startup blocked`).
4. HTTP 5xx error rate exceeds 1% on clinical workflows (triage, prescriptions, transfers).
5. Data serialization or database constraint failures occur systematically across API routes.

---

## 3. Step-by-Step Rollback Procedure

```
1. Identify Failed Release
       ↓
2. Halt Active Rollouts in Railway
       ↓
3. Select Previous Known-Good Deployment
       ↓
4. Trigger Instant Rollback
       ↓
5. Probe Liveness (/health) & Readiness (/ready)
       ↓
6. Execute Production Smoke Tests
       ↓
7. Inspect Application Logs & Document Incident
```

### Step 1: Halt Rollout
In the Railway dashboard for the backend project, locate the deploying service and cancel any in-progress build or deployment.

### Step 2: Revert to Previous Deployment
1. Navigate to **Deployments** in Railway.
2. Identify the last successful deployment that passed all smoke tests.
3. Click the options menu (`...`) on that deployment and click **Rollback to this deployment** (or redeploy that specific commit SHA).
4. Railway will route incoming ingress traffic back to the container running the previous image.

### Step 3: Verify Restoration
Run the operational probes against the production domain:
```bash
# 1. Check Liveness
curl -f https://api.healthsetu.com/api/v1/health

# 2. Check Readiness & Database
curl -f https://api.healthsetu.com/api/v1/ready
```

### Step 4: Run Smoke Tests
Execute the automated smoke test script or run:
```bash
pytest tests/test_production_smoke.py -v
```

---

## 4. Database Migration Considerations

1. **Forward-Compatible Migrations**:
   * All database schema changes provided by the Database Team must be backwards-compatible with the immediately preceding application version (Expand-Contract pattern).
2. **Schema Incompatibility**:
   * If a migration added a breaking column or constraint that caused the failure, contact the Database Team immediately before attempting schema alterations.
   * Under no circumstances should backend engineers execute manual `DROP TABLE` or `ALTER TABLE` commands in production.
3. **Incident Documentation**:
   * Post-rollback, document the trigger, root cause, deployment ID, and resolution in the incident response log per Phase 15 protocol.
