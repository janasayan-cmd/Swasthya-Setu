# HealthSetu Runbook — Object Storage Recovery & Document Integrity

================================================================================
ALERT IDENTIFIERS & SYMPTOMS
================================================================================
- **Alert**: `ObjectStorageUnavailable`, `DocumentChecksumMismatch`, `ObjectStorageAccessDenied`
- **Symptoms**:
  - Clinicians cannot view attached medical PDFs or prescription scans.
  - Document upload returns HTTP 503 or 500 error.
  - Log entries contain `S3Error`, `NoSuchKey`, `SignatureDoesNotMatch`, or `EndpointConnectionError`.
- **Severity**: **SEV-2 (Major)** / **SEV-1 (if active patient transfer impacted)**

================================================================================
1. FAILURE SCENARIOS & RECOVERY PROCEDURES
================================================================================

### Scenario 1: Object Storage Cloud Outage (S3 / Cloudflare R2 / Supabase Storage)
If the storage provider experiences a cloud service disruption:
1. **Enter Degraded Mode**:
   - The backend automatically degrades: document upload/download routes return HTTP 503 with explicit payload:
     `{"error": "DOCUMENT_STORAGE_UNAVAILABLE", "message": "Clinical document storage is temporarily degraded. Structured EHR data remains accessible."}`
   - DO NOT halt the entire backend. Structured clinical notes, encounters, and medication records continue to operate via PostgreSQL.
2. **Buffer Uploads**:
   - Client applications queue pending document uploads locally or show a retry banner to the user.
3. **Provider Recovery Verification**:
   - When provider status reports resolution, execute an authenticated test probe:
     ```bash
     # Probe test upload and download of healthcheck object
     python -c "from app.services.storage import StorageService; s = StorageService(); assert s.probe_storage_health()"
     ```

### Scenario 2: Accidental Object Deletion / Malicious Overwrite
If medical documents are accidentally deleted or overwritten:
1. **Leverage S3 Bucket Versioning**:
   - HealthSetu buckets enforce S3 Object Versioning.
   - A deletion creates a "Delete Marker" rather than deleting underlying data bytes.
2. **Undelete Procedure**:
   ```bash
   # List delete markers for the affected prefix
   aws s3api list-object-versions --bucket healthsetu-production-docs --prefix "documents/" \
     --query 'DeleteMarkers[?IsLatest==`true`].[Key, VersionId]' --output text

   # Remove delete marker to restore the previous valid object version
   aws s3api delete-object --bucket healthsetu-production-docs \
     --key "documents/HS-DOC-1234.pdf" --version-id "<DeleteMarkerVersionId>"
   ```
3. **Replication Bucket Sync**:
   - If objects in primary region were corrupted, sync from secondary cross-region replication bucket:
     ```bash
     aws s3 sync s3://healthsetu-backup-docs-replica s3://healthsetu-production-docs
     ```

================================================================================
2. THREE-WAY DOCUMENT INTEGRITY VERIFICATION
================================================================================

Following an object storage restore or database restore, execute the 3-way consistency check:

```
  [ PostgreSQL Metadata ] <──(1) Key Exists──> [ Object Storage (S3) ]
            │                                             │
      (2) sha256_checksum                           (3) Computed Hash
            │                                             │
            └─────────── MUST MATCH 100% ─────────────────┘
```

### Verification Script:
```python
import hashlib
from app.core.database import get_db_session
from app.services.storage import StorageService

async def verify_document_integrity(sample_size: int = 500):
    storage = StorageService()
    async with get_db_session() as session:
        # Fetch document metadata records
        docs = await session.execute("SELECT id, storage_key, sha256_checksum FROM documents LIMIT :lim", {"lim": sample_size})
        mismatches = []
        for doc_id, key, expected_hash in docs.fetchall():
            try:
                data = await storage.get_object_bytes(key)
                actual_hash = hashlib.sha256(data).hexdigest()
                if actual_hash != expected_hash:
                    mismatches.append({"id": doc_id, "key": key, "reason": "CHECKSUM_MISMATCH"})
            except Exception as e:
                mismatches.append({"id": doc_id, "key": key, "reason": f"NOT_FOUND: {e}"})
        
        assert len(mismatches) == 0, f"Integrity failure in {len(mismatches)} documents: {mismatches}"
        print(f"[OK] Verified {sample_size} document objects: 100% checksum match.")
```

================================================================================
3. POST-RECOVERY VALIDATION
================================================================================

1. Generate a pre-signed download URL for a verified test document.
2. Confirm HTTP 200 download from client.
3. Record recovery telemetry:
   ```python
   metrics.record_recovery_result(subsystem="object_storage", success=True)
   ```
4. Verify document viewing operational in Doctor Clinical Workspace.
