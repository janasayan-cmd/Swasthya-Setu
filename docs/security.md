# HealthSetu — Production Security Architecture & Standards

## 1. Security Overview & Defense-in-Depth

HealthSetu handles sensitive clinical data and Protected Health Information (PHI). Security is implemented in depth across network, application, database, and telemetry layers:

```
[ INBOUND REQUEST ]
       │
       ▼
[ Security Headers Middleware ] ──> (HSTS, CSP, X-Frame-Options: DENY, Sniff-Protection)
       │
       ▼
[ Request Size Limit Middleware] ──> (Rejects payloads > 10MB to prevent DoS)
       │
       ▼
[ Strict CORS Middleware ] ───────> (Allows only explicitly configured HTTPS origins; NO wildcard)
       │
       ▼
[ Rate Limiter Middleware ] ─────> (IP & Account-based token bucket; mitigates brute-force)
       │
       ▼
[ Authentication Middleware ] ───> (Argon2id + HS256 JWT validation, expiry, and revocation checks)
       │
       ▼
[ Authorization & Consent ] ─────> (RBAC, Active patient consent check, IDOR isolation)
       │
       ▼
[ Core Clinical Handler ] ───────> (Parameterized SQL queries via SQLAlchemy, provenance recorded)
       │
       ▼
[ Telemetry & Audit Layer ] ─────> (PHI scrubber removes sensitive tokens before stdout logging)
```

---

## 2. Authentication & Identity Management

- **Password Hashing**: Implemented using **Argon2id** (`argon2-cffi`) with secure memory cost (64MB), time cost (3 iterations), and parallelism (4 lanes). Plaintext passwords are never logged or stored.
- **Token Format**: Standard JSON Web Tokens (JWT) signed with **HS256**.
- **Secret Requirements**: In production, `JWT_SECRET_KEY` MUST be a cryptographically random secret of at least 32 bytes. Placeholder values (e.g. `secret`, `changeme`, `your-secret-key`) cause startup failure.
- **Token Lifespans**:
  - `access_token`: 15 minutes (short-lived to minimize replay vulnerability).
  - `refresh_token`: 30 days (stored securely in database, invalidated upon logout or rotation).
- **Session Termination**: Calling `POST /api/v1/auth/logout` revokes the refresh token and terminates the session immediately.

---

## 3. Authorization & Tenant Isolation (Patient A $\neq$ Patient B)

HealthSetu enforces strict multi-tenant and cross-patient isolation:
1. **Self-Access Rule**: A user with role `PATIENT` is strictly authorized ONLY to read and manage their own clinical record (`user_id == current_user.id`).
2. **Clinician Consent Gate**: A user with role `DOCTOR` or `CLINICIAN` cannot query a patient's records or prescriptions unless:
   - An active, unexpired `ConsentRecord` exists granting access for the specific purpose (`care_delivery`, `referral`).
   - The clinician is actively assigned to the patient's current clinical encounter or network transfer.
3. **IDOR Prevention**: Any attempt by Patient A to query `/api/v1/patients/Patient-B/...` fails with HTTP `403 Forbidden` or `404 Not Found` and logs a high-severity security audit event.

---

## 4. Production Security Configuration Gate (`app/core/security_config.py`)

At startup, HealthSetu executes a strict **fail-closed** security validation gate:

```python
enforce_security_config(settings)
```

In production (`APP_ENV=production`), the application **refuses to start** if any of the following fatal violations are detected:
- `DEBUG=true` (prohibited in production to prevent stack trace leakage).
- `CORS_ALLOWED_ORIGINS` contains wildcard `*` while credentials are enabled.
- `CORS_ALLOWED_ORIGINS` contains unencrypted `http://` origins (outside localhost).
- `JWT_SECRET_KEY` is missing, under 32 characters, or a known placeholder.
- `DATABASE_URL` is missing or contains placeholder passwords.
- `AI_TRAINING_OPT_IN=true` (patient data must NEVER be opted into external AI model training).
- External API keys for active production providers are missing or placeholders.

---

## 5. Secret Management & Hygiene

- **Storage**: All production secrets (`DATABASE_URL`, `JWT_SECRET_KEY`, cloud storage keys, AI provider tokens) are injected exclusively via Railway Environment Variables or encrypted secret managers.
- **Git Hygiene**: No secrets are committed to source control. `.env` and `.env.local` are explicitly ignored in `.gitignore`.
- **Log Hygiene**: Structured logging (`app/core/logging.py`) and log sanitizers (`app/core/log_sanitizer.py`) redact Authorization headers, passwords, connection strings, and tokens.
- **Error Hygiene**: Exception handlers convert internal exceptions into generic, safe error codes. Stack traces and SQL queries are suppressed in production.

---

## 6. PHI Scrubbing & Log Sanitization

HealthSetu strictly prohibits Protected Health Information (PHI) in application telemetry:
- Standard logs contain: timestamp, level, `request_id`, route, status code, latency, and sanitized actor ID.
- Sanitizer regex patterns automatically scrub:
  - Email addresses: `[\w\.-]+@[\w\.-]+\.\w+`
  - Indian mobile numbers: `(?:\+91\|0)?[6-9]\d{9}`
  - Aadhaar / ABHA IDs: `\b\d{4}[-\s]?\d{4}[-\s]?\d{4}\b`
  - Medical Record Numbers (MRN) and raw medication prescription instructions.

---

## 7. SSRF Protection & Network Defense

- **SSRF Defense (`app/core/ssrf.py`)**: Interoperability webhook calls, document download URLs, and external FHIR endpoints are validated against an IP denylist before dispatching HTTP requests. Connections to private ranges (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `127.0.0.0/8`, `169.254.0.0/16`) and cloud metadata endpoints (`169.254.169.254`) are blocked.
- **Payload Size Limiter**: Incoming HTTP request bodies are limited to 10 MB. Requests exceeding this threshold receive HTTP `413 Payload Too Large`.
- **Security Headers**:
  - `Strict-Transport-Security: max-age=31536000; includeSubDomains; preload`
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `Content-Security-Policy: default-src 'self'`
