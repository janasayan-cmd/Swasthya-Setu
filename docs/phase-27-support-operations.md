# Phase 27: Support Operations & Privacy Boundary

## 1. Objective & Boundaries

Support operators provide tier-1 and tier-2 operational troubleshooting for HealthSetu users and partner facilities. Support personnel often need to verify account status, check whether background processing has finished, and correlate operational inquiries with logs.

However:
```
SUPPORT ACCESS != UNLIMITED DATA ACCESS
PATIENT LOOKUP != CLINICAL RECORD ACCESS
OPERATOR OVERVIEW != CLINICAL OVERVIEW
```

Support operators are strictly segregated from patient clinical charts. They do not have access to diagnoses, medications, allergies, clinical notes, doctor orders, or raw medical documents unless explicitly granted by the patient through time-bound consent under Phase 3.

---

## 2. Privacy-Safe Patient Support Lookup

### Endpoint
`GET /api/v1/admin/support/patients/search?query={identifier}`

### Permitted Roles
- `SYSTEM_ADMIN`
- `OPERATIONS_ADMIN`
- `SUPPORT_OPERATOR`

### Data Minimization Invariant
The search response returns strictly minimized account identifiers:

```json
{
  "success": true,
  "data": {
    "items": [
      {
        "patient_id": "pat-01928374",
        "sovereign_id": "HS-PAT-8921",
        "masked_name": "A*** C***",
        "account_status": "ACTIVE",
        "city": "Kolkata",
        "registered_at": "2026-03-15T10:30:00Z",
        "active_consent_count": 2
      }
    ],
    "total": 1
  }
}
```

### Strictly Forbidden Fields
The following fields are never returned in support responses:
- Full unmasked names
- Diagnoses, conditions, or ICD-10 codes
- Prescriptions, medications, or dosages
- Known allergies or adverse reactions
- Clinical notes, consultation history, or SBAR records
- Document contents or raw OCR text
- Discharge instructions or triage severity scores

---

## 3. Support Audit Trail

Every search query executed by a support operator triggers an immutable audit log event:

- **Event Type**: `ADMIN_SUPPORT_LOOKUP`
- **Actor**: Operator User ID and Role
- **Resource**: `patient_support_search`
- **Metadata**: Query length, match count, and request correlation ID (zero PHI)

Any unauthorized access attempt or query that violates authorization policies raises `403 Forbidden` (`SUPPORT_LOOKUP_NOT_ALLOWED`).
