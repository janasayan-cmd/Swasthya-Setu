# HealthSetu Runbook — Full System Disaster Recovery & Master Cold-Start

================================================================================
EXECUTIVE OVERVIEW & AUTHORITY
================================================================================
This master runbook orchestrates a cold-start recovery of the entire HealthSetu production
backend following a total catastrophic infrastructure failure (e.g. cloud region loss,
multi-service compromise, or simultaneous Railway + database loss).

**Incident Commander**: Engineering Director / Lead Backend Architect
**Co-Commander**: Lead Database Administrator & Clinical Safety Officer
**Authorized Target RTO**: < 60 Minutes
**Authorized Target RPO**: < 5 Minutes

================================================================================
MASTER 15-STEP RECOVERY SEQUENCE
================================================================================

```
 1. Incident Containment & Declaring Disaster State
 2. Infrastructure & Cloud Resource Provisioning
 3. Database Availability & Point-In-Time Restoration
 4. Object Storage Availability & Access Verification
 5. Backend Container Deployment from Known-Good Git Release Tag
 6. Configuration & Secret Injection from Encrypted Vault
 7. Authentication & Token Signing Infrastructure Verification
 8. Monitoring & Telemetry Infrastructure Verification (/metrics)
 9. External Healthcare Provider Connectivity & Probe Validation
10. Background Workers Re-initialization with Idempotency Locks
11. Liveness Probe Verification (GET /api/v1/health -> 200 OK)
12. Readiness Probe Verification (GET /api/v1/ready -> 200 OK)
13. Core Integration Smoke Tests (scripts/verify_integration.py)
14. Clinical Safety & 12-Invariant Regression Validation
15. Controlled Production Traffic Cutover & Canary Ramp
```

================================================================================
STEP-BY-STEP EXECUTION GUIDE
================================================================================

### Step 1: Incident Containment & Disaster Declaration
- Formally declare SEV-0 disaster.
- Launch incident war room bridge (Slack `#incident-dr-bridge` / Zoom).
- Halt all active deployments and write-access on compromised infrastructure.

### Step 2: Infrastructure & Cloud Resource Provisioning
- Verify or spin up a clean Railway production environment in target region:
  ```bash
  railway init --project healthsetu-production-dr
  ```

### Step 3: Database Restoration (Supabase PostgreSQL)
- Database team restores database to target recovery point (PITR) following `docs/runbooks/database-restore.md`.
- Database team runs schema, foreign-key, and constraint verification.
- Obtain restored `DATABASE_URL` (with `sslmode=require`).

### Step 4: Object Storage Verification
- Verify private S3 bucket availability and cross-region replica synchronization following `docs/runbooks/object-storage-recovery.md`.
- Verify storage API credentials (`STORAGE_ACCESS_KEY`, `STORAGE_SECRET_KEY`).

### Step 5: Backend Container Deployment from Known-Good Source
- Deploy container image strictly from the verified, tagged Git release (e.g. `tags/v1.19.0`):
  ```bash
  # Deploy directly from Git tag
  git checkout tags/v1.19.0
  railway up --detach
  ```

### Step 6: Configuration & Secret Injection
- Inject all production secrets from the encrypted password vault:
  ```bash
  railway variables set \
    APP_ENV="production" \
    APP_VERSION="1.19.0" \
    DATABASE_URL="<Restored-Postgres-URL>" \
    JWT_SECRET_KEY="<Restored-Or-Rotated-JWT-Secret>" \
    STORAGE_ACCESS_KEY="<Restored-Storage-Key>" \
    STORAGE_SECRET_KEY="<Restored-Storage-Secret>" \
    AI_API_KEY="<API-Key>" \
    OCR_API_KEY="<API-Key>" \
    MEDICATION_SAFETY_API_KEY="<API-Key>"
  ```

### Step 7: Verify Authentication Infrastructure
- Verify JWT signing algorithms and password hasher initializations.
- Confirm fail-closed behavior for unauthorized requests.

### Step 8: Verify Monitoring & Telemetry
- Ensure `/metrics` endpoint is reachable and exporting Prometheus counters.
- Record initiation metric: `metrics.record_recovery_attempt("full_system")`.

### Step 9: Validate External Healthcare Providers
- Follow `docs/runbooks/provider-recovery.md`.
- Confirm Medication Safety engine, OCR engine, and AI fallbacks respond correctly.

### Step 10: Re-initialize Background Workers
- Restart asynchronous workers.
- Verify stale task locks are cleared and idempotency keys prevent duplicate processing.

### Step 11 & 12: Validate Liveness & Readiness Probes
```bash
# Liveness Probe (process responsiveness)
curl -f -s https://<railway-url>/api/v1/health | jq .
# Expected: {"status": "ok", "service": "healthsetu-backend", "version": "1.19.0"}

# Readiness Probe (database connectivity)
curl -f -s https://<railway-url>/api/v1/ready | jq .
# Expected: {"status": "ready", "checks": {"database": "available"}}
```

### Step 13: Execute Integration Smoke Test Suite
Run the full verification script:
```bash
python scripts/verify_integration.py
```
Assert that patient fetch, doctor clinical workspace, medication list, allergies, and consents pass 100%.

### Step 14: Clinical Safety Regression Verification
Execute clinical safety checks:
1. Confirm prospective medication safety evaluation alerts on major drug interactions.
2. Confirm medication safety provider outage does NOT report `CLEAR` or `SAFE`.
3. Confirm unverified OCR data remains marked `EXTRACTED_UNVERIFIED`.
4. Confirm audit logs are intact and chronological.

### Step 15: Controlled Traffic Restoration & DNS Cutover
1. Point `api.healthsetu.com` DNS CNAME to the recovered Railway endpoint.
2. Monitor initial canary traffic (5% -> 25% -> 100%).
3. Record recovery completion:
   ```python
   metrics.record_recovery_result(subsystem="full_system", success=True, duration_seconds=elapsed)
   ```
4. Begin 24-hour intensive post-recovery monitoring window.
