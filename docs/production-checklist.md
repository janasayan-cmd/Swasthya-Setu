# HealthSetu — Production Go-Live & Operational Checklist

## 1. Pre-Go-Live Verification Checklist (Section 20)

Before authorizing production cutover to `https://api.healthsetu.com`, the following verification gates MUST be completed and checked:

- [x] **Backend Build**: Container image builds cleanly from pinned `Dockerfile`.
- [x] **Unit Tests**: Full unit test suite passes with 0 failures (`pytest tests/`).
- [x] **Integration Tests**: Repository layer and mock engine tests pass.
- [x] **API Contract Tests**: OpenAPI 3.x schema valid and up to date (`test_openapi_contract.py`).
- [x] **Security Tests**: No hardcoded credentials; input validation and rate limiting verified.
- [x] **PHI Leakage Tests**: Log sanitizers verified to strip patient names, phones, and emails.
- [x] **Database Integration**: Production Supabase PostgreSQL asyncpg connection verified via TLS.
- [x] **Authentication**: Argon2id password verification and JWT HS256 token issuance working.
- [x] **Authorization (RBAC)**: Role boundaries (PATIENT, DOCTOR, NURSE, ADMIN) enforced.
- [x] **Consent Enforcement**: Active purpose-based patient consent verified prior to clinician access.
- [x] **Document Processing**: Upload, SHA-256 deduplication, and OCR text extraction functioning.
- [x] **Medication Normalization**: RxNorm terminology mapping and canonical concept resolution working.
- [x] **Medication Safety Fail-Safe**: Provider timeout/failure yields `UNKNOWN` or `ERROR`, NEVER `CLEAR`.
- [x] **Clinical Triage Engine**: Deterministic triage rules assign operational urgency with disclaimer.
- [x] **Care Plan Generation**: Extracted discharge summaries generate versioned care plans.
- [x] **Clinician Workflow**: Clinical encounters, versioned notes, and orders recorded with audit link.
- [x] **Facility Discovery**: Departmental bed/service capacity and distance calculation operational.
- [x] **Transfer Workflow**: Two-sided clinician coordination requires explicit receiving facility acceptance.
- [x] **Interoperability Fail-Safe**: FHIR / ABDM exchange failures handle safely without data loss.
- [x] **AI Safety Boundaries**: Non-authoritative summarization verified; autonomous diagnosis blocked.
- [x] **Audit Trail**: Every clinical mutation logged to immutable audit repository.
- [x] **Operational Monitoring**: Prometheus `/metrics` endpoint exports HTTP latency and error counters.
- [x] **Health Endpoint**: `GET /api/v1/health` returns `status=ok` and `version=1.0.0`.
- [x] **Readiness Endpoint**: `GET /api/v1/ready` returns `status=ready` and `database=available`.
- [x] **Disaster Recovery**: Disaster recovery protocols and RTO/RPO targets codified in `docs/disaster-recovery.md`.
- [x] **Rollback Procedure**: 2-minute rollback procedure verified and tested on Railway platform.
- [x] **Production Secrets**: High-entropy JWT secrets and database credentials configured securely in Railway.
- [x] **Production CORS**: Restricted explicitly to `https://healthsetu.com` and `https://www.healthsetu.com`.
- [x] **Production Domain**: Custom domain `api.healthsetu.com` routed with automated SSL/TLS termination.
- [x] **OpenAPI Documentation**: Complete tag metadata and request/response models documented.
- [x] **Production Storage**: Private object storage bucket configured with restricted access policies.

---

## 2. Production Smoke Test Procedure (Section 21)

Execute immediately following any deployment using synthetic test accounts:

1. **Liveness Probe**:
   ```bash
   curl -fsS https://api.healthsetu.com/api/v1/health
   # Expected: {"status": "ok", "service": "healthsetu-backend", "version": "1.0.0"}
   ```
2. **Readiness Probe**:
   ```bash
   curl -fsS https://api.healthsetu.com/api/v1/ready
   # Expected: {"status": "ready", "checks": {"database": "available"}}
   ```
3. **Authentication Smoke**:
   Authenticate synthetic test account (`POST /api/v1/auth/login`) and retrieve JWT access token.
4. **Patient Self-Access Smoke**:
   Retrieve authenticated user profile via `GET /api/v1/auth/me`.
5. **IDOR Authorization Smoke**:
   Attempt to access another patient's records using test token $\longrightarrow$ Verify `403 Forbidden` / `404 Not Found`.
6. **Medication Safety Smoke**:
   Execute prospective safety check $\longrightarrow$ Verify provider returns valid evaluation with clinical disclaimer.
7. **Triage Evaluation Smoke**:
   Submit test symptom intake $\longrightarrow$ Verify deterministic urgency ranking and clinical disclaimer.

---

## 3. Clinical Safety Go-Live Verification (Section 22)

Verify the 7 core safety invariants:
- [x] **Medication Safety Provider Failure** $\longrightarrow$ `NOT CLEAR` (fails to `UNKNOWN`/`ERROR`).
- [x] **Missing Clinical Information** $\longrightarrow$ `NOT NORMAL` (flags `INSUFFICIENT_INFORMATION`).
- [x] **Extracted Information** $\longrightarrow$ `NOT Automatically Verified` (`is_verified=False`).
- [x] **Imported Information** $\longrightarrow$ `NOT Automatically Verified` (requires clinician review).
- [x] **AI Output** $\longrightarrow$ `NOT Clinical Authority` (advisory draft only; never diagnosis).
- [x] **Triage Output** $\longrightarrow$ `NOT Diagnosis` (operational urgency with mandatory disclaimer).
- [x] **Transfer Request** $\longrightarrow$ `NOT Automatic Transfer` (starts in `REQUESTED`; requires clinician acceptance).

---

## 4. Authorization & Isolation Go-Live Verification (Section 23)

- [x] Verify Patient A cannot query or mutate Patient B records (IDOR protection).
- [x] Verify Clinicians cannot access unconsented patient records.
- [x] Verify Organization and Facility boundaries are strictly enforced.

---

## 5. Operational Phase Checklists (Section 51)

### Pre-Deployment
- [ ] Pull request reviewed and approved by at least 2 senior engineers.
- [ ] Database migration compatibility confirmed with Database Team.
- [ ] CI pipeline passes: linting, tests, security scan, and Docker build.
- [ ] Railway environment variables verified.

### Deployment
- [ ] Git release tag created and pushed (`git tag -a v1.0.0`).
- [ ] Railway automated build initiated.
- [ ] Railway deployment healthcheck probe passes.

### Post-Deployment
- [ ] Execute Production Smoke Test Suite.
- [ ] Verify Prometheus metrics flow (`GET /api/v1/metrics`).
- [ ] Monitor error rate and container crash counts for 30 minutes.

### Rollback (If needed)
- [ ] Revert to previous deployment tag in Railway Dashboard.
- [ ] Verify database backward compatibility.
- [ ] Confirm service restoration via `/api/v1/health` and `/api/v1/ready`.

---

## 6. Production Support Incident Checklist (Section 52)

For every production incident:
- [ ] Incident identified and logged in incident tracking channel.
- [ ] Severity assigned (CRITICAL / HIGH / MEDIUM / LOW).
- [ ] Correlation `request_id` values extracted from client reports.
- [ ] Structured JSON logs reviewed for exceptions and trace context.
- [ ] Real-time Prometheus metrics reviewed for 5xx spikes or latency anomalies.
- [ ] Supabase database status and connection pool checked.
- [ ] External provider health checked (AI, RxNorm, Storage).
- [ ] Recent deployments and configuration changes audited.
- [ ] Security and PHI leakage evaluated.
- [ ] Clinical safety impact evaluated.
- [ ] Mitigation applied (rollback, failover, or restart).
- [ ] Recovery verified via smoke tests.
- [ ] Incident documented and blameless post-mortem scheduled within 48 hours.
