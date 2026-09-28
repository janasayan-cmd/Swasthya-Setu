# HealthSetu — Production Release Process & Change Management

## 1. Production Release Principle (Section 3)

Production releases follow a deterministic, gated progression:

```
    Build
      ↓
    Automated Test Suite
      ↓
    Security & PHI Validation
      ↓
    Database Compatibility Check
      ↓
    Staging Deployment
      ↓
    Staging Smoke Tests
      ↓
    Formal Release Approval
      ↓
    Production Deployment (Railway)
      ↓
    Health Check (/api/v1/health)
      ↓
    Readiness Check (/api/v1/ready)
      ↓
    Production Smoke Tests
      ↓
    Controlled Traffic Cutover
      ↓
    Operational Monitoring (5xx, latency, logs)
      ↓
    Go-Live Confirmation
```

---

## 2. Release Versioning (Section 14)

HealthSetu strictly adheres to **Semantic Versioning 2.0.0** (`MAJOR.MINOR.PATCH`):

- **PATCH** (`1.0.1`): Backwards-compatible bug fixes, security patches, dependency point updates, and performance tuning.
- **MINOR** (`1.1.0`): Backwards-compatible new features, added API endpoints, non-breaking schema additions, and non-destructive enhancements.
- **MAJOR** (`2.0.0`): Backwards-incompatible API changes, breaking data schema migrations, or fundamental architecture transitions requiring client migration.

---

## 3. Git Release Flow (Section 15)

```
[ Feature Branch ] ──> [ Pull Request ] ──> [ Code Review (2 Approvals) ]
                             │
                             ▼
                    [ CI Automated Suite ]
                             │
                             ▼
                      [ Staging Branch ] ──> (Staging Environment Deploy)
                             │
                             ▼
                    [ Git Tag: v1.0.0 ] ──> (Production Ingress Deploy)
```

1. **Feature Branches**: Branch from `main` named `feature/<short-desc>` or `fix/<short-desc>`.
2. **Pull Request**: Must pass CI automated checks and receive at least two peer reviews, including one from the Security or Clinical Safety Lead for sensitive modules.
3. **Release Tagging**: Production builds are triggered exclusively from cryptographically signed Git tags (e.g. `git tag -a v1.0.0 -m "Release v1.0.0"`).

---

## 4. CI/CD Requirements & Deployment Gates (Sections 16, 17)

Every release candidate MUST execute and pass all automated pipeline gates prior to production deployment:

1. **Linting & Code Quality**: `flake8` / `black --check` / `ruff`.
2. **Unit Tests**: Full execution of isolated unit tests across all domain services.
3. **Integration Tests**: Repository tests, database engine mock tests, and dependency checks.
4. **API Contract Tests**: OpenAPI 3.x schema validation (`test_openapi_contract.py`).
5. **Security & PHI Leakage Tests**: Scan for hardcoded credentials, secret patterns, and PHI leaks in log streams.
6. **Dependency Vulnerability Scan**: Audit `requirements.txt` against known CVEs (`pip-audit` / `safety`).
7. **Production Gate Failure**: Deployment immediately halts if any test fails, Docker build errors occur, or required environment variables are unset.

---

## 5. Database Release Coordination & Expand-Contract Pattern (Sections 18, 19)

When an application feature requires a database change:

```
[ Backend Change ] + [ Database Change ]
                  │
                  ▼
      [ Compatibility Review ]
                  │
                  ▼
         [ Migration Plan ]
                  │
                  ▼
       [ Staging Validation ]
                  │
                  ▼
      [ Production DB Migration ] ──> (Executed by Database Team)
                  │
                  ▼
      [ Backend Deployment ] ────────> (Executed by Backend Team)
                  │
                  ▼
       [ Operational Validation ]
```

### Expand-Contract Migration Pattern
To guarantee zero-downtime and rollback compatibility:
1. **Expand**: Database Team adds new nullable columns or tables. The existing backend ignores the new columns.
2. **Deploy Compatible Backend**: Backend Team deploys the new release that reads both old/new data and writes to the new schema.
3. **Data Backfill**: Database Team backfills historical records in background batches.
4. **Verify**: Systems operate stably on the new data structures.
5. **Contract**: In a subsequent release cycle, the deprecated old columns are safely dropped.

---

## 6. Controlled Traffic Cutover & Acceptance (Sections 25, 26)

1. **Container Startup**: Railway deploys the new container image alongside the active version.
2. **Liveness Verification**: Railway issues automated HTTP probes to `/api/v1/health`.
3. **Readiness Verification**: Probes verify database connectivity via `/api/v1/ready`.
4. **Synthetic Smoke Testing**: Responders execute the synthetic smoke test suite using test credentials.
5. **Traffic Cutover**: Ingress switches 100% of user traffic to the verified container.
6. **Go-Live Acceptance Criteria**:
   - `status == ok` on `/api/v1/health`.
   - `status == ready` and `database == available` on `/api/v1/ready`.
   - 0 container crash loops or restart events.
   - P95 latency $< 500\text{ms}$.
   - HTTP 5xx error rate $< 0.05\%$.
   - Zero clinical safety boundary violations observed.

---

## 7. Emergency Hotfix Policy (Section 28)

Emergency hotfixes are permitted exclusively for:
- Exploitable security vulnerabilities (CVE $\ge$ 8.0).
- Complete production service outage.
- Data corruption or clinical safety boundary failures.
- Severe regressions blocking critical clinician or patient workflows.

```
[ IDENTIFY SEVERITY ] ──> [ HOTFIX BRANCH ] ──> [ TARGETED PATCH ] ──> [ REGRESSION TEST ] ──> [ EXPEDITED APPROVAL ] ──> [ DEPLOY & MONITOR ]
```

All hotfixes MUST be merged back into `main` and tagged with an updated PATCH version (`v1.0.1`).
