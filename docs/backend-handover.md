# HealthSetu — Backend Operational Handover Document

## 1. Executive Summary & Purpose

This handover document provides complete operational, architectural, and procedural context for engineers, Site Reliability Engineers (SREs), and technical leads assuming operational ownership of the HealthSetu backend service (`api.healthsetu.com`).

---

## 2. Repository & Application Structure

### Repository Details
- **Repository URI**: `https://github.com/kamanasis/HealthSetu`
- **Primary Branch**: `main`
- **Runtime Environment**: Python 3.12 (Pinned in `pyproject.toml` and `Dockerfile`)
- **Web Framework**: FastAPI $\ge 0.115.0$ / Uvicorn (ASGI)

### Codebase Organization
```
HealthSetu/
├── app/
│   ├── api/                      # Routing layer
│   │   ├── router.py             # Root versioned API router (/api/v1)
│   │   └── v1/                   # Phase 1-18 endpoint controllers
│   ├── core/                     # Foundational runtime primitives
│   │   ├── config.py             # Pydantic BaseSettings & env parsing
│   │   ├── database.py           # SQLAlchemy asyncpg engine & pool
│   │   ├── security.py           # Argon2id & JWT crypto operations
│   │   ├── security_config.py    # Startup fail-closed security gates
│   │   ├── middleware.py         # Correlation, headers, size limiters
│   │   ├── logging.py            # Structured JSON operational logs
│   │   ├── log_sanitizer.py      # PHI & credential scrubbing filters
│   │   ├── metrics.py            # Prometheus metric collectors
│   │   └── exceptions.py         # Standardized error envelopes
│   ├── integrations/             # External service boundaries & providers
│   │   ├── ai/                   # LLM providers, prompts, and validators
│   │   ├── medication_safety/    # Interaction & allergy engines
│   │   ├── terminology/          # RxNorm / SNOMED normalization
│   │   ├── ocr/                  # Optical character recognition
│   │   └── triage/               # Deterministic rule engine
│   ├── models/                   # SQLAlchemy database entity models
│   ├── repositories/             # Database access & persistence abstraction
│   ├── schemas/                  # Pydantic request/response/domain models
│   ├── services/                 # Clinical business logic & orchestration
│   └── main.py                   # FastAPI application factory & lifespan
├── docs/                         # Technical documentation & runbooks
│   └── runbooks/                 # Incident mitigation & disaster recovery
├── tests/                        # Comprehensive automated test suite
├── Dockerfile                    # Production container build specification
├── railway.json                  # Railway deployment configuration
└── pyproject.toml                # Pinned project dependencies and metadata
```

---

## 3. Environment Variables & Secret Configuration

Production secrets are injected via Railway Dashboard under Service Settings:

| Environment Variable | Production Value / Description | Required? |
| :--- | :--- | :--- |
| `APP_ENV` | `production` | **Yes** |
| `APP_VERSION` | `1.0.0` | **Yes** |
| `DEBUG` | `false` (Fail-closed validation halts startup if `true`) | **Yes** |
| `HOST` | `0.0.0.0` | **Yes** |
| `PORT` | Dynamic `$PORT` provided by Railway (defaults to `8000`) | **Yes** |
| `DATABASE_URL` | `postgresql+asyncpg://<user>:<password>@<supabase-host>:5432/postgres` | **Yes** |
| `JWT_SECRET_KEY` | High-entropy random secret ($\ge 32$ characters) | **Yes** |
| `JWT_ALGORITHM` | `HS256` | **Yes** |
| `ACCESS_TOKEN_EXPIRE_MINUTES`| `15` | **Yes** |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `30` | **Yes** |
| `CORS_ALLOWED_ORIGINS` | `https://healthsetu.com,https://www.healthsetu.com` | **Yes** |
| `RATE_LIMIT_ENABLED` | `true` | **Yes** |
| `AI_ENABLED` | `true` (or `false` for safe disablement) | **Yes** |
| `AI_API_KEY` | Enterprise AI API Key (Gemini Vertex / OpenAI) | If AI enabled |
| `AI_DATA_RETENTION_MODE` | `stateless` | **Yes** |
| `AI_TRAINING_OPT_IN` | `false` (Fail-closed gate rejects startup if `true`) | **Yes** |

---

## 4. Cloud Infrastructure & Platform Dependencies

### Railway Container Deployment
- **Ingress URL**: `https://api.healthsetu.com`
- **Internal Port**: Automatically bound to dynamic `$PORT`.
- **Healthcheck Path**: `/api/v1/health` (Timeout: 100s).
- **Restart Policy**: `ON_FAILURE` (Max 10 retries).

### Supabase Managed PostgreSQL
- **Connection**: Managed asyncpg connection pool with health pre-pinging.
- **Connection Pool Size**: Default 10 connections, max overflow 20, recycle 1800s.
- **Database Team Ownership**: The database team manages migrations, table schemas, backups, and point-in-time recovery.

### Storage Dependencies
- **Medical Documents**: Stored in private, encrypted S3-compatible cloud storage buckets.
- **Access Control**: Documents are accessed via short-lived signed URLs with role and consent authorization checks.

---

## 5. Operational Procedures & Runbooks

All operational procedures are codified in `docs/runbooks/`:

| Scenario | Primary Runbook | Key Actions |
| :--- | :--- | :--- |
| **Backend Outage / 502** | `docs/runbooks/backend-down.md` | Inspect container logs, verify environment variables, trigger Railway restart. |
| **Database Unavailable** | `docs/runbooks/database-unavailable.md`| Check Supabase status, verify PgBouncer pool connections, execute failover. |
| **Elevated HTTP 5xx Errors** | `docs/runbooks/high-5xx.md` | Filter structured logs by `level=ERROR`, identify failing provider or query. |
| **Elevated Latency ($> 2\text{s}$)**| `docs/runbooks/high-latency.md` | Inspect slow query logs, review external provider timeouts. |
| **Security Incident / Leak** | `docs/runbooks/security-incident.md` | Revoke compromised credentials, rotate JWT secrets, audit access logs. |
| **Emergency Rollback** | `docs/runbooks/full-system-recovery.md` | Revert Railway deployment to previous release tag within 2 minutes. |

---

## 6. Testing, Quality & Acceptance Gates

Execute the full verification suite before promoting code:
```bash
# Run complete test suite (500+ unit, integration, and security tests)
pytest -q

# Run Phase 20 Production Go-Live verification suite
pytest tests/test_phase20_go_live.py -v
```

---

## 7. Operational Contact Matrix

- **Backend Technical Lead**: Sayan Mondal (`lead-backend@healthsetu.internal`)
- **Database Lead (DBA)**: Database Operations Team (`dba@healthsetu.internal`)
- **Cloud Infrastructure (SRE)**: Infrastructure On-Call (`sre-oncall@healthsetu.internal`)
- **Clinical Safety Officer**: Clinical Governance Board (`clinical-safety@healthsetu.internal`)
