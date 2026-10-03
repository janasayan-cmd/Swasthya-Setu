# HealthSetu — Phase 34: Database Dependencies & Contracts

## 1. Ownership Boundary
The database schema, constraints, migrations, and index definitions are strictly owned by the **Database Team**. The Backend Team relies on database contracts without executing direct DDL or creating parallel database models.

## 2. Expected Database Tables & Relations

### `diagnostic_tests` (Catalog)
- `test_id` (PK, text/uuid)
- `code` (varchar, LOINC/CPT)
- `system` (varchar)
- `name` (varchar)
- `raw_name` (varchar)
- `category` (varchar)
- `specimen_type` (varchar, nullable)
- `default_unit` (varchar, nullable)
- `is_active` (boolean)

### `diagnostic_orders`
- `order_id` (PK, uuid/text)
- `order_number` (varchar, unique, e.g. `ORD-YYYYMMDD-XXXX`)
- `patient_id` (FK to patients)
- `clinician_id` (FK to clinicians/users)
- `organization_id` (FK to organizations)
- `facility_id` (FK to facilities)
- `encounter_id` (FK to encounters, nullable)
- `status` (varchar enum)
- `priority` (varchar enum)
- `clinical_reason` (text, nullable)
- `provider_id` (varchar, nullable)
- `provider_order_id` (varchar, nullable)
- `ordered_at` (timestamptz)
- `submitted_at` (timestamptz, nullable)
- `cancelled_at` (timestamptz, nullable)
- `completed_at` (timestamptz, nullable)
- `idempotency_key` (varchar, unique, nullable)

### `diagnostic_order_items`
- `item_id` (PK)
- `order_id` (FK to diagnostic_orders)
- `test_id` (FK to diagnostic_tests)
- `test_code` (varchar)
- `test_name` (varchar)
- `specimen_id` (FK to specimens, nullable)
- `status` (varchar)

### `specimens`
- `specimen_id` (PK)
- `order_id` (FK to diagnostic_orders)
- `patient_id` (FK to patients)
- `specimen_type` (varchar)
- `status` (varchar)
- `collected_at` (timestamptz, nullable)
- `received_at` (timestamptz, nullable)
- `rejection_reason` (text, nullable)

### `diagnostic_results`
- `result_id` (PK)
- `order_id` (FK to diagnostic_orders, nullable)
- `patient_id` (FK to patients)
- `provider_id` (varchar)
- `provider_result_id` (varchar)
- `status` (varchar enum: PRELIMINARY, FINAL, CORRECTED, AMENDED, CANCELLED)
- `verification_status` (varchar enum: REVIEW_REQUIRED, VERIFIED, REJECTED, SUPERSEDED)
- `has_critical_flag` (boolean)
- `version` (int)
- `is_current` (boolean)
- `supersedes_result_id` (FK to diagnostic_results, nullable)
- `correction_reason` (text, nullable)
- `verified_by` (FK to users, nullable)
- `verified_at` (timestamptz, nullable)
- `resulted_at` (timestamptz)

### `diagnostic_result_items`
- `item_id` (PK)
- `result_id` (FK to diagnostic_results)
- `analyte_name` (varchar)
- `analyte_code` (varchar, nullable)
- `numeric_value` (numeric/float, nullable)
- `qualitative_value` (varchar, nullable)
- `unit` (varchar, nullable)
- `abnormal_flag` (varchar)
- `ref_low` (float, nullable)
- `ref_high` (float, nullable)
- `ref_text` (varchar, nullable)
- `ref_is_available` (boolean)

### `diagnostic_reports`
- `report_id` (PK)
- `report_number` (varchar, unique, e.g. `RPT-YYYYMMDD-XXXX`)
- `order_id` (FK to diagnostic_orders, nullable)
- `patient_id` (FK to patients)
- `provider_id` (varchar)
- `status` (varchar)
- `conclusion_text` (text, nullable)
- `document_id` (FK to documents, nullable)
- `reported_at` (timestamptz)

### `diagnostic_webhooks`
- `event_id` (PK)
- `provider_id` (varchar)
- `event_type` (varchar)
- `payload` (jsonb)
- `received_at` (timestamptz)
- Unique index on `(provider_id, event_id)` for replay protection.
