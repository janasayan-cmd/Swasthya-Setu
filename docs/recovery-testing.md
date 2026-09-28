# HealthSetu — Disaster Recovery Testing & Validation Program (Phase 19)

================================================================================
1. TESTING POLICY & SAFETY GATES
================================================================================

HealthSetu maintains an uncompromising policy regarding disaster recovery:
    A DISASTER RECOVERY MECHANISM DOES NOT EXIST UNTIL IT HAS BEEN TESTED.

Recovery mechanisms that are only documented on paper inevitably fail during real
outages due to configuration drift, permission changes, or expired credentials.

### Critical Safety Invariants:
1. **Zero Production Patient Data in Recovery Testing**:
   - DR drills and restore exercises must NEVER execute against the live production database.
   - Restore tests use dedicated, isolated staging/recovery databases populated with synthetic test data.
2. **Environment Isolation**:
   - The disaster recovery testing environment is strictly isolated via independent VPCs and unique environment credentials.
   - `APP_ENV=recovery` is explicitly set to block any accidental cross-talk with production endpoints.
3. **No Clinical Workflow Compromise**:
   - Test exercises must not generate phantom alerts, test referrals, or mock prescriptions in external production healthcare partner systems.

================================================================================
2. DISASTER RECOVERY DRILL SCHEDULE
================================================================================

| Drill / Exercise | Cadence | Scope & Target Subsystem | Environment | Owning Team |
|------------------|---------|--------------------------|-------------|-------------|
| **Application Redeployment** | Monthly | Cold rebuild of Railway container from Git SHA | Staging / Railway | Backend |
| **Release Rollback** | Monthly | Instant rollback of running deployment to previous commit | Staging / Railway | Backend |
| **Database PITR Restore** | Quarterly | Full point-in-time restore from WAL archive to target second | Isolated DR Database | Database |
| **Secret Rotation Exercise** | Quarterly | End-to-end rotation of `JWT_SECRET_KEY` and API credentials | Staging | Backend / Security |
| **Object Storage Checksum Audit** | Quarterly | Cross-region replication and SHA-256 digest verification | Object Storage | Backend |
| **Provider Safe Degradation Drill**| Monthly | Synthetic blackhole test of Medication Safety & OCR APIs | Automated CI / Staging | Backend |
| **Full Disaster Recovery Exercise**| Semi-Annually | Multi-tier cold start of all systems from zero state | Isolated Cloud Region | Joint (Backend + DB) |

================================================================================
3. RECOVERY TEST SCENARIOS & PROCEDURES
================================================================================

### Scenario A: Application Rollback Drill
* **Objective**: Verify that an unhealthy release can be rolled back to the previous stable release within < 5 minutes without data corruption.
* **Procedure**:
  1. Record current stable deployment ID: `DEP_STABLE`.
  2. Deploy intentional failure commit (or simulated crash container).
  3. Verify automated health check failure (`GET /api/v1/health` returns failure).
  4. Trigger Railway rollback: `railway rollback`.
  5. Poll `/api/v1/health` and `/api/v1/ready`.
  6. Execute smoke test suite: `python scripts/verify_integration.py`.
* **Expected Result**: System returns to healthy status in under 3 minutes; smoke test passes 100%; `deployment_rollback_total` incremented.

### Scenario B: Database Restore & Schema Integrity Drill
* **Objective**: Verify that Supabase PostgreSQL WAL archive can be restored to an isolated instance and that all 14 clinical integrity domains are valid.
* **Procedure**:
  1. Database team triggers a PITR restore of the 24-hour-old WAL stream to an isolated target instance: `healthsetu-dr-test-db`.
  2. Database team verifies table row counts, foreign key constraints, and index validity.
  3. Backend container configured with `DATABASE_URL` pointing to the recovered instance.
  4. Backend container boots and executes startup checks.
  5. Automated verification script checks patient records, encounters, allergies, and prescriptions.
* **Expected Result**: Restore completes within 30 minutes; zero foreign key violations; backend connects and serves read queries without error.

### Scenario C: Medication Safety Provider Fail-Closed Drill (Phase 7)
* **Objective**: Verify that if the external drug interaction provider fails, the platform safely degrades and NEVER reports `CLEAR` or `SAFE`.
* **Procedure**:
  1. Point `MEDICATION_SAFETY_PROVIDER_URL` to an unreachable local mock blackhole (`http://127.0.0.1:9999`).
  2. Send a POST request to check prospective prescription (e.g. Aspirin + Warfarin).
  3. Assert response HTTP status and payload content.
  4. Verify response reports status `DEGRADED` or `UNKNOWN` with clinical warning.
  5. Assert that response alert list does NOT contain `CLEAR`, and overall evaluation is NOT `SAFE`.
* **Expected Result**: System fails closed; clinician is explicitly alerted; no false-negative safety checks.

### Scenario D: Medical Document Storage Checksum Validation Drill
* **Objective**: Verify that uploaded medical documents in object storage match the database SHA-256 digests.
* **Procedure**:
  1. Retrieve a random sample of 100 document records from the `documents` table.
  2. Fetch each corresponding object binary from S3 storage via pre-signed URL.
  3. Calculate the SHA-256 digest of each fetched byte stream.
  4. Compare the calculated digest against `documents.sha256_checksum`.
* **Expected Result**: 100% digest match; zero missing objects; pre-signed URL generation functional.

### Scenario E: Full Disaster Recovery Simulation (End-to-End)
* **Objective**: Simulate total loss of Railway application and primary database; rebuild entire platform from scratch.
* **Procedure**:
  1. Spin up a fresh Railway project / container runtime in a secondary cloud region.
  2. Point `DATABASE_URL` to the restored disaster recovery database.
  3. Restore production environment variables from encrypted password vault.
  4. Deploy backend directly from tagged release Git commit.
  5. Verify liveness probe (`/api/v1/health`) and readiness probe (`/api/v1/ready`).
  6. Execute full API smoke test suite: `python scripts/verify_integration.py`.
  7. Verify Prometheus `/metrics` exposition.
* **Expected Result**: Full platform operational and passing all smoke tests in under 45 minutes.

================================================================================
4. RECOVERY DRILL REPORTING TEMPLATE
================================================================================

Every recovery exercise must produce a post-drill report archived in `docs/dr-reports/`:

```markdown
# Disaster Recovery Drill Report: [DRILL-NAME]
- **Date / Time Executed**: [UTC Timestamp]
- **Lead Engineers**: [Names / Roles]
- **Scenario Tested**: [Scenario A / B / C / D / E]
- **Target RTO**: [e.g. 15 minutes] | **Actual RTO Achieved**: [e.g. 8 minutes 45 seconds]
- **Target RPO**: [e.g. 5 minutes]  | **Actual RPO Achieved**: [0 minutes]
- **Automated Test Results**: [X passed / Y failed]
- **Issues & Blockers Encountered**:
  1. [Description of any friction, permission error, or delay]
- **Corrective Action Items**:
  - [ ] [Task to improve runbook or automation] (Assignee: [Name], Due: [Date])
- **Sign-off**: Lead Clinical Engineer & Backend Lead
```
