# HealthSetu — Enterprise Backup & Storage Recovery Strategy (Phase 19)

================================================================================
1. STRATEGY OVERVIEW & TEAM BOUNDARIES
================================================================================

HealthSetu utilizes a strictly segregated backup model:

1. **Structured Clinical Data**: Supabase PostgreSQL is the single authoritative source of truth.
   - **OWNER: DATABASE TEAM**
   - The backend MUST NOT attempt to implement its own competing database backup mechanism.
   - The backend MUST NOT create duplicate or shadow databases.
2. **Unstructured Medical Documents**: Dedicated private S3-compatible Object Storage.
   - **OWNER: BACKEND TEAM**
   - Preserves patient scans, discharge summaries, laboratory reports, and DICOM images.
3. **Application Configuration & Infrastructure as Code**: Git & Vault.
   - **OWNER: BACKEND TEAM**
   - Dockerfile, runtime dependency locks, and encrypted secrets vault.

```
                      [ BACKUP & PERSISTENCE ARCHITECTURE ]
                                       │
            ┌──────────────────────────┴──────────────────────────┐
            │                                                     │
            ▼                                                     ▼
 [ SUPABASE POSTGRESQL ]                                [ OBJECT STORAGE ]
 Owner: Database Team                                   Owner: Backend Team
 - Automated continuous WAL stream                      - Encrypted Medical Objects (S3)
 - Point-In-Time Recovery (PITR)                        - S3 Bucket Versioning Enabled
 - Daily physical database snapshots                    - Multi-Region Bucket Replication
 - Immutable Audit Logs                                 - SHA-256 Checksum Validation
```

================================================================================
2. DATABASE BACKUP SPECIFICATION (SUPABASE POSTGRESQL)
================================================================================

### 2.1 Ownership & Responsibilities
- **Database Team** manages all PostgreSQL backup policies, continuous archiving, snapshot retention, restore operations, and point-in-time recovery configurations.
- **Backend Team** consumes the database via `DATABASE_URL` with TLS enforced (`sslmode=require`) and verifies application compatibility.

### 2.2 Backup Mechanisms
1. **Continuous Write-Ahead Logging (WAL)**:
   - Supabase continuously streams Write-Ahead Logs to secure cold storage.
   - Enables Point-In-Time Recovery (PITR) to any second within the retention window.
   - RPO target: **< 5 minutes** of committed clinical transactions.
2. **Daily Snapshot Backups**:
   - Automated full database physical snapshots taken daily during low-traffic windows (02:00 UTC).
   - Snapshots stored encrypted in isolated, redundant cloud storage.

### 2.3 Retention Policy
- Continuous WAL streaming retained for **30 days**.
- Daily physical snapshots retained for **90 days**.
- Monthly archival snapshots retained for **7 years** to satisfy healthcare compliance requirements.

### 2.4 Encryption & Access Control
- **At Rest**: AES-256 encryption applied at the storage volume and backup bucket level.
- **In Transit**: TLS 1.3 encryption enforced for all replication and database connections.
- **Access Control**: Database restore operations require multi-factor authentication (MFA) and are restricted to authorized Database Administrators.

================================================================================
3. OBJECT STORAGE BACKUP & RECOVERY (MEDICAL DOCUMENTS)
================================================================================

### 3.1 Architecture & Separation of Concerns
- Medical documents (PDFs, images) are NEVER stored directly in PostgreSQL database columns.
- The PostgreSQL database holds document metadata (`document_id`, `patient_id`, `filename`, `mime_type`, `file_size_bytes`, `storage_key`, `sha256_checksum`, `created_at`).
- The actual document binary payload resides in a private, encrypted S3-compatible bucket.

### 3.2 Backup & Durability Controls
1. **Object Versioning**:
   - Enabled on the production documents bucket.
   - Overwrites or deletions create a new version marker rather than permanently destroying the object.
   - Allows instant recovery from accidental deletion or malicious overwrite.
2. **MFA Delete Protection**:
   - Permanent deletion of object versions requires dedicated root credential with hardware MFA.
3. **Cross-Region Replication (CRR)**:
   - All uploaded clinical documents are asynchronously replicated to a secondary cloud region within 15 minutes of upload.
   - Protects against catastrophic regional data center outages.

### 3.3 Document Integrity & Checksum Verification
- Every uploaded document is hashed with **SHA-256** prior to or during storage.
- The resulting digest is stored in the database `sha256_checksum` column.
- During disaster recovery validation:
  1. Retrieve object from storage.
  2. Compute SHA-256 hash of retrieved payload.
  3. Assert computed hash == database metadata hash.
  4. Discrepancies raise immediate clinical alerts (`DOCUMENT_INTEGRITY_MISMATCH`).

================================================================================
4. DATABASE RESTORE PROCESS & SAFETY GATES
================================================================================

Restoring production database data is a high-risk operational event that can result
in data loss for transactions occurring after the selected recovery point.

### Pre-Restore Safety Checklist:
1. **Incident Triage**: Formally identify the failure mode (e.g., table corruption, ransomware, catastrophic user error).
2. **Forensic Evidence Snapshot**: Before overwriting any existing production database, take a manual snapshot of the current state to preserve audit and investigation evidence.
3. **Determine Recovery Point**: Select the exact timestamp (UTC) immediately preceding the incident.
4. **Impact Assessment**: Calculate the delta of clinical transactions created between the target recovery point and the incident time. Notify clinical administration of potential record resubmissions.
5. **Two-Person Authorization**: Restore execution requires formal sign-off from:
   - Lead Database Engineer
   - Backend Incident Commander

### Step-by-Step Restoration Flow:
```
  [ Incident Detected ]
           │
           ▼
  [ 1. Stop Backend Deployment / Set Maintenance Mode ]
           │
           ▼
  [ 2. Take Forensic Snapshot of Current Database ]
           │
           ▼
  [ 3. Restore Database to Target Recovery Point (PITR) ]
           │
           ▼
  [ 4. Database Team Verifies Schema & Foreign Key Constraints ]
           │
           ▼
  [ 5. Backend Team Verifies Application Compatibility ]
           │
           ▼
  [ 6. Connect Backend & Execute Health/Readiness Probes ]
           │
           ▼
  [ 7. Execute Automated Smoke & Clinical Safety Tests ]
           │
           ▼
  [ 8. Reopen Production Traffic & Maintain Post-Recovery Watch ]
```

================================================================================
5. BACKUP RETENTION & RECOVERY EXERCISE SCHEDULE
================================================================================

| Subsystem | Backup Frequency | Retention Window | Storage Tier | Encryption | Restore Verification Cadence |
|-----------|------------------|------------------|--------------|------------|------------------------------|
| **PostgreSQL WAL** | Continuous streaming | 30 Days | Hot / Warm S3 | AES-256 / TLS | Monthly automated drill |
| **PostgreSQL Snapshots** | Daily (02:00 UTC) | 90 Days | Standard Cloud | AES-256 | Quarterly full PITR restore |
| **PostgreSQL Compliance Archive** | Monthly | 7 Years | Cold Glacier | AES-256 | Annual audit retrieval |
| **Medical Documents (S3)** | Real-time write | Indefinite (Clinical)| Standard + CRR | SSE-S3 / AES-256 | Quarterly checksum audit |
| **Environment & Secrets** | On modification | Git / Vault History | Encrypted Vault | AES-256 / Argon2 | Quarterly secret rotation drill |

================================================================================
6. RECOVERY ACCESS CONTROLS & AUDITABILITY
================================================================================

- Backup and restore actions are restricted to authorized personnel.
- All restore operations must generate an immutable audit log containing:
  - Timestamp of restore command
  - Actor identity (email / IAM ARN)
  - Target recovery timestamp
  - Source and destination database identifiers
  - Post-restore integrity verification checksums
