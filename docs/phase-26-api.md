# Phase 26: Data Quality & Reconciliation API Reference

## 1. Patient Data Quality Endpoints

### Run Deterministic Data Quality Check
- **POST** `/api/v1/patients/{patient_id}/data-quality/check`
- **Requires**: `DATA_QUALITY_CHECK` permission (`doctor`, `admin`)
- **Request Body** (optional):
```json
{
  "resource_types": ["medication", "allergy"],
  "rule_types": ["duplicate_record", "conflicting_information"],
  "external_imports": []
}
```
- **Response**: StandardSuccessResponse containing `DataQualityCheckResponse`.

### List Patient Findings
- **GET** `/api/v1/patients/{patient_id}/data-quality?status=pending&severity=high`
- **Requires**: `DATA_QUALITY_READ` permission (`patient` for own, `doctor`, `admin`)
- **Response**: Paginated list of `DataQualityFindingResponse`.

### Review Finding
- **POST** `/api/v1/patients/{patient_id}/data-quality/{finding_id}/review`
- **Requires**: `DATA_QUALITY_REVIEW` permission (`doctor`, `admin`)
- **Request Body**:
```json
{
  "notes": "Initiated manual review of conflicting records."
}
```

### Resolve Finding
- **POST** `/api/v1/patients/{patient_id}/data-quality/{finding_id}/resolve`
- **Requires**: `DATA_QUALITY_RESOLVE` permission (`doctor`, `admin`)
- **Request Body**:
```json
{
  "action": "accept_clinician_source",
  "expected_version": 1,
  "reason": "Clinician entry confirmed against physical hospital discharge note.",
  "notes": "Preserving unverified entry as superseded."
}
```
*Returns 409 Conflict if expected_version does not match current version.*

## 2. Clinical Reconciliation Endpoints

### Reconcile Patient Records
- **POST** `/api/v1/patients/{patient_id}/data-quality/reconcile`
- **Requires**: `RECONCILIATION_EXECUTE` permission (`doctor`, `admin`)
- **Request Body**:
```json
{
  "scope": "all",
  "external_records": [
    {
      "resource_type": "allergy",
      "allergen": "Penicillin",
      "status": "active",
      "source_system": "Apollo_FHIR"
    }
  ]
}
```

### Resolve Reconciliation
- **POST** `/api/v1/patients/{patient_id}/reconciliation/{reconciliation_id}/resolve`
- **Requires**: `RECONCILIATION_RESOLVE` permission (`doctor`, `admin`)
- **Request Body**:
```json
{
  "action": "keep_both_annotated",
  "expected_version": 1,
  "reason": "Retaining external observation alongside internal note for specialist review."
}
```

## 3. Clinician Review Queue

- **GET** `/api/v1/clinicians/me/data-quality/findings`
- **GET** `/api/v1/clinicians/me/patients/{patient_id}/data-quality`
- **POST** `/api/v1/clinicians/me/data-quality/{finding_id}/review`
- **POST** `/api/v1/clinicians/me/data-quality/{finding_id}/resolve`
