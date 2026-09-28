# HealthSetu — Privacy & Data Governance Operational Runbook (Phase 24)

## 1. Daily Operations & Periodic Maintenance

1. **Daily Cleanup Cycle**:
   - Background worker executes `PURGE_EXPIRED_EXPORT` and `CLEANUP_TEMPORARY_DATA`.
   - Purges all export blobs with `expires_at < NOW()`.
   - Verifies temporary scratch directories contain no orphaned extraction files.
2. **Weekly Retention Evaluation**:
   - Evaluates `RETENTION_EVALUATION` job across all records in `ACTIVE` state.
   - Identifies candidate records whose configured `retention_period_days` have lapsed.
   - Enqueues `ARCHIVE_RESOURCE` jobs for approved transitions.

---

## 2. Operational Procedures

### A. Placing a Legal Preservation Hold
When formal legal notice or subpoena is received:
```bash
curl -X POST https://api.healthsetu.com/api/v1/admin/privacy/holds \
  -H "Authorization: Bearer <ADMIN_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "resource_type": "patient",
    "resource_id": "pat-12345",
    "patient_id": "pat-12345",
    "hold_type": "LEGAL_HOLD",
    "reason": "Subpoena Case #2026-CV-8891 Preservation Order"
  }'
```

### B. Triggering an On-Demand Retention Purge
```bash
curl -X POST https://api.healthsetu.com/api/v1/admin/privacy/retention/run \
  -H "Authorization: Bearer <ADMIN_TOKEN>"
```

### C. Reviewing Privacy Denials & Access Anomalies
Monitor Prometheus alerts:
- `privacy_policy_denials_total`: Spikes suggest credential compromise or unauthorized scraping.
- `data_export_failed_total`: Storage quota issues or pipeline errors.
- Inspect structured logs with `grep "PRIVACY_POLICY_DENIED"` to review actor IDs, purposes, and correlation IDs (guaranteed free of patient clinical text).
