# HealthSetu — Disaster Recovery & Business Continuity Master Plan (Phase 19)

================================================================================
CRITICAL CLINICAL & OPERATIONAL GOVERNANCE
================================================================================
This document defines the disaster recovery (DR), backup, rollback, and business
continuity (BC) framework for the HealthSetu production backend platform.

HealthSetu handles sensitive electronic health records (EHR), prospective medication
safety evaluations, real-time emergency department triage, patient consent artifacts,
and cross-facility transfers. Under disaster conditions, operational priorities are:

    PATIENT SAFETY & DATA INTEGRITY > AUDIT PROVENANCE > SERVICE AVAILABILITY

Under NO circumstances shall recovery operations bypass clinical safety boundaries,
silently modify patient health records, invent clinical data, or bypass authentication
and authorization controls.

================================================================================
1. PRIMARY PRODUCTION ARCHITECTURE
================================================================================

```
                      [ FRONTEND APPLICATIONS ]
                    (Vercel / Clinical Portals)
                                 │
                                 ▼
                     https://api.healthsetu.com
              (Custom Domain / Cloudflare / Automated TLS)
                                 │
                                 ▼
                     [ RAILWAY PAAS CONTAINER ]
                 FastAPI Backend (Uvicorn / Python 3.12)
                 Stateless Application Runtime & Probes
                                 │
         ┌───────────────────────┼────────────────────────┐
         │                       │                        │
         ▼                       ▼                        ▼
[ SUPABASE POSTGRESQL ]   [ OBJECT STORAGE ]    [ HEALTHCARE PROVIDERS ]
- Primary Authoritative    - Encrypted Documents  - Medication Safety (Phase 7)
- Automated WAL & PITR     - Versioning Enabled   - AI Clinical Extraction
- Managed by DB Team       - SHA-256 Checksums    - Terminology / RxNorm
                                                  - Interoperability (FHIR/HL7)
                                                  - Geolocation Directory
```

Architecture Invariants:
1. **Stateless Backend**: The Railway FastAPI container holds no persistent patient state. All clinical state resides in Supabase PostgreSQL or private Object Storage.
2. **Authoritative Persistence**: Supabase PostgreSQL is the single source of truth for patient records, clinical encounters, allergies, medications, and audit logs.
3. **External Medical Documents**: Original clinical documents (PDFs, scans, DICOMs) are persisted in private object storage outside the container.
4. **Architectural Stability**: Phase 19 does NOT redesign application architecture, alter the PostgreSQL schema, or introduce new clinical workflows.

================================================================================
2. STRICT TEAM BOUNDARIES
================================================================================

### Backend Engineering Team Owns:
- Backend recovery procedures and orchestration runbooks
- Application redeployment to Railway or standby container infrastructure
- Railway platform configuration, build settings, and environment variables
- Secrets and configuration inventory (excluding raw DB master passwords)
- External healthcare provider connectivity, circuit-breakers, and fallback policies
- Object storage integration, secure pre-signed URLs, and client recovery
- Application rollback execution and version pinning
- Post-recovery smoke tests, integration validation, and clinical safety regression tests
- Recovery telemetry and Prometheus metrics instrumentation (`recovery_attempts_total`, etc.)

### Database Engineering Team Owns:
- Supabase PostgreSQL automated continuous backups and WAL archiving
- Point-In-Time Recovery (PITR) configuration and execution
- PostgreSQL snapshot management, restore operations, and retention policies
- Database integrity checks (foreign keys, table constraints, indices)
- Migration rollback scripts and schema compatibility verification
- Database disaster recovery testing and failover procedures

### Shared Responsibilities:
- Application-to-database schema compatibility and version coordination
- Recovery validation and end-to-end data integrity verification
- Release deployment order (backward-compatible schema changes first)
- Production recovery drills and joint post-incident reviews (PIR)

### Prohibited Actions:
- DO NOT create duplicate or competing production databases.
- DO NOT redesign the PostgreSQL schema during recovery.
- DO NOT create a second patient-record system.
- DO NOT automatically restore or sanitize corrupted clinical data without clinical engineering verification.
- DO NOT bypass security controls, RBAC, or consent enforcement during recovery.

================================================================================
3. CORE DISASTER RECOVERY PRINCIPLES
================================================================================

1. **Patient-Data Integrity First**: Recovery procedures must guarantee zero silent corruption of clinical facts, vitals, allergies, or medications.
2. **Recover Known-Good Versions**: Rollback and restoration targets must always be cryptographically identifiable, verified release tags or PITR timestamps.
3. **Verify Before Declaring Recovery Complete**: A responding `/health` endpoint is insufficient; full readiness, database integrity, and clinical safety tests must pass.
4. **Least Privilege**: Recovery operations must be executed exclusively by authorized engineering personnel using role-based access controls and auditable credentials.
5. **Documented & Auditable Recovery**: Every manual intervention, database restore, or credential rotation must be logged with incident timestamps and actor identities.
6. **No Silent Data Loss**: If a database PITR restore causes data loss between the failure point and the restore point, the affected interval must be formally identified, reconciled, and documented.
7. **No Uncontrolled Rollback**: Downgrading an application release without verifying schema compatibility is strictly prohibited.
8. **No Unsafe Clinical-State Reconstruction**: Missing clinical context must never be filled in with default "normal" values. Missing data is explicitly UNKNOWN.
9. **No Production Experimentation**: Triage and emergency fixes must be verified in an isolated staging or recovery environment before production application.

CRITICAL INVARIANT PRESERVATION:
Recovery procedures MUST preserve:
- Provenance (source of every record, import metadata, and practitioner identity)
- Audit History (immutable audit trail preserved across failovers)
- Verification State (unverified OCR extractions remain unverified)
- Medication Safety State (active medications remain distinct from historical)
- Clinical Record Integrity (all foreign-key patient relationships intact)
- Document Integrity (checksum verified against object storage)
- Consent State (active consents, denials, and revocations enforced)

================================================================================
4. 22 FAILURE SCENARIOS & RECOVERY STRATEGIES
================================================================================

| # | Failure Scenario | Impact | Primary Recovery Action | Owning Team |
|---|------------------|--------|-------------------------|-------------|
| 1 | Railway Application Outage | Backend API unavailable | Trigger standby deployment / redeploy to alternative region or container platform | Backend |
| 2 | Failed Production Deployment | New version fails health check or crashes | Immediate automated/manual rollback to previous known-good deployment | Backend |
| 3 | Container Crash | OOM or unhandled fatal exception | Container auto-restart; inspect logs/metrics; scale memory limits if valid | Backend |
| 4 | Configuration Corruption | Misconfigured env vars cause startup failure | Restore verified environment variable snapshot from secure inventory | Backend |
| 5 | Secret / Config Loss | Lost API keys or database credentials | Repopulate Railway variables from encrypted vault (Bitwarden/1Password) | Backend |
| 6 | Supabase PostgreSQL Outage | Database connectivity severed | Failover to Supabase standby read/write replica; backend enters degraded mode (503) | Database |
| 7 | PostgreSQL Data Corruption | Corrupted table pages or logical corruption | Point-In-Time Recovery (PITR) to timestamp immediately prior to corruption | Database / Shared |
| 8 | Accidental Data Deletion | Clinical records deleted via rogue query | PITR restore to staging DB; selective row-level clinical reconciliation | Database / Shared |
| 9 | DB Migration Failure | Schema migration fails halfway | Halt deployment; DB team executes migration rollback script; restore compatible backend | Shared |
| 10| Object Storage Outage | Documents cannot be uploaded or downloaded | Backend enters degraded mode; document endpoints return explicit 503; retry queued | Backend |
| 11| Object Storage Accidental Deletion | S3 objects removed | Restore objects from object versioning or cloud replication bucket; verify checksums | Backend |
| 12| OCR Provider Outage | Prescription/report scans cannot be extracted | Preserve raw document; mark extraction as PENDING; retry with exponential backoff | Backend |
| 13| Medication Terminology Outage | RxNorm / drug search unavailable | Use internal cached terminology database; return partial match with warning | Backend |
| 14| Medication Safety Outage | Drug interaction/allergy engine down | Phase 7 fail-closed rule: Return UNKNOWN / ERROR; NEVER return CLEAR or SAFE | Backend |
| 15| AI Provider Outage | Clinical summarization or extraction down | Fall back to deterministic rules or return safe failure; NEVER invent clinical facts | Backend |
| 16| Interoperability Outage | FHIR / HL7 partner endpoint unavailable | Buffer outgoing requests in dead-letter/retry queue; preserve source provenance | Backend |
| 17| Domain / DNS Failure | api.healthsetu.com unresolvable | Verify DNS provider records; update CNAME to Railway DNS target; check TTL | Backend |
| 18| Security Incident | Active intrusion or abnormal access | Isolate network; revoke tokens; rotate master credentials; audit access logs | Backend / Security |
| 19| Credential Compromise | Secret leaked in logs or external repo | Immediate key revocation; generate new secret; redeploy backend; invalidate sessions | Backend / Security |
| 20| Large-Scale Infra Outage | Multi-service cloud provider downtime | Activate multi-region disaster recovery standby; execute full-system restore runbook | Shared |
| 21| App Version Incompatibility | Backend schema expectations mismatch DB | Pin backend container to compatible git commit matching current DB schema | Backend |
| 22| Background Job Corruption/Failure| Asynchronous queue stuck or failing jobs | Purge poison messages to dead-letter queue; enforce worker idempotency; restart worker | Backend |

================================================================================
5. RECOVERY OBJECTIVES (RPO & RTO)
================================================================================

HealthSetu defines strict operational recovery targets derived from actual clinical
and infrastructure dependencies. These targets balance patient safety with real-world
cloud provider capabilities.

### Recovery Point Objective (RPO)
The maximum acceptable data loss measured in time:

| Subsystem | RPO Target | Mechanism & Dependency Assumptions | Recovery Limitations |
|-----------|------------|------------------------------------|----------------------|
| **Core Database (Supabase)** | **< 5 minutes** | Continuous WAL archiving with Supabase automated PITR; physical backup snapshots taken daily. | Uncommitted transactions in flight during unexpected DB termination cannot be recovered. |
| **Medical Documents (Object Storage)** | **0 minutes** | Object versioning enabled; deletion protection (MFA delete) enabled; cross-region replication. | In-transit uploads aborted during network partition must be re-uploaded by the client. |
| **Backend Application Runtime** | **0 minutes** | Stateless architecture. Pinned Git commits, automated Dockerfile builds, static configuration inventory. | In-memory HTTP metrics are reset on container restart (aggregated in Prometheus). |
| **Audit Logs** | **< 5 minutes** | Synchronous database persistence within PostgreSQL audit table with WAL streaming. | Any crash occurring before transaction commit is rolled back by PostgreSQL. |

### Recovery Time Objective (RTO)
The maximum acceptable downtime before service restoration:

| Failure Mode | RTO Target | Procedure & Dependency Assumptions | Recovery Limitations |
|--------------|------------|------------------------------------|----------------------|
| **Backend Release Rollback** | **< 5 minutes** | Railway deployment rollback to previous known-good deployment artifact via CLI/UI. | Dependent on Railway API availability. |
| **Container Crash / OOM** | **< 2 minutes** | Railway automated health check restart policy; container restart. | Railway node health. |
| **Database Read Replica Failover** | **< 10 minutes**| Supabase automated managed standby promotion. | Supabase control plane availability. |
| **Database Point-In-Time Restore**| **< 30 minutes**| Database team restores snapshot to isolated instance; compatibility validated. | Restore duration scales with total database storage volume. |
| **External Provider Outage** | **0 minutes (Immediate)** | Automated circuit breaking; immediate graceful degradation to safe failure state. | Third-party service downtime remains outside HealthSetu control. |
| **Full Disaster Recovery** | **< 60 minutes**| Cold-start restoration across all infrastructure components using master runbook. | Requires authorized on-call engineers with secure vault access. |

================================================================================
6. APPLICATION RECOVERY MODEL
================================================================================

The HealthSetu production backend MUST be 100% reproducible from immutable assets:

```
  Source Repository (GitHub: main branch / release tags)
       +
  Dockerfile (Multi-stage Python 3.12-slim build)
       +
  Dependency Lock (requirements.txt with strict hash/version pins)
       +
  Environment Configuration (.env.production specification)
       +
  Railway Configuration (railway.json / Procfile)
       +
  Database (Supabase PostgreSQL schema + WAL recovery point)
       +
  Object Storage (S3-compatible bucket + IAM policy)
       +
  External Provider Credentials (Vault-backed API credentials)
       =
  RECOVERABLE PRODUCTION BACKEND
```

Zero Dependency on Local State:
- No production code, migration, or certificate may exist exclusively on a developer workstation.
- Every deployed container artifact must correspond to an identifiable Git commit SHA.

================================================================================
7. SOURCE CODE & DOCKER IMAGE RECOVERY
================================================================================

1. **Git Repository Management**:
   - Master repository hosted on GitHub: `HealthSetu`.
   - Release branches are protected; force-pushes are blocked.
   - Every production deployment MUST be tagged with semantic versioning (e.g. `v1.19.0`) and map directly to a commit SHA.
2. **Reproducible Docker Images**:
   - Production Docker images are built from the workspace root `Dockerfile`:
     - Base image: `python:3.12-slim`
     - Pinned dependencies installed from `requirements.txt`
     - Non-root user execution (`appuser`)
     - Standard entrypoint: `uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}`
3. **Image Metadata**:
   - Build metadata includes `APP_VERSION`, Git commit hash, and build timestamp.

================================================================================
8. RAILWAY APPLICATION RECOVERY & ROLLBACK
================================================================================

### Failure Detection:
- Railway monitors container exit codes and probes `GET /api/v1/health`.
- If 3 consecutive health probes fail or container crashes, Railway marks deployment as `CRASHED` or `UNHEALTHY`.

### Rollback Procedure:
```
           [ FAILED DEPLOYMENT DETECTED ]
                         │
                         ▼
        [ Step 1: Halt Rollout / Stop Deployment ]
                         │
                         ▼
      [ Step 2: Identify Previous Known-Good Release ]
       (Inspect Railway Deployment History / Git Tag)
                         │
                         ▼
      [ Step 3: Trigger Rollback in Railway ]
       railway rollback OR UI -> Deploy Previous
                         │
                         ▼
      [ Step 4: Verify Liveness Probe: GET /health ]
                         │
                         ▼
      [ Step 5: Verify Readiness Probe: GET /ready ]
                         │
                         ▼
      [ Step 6: Execute HealthSetu Smoke Test Suite ]
       python scripts/verify_integration.py
                         │
                         ▼
     [ Step 7: Record Metrics & Confirm Recovery ]
      metrics.record_deployment_rollback()
```

================================================================================
9. DATABASE BACKUP & RESTORE INTEGRATION
================================================================================

1. **Database Team Authority**:
   - Supabase PostgreSQL backups are managed strictly by the Database Team.
   - Continuous WAL archiving guarantees Point-In-Time Recovery (PITR) capability.
2. **Restore Safety Checks (Before Restoring Data)**:
   - Identify the affected database instance and reason for restore.
   - Preserve incident evidence: Take an immediate forensic snapshot of the current state before rolling back.
   - Determine whether uncommitted or recent records since the recovery point can be salvaged.
   - Document the formal Recovery Decision signed off by the Incident Commander and Lead Clinical Engineer.
3. **Controlled Restore Flow**:
   ```
   Forensic Snapshot -> PITR Restore -> Schema Integrity Check -> Backend Reconnect -> Smoke Tests
   ```
4. **Migration Failure Recovery**:
   - If a database migration fails during deployment:
     1. Stop backend deployment immediately.
     2. Database team executes migration down/rollback script.
     3. Verify database schema compatibility with the previous backend version.
     4. Redeploy known-good backend container.
     5. Run automated test suite to confirm data integrity.

================================================================================
10. DATA INTEGRITY VALIDATION
================================================================================

Following any database restoration or failover, the engineering team MUST execute
integrity verification across 14 critical clinical domains:

1. **Patient Records**: Demographic, contact, and identifier records accessible and unmodified.
2. **Clinical Relationships**: Doctor-patient assignments and clinician linkages preserved.
3. **Encounters**: Chronological encounter history and consultation notes intact.
4. **Medication Records**: Active medications distinct from historical; dosage intact.
5. **Prescriptions**: Prescriptions linked to valid encounters and clinicians.
6. **Allergies & Sensitivities**: Critical hypersensitivities and severe reaction flags intact.
7. **Document Metadata**: Document IDs, mime-types, file sizes, and patient associations intact.
8. **Triage Records**: Emergency department acuity scores (ESI 1-5) and vital signs intact.
9. **Care Plans**: Multi-disciplinary care plans and goal targets intact.
10. **Clinician Records**: Clinician licenses, specializations, and departmental mappings intact.
11. **Organization / Facility Relationships**: Hospital networks and department hierarchies intact.
12. **Transfer Records**: Inter-facility transfer requests, approvals, and statuses intact.
13. **Interoperability Records**: FHIR resource mappings and HL7 message history intact.
14. **Audit Logs**: Immutable audit log chain, actor IDs, timestamps, and action types intact.

CRITICAL RULE: DO NOT execute automatic bulk scripts to "clean up" or modify clinical records
to make them appear valid. Discrepancies must be flagged for clinical review.

================================================================================
11. OBJECT STORAGE RECOVERY & DOCUMENT CHECKSUMS
================================================================================

1. **Storage Decoupling**:
   - Clinical documents (discharge summaries, lab PDFs, scan images) are stored in private S3-compatible object storage.
   - The PostgreSQL `documents` table stores file metadata, object keys, and SHA-256 checksums.
2. **Consistency Verification**:
   - Restored systems must validate the three-way agreement:
     `Document Metadata (DB) <===> Object Existence (Storage) <===> SHA-256 Checksum`
3. **Accidental Deletion Recovery**:
   - S3 bucket versioning allows immediate undeletion of soft-deleted object versions.
   - Cross-region replication provides backup copies in case of primary bucket failure.

================================================================================
12. SECRETS RECOVERY & COMPROMISE MANAGEMENT
================================================================================

1. **Inventory of Required Secrets**:
   - `DATABASE_URL` (Supabase PostgreSQL connection string with TLS `sslmode=require`)
   - `JWT_SECRET_KEY` (Symmetric secret for HS256 JWT access and refresh token signing)
   - `STORAGE_ACCESS_KEY` / `STORAGE_SECRET_KEY` (Object storage credentials)
   - `AI_API_KEY` (Gemini / Anthropic / OpenAI clinical extraction keys)
   - `OCR_API_KEY` (Document OCR service credentials)
   - `MEDICATION_SAFETY_API_KEY` (RxNorm / interaction engine credentials)
   - `INTEROPERABILITY_CREDENTIALS` (ABDM / FHIR partner client certificates / secrets)
2. **Secrets Storage**:
   - Secrets are stored exclusively in Railway encrypted environment variables and backed up in an enterprise password vault (Bitwarden/1Password). Secrets are NEVER committed to Git.
3. **Compromise Response**:
   - Immediate key revocation on the provider portal.
   - Generate high-entropy replacement credential.
   - Update Railway environment variables.
   - Trigger zero-downtime redeployment.
   - Invalidate all existing user sessions if `JWT_SECRET_KEY` is compromised.
   - Inspect security audit logs for unauthorized access during the exposure window.

================================================================================
13. DOMAIN & DNS RECOVERY
================================================================================

1. **Production Domain**: `api.healthsetu.com`
2. **DNS Architecture**:
   - Hosted on managed DNS (Cloudflare / Route53).
   - Record type: `CNAME` pointing to Railway custom domain target (`xxx.railway.app`).
   - TTL: Configured to 300 seconds (5 minutes) for rapid disaster failover.
3. **DNS Outage Recovery Steps**:
   1. Query DNS propagation using `dig api.healthsetu.com +trace` and `nslookup`.
   2. Verify Railway Custom Domain configuration and automated TLS certificate status.
   3. If DNS provider is compromised or down, update nameservers to backup DNS provider.
   4. Verify endpoints: `curl -I https://api.healthsetu.com/api/v1/health`.
   5. Execute smoke tests once DNS propagation confirms resolution.

================================================================================
14. EXTERNAL HEALTHCARE PROVIDER RECOVERY & CLINICAL SAFETY
================================================================================

### Medication Safety Engine Recovery (Phase 7 Governance)
- During external provider outage:
  - System enters degraded mode.
  - Evaluation returns `UNKNOWN` or `ERROR` with explicit clinical warning.
  - Provider unavailable MUST NEVER evaluate to `CLEAR` or `SAFE`.
- After provider recovery:
  1. Validate provider API reachability and TLS handshake.
  2. Verify API key authentication with a test query (e.g. check Aspirin vs Warfarin).
  3. Validate returned response structure and provider engine version.
  4. Record provider recovery metric: `metrics.record_provider_recovery("medication_safety")`.
  5. Resume automated clinical safety checks.

### OCR & Document Extraction Recovery
- Raw uploaded document is always preserved in object storage regardless of OCR status.
- Document processing state marked `PENDING` or `FAILED` during outage; never fabricate extracted clinical fields.
- Background worker re-processes queued documents when OCR service confirms availability.

### AI Clinical Provider Recovery
- AI services are strictly non-authoritative assistive tools.
- AI failure immediately falls back to deterministic rule-based algorithms or explicit safe error messages.
- AI outage NEVER results in automated diagnosis, automated prescription, or invented triage scores.

### Interoperability Provider Recovery
- If external FHIR/HL7 endpoints fail, outgoing transfers are queued with exponential backoff.
- Inbound records maintain source provenance and are never allowed to overwrite verified internal records.

================================================================================
15. BACKGROUND JOB RECOVERY & DUPLICATE-PROCESSING PROTECTION
================================================================================

1. **Lifecycle States**:
   `QUEUED` -> `PROCESSING` -> `COMPLETED` | `FAILED` | `RETRYING` | `CANCELLED`
2. **Idempotency Enforcement**:
   - Every background job (OCR extraction, document indexing, FHIR push) is assigned an immutable `idempotency_key`.
   - Before executing, worker checks if a completed result already exists for the key.
   - If job is in `PROCESSING` state for longer than timeout (e.g. 5 minutes), worker safely reclaims lock or fails the job.
3. **Duplicate Processing Prevention**:
   - Workers MUST NOT re-execute already completed clinical workflows after a server restart.
   - Dead-letter queues store permanently failed jobs for manual engineering inspection.

================================================================================
16. SESSION & AUTHENTICATION RECOVERY
================================================================================

1. **Fail-Closed Security**:
   - If authentication infrastructure or token verification encounters an error, the system denies access by default (HTTP 401/403).
   - Under no circumstances is authentication bypassed to "keep the system running" during an incident.
2. **Token Invalidation**:
   - In the event of a security incident or `JWT_SECRET_KEY` rotation, all existing JWT tokens immediately become invalid.
   - Users are forced to re-authenticate using their credentials.

================================================================================
17. SECURITY INCIDENT & RANSOMWARE RECOVERY
================================================================================

1. **Containment Protocol**:
   - Isolate affected network boundaries or pause the Railway service if active compromise is detected.
   - Preserve volatile container memory and logs before restarting containers.
2. **Ransomware / Destructive Activity**:
   - Do NOT overwrite backups.
   - Verify backup snapshot integrity and confirm cold-storage air-gapped snapshots are clean.
   - Restore database to a clean, isolated recovery environment.
   - Perform full malware and vulnerability audit before redirecting production DNS traffic.

================================================================================
18. RECOVERY ENVIRONMENTS & RECOVERY DATABASE SAFETY
================================================================================

1. **Environment Segregation**:
   - Environments: `development`, `staging`, `production`, `recovery`.
   - Distinct environment variables prevent cross-environment contamination.
   - `APP_ENV` strictly distinguishes the operating mode.
2. **Zero Production Data in Test Restores**:
   - Routine DR restore drills use synthetic or sanitized patient data.
   - DR testing MUST NEVER execute against the live production database.

================================================================================
19. RECOVERY VALIDATION: DEFINITION OF RECOVERED
================================================================================

A system MUST NEVER be declared recovered merely because `GET /health` returns HTTP 200.
Formal Declaration of Recovery requires unanimous satisfaction of:

[ ] Liveness probe: `GET /api/v1/health` returns `200 OK`
[ ] Readiness probe: `GET /api/v1/ready` returns `200 OK` (database confirmed available)
[ ] Database connectivity: Read and write transactions verified
[ ] Object storage: Pre-signed upload and download URLs functional
[ ] Authentication: Login and token generation operational
[ ] Authorization: Role-based access control and consent enforcement confirmed
[ ] Audit Logging: Audit records successfully written and immutable
[ ] Smoke Tests: Core API workflows pass via `scripts/verify_integration.py`
[ ] Clinical Safety Tests: Prospective medication safety fails closed and evaluates accurately
[ ] Monitoring: Telemetry active and reporting to Prometheus `/metrics`

================================================================================
20. CLINICAL SAFETY RECOVERY TESTS (12 INVARIANTS)
================================================================================

Following recovery, the automated test suite verifies:
1. Medication safety provider failure does NOT evaluate to `CLEAR` or `SAFE`.
2. Missing clinical context is NOT converted to default "NORMAL".
3. Extracted OCR data remains clearly distinguishable from verified clinician data.
4. Imported interoperability records remain distinct from internally verified records.
5. Historical medications do NOT automatically become active prescriptions.
6. Triage acuity scoring remains distinct from clinical diagnosis.
7. SBAR handover summaries remain distinct from diagnosis.
8. AI outputs remain strictly assistive and non-authoritative.
9. Facility capabilities and bed availability are never fabricated.
10. Transfer requests do not automatically execute without clinician authorization.
11. Clinical audit trails remain accessible, sequential, and un-truncated.
12. Deny-by-default authorization remains strictly enforced.

================================================================================
21. RECOVERY INVENTORY & DEPENDENCY MAP
================================================================================

### Recovery Inventory:
| Component | Owner | Provider | Production Endpoint / Target | Backup / Recovery Mechanism | Primary Validation Procedure |
|-----------|-------|----------|------------------------------|-----------------------------|------------------------------|
| **Backend API** | Backend Team | Railway | `https://api.healthsetu.com` | Pinned Git commit / Dockerfile redeploy | `GET /api/v1/health` + `verify_integration.py` |
| **Database** | Database Team | Supabase | Managed PostgreSQL (AWS) | Continuous WAL / PITR automated snapshots | `GET /api/v1/ready` + row count & FK verification |
| **Object Storage** | Backend Team | S3 / Supabase Storage | Private S3 Bucket | Versioning enabled / Cross-region replication | Pre-signed URL GET / SHA-256 checksum match |
| **DNS / CDN** | Backend Team | Cloudflare / Route53 | `api.healthsetu.com` | Managed DNS with 300s TTL / Standby NS | `dig` verification + TLS cert check |
| **Authentication** | Backend Team | FastAPI (Argon2 / JWT) | `/api/v1/auth/*` | Vault-backed `JWT_SECRET_KEY` | POST `/api/v1/auth/login` for demo personas |
| **OCR Service** | Backend Team | Cloud OCR Provider | HTTPS REST API | Fail-safe queueing / original file retention | Test OCR request on standard document scan |
| **Medication Terminology**| Backend Team | RxNorm / NLM | HTTPS REST API | Internal local fallback cache | Drug search query resolution |
| **Medication Safety** | Backend Team | Internal / DrugBank | `/api/v1/patients/{id}/medication-safety/*` | Fail-closed UNKNOWN evaluation | Negative & positive interaction test payload |
| **AI Assistive Engine** | Backend Team | Gemini / OpenAI | HTTPS REST API | Deterministic rule fallback / safe error | Controlled clinical extraction test |
| **Interoperability** | Backend Team | ABDM / FHIR Partner | HTTPS REST API | Dead-letter queue / idempotent replay | HL7 / FHIR mock import validation |
| **Geolocation** | Backend Team | OSRM / Mapbox | HTTPS REST API | Internal coordinate cache | Facility search by geo-coordinates |
| **Monitoring** | Backend Team | Prometheus / Grafana | `/metrics` | Ephemeral telemetry + external Prometheus | `GET /metrics` text exposition format |

### Dependency Map:
```
                      [ HealthSetu Backend ]
                                 │
         ┌───────────────────────┼────────────────────────┐
         │                       │                        │
         ▼                       ▼                        ▼
[ PostgreSQL DB ]       [ Object Storage ]      [ Monitoring Engine ]
 (Authoritative Data)    (Medical Documents)     (Prometheus / Grafana)
         │                       │
         ├───────────────────────┼────────────────────────┐
         │                       │                        │
         ▼                       ▼                        ▼
[ Medication Safety ]     [ OCR Engine ]          [ AI Engine ]
 (Phase 7 Fail-Closed)   (Prescription Scans)    (Assistive Extraction)
         │                       │
         ▼                       ▼
[ Terminology Engine ]   [ Interoperability ]
 (RxNorm / SNOMED)       (FHIR / HL7 / ABDM)
```

================================================================================
22. RECOMMENDED 15-STEP RECOVERY ORDER
================================================================================

```
 1. Incident Containment & Triage
 2. Verify Underlying Cloud Infrastructure Availability
 3. Restore & Verify Database Availability (Supabase PostgreSQL)
 4. Restore & Verify Object Storage Availability
 5. Deploy Known-Good Backend Container (Railway)
 6. Restore & Verify Environment Variables & Secrets
 7. Verify Authentication & Token Infrastructure
 8. Verify Monitoring & Telemetry Systems (/metrics)
 9. Probe & Restore Critical External Healthcare Providers
10. Re-initialize Background Workers with Idempotency Protection
11. Validate Liveness Probe (/api/v1/health)
12. Validate Readiness Probe (/api/v1/ready)
13. Execute Core Integration Smoke Tests (verify_integration.py)
14. Execute Clinical Safety & Regression Verification Tests
15. Controlled Production Traffic Restoration (Canary / Full)
```

================================================================================
23. CONTROLLED TRAFFIC RESTORATION & POST-RECOVERY MONITORING
================================================================================

### Traffic Restoration Flow:
```
Recovery Complete -> Health OK -> Ready OK -> Smoke Tests Pass -> Canary Traffic (5%) -> Full Traffic
```

### Post-Recovery Monitoring Window:
Following recovery, the on-call engineering team maintains an intensive monitoring
window of at least **2 hours** (for minor incidents) or **24 hours** (for major disaster recoveries).

Metrics tracked with alert thresholds:
- HTTP 5xx error rate (< 0.1%)
- HTTP p95 latency (< 250ms)
- Database connection errors (= 0)
- Authentication / authorization anomalies
- Background job dead-letter rates (= 0)
- Medication safety provider errors
- Container memory and CPU utilization (< 75%)

================================================================================
24. RECOVERY METRICS INSTRUMENTATION
================================================================================

Operational disaster recovery telemetry is tracked in `app/core/metrics.py` without
exposing patient identifiers:
- `recovery_attempts_total{subsystem="<name>"}`
- `recovery_success_total{subsystem="<name>"}`
- `recovery_failure_total{subsystem="<name>"}`
- `recovery_duration_seconds{subsystem="<name>"}`
- `database_restore_duration_seconds`
- `deployment_rollback_total`
- `provider_recovery_total{provider="<name>"}`

================================================================================
25. POST-INCIDENT REVIEW (PIR) TEMPLATE
================================================================================

For any disaster recovery or significant rollback event, the Incident Commander
must publish a PIR document within 48 hours containing:

- **Incident ID**: `INC-YYYYMMDD-XX`
- **Failure Type**: (e.g. Database Outage, Deployment Crash, Secret Compromise)
- **Detection Time & Mechanism**: (Automated Alert vs Customer Report)
- **Impact Duration & Affected Services**:
- **Recovery Point Objective (RPO) Achieved**: (Minutes of data loss, if any)
- **Recovery Time Objective (RTO) Achieved**: (Total minutes to restoration)
- **Root Cause Analysis (5 Whys)**:
- **Sequential Recovery Steps Taken**:
- **Data Integrity Verification Result**: (Summary of 14-point check)
- **Security & Authorization Verification Result**:
- **Clinical Safety Verification Result**:
- **Corrective & Preventive Actions Assigned**:
