# Phase 68: Clinical Safety Governance Decision Assurance, Authorization Integrity & Cross-Workflow Decision Traceability
## Database Dependencies Specification

**Document Version:** 1.0.0  
**Phase:** 68 (Governance Decision Assurance)  
**Boundary:** Backend application layer contract requirements for the database team.  
**Notice:** Backend does NOT create migrations, alter schemas, or manage DDL. This document defines the exact PostgreSQL entities, fields, constraints, and indexes required by HealthSetu backend services.

---

### 1. Conceptual Architecture & Isolation Boundary

Phase 68 verifies decision provenance, historical authorization, separation of duties, policy applicability, evidence integrity, and cross-workflow consistency across all previous clinical safety phases.
- Entities are tenant-isolated via `organization_id` and optionally `facility_id`.
- The database schema preserves complete provenance: source phase, source record ID, source version, and immutable audit history.
- Historical decision records must never be overwritten or deleted; decisions failing assurance generate explicit finding records and correction requests directed to authoritative source phase owners.

---

### 2. Required Database Entities

#### 2.1 Table: `governance_decision_register`
Stores references to authoritative decisions across safety phases without duplicating domain entities.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `decision_id` | VARCHAR(64) | PRIMARY KEY | Unique identifier (`gdec-uuid`) |
| `source_phase` | VARCHAR(32) | NOT NULL, INDEXED | Originating phase (`PHASE_49`..`PHASE_67`) |
| `source_record_id` | VARCHAR(64) | NOT NULL, INDEXED | Primary key in the source system |
| `source_version` | VARCHAR(32) | NOT NULL DEFAULT 'v1.0.0' | Semantic version of source record |
| `decision_type` | VARCHAR(64) | NOT NULL, INDEXED | Domain decision type |
| `decision_title` | VARCHAR(255) | NOT NULL | Human-readable title |
| `decision_outcome` | VARCHAR(64) | NOT NULL, INDEXED | Outcome rendered |
| `organization_id` | VARCHAR(64) | NOT NULL, INDEXED | Multi-tenant organization scope |
| `facility_id` | VARCHAR(64) | NOT NULL, INDEXED | Associated facility scope |
| `patient_id` | VARCHAR(64) | NULLABLE, INDEXED | Associated patient scope (if applicable) |
| `decided_by_id` | VARCHAR(64) | NOT NULL, INDEXED | User ID who rendered decision |
| `decided_by_role` | VARCHAR(64) | NOT NULL | Role of decision maker at decision time |
| `decided_by_scope` | VARCHAR(64) | NOT NULL DEFAULT 'facility' | Jurisdiction scope (`facility`, `organization`, etc.) |
| `is_automated` | BOOLEAN | NOT NULL DEFAULT FALSE | True if algorithmic or automated |
| `service_identity` | VARCHAR(128) | NULLABLE | Service identity if automated |
| `decided_at` | TIMESTAMPTZ | NOT NULL | Timestamp decision was rendered |
| `requester_id` | VARCHAR(64) | NULLABLE, INDEXED | User ID of requester (if applicable) |
| `approver_id` | VARCHAR(64) | NULLABLE, INDEXED | User ID of secondary approver |
| `authorization_evidence_ref` | VARCHAR(255) | NULLABLE | Historical auth credential/token ref |
| `policy_reference` | VARCHAR(128) | NOT NULL | Governance policy reference |
| `policy_version` | VARCHAR(32) | NOT NULL | Policy version in effect at decision time |
| `policy_effective_date` | TIMESTAMPTZ | NULLABLE | Effective start timestamp of policy |
| `supporting_evidence_refs` | JSONB | NOT NULL DEFAULT '[]' | List of supporting clinical evidence refs |
| `rationale` | TEXT | NOT NULL | Documented justification |
| `related_decision_ids` | JSONB | NOT NULL DEFAULT '[]' | References to related decision IDs |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Registration timestamp |
| `updated_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Last update timestamp |
| `metadata` | JSONB | NOT NULL DEFAULT '{}' | Extensible attributes |

#### 2.2 Table: `governance_decision_assurances`
Stores multi-dimensional assurance evaluation runs for registered decisions.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `assurance_id` | VARCHAR(64) | PRIMARY KEY | Unique identifier (`gass-uuid`) |
| `decision_id` | VARCHAR(64) | NOT NULL, FK to `governance_decision_register`, INDEXED | Associated decision |
| `organization_id` | VARCHAR(64) | NOT NULL, INDEXED | Tenant isolation |
| `facility_id` | VARCHAR(64) | NOT NULL, INDEXED | Facility isolation |
| `lifecycle_state` | VARCHAR(64) | NOT NULL, INDEXED | Assurance lifecycle state (21 states) |
| `evaluated_by` | VARCHAR(64) | NOT NULL | User ID who executed evaluation |
| `evaluated_at` | TIMESTAMPTZ | NOT NULL | Timestamp evaluation was executed |
| `provenance_verified` | BOOLEAN | NOT NULL DEFAULT FALSE | Provenance check passed |
| `provenance_details` | JSONB | NOT NULL DEFAULT '{}' | Diagnostic provenance metadata |
| `authorization_status` | VARCHAR(64) | NOT NULL | Auth status enum |
| `separation_of_duties_status` | VARCHAR(64) | NOT NULL | Separation-of-duties enum |
| `authorization_details` | JSONB | NOT NULL DEFAULT '{}' | Authorization diagnostic metadata |
| `policy_compliance_verified`| BOOLEAN | NOT NULL DEFAULT FALSE | Policy temporal & version check |
| `policy_version` | VARCHAR(32) | NOT NULL | Policy version used during evaluation |
| `policy_details` | JSONB | NOT NULL DEFAULT '{}' | Policy diagnostic metadata |
| `evidence_assurance_status` | VARCHAR(64) | NOT NULL | Evidence taxonomy status enum |
| `evidence_details` | JSONB | NOT NULL DEFAULT '{}' | Evidence diagnostic metadata |
| `cross_workflow_consistent` | BOOLEAN | NOT NULL DEFAULT TRUE | Cross-workflow check passed |
| `consistency_details` | JSONB | NOT NULL DEFAULT '{}' | Consistency diagnostic metadata |
| `findings_count` | INTEGER | NOT NULL DEFAULT 0 | Total findings generated |
| `critical_findings_count` | INTEGER | NOT NULL DEFAULT 0 | High and critical findings count |
| `limitations` | JSONB | NOT NULL DEFAULT '[]' | Non-critical limitations noted |
| `assurance_rationale` | TEXT | NULLABLE | Overall evaluation synthesis rationale |
| `idempotency_key` | VARCHAR(128) | NULLABLE, UNIQUE | Client idempotency token |
| `correlation_id` | VARCHAR(128) | NULLABLE | Distributed tracing correlation ID |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Timestamp record created |
| `metadata` | JSONB | NOT NULL DEFAULT '{}' | Extensible attributes |

#### 2.3 Table: `assurance_findings`
Stores specific integrity findings, breaches, or discrepancies detected during assurance.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `finding_id` | VARCHAR(64) | PRIMARY KEY | Unique identifier (`gfind-uuid`) |
| `assurance_id` | VARCHAR(64) | NOT NULL, FK to `governance_decision_assurances`, INDEXED | Parent assurance run |
| `decision_id` | VARCHAR(64) | NOT NULL, FK to `governance_decision_register`, INDEXED | Target decision |
| `category` | VARCHAR(64) | NOT NULL, INDEXED | Finding category enum |
| `severity` | VARCHAR(32) | NOT NULL, INDEXED | Finding severity enum (`INFO`..`CRITICAL`) |
| `title` | VARCHAR(255) | NOT NULL | Short finding title |
| `description` | TEXT | NOT NULL | Detailed finding narrative |
| `evidence_refs` | JSONB | NOT NULL DEFAULT '[]' | Supporting diagnostic refs |
| `is_resolved` | BOOLEAN | NOT NULL DEFAULT FALSE, INDEXED | Resolution status |
| `resolution_rationale` | TEXT | NULLABLE | Rationale for resolution |
| `resolved_by` | VARCHAR(64) | NULLABLE | User ID who resolved finding |
| `resolved_at` | TIMESTAMPTZ | NULLABLE | Timestamp of resolution |
| `review_outcome` | VARCHAR(64) | NULLABLE | Review outcome enum |
| `reviewed_by` | VARCHAR(64) | NULLABLE | User ID who performed review |
| `reviewed_at` | TIMESTAMPTZ | NULLABLE | Timestamp of review |
| `review_rationale` | TEXT | NULLABLE | Review justification |
| `recommended_action` | TEXT | NULLABLE | Action recommended to authoritative owner |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Discovery timestamp |
| `metadata` | JSONB | NOT NULL DEFAULT '{}' | Extensible attributes |

#### 2.4 Table: `decision_correction_requests`
Stores formal correction and revocation review requests transmitted to authoritative owners.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `request_id` | VARCHAR(64) | PRIMARY KEY | Unique identifier (`gcorr-uuid`) |
| `decision_id` | VARCHAR(64) | NOT NULL, FK to `governance_decision_register`, INDEXED | Target decision |
| `target_phase` | VARCHAR(32) | NOT NULL, INDEXED | Target source phase |
| `target_record_id` | VARCHAR(64) | NOT NULL | Primary key in target phase |
| `request_type` | VARCHAR(32) | NOT NULL | `CORRECTION` or `REVOCATION_REVIEW` |
| `status` | VARCHAR(32) | NOT NULL, INDEXED | Request status enum |
| `reason` | TEXT | NOT NULL | Detailed justification |
| `finding_refs` | JSONB | NOT NULL DEFAULT '[]' | Associated finding IDs |
| `requested_by` | VARCHAR(64) | NOT NULL | Submitting user ID |
| `requested_at` | TIMESTAMPTZ | NOT NULL | Submission timestamp |
| `responded_by` | VARCHAR(64) | NULLABLE | Responding owner user ID |
| `responded_at` | TIMESTAMPTZ | NULLABLE | Response timestamp |
| `response_notes` | TEXT | NULLABLE | Authoritative owner response narrative |
| `authoritative_action_taken`| VARCHAR(64) | NULLABLE | Action taken enum |
| `updated_record_version`| VARCHAR(32) | NULLABLE | New version of authoritative record |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Creation timestamp |
| `updated_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Last update timestamp |
| `metadata` | JSONB | NOT NULL DEFAULT '{}' | Extensible attributes |

#### 2.5 Table: `cross_workflow_consistency_checks`
Stores individual cross-workflow consistency evaluation checks.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `check_id` | VARCHAR(64) | PRIMARY KEY | Unique identifier (`gchk-uuid`) |
| `decision_id` | VARCHAR(64) | NOT NULL, INDEXED | Target decision evaluated |
| `related_decision_id` | VARCHAR(64) | NOT NULL, INDEXED | Correlated decision compared against |
| `target_phase` | VARCHAR(32) | NOT NULL | Source phase of compared decision |
| `target_record_id` | VARCHAR(64) | NOT NULL | Source record ID of compared decision |
| `is_consistent` | BOOLEAN | NOT NULL | Evaluation outcome |
| `conflict_type` | VARCHAR(64) | NULLABLE | Type of contradiction detected |
| `conflict_description` | TEXT | NULLABLE | Description of conflicting states |
| `checked_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Evaluation timestamp |

---

### 3. Recommended PostgreSQL Indexes

```sql
-- Tenant Isolation & Lookup Indexes
CREATE INDEX idx_gdec_org_fac ON governance_decision_register(organization_id, facility_id);
CREATE INDEX idx_gdec_source ON governance_decision_register(source_phase, source_record_id);
CREATE INDEX idx_gdec_decided_by ON governance_decision_register(decided_by_id);

CREATE INDEX idx_gass_decision ON governance_decision_assurances(decision_id);
CREATE INDEX idx_gass_lifecycle ON governance_decision_assurances(organization_id, lifecycle_state);
CREATE INDEX idx_gass_idempotency ON governance_decision_assurances(idempotency_key) WHERE idempotency_key IS NOT NULL;

CREATE INDEX idx_gfind_assurance ON assurance_findings(assurance_id);
CREATE INDEX idx_gfind_decision ON assurance_findings(decision_id);
CREATE INDEX idx_gfind_unresolved ON assurance_findings(is_resolved) WHERE is_resolved = FALSE;
CREATE INDEX idx_gfind_category_sev ON assurance_findings(category, severity);

CREATE INDEX idx_gcorr_decision ON decision_correction_requests(decision_id);
CREATE INDEX idx_gcorr_target ON decision_correction_requests(target_phase, target_record_id);
CREATE INDEX idx_gcorr_status ON decision_correction_requests(status);

CREATE INDEX idx_gchk_decision ON cross_workflow_consistency_checks(decision_id);
CREATE INDEX idx_gchk_related ON cross_workflow_consistency_checks(related_decision_id);
```
