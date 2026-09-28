# HealthSetu — Production Architecture Specification

## 1. System Overview & Topology

HealthSetu is a unified healthcare interoperability, clinical coordination, and patient safety backend platform. The production architecture is structured as a resilient, containerized service running on **Railway**, backed by a managed **Supabase PostgreSQL** instance, private object storage, and authenticated external healthcare providers:

```
[ CLINICAL ACTORS & PATIENTS ]
             │
             │ HTTPS (TLS 1.3)
             ▼
     healthsetu.com (Frontend on Vercel)
             │
             │ HTTPS API (TLS 1.3, Strict CORS, Correlation Header)
             ▼
   api.healthsetu.com (Railway Ingress / Custom Domain)
             │
             ▼
┌─────────────────────────────────────────────────────────────────┐
│            RAILWAY CONTAINER: FASTAPI / UVICORN                 │
│                                                                 │
│  [ Middlewares: SecurityHeaders, SizeLimit, CORS, RateLimit ]   │
│                                │                                │
│                     [ Central Exception Handler ]               │
│                                │                                │
│                     [ API Router: /api/v1/... ]                 │
│                                │                                │
│  ┌─────────────────────────────┼─────────────────────────────┐  │
│  │ Phase 1-3: Core & Identity  │ Phase 4-6: Records & Rx     │  │
│  │ Phase 7-9: Safety & Care    │ Phase 10-12: Network/Xfer   │  │
│  │ Phase 13-14: Interop & AI   │ Phase 15-19: Ops & DR       │  │
│  └─────────────────────────────┼─────────────────────────────┘  │
│                                │                                │
│         [ Repository Layer & Data Provenance Tracker ]          │
└────────────────────────────────┬────────────────────────────────┘
                                 │
         ┌───────────────────────┼───────────────────────┐
         │ (asyncpg pool / TLS)  │ (Private API / TLS)   │ (HTTPS / Auth)
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────────┐
│    SUPABASE     │    │  OBJECT STORAGE │    │ EXTERNAL PROVIDERS  │
│   POSTGRESQL    │    │ (S3 / Encrypted)│    │ • RxNorm Terminology│
│  • App DB       │    │ • Medical Docs  │    │ • Med Safety Engine │
│  • Audit Trail  │    │ • Scanned PDF/TIFF│  │ • OCR / Textract    │
│  • Consents     │    │ • Extracted Text│    │ • ABDM / FHIR R4    │
└─────────────────┘    └─────────────────┘    │ • Non-Auth AI Layer │
                                              └─────────────────────┘
```

---

## 2. Strict Team Boundaries & Database Contract

### Backend Team Ownership
- Backend production readiness and runtime lifecycle.
- Application deployment on Railway.
- API lifecycle management (`/api/v1`), OpenAPI schema specifications, and contract stability.
- Application configuration, secrets injection, and environment separation.
- Security patch management and dependency upgrade evaluation.
- Application-layer verification, release rollback, and incident recovery.
- Operational runbooks, developer onboarding, and technical handover documentation.

### Database Team Ownership
- PostgreSQL database infrastructure and cloud provisioning (Supabase).
- Production database operations, connection pooler configuration (PgBouncer), and tuning.
- Schema definitions, table creation, foreign keys, and indexes.
- Database migrations, rollback scripts, and zero-downtime expand-contract schema evolutions.
- Database backups, point-in-time recovery (PITR), and physical disaster recovery.

### Shared Responsibilities
- Schema/backend release coordination and backward compatibility review.
- Production incident triaging and database query performance optimization.
- Disaster recovery drills and recovery validation.

> **CRITICAL ARCHITECTURAL RULE:** The backend team consumes the existing database schema contract as deployed by the database team. The backend MUST NOT alter DDL schemas, bypass constraints, or execute destructive queries (`DROP`, `TRUNCATE`, mass `DELETE`) in production.

---

## 3. Modular System Architecture (Phases 1–20)

| Phase | Subsystem | Core Purpose & Technical Boundary |
| :--- | :--- | :--- |
| **Phase 1** | Foundation & Runtime | Base FastAPI application, logging, async database engine, liveness/readiness probes. |
| **Phase 2** | Authentication | Argon2id password hashing, HS256 JWT access/refresh token rotation, credential revocation. |
| **Phase 3** | Authorization & Consent | Role-Based Access Control (RBAC), purpose-based patient consent verification, audit logging. |
| **Phase 4** | Patient Clinical Records | Patient demographics, condition histories, allergies, vitals, and encounter timeline. |
| **Phase 5** | Medical Documents | Secure document upload, SHA-256 deduplication, OCR text extraction, and extraction storage. |
| **Phase 6** | Prescriptions & Medications| Structured prescription entry, document extraction linkage, medication lifecycle. |
| **Phase 7** | Medication Safety | Multi-drug interaction checking, allergy contraindication, safe-failure boundary (fails to `UNKNOWN`). |
| **Phase 8** | Triage & SBAR | Deterministic clinical rule triage, operational urgency ranking, structured SBAR generation. |
| **Phase 9** | Care Plans & Discharge | Extracted discharge summaries, care plan goal tracking, follow-up scheduling. |
| **Phase 10**| Clinician Workflow | Clinical workspace, encounter-tied versioned notes, clinical assessments, and order tracking. |
| **Phase 11**| Organization Network | Healthcare networks, facility directories, departmental capacity, and operational status. |
| **Phase 12**| Discovery & Transfer | Inter-facility capability discovery, distance calculation, two-sided coordinated transfers. |
| **Phase 13**| Interoperability | ABDM / FHIR R4 clinical artifact import/export, provenance attribution. |
| **Phase 14**| AI Intelligence | Non-authoritative summarization and drafts with strict safety and grounding boundaries. |
| **Phase 15**| Security Hardening | SSRF protection, rate limiting, request size limits, PHI sanitization, secure headers. |
| **Phase 16**| Production Readiness | Contract testing, integration suites, performance baselines, release gates. |
| **Phase 17**| Deployment | Railway infrastructure, containerization, custom domain routing, zero-downtime deployment. |
| **Phase 18**| Observability | Structured JSON telemetry, Prometheus `/metrics`, bounded timers, correlation IDs. |
| **Phase 19**| Disaster Recovery | Business continuity, RTO/RPO targets, failover protocols, runbooks for outages. |
| **Phase 20**| Production Go-Live | Final verification, operational handover, support model, continuous maintenance process. |

---

## 4. Clinical Safety Architecture & Boundaries

HealthSetu enforces non-negotiable clinical safety boundaries at the service layer:

```
[ Incoming Clinical Data / External Engine Output ]
                      │
                      ▼
     ┌───────────────────────────────────┐
     │      DATA PROVENANCE TRACKER      │
     │  Source: Patient / Doctor / OCR   │
     │          Imported / AI-assisted   │
     └─────────────────┬─────────────────┘
                       │
                       ▼
     ┌───────────────────────────────────┐
     │    VERIFICATION STATE GATEWAY     │
     │  is_verified = FALSE by default   │
     │  status = REVIEW_REQUIRED         │
     └─────────────────┬─────────────────┘
                       │
       ┌───────────────┴───────────────┐
       │ (Clinician Verified)          │ (Unverified / Raw)
       ▼                               ▼
┌──────────────┐               ┌──────────────┐
│  ACTIVE EHR  │               │ DRAFT/REVIEW │
│  DECISIONS   │               │ ONLY         │
└──────────────┘               └──────────────┘
```

1. **Medication Safety Failure $\longrightarrow$ `NOT CLEAR`**: If an external safety engine times out or fails, the status is set to `UNKNOWN` or `ERROR`. The system NEVER marks an unverified interaction check as `CLEAR` or `SAFE`.
2. **Missing Clinical Information $\longrightarrow$ `NOT NORMAL`**: Missing vitals or clinical inputs (e.g. absent SpO2 in acute dyspnea) flag `INSUFFICIENT_INFORMATION` or escalate urgency. The engine never assumes absent data is normal.
3. **Extracted Data $\longrightarrow$ `NOT Automatically Verified`**: Scanned prescriptions or OCR extractions default to `is_verified=False` (`status=REVIEW_REQUIRED`). A licensed human clinician must verify before clinical execution.
4. **Imported Data $\longrightarrow$ `NOT Automatically Verified`**: FHIR/ABDM records maintain full source provenance and require clinician review.
5. **AI Assistance $\longrightarrow$ `NOT Clinical Authority`**: Generative AI models generate non-authoritative drafts and summaries. They are prohibited from making diagnoses or prescribing medication.
6. **Triage $\longrightarrow$ `NOT Diagnosis`**: Triage calculates operational urgency (Emergency, Urgent, Routine), never a medical diagnosis. Every triage output carries an explicit clinical disclaimer.
7. **Transfer Request $\longrightarrow$ `NOT Automatic Transfer`**: Inter-facility transfer requests require explicit clinician acceptance from the receiving facility.

---

## 5. Environment Separation & Configuration Hygiene

| Configuration | Development | Staging | Production |
| :--- | :--- | :--- | :--- |
| `APP_ENV` | `development` | `staging` | `production` |
| `DEBUG` | `true` | `false` | `false` |
| `DATABASE_URL` | Local / Dev Supabase | Staging Supabase DB | Dedicated Production DB (TLS) |
| Interactive Docs (`/docs`) | Enabled | Enabled | Disabled (OpenAPI schema available) |
| CORS Origins | `http://localhost:*` | Staging Web Ingress | `https://healthsetu.com`, `https://www.healthsetu.com` |
| JWT Secret | Local Dev Key | High-Entropy Secret | Cryptographically Random $\ge$ 32 bytes |
| Storage Provider | Local / Dev Bucket | Staging Private S3 | Production Private Object Storage |
| AI / External Keys | Mock / Sandbox | Staging Sandbox Keys | Dedicated Production Enterprise Keys |
