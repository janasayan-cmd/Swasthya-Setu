# Phase 30: Authorized Search, Indexing & Clinical Resource Retrieval — Database Dependencies

## 1. Overview & Team Boundary

This document outlines the database contracts, indexes, and full-text search requirements needed from the **Database Team** for Phase 30.

**CRITICAL RULE:**
The Backend Team does NOT create competing database tables or execute unilateral schema changes. The backend consumes the existing schema via repository abstractions.

---

## 2. Consumed Existing Tables & Search Fields

| Table Name | Primary Identifier | Searchable Fields | Recommended Index |
|------------|-------------------|-------------------|-------------------|
| `patients` | `id` (UUID) | `first_name`, `last_name`, `sovereign_id` | B-tree on `sovereign_id`, trigram gin on `(first_name || ' ' || last_name)` |
| `documents` | `id` (UUID) | `filename`, `document_type`, `patient_id` | B-tree on `patient_id`, B-tree on `document_type`, gin trigram on `filename` |
| `encounters` | `id` (UUID) | `encounter_type`, `external_id`, `organization_id`, `patient_id` | B-tree on `patient_id`, B-tree on `organization_id` |
| `prescriptions` | `id` (UUID) | `id`, `patient_id`, `status` | B-tree on `patient_id` |
| `medications` | `id` (UUID) | `canonical_name`, `generic_name`, `brand_name`, `terminology_code` | gin trigram on `canonical_name`, B-tree on `terminology_code` |
| `clinical_notes` | `id` (UUID) | `title`, `note_type`, `patient_id`, `status` | B-tree on `patient_id`, gin trigram on `title` |
| `patient_care_plans` | `id` (UUID) | `title`, `patient_id`, `status` | B-tree on `patient_id` |
| `clinical_discharge_instructions` | `id` (UUID) | `id`, `document_id`, `patient_id` | B-tree on `patient_id`, B-tree on `document_id` |
| `organizations` | `id` (UUID) | `name`, `status` | gin trigram on `name` |
| `facilities` | `id` (UUID) | `name`, `organization_id`, `status` | B-tree on `organization_id`, gin trigram on `name` |
| `transfers` | `id` (UUID) | `id`, `patient_id`, `sending_facility_id`, `receiving_facility_id` | B-tree on `patient_id`, B-tree on facility IDs |

---

## 3. Recommended PostgreSQL Extensions

For high-performance exact, prefix, and trigram fuzzy matching:
```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS btree_gin;
```

---

## 4. Operational & Performance SLAs
- **Query Timeout**: 5 seconds bounded execution (`statement_timeout = '5s'`).
- **Paging**: Bounded cursor or offset-limit (`LIMIT <= 100`).
- **Tenant Isolation**: All queries on multi-tenant tables must include `organization_id` or `facility_id` in their execution plans.
