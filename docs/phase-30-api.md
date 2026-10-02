# Phase 30: Authorized Search, Indexing & Clinical Resource Retrieval — API Specification

## Overview

The HealthSetu Search API exposes authorized, multi-tenant endpoints for resource discovery across patients, clinical documents, prescriptions, normalized medications, encounters, care plans, discharges, clinical notes, organizations, facilities, and transfers.

All responses strictly follow the standard Phase 23 JSON contract:
```json
{
  "success": true,
  "data": { ... }
}
```

---

## Endpoints

### 1. Unified Search
`GET /api/v1/search`

Executes cross-resource search across all domains authorized for the authenticated user's role and context.

**Query Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `q` | string | Yes | - | Search query (2–200 characters) |
| `resource_type` | string | No | null | One of `patient`, `encounter`, `document`, `prescription`, `medication`, `care_plan`, `discharge`, `clinical_note`, `organization`, `facility`, `clinician`, `transfer` |
| `patient_id` | string | No | null | Scope to specific patient |
| `organization_id` | string | No | null | Scope to specific healthcare organization |
| `facility_id` | string | No | null | Scope to specific facility |
| `status` | string | No | null | Resource lifecycle status (e.g., `ACTIVE`, `VERIFIED`) |
| `page` | integer | No | 1 | 1-based page number |
| `page_size` | integer | No | 20 | Page size (1–100) |
| `sort` | string | No | `relevance` | Allowlisted: `relevance`, `name`, `status`, `created_at`, `updated_at` |
| `sort_order` | string | No | `desc` | `asc` or `desc` |

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "items": [
      {
        "resource_type": "document",
        "resource_id": "doc-001",
        "display": "DISCHARGE_SUMMARY - discharge_note.pdf",
        "match_type": "CONTAINS",
        "source": "healthsetu",
        "status": "STORED",
        "relevance_score": 0.6,
        "provenance": {
          "source": "healthsetu",
          "source_version": null,
          "source_system": null,
          "external_resource_id": null,
          "source_organization_id": null,
          "imported_at": null
        }
      }
    ],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total": 1,
      "total_pages": 1
    }
  }
}
```

---

### 2. Autocomplete Suggestions
`GET /api/v1/search/suggestions`

Retrieves prefix-matched suggestions within the user's authorized scope.

**Query Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `q` | string | Yes | - | Prefix query (2–100 characters) |
| `resource_type` | string | No | null | Scope suggestion to specific resource |
| `limit` | integer | No | 10 | Max suggestions (1–20) |

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "suggestions": [
      {
        "text": "Paracetamol 500mg",
        "resource_type": "medication",
        "resource_id": "med-paracetamol-500"
      }
    ]
  }
}
```

---

### 3. Resource-Specific Endpoints
- `GET /api/v1/search/patients` (Requires `search:patient` permission)
- `GET /api/v1/search/documents` (Requires `search:document` permission)
- `GET /api/v1/search/medications` (Requires `search:execute` permission)
- `GET /api/v1/search/facilities` (Requires `search:facility` permission)
- `GET /api/v1/search/organizations` (Requires `search:organization` permission)

---

### 4. Admin Search Endpoints
- `GET /api/v1/search/admin/status` (Requires `admin:search_view`)
- `POST /api/v1/search/admin/rebuild` (Requires `admin:search_manage`)
