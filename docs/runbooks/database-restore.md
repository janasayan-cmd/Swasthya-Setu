# HealthSetu Runbook — Database Restore & Data Integrity Recovery

================================================================================
ALERT IDENTIFIERS & TRIGGER CONDITIONS
================================================================================
- **Alert**: `PostgresDataCorruption`, `AccidentalDataDeletion`, `FailedDatabaseMigration`, `DatabaseDisaster`
- **Severity**: **SEV-1 (Catastrophic / Critical)**
- **Primary Owner**: **DATABASE TEAM** (Supported by Backend Team)

================================================================================
1. PRE-RESTORE SAFETY GATES (CRITICAL)
================================================================================

A database restore can cause permanent loss of any clinical transactions committed
between the target recovery point and the current moment.

### Mandatory Pre-Restore Checklist:
1. **Identify the Incident**:
   - Determine whether corruption is logical (bad SQL update/delete), structural (page corruption), or migration-related.
2. **Preserve Current Evidence (Forensic Dump)**:
   - Before restoring any backup, the Database Team MUST take an immediate full forensic physical/logical backup of the current state:
     ```bash
     pg_dump -Fc -v "$DATABASE_URL" -f "forensic_pre_restore_$(date +%s).dump"
     ```
3. **Determine Target Recovery Point**:
   - Locate the exact UTC timestamp immediately preceding the corruption or accidental deletion.
4. **Impact Assessment**:
   - Estimate records created after the recovery point that will need manual clinical re-entry.
5. **Formal Authorization**:
   - Obtain written sign-off from Incident Commander, Lead Database Engineer, and Clinical Safety Officer.

================================================================================
2. DATABASE RESTORE FLOW
================================================================================

```
       [ Incident Confirmed & Recovery Point Identified ]
                                │
                                ▼
       [ Step 1: Set Backend to Maintenance Mode ]
        Railway: Set MAINTENANCE_MODE=true or pause container
                                │
                                ▼
       [ Step 2: Take Forensic Pre-Restore Snapshot ]
                                │
                                ▼
       [ Step 3: Execute Supabase Point-In-Time Recovery ]
        Database Team triggers PITR in Supabase Console
                                │
                                ▼
       [ Step 4: Verify Database Schema & Table Constraints ]
        Database Team runs constraint & foreign-key checks
                                │
                                ▼
       [ Step 5: Backend Compatibility Verification ]
        Verify current backend version is compatible with restored schema
                                │
                                ▼
       [ Step 6: Restart Backend Container & Reconnect ]
                                │
                                ▼
       [ Step 7: Execute 14-Point Clinical Integrity Validation ]
                                │
                                ▼
       [ Step 8: Execute Integration Smoke Tests ]
        python scripts/verify_integration.py
                                │
                                ▼
       [ Step 9: Lift Maintenance Mode & Restore Traffic ]
```

================================================================================
3. DATABASE TEAM RESTORE PROCEDURE
================================================================================

1. **Supabase Console PITR**:
   - Log in to Supabase Organization Dashboard.
   - Select Project: `healthsetu-production`.
   - Navigate to **Database** -> **Backups** -> **Point in Time (PITR)**.
   - Choose target date and exact timestamp (e.g. `2026-09-27 18:45:00 UTC`).
   - Select **Restore to new database** (RECOMMENDED: allows safe comparison) OR **Restore in-place**.
2. **Connection String Update**:
   - If restored to a new database instance, update `DATABASE_URL` in Railway:
     ```bash
     railway variables set DATABASE_URL="postgresql://postgres:[PASSWORD]@[HOST]:[PORT]/postgres?sslmode=require"
     ```

================================================================================
4. 14-POINT DATA INTEGRITY VALIDATION
================================================================================

Following the database restore, run the integrity validation script to verify:

```sql
-- 1. Verify Patient Records Exist and are Not Empty
SELECT count(*) AS total_patients FROM patients;

-- 2. Verify Encounters are Linked to Valid Patients
SELECT count(*) AS orphaned_encounters 
FROM encounters e LEFT JOIN patients p ON e.patient_id = p.id 
WHERE p.id IS NULL;

-- 3. Verify Active Medications Intact
SELECT count(*) AS active_medications FROM medications WHERE status = 'active';

-- 4. Verify Prescriptions Linked to Clinicians
SELECT count(*) AS valid_prescriptions FROM prescriptions WHERE practitioner_id IS NOT NULL;

-- 5. Verify Critical Allergies & Sensitivities Preserved
SELECT count(*) AS verified_allergies FROM allergies WHERE verification_status = 'confirmed';

-- 6. Verify Document Metadata Matches
SELECT count(*) AS total_documents FROM documents;

-- 7. Verify Triage Records Intact
SELECT count(*) AS emergency_triage FROM triage_records;

-- 8. Verify Care Plans Intact
SELECT count(*) AS active_care_plans FROM care_plans WHERE status = 'active';

-- 9. Verify Clinician Profiles Accessible
SELECT count(*) AS clinicians FROM practitioners;

-- 10. Verify Facilities & Network Relationships
SELECT count(*) AS facilities FROM facilities;

-- 11. Verify Transfer Requests Preserved
SELECT count(*) AS pending_transfers FROM transfer_requests WHERE status = 'pending';

-- 12. Verify Interoperability Sync Records
SELECT count(*) AS fhir_resources FROM interoperability_resources;

-- 13. Verify Audit Log Chain Intact and Chronological
SELECT count(*) AS total_audit_events, min(created_at) AS earliest, max(created_at) AS latest FROM audit_logs;

-- 14. Verify Consents Enforced
SELECT count(*) AS active_consents FROM patient_consents WHERE status = 'granted';
```
ALL foreign-key orphan checks must return `0`.

================================================================================
5. MIGRATION FAILURE RECOVERY
================================================================================

If an automated Alembic / SQL migration fails mid-deployment:
1. Halt application deployment immediately.
2. Inspect migration error logs:
   ```bash
   railway logs | grep -i "migration"
   ```
3. Database Team executes migration downgrade script:
   ```bash
   alembic downgrade -1
   # OR execute specific down-revision SQL script
   ```
4. Verify schema matches the previous backend release.
5. Redeploy the previous backend release container.

================================================================================
6. POST-RESTORE VALIDATION & TELEMETRY
================================================================================

1. Record restoration duration in metrics:
   ```python
   metrics.record_database_restore(duration_seconds=elapsed_time)
   metrics.record_recovery_result(subsystem="database", success=True)
   ```
2. Probe endpoints:
   - `GET /api/v1/health` -> HTTP 200
   - `GET /api/v1/ready` -> HTTP 200 (`checks: {database: "available"}`)
3. Run integration smoke tests:
   ```bash
   python scripts/verify_integration.py
   ```
4. Document the restore event in a post-incident review (PIR).
