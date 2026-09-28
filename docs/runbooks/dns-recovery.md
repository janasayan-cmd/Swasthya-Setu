# HealthSetu Runbook — Domain & DNS Disaster Recovery

================================================================================
ALERT IDENTIFIERS & SYMPTOMS
================================================================================
- **Alert**: `DNSResolutionFailure`, `TLSCertificateExpiredOrInvalid`, `DomainUnreachable`
- **Symptoms**:
  - `curl https://api.healthsetu.com` returns `Could not resolve host: api.healthsetu.com` (NXDOMAIN).
  - Browser displays `SSL_ERROR_BAD_CERT_DOMAIN` or `ERR_CERT_COMMON_NAME_INVALID`.
  - Frontend applications report network errors when calling the API.
- **Severity**: **SEV-1 (Critical)**

================================================================================
1. DOMAIN & DNS ARCHITECTURE
================================================================================

- **Production API FQDN**: `api.healthsetu.com`
- **DNS Provider**: Cloudflare Managed DNS / AWS Route 53
- **Record Type**: `CNAME`
- **Target Value**: Railway Service Custom Domain Endpoint (`<service-id>.railway.app`)
- **TTL**: 300 seconds (5 minutes) for rapid DNS propagation during disaster recovery
- **TLS Termination**: Automated Let's Encrypt certificates managed via Railway Edge / Cloudflare
- **Credentials Policy**: DNS provider credentials are managed in 1Password with hardware MFA. Zero DNS credentials in source control.

================================================================================
2. STEP-BY-STEP DNS OUTAGE RECOVERY
================================================================================

If `api.healthsetu.com` becomes unavailable:

### Step 1: Verify DNS Resolution & Propagation
Check resolution across global recursive resolvers:
```bash
# Test local resolution
nslookup api.healthsetu.com

# Trace authoritative DNS answers
dig api.healthsetu.com +trace +nodnssec

# Query Google and Cloudflare public resolvers directly
dig @8.8.8.8 api.healthsetu.com CNAME
dig @1.1.1.1 api.healthsetu.com CNAME
```
If queries return `NXDOMAIN` or point to a non-existent host, DNS records have been dropped or corrupted.

### Step 2: Verify Railway Service Availability
Check whether the backend service is responding on its direct Railway URL:
```bash
curl -f -s https://<railway-internal-subdomain>.up.railway.app/api/v1/health | jq .
```
- If this succeeds, the backend is healthy and the issue is strictly DNS/TLS routing.
- If this fails, consult `docs/runbooks/application-recovery.md`.

### Step 3: Verify & Restore DNS Record Configuration
1. Log in to the Cloudflare / Route 53 DNS dashboard.
2. Verify that the CNAME record exists:
   - **Name**: `api`
   - **Type**: `CNAME`
   - **Target**: `<railway-target>.railway.app`
   - **Proxy Status**: DNS Only (or Proxied if using Cloudflare WAF)
   - **TTL**: `300` (5 minutes)
3. If missing or misconfigured, re-create the record immediately and save.

### Step 4: Verify Railway Custom Domain & TLS Status
1. Navigate to Railway Dashboard -> Project `HealthSetu` -> `healthsetu-backend` -> **Settings** -> **Networking**.
2. Locate `api.healthsetu.com` under **Custom Domains**.
3. Verify TLS certificate status:
   - If certificate generation is stuck, click **Verify DNS** or **Refresh Certificate**.
   - If Railway requires an ACME challenge TXT record, add the `_acme-challenge.api` TXT record in your DNS portal.

### Step 5: Verify End-to-End Resolution & Probes
Once DNS propagates (usually within 1 to 5 minutes due to 300s TTL):
```bash
# Verify TLS handshake and certificate validity
curl -Iv https://api.healthsetu.com/api/v1/health

# Verify liveness probe
curl -f -s https://api.healthsetu.com/api/v1/health | jq .

# Verify readiness probe
curl -f -s https://api.healthsetu.com/api/v1/ready | jq .
```

### Step 6: Execute Smoke Tests
Confirm complete clinical path operational:
```bash
python scripts/verify_integration.py
```
Record recovery metric:
```python
metrics.record_recovery_result(subsystem="dns", success=True)
```
