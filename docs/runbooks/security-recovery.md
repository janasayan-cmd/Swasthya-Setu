# HealthSetu Runbook — Security Incident & Destructive Attack Recovery

================================================================================
ALERT IDENTIFIERS & TRIGGER CONDITIONS
================================================================================
- **Alert**: `SecurityBreachDetected`, `RansomwareIndicatorDetected`, `MassUnauthorizedAccess`, `CredentialCompromise`
- **Severity**: **SEV-0 (Catastrophic) / SEV-1 (Critical)**
- **Lead Role**: **Incident Commander & Clinical Security Officer**

================================================================================
1. SECURITY INCIDENT RECOVERY LIFECYCLE
================================================================================

```
       [ 1. DETECTION ]
       Abnormal access, leak alert, or intrusion detected
              │
              ▼
       [ 2. CONTAINMENT ]
       Isolate container, revoke tokens, sever malicious network connections
              │
              ▼
       [ 3. CREDENTIAL ROTATION ]
       Rotate JWT_SECRET_KEY, DATABASE_URL, and third-party API credentials
              │
              ▼
       [ 4. ACCESS & AUDIT REVIEW ]
       Inspect audit_logs for scope of unauthorized access / PHI exposure
              │
              ▼
       [ 5. INFRASTRUCTURE RECOVERY ]
       Redeploy clean container images from verified Git commit SHA
              │
              ▼
       [ 6. DATA-INTEGRITY VALIDATION ]
       Verify 14 clinical integrity domains; confirm zero clinical tampering
              │
              ▼
       [ 7. SECURITY VERIFICATION ]
       Verify deny-by-default, RBAC enforcement, and rate limiters
              │
              ▼
       [ 8. SERVICE RECOVERY ]
       Restore production traffic through canary gate
              │
              ▼
       [ 9. POST-INCIDENT MONITORING & DISCLOSURE ]
       Heightened 72-hour watch; statutory HIPAA/DPDP breach reporting if PHI impacted
```

================================================================================
2. CONTAINMENT PROTOCOL (STEP-BY-STEP)
================================================================================

### Step 2.1: Immediate Network Isolation
If active attacker access is detected inside the container runtime:
1. In Railway Dashboard: Click **Pause** on the `healthsetu-backend` service.
2. In Cloudflare / CDN: Enable **Under Attack Mode** or apply firewall rule blocking attacker IP ranges.
3. In Supabase Dashboard: Terminate active connections via SQL:
   ```sql
   SELECT pg_terminate_backend(pid) 
   FROM pg_stat_activity 
   WHERE usename = 'postgres' AND client_addr != '<trusted-ip>';
   ```

### Step 2.2: Invalidate All Active Sessions
Immediately invalidate all issued JWT access and refresh tokens:
```bash
# Rotate the JWT signing secret in Railway
railway variables set JWT_SECRET_KEY="$(openssl rand -hex 48)"
```
This guarantees that any stolen JWT token immediately returns HTTP 401.

### Step 2.3: Rotate All Infrastructure Secrets
Follow `docs/runbooks/secrets-recovery.md` to rotate:
- Supabase database password
- S3 storage access keys
- External healthcare API keys

================================================================================
3. RANSOMWARE & DESTRUCTIVE INCIDENT RECOVERY
================================================================================

If ransomware or deliberate mass deletion of clinical data is suspected:

1. **DO NOT OVERWRITE EXISTING EVIDENCE**:
   - Capture a forensically sound image/snapshot of the compromised database and container logs.
   - Do NOT run destructive cleanup scripts.
2. **Sever Cloud Write Access**:
   - Immediately revoke IAM credentials associated with storage and database services.
3. **Verify Backup Air-Gap Integrity**:
   - Database team inspects the immutable continuous WAL stream and daily snapshots.
   - Verify that backup snapshots themselves have not been deleted or encrypted.
4. **Clean-Room Restoration**:
   - Stand up a fresh, isolated PostgreSQL database instance (`healthsetu-clean-recovery`).
   - Restore database from the last verified clean recovery point prior to the attack.
   - Verify that all database schemas, triggers, and foreign keys are intact.
5. **Document Storage Verification**:
   - Verify that S3 object versioning delete markers are rolled back using `docs/runbooks/object-storage-recovery.md`.
   - Run SHA-256 checksum integrity verification across all medical records.
6. **Code Re-Verification**:
   - Verify that production Docker container builds strictly from the signed Git release tag (`git verify-tag v1.x.x`).
   - Confirm no malicious backdoor files exist in the repository.

================================================================================
4. PATIENT PRIVACY & COMPLIANCE BOUNDARY
================================================================================

1. **Audit Log Forensics**:
   - Extract and analyze `audit_logs` table for all queries executed by compromised accounts:
     ```sql
     SELECT timestamp, user_id, action, resource_type, resource_id 
     FROM audit_logs 
     WHERE timestamp >= '<compromise-start-timestamp>'
     ORDER BY timestamp ASC;
     ```
2. **Breach Assessment**:
   - Determine whether Protected Health Information (PHI) was exfiltrated or merely altered.
   - Formally document the incident for DPDP (Digital Personal Data Protection) and clinical compliance authorities within regulatory timelines.
3. **Zero Bypasses**:
   - Never disable authentication, authorization, or audit logging to "speed up recovery".
