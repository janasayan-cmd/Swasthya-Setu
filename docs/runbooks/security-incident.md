# Runbook: Security Incident & Access Anomaly

## 1. Overview
- **Incident Type**: Unauthorized Access Attempt, Rate-Limit Abuse, or Security Threat
- **Severity**: HIGH (P1) to CRITICAL (P0)
- **Primary Symptom**: Spike in `healthsetu_authz_denials_total`, security event alerts from Phase 15 security monitor, or anomalous bulk access patterns.

---

## 2. Immediate Diagnostic Procedure

1. **Query Security Event Logs & Metrics**:
   - Inspect `/api/v1/metrics?format=json` under `security.authorization_denials`.
   - Check structured security events:
     - `repeated_auth_failures`
     - `repeated_authz_denials`
     - `rate_limit_violation`
     - `ssrf_attempt`
     - `malformed_upload_attempt`
     - `suspicious_document_access`

2. **Differentiate Security Event from Clinical Audit**:
   - **Operational Security Log**: Records IP, route, failure code, and timestamp.
   - **Clinical Audit Trail**: Records user identity, patient ID, and clinical resource accessed.
   - Do **NOT** expose clinical audit logs to external, non-HIPAA monitoring tools.

3. **Check for Potential PHI Exposure**:
   - Inspect log outputs to verify that the PHI log sanitizer has properly scrubbed any patient data or tokens involved in the attack vector.

---

## 3. Containment & Mitigation Steps

1. **Perimeter Containment**:
   - Block malicious source IPs at Railway / Cloudflare perimeter.
2. **Session / Credential Revocation**:
   - If an account was compromised, immediately invalidate user tokens and mark user account inactive.
   - If API secret or signing key was leaked, initiate immediate key rotation.
3. **Clinical Safety Verification**:
   - Verify whether unauthorized modifications occurred to:
     - Patient records
     - Medication lists
     - Care plans
     - Facility capabilities
   - If clinical data integrity was impacted, freeze affected records and notify Clinical Safety Officer.

---

## 4. Post-Incident & Forensic Reporting

1. Export security event logs for forensic review.
2. Preserve tamper-evident audit logs from PostgreSQL `audit_logs` table.
3. Complete HIPAA / DPDP breach assessment to determine if notification obligations are triggered.
