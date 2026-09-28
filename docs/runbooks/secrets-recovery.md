# HealthSetu Runbook — Secrets Recovery & Compromise Management

================================================================================
ALERT IDENTIFIERS & TRIGGER CONDITIONS
================================================================================
- **Alert**: `SecretCompromiseAlert`, `CredentialLeakedInLog`, `InvalidMasterSecret`
- **Symptoms**:
  - API keys or secrets detected in public code repository or build log.
  - Unauthorized API calls observed using valid internal keys.
  - Backend fails startup with `SecretKeyMissingError` or `SecurityConfigError`.
- **Severity**: **SEV-1 (Critical)**

================================================================================
1. PRODUCTION SECRETS INVENTORY
================================================================================

All production secrets are stored in an encrypted password vault (Bitwarden / 1Password)
and injected as environment variables in the Railway production environment.
NEVER COMMIT RAW SECRETS TO GIT.

| Secret Key Name | Purpose | Where Managed | Who Can Rotate | Rotation Impact |
|-----------------|---------|---------------|----------------|-----------------|
| `DATABASE_URL` | Supabase PostgreSQL connection with TLS | Supabase / Railway | Lead DB Admin | Zero downtime if pooled; restart container |
| `JWT_SECRET_KEY` | HMAC-SHA256 signing key for JWT auth tokens | Railway Env / Vault | Security Lead | **All active user sessions invalidated** |
| `STORAGE_ACCESS_KEY` / `STORAGE_SECRET_KEY` | S3 Object Storage API credentials | AWS / Cloudflare / Railway | Cloud Admin | Zero downtime with dual-key rotation |
| `AI_API_KEY` | Gemini / Anthropic / OpenAI API key | AI Provider / Railway | Lead Backend Eng | Fallback to deterministic mode during swap |
| `OCR_API_KEY` | Prescription OCR service API key | OCR Provider / Railway | Lead Backend Eng | Document queue pauses temporarily |
| `MEDICATION_SAFETY_API_KEY` | RxNorm / DrugBank safety engine key | Provider / Railway | Lead Backend Eng | Degraded fail-closed mode during swap |
| `INTEROPERABILITY_CREDENTIALS` | ABDM / FHIR client certificate / token | National Gateway / Railway | Interop Lead | Outbound FHIR sync queued during swap |

================================================================================
2. SECRET COMPROMISE EMERGENCY RESPONSE PROCEDURE
================================================================================

If ANY production secret is leaked, suspected compromised, or inadvertently exposed:

```
  [ Step 1: Identify Affected Credential & Blast Radius ]
                           │
                           ▼
  [ Step 2: Revoke / Disable Compromised Key at Provider ]
                           │
                           ▼
  [ Step 3: Generate New Cryptographically Secure Secret ]
   openssl rand -hex 32
                           │
                           ▼
  [ Step 4: Update Secret in Railway Environment Variables ]
   railway variables set KEY="new_value"
                           │
                           ▼
  [ Step 5: Redeploy / Restart Backend Container ]
   railway restart
                           │
                           ▼
  [ Step 6: Invalidate Active Sessions / Tokens (if JWT) ]
                           │
                           ▼
  [ Step 7: Inspect Security Audit Logs for Unauthorized Actions ]
                           │
                           ▼
  [ Step 8: Verify System Health & Execute Smoke Tests ]
```

### Specific Action: JWT Secret Compromise (`JWT_SECRET_KEY`)
1. Generate new 256-bit secret:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   ```
2. Update Railway variable:
   ```bash
   railway variables set JWT_SECRET_KEY="<new-high-entropy-secret>"
   ```
3. Restart container to trigger immediate application of the new key.
4. Consequence: All previously issued JWT access tokens and refresh tokens will immediately fail signature validation (`Signature verification failed`).
5. All clinicians, patients, and administrators are forced to re-login.
6. Review `audit_logs` table for any unauthorized operations executed prior to rotation.

### Specific Action: Database Password Compromise (`DATABASE_URL`)
1. In Supabase Dashboard: Navigate to **Settings** -> **Database** -> Click **Reset Database Password**.
2. Immediately update `DATABASE_URL` in Railway variables:
   ```bash
   railway variables set DATABASE_URL="postgresql://postgres:<NewPassword>@<Host>:6543/postgres?sslmode=require"
   ```
3. Restart backend container.
4. Verify database connectivity: `curl -f https://api.healthsetu.com/api/v1/ready`.

================================================================================
3. ROUTINE SECRET ROTATION CADENCE
================================================================================

- `JWT_SECRET_KEY`: Rotated semi-annually (or during user credential breach).
- Database Master Password: Rotated annually by Database Team.
- Third-Party Healthcare API Keys: Rotated every 90 days.
- Pre-production vs Production Isolation: Test secrets MUST NOT match production secrets.
