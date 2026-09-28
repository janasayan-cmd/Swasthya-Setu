# HealthSetu — Production Environment Configuration (Phase 17)

## 1. Overview & Policy

All production configuration must be provided via Railway environment variables and protected secrets. Credentials, database passwords, and API keys must **never** be committed to Git or baked into the Docker image.

Startup configuration validation (`enforce_security_config`) executes on container boot and adheres to the **Fail-Closed Principle**: any missing secret or insecure placeholder in production will abort application startup immediately.

---

## 2. Environment Variables & Secret Specifications

### Core Application
| Variable | Production Value | Description |
| :--- | :--- | :--- |
| `APP_NAME` | `healthsetu-backend` | Identifier for service logs and diagnostics |
| `APP_ENV` | `production` | Enables strict security guardrails |
| `APP_VERSION` | `1.0.0` | Semantic release version |
| `DEBUG` | `false` | Must be false in production (prevents traceback leaks) |
| `HOST` | `0.0.0.0` | Server binding address |
| `PORT` | Dynamic | Injected by Railway runtime |
| `API_PREFIX` | `/api/v1` | Base route path |
| `ENABLE_DOCS` | `false` | Set to false to disable OpenAPI/Swagger in production |

### Database & Pooling
| Variable | Production Value | Description |
| :--- | :--- | :--- |
| `DATABASE_URL` | `postgresql+asyncpg://...` | Secure connection string to Supabase PostgreSQL |
| `DB_POOL_SIZE` | `10` | Base SQLAlchemy connection pool size |
| `DB_MAX_OVERFLOW` | `20` | Max temporary connections during burst traffic |
| `DB_POOL_TIMEOUT` | `30.0` | Timeout in seconds waiting for connection checkout |
| `DB_POOL_RECYCLE` | `1800` | Recycles stale connections after 30 minutes |
| `DB_POOL_PRE_PING`| `true` | Pings connection with `SELECT 1` on checkout |

### Security, CORS & Authentication
| Variable | Production Value | Description |
| :--- | :--- | :--- |
| `JWT_SECRET_KEY` | *(Secret)* | Min 32-byte cryptographically random secret |
| `JWT_ALGORITHM` | `HS256` | Token signing algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `15` | Short-lived token expiry |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `30` | Refresh token lifespan with rotation |
| `CORS_ALLOWED_ORIGINS` | `https://healthsetu.com,https://www.healthsetu.com` | Explicit origins (wildcards forbidden) |
| `RATE_LIMIT_ENABLED` | `true` | Enforces sliding-window rate limits |
| `RATE_LIMIT_DEFAULT_PER_MINUTE` | `60` | Limit for standard endpoints |
| `RATE_LIMIT_AUTH_PER_MINUTE` | `10` | Strict brute-force protection limit |
| `SECURITY_HEADERS_ENABLED` | `true` | Injects HSTS, CSP, and framing defenses |
| `STRICT_TRANSPORT_SECURITY_ENABLED`| `true` | Enables 1-year HSTS header |
| `AUDIT_ENABLED` | `true` | Centralized immutable audit event recording |
| `PHI_SAFE_LOGGING_ENABLED` | `true` | Strips patient names, tokens, & clinical bodies |

### Document Storage & OCR
| Variable | Production Value | Description |
| :--- | :--- | :--- |
| `DOCUMENT_STORAGE_PROVIDER` | `local` / `s3` | Storage backend (`s3` for multi-instance production) |
| `DOCUMENT_PRIVATE_STORAGE` | `true` | Enforces private non-public document access |
| `OCR_PROVIDER` | `local` / `cloud` | OCR engine |
| `OCR_TIMEOUT_SECONDS` | `120` | Max timeout for optical text extraction |

### External Healthcare Providers
| Integration | Enabled Toggle | Provider Setting | Notes |
| :--- | :--- | :--- | :--- |
| Medication Terminology | `MEDICATION_NORMALIZATION_ENABLED=true` | `local` or `rxnorm` | Normalizes medications to RxNorm / SNOMED |
| Medication Safety | `MEDICATION_SAFETY_ENABLED=true` | `mock` or `licensed_provider` | Drug-drug interaction checks |
| Clinical Triage | `TRIAGE_ENABLED=true` | Deterministic Rule Set | Strict non-autonomous triage evaluation |
| Interoperability | `INTEROPERABILITY_ENABLED=true` | `none` or `fhir_server` | FHIR R4 standard exchange |
| AI Intelligence | `AI_ENABLED=true` | `mock` / `openai` / `azure` | Non-authoritative clinical drafting |

---

## 3. Production Configuration Guardrails

The application will reject startup under any of the following conditions:
1. `DEBUG=true` in production environment.
2. `CORS_ALLOWED_ORIGINS` containing wildcard `*` with credentials.
3. `JWT_SECRET_KEY` matching known default strings or shorter than 32 characters.
4. `DATABASE_URL` missing or containing placeholder passwords.
5. `AI_TRAINING_OPT_IN=true` (prohibited: patient data must never train third-party AI models).
6. Plain HTTP origins declared in production CORS.
