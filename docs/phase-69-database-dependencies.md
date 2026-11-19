# Phase 69: Clinical Safety Governance Compliance Monitoring & Regulatory Evidence Management
## Database Dependencies Specification

**Document Version:** 1.0.0  
**Phase:** 69 (Governance Compliance Monitoring & Regulatory Evidence Management)  
**Boundary:** Backend application layer contract requirements for the database team.  
**Notice:** Backend does NOT create migrations, alter schemas, or manage DDL. This document defines the exact PostgreSQL entities, fields, constraints, and indexes required by HealthSetu backend services.

---

### 1. Conceptual Architecture & Isolation Boundary

Phase 69 monitors adherence to governance policies and regulatory frameworks, indexes supporting evidence across all predecessor phases (Phases 22, 24, 26, 43, 47, 48, 49, 51, 52, 54, 55, 58, 63, 65, 66, 67, 68), assesses compliance status, and coordinates corrective actions through Phase 54 and Phase 55.
- Entities are tenant-isolated via `organization_id` and optionally `facility_id`.
- Complete versioning and historical evaluation runs are preserved; past compliance results are locked to their evaluation timestamps and policy versions and are never retroactively overwritten.

---

### 2. Required Database Entities

#### 2.1 Table: `compliance_frameworks`
Stores registered governance policy frameworks and standards.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `framework_id` | VARCHAR(64) | PRIMARY KEY | Unique identifier (`gfw-uuid`) |
| `name` | VARCHAR(255) | NOT NULL | Framework name |
| `version` | VARCHAR(32) | NOT NULL DEFAULT 'v1.0.0' | Semantic version |
| `framework_type` | VARCHAR(64) | NOT NULL, INDEXED | Framework type enum |
| `description` | TEXT | NOT NULL | Context and objectives |
| `organization_id` | VARCHAR(64) | NOT NULL, INDEXED | Tenant isolation |
| `facility_id` | VARCHAR(64) | NULLABLE, INDEXED | Facility isolation |
| `effective_date` | TIMESTAMPTZ | NULLABLE | Effective start timestamp |
| `expiry_date` | TIMESTAMPTZ | NULLABLE | Deprecation timestamp |
| `lifecycle_status` | VARCHAR(32) | NOT NULL, INDEXED | Lifecycle status enum |
| `approved_by` | VARCHAR(64) | NULLABLE | User ID who approved |
| `approved_at` | TIMESTAMPTZ | NULLABLE | Approval timestamp |
| `created_by` | VARCHAR(64) | NOT NULL | Creator user ID |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Registration timestamp |
| `updated_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Last update timestamp |
| `metadata` | JSONB | NOT NULL DEFAULT '{}' | Extensible attributes |

#### 2.2 Table: `compliance_requirements`
Stores individual requirements under registered frameworks.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `requirement_id` | VARCHAR(64) | PRIMARY KEY | Unique identifier (`greq-uuid`) |
| `framework_id` | VARCHAR(64) | NOT NULL, FK to `compliance_frameworks`, INDEXED | Parent framework |
| `framework_version` | VARCHAR(32) | NOT NULL DEFAULT 'v1.0.0' | Framework version at registration |
| `requirement_code` | VARCHAR(64) | NOT NULL, INDEXED | Requirement code (e.g. `REQ-SAF-001`) |
| `title` | VARCHAR(255) | NOT NULL | Human-readable title |
| `description` | TEXT | NOT NULL | Requirement specification |
| `category` | VARCHAR(64) | NOT NULL, INDEXED | Requirement category enum |
| `organization_id` | VARCHAR(64) | NOT NULL, INDEXED | Tenant isolation |
| `facility_id` | VARCHAR(64) | NULLABLE, INDEXED | Facility isolation |
| `effective_date` | TIMESTAMPTZ | NULLABLE | Effective start timestamp |
| `expiry_date` | TIMESTAMPTZ | NULLABLE | Expiry timestamp |
| `owner_id` | VARCHAR(64) | NULLABLE, INDEXED | Responsible user ID |
| `owner_role` | VARCHAR(64) | NULLABLE | Responsible role |
| `related_policy_refs` | JSONB | NOT NULL DEFAULT '[]' | Referenced policy IDs |
| `related_control_refs` | JSONB | NOT NULL DEFAULT '[]' | Referenced control IDs |
| `expected_evidence_types` | JSONB | NOT NULL DEFAULT '[]' | Expected evidence categories |
| `assessment_frequency` | VARCHAR(32) | NOT NULL DEFAULT 'MONTHLY' | Assessment cadence enum |
| `review_requirements` | TEXT | NULLABLE | Special review criteria |
| `lifecycle_status` | VARCHAR(32) | NOT NULL, INDEXED | Lifecycle status enum |
| `version` | VARCHAR(32) | NOT NULL DEFAULT 'v1.0.0' | Requirement version |
| `approved_by` | VARCHAR(64) | NULLABLE | Governance approver |
| `approved_at` | TIMESTAMPTZ | NULLABLE | Approval timestamp |
| `activated_by` | VARCHAR(64) | NULLABLE | Activator user ID |
| `activated_at` | TIMESTAMPTZ | NULLABLE | Activation timestamp |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Registration timestamp |
| `updated_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Last update timestamp |
| `metadata` | JSONB | NOT NULL DEFAULT '{}' | Extensible attributes |

#### 2.3 Table: `requirement_control_mappings`
Maps compliance requirements to authoritative workflow controls.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `mapping_id` | VARCHAR(64) | PRIMARY KEY | Unique identifier (`gmap-uuid`) |
| `requirement_id` | VARCHAR(64) | NOT NULL, FK to `compliance_requirements`, INDEXED | Target requirement |
| `control_id` | VARCHAR(64) | NOT NULL, INDEXED | Control identifier |
| `control_name` | VARCHAR(255) | NOT NULL | Human-readable control name |
| `control_owner_phase` | VARCHAR(32) | NOT NULL, INDEXED | Authoritative source phase (`PHASE_48`..`PHASE_68`) |
| `control_owner_id` | VARCHAR(64) | NULLABLE | Control owner ID |
| `control_purpose` | TEXT | NOT NULL | Functional purpose |
| `verification_method` | VARCHAR(64) | NOT NULL | Verification methodology |
| `expected_evidence` | TEXT | NOT NULL | Expected evidence description |
| `mapping_status` | VARCHAR(32) | NOT NULL DEFAULT 'APPROVED' | Status (`APPROVED`, `DEPRECATED`) |
| `approved_by` | VARCHAR(64) | NULLABLE | User who approved mapping |
| `approved_at` | TIMESTAMPTZ | NULLABLE | Approval timestamp |
| `policy_version` | VARCHAR(32) | NOT NULL DEFAULT 'v1.0.0' | Policy version |
| `rationale` | TEXT | NOT NULL | Mapping justification |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Mapping creation timestamp |
| `metadata` | JSONB | NOT NULL DEFAULT '{}' | Extensible attributes |

#### 2.4 Table: `compliance_assessments`
Stores deterministic compliance assessment evaluation runs.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `assessment_id` | VARCHAR(64) | PRIMARY KEY | Unique identifier (`gasm-uuid`) |
| `framework_id` | VARCHAR(64) | NOT NULL, FK to `compliance_frameworks`, INDEXED | Parent framework |
| `framework_version` | VARCHAR(32) | NOT NULL DEFAULT 'v1.0.0' | Framework version evaluated |
| `requirement_id` | VARCHAR(64) | NOT NULL, FK to `compliance_requirements`, INDEXED | Target requirement |
| `organization_id` | VARCHAR(64) | NOT NULL, INDEXED | Tenant isolation |
| `facility_id` | VARCHAR(64) | NULLABLE, INDEXED | Facility isolation |
| `assessment_scope` | VARCHAR(64) | NOT NULL DEFAULT 'ORGANIZATION' | Evaluation scope |
| `assessment_type` | VARCHAR(32) | NOT NULL DEFAULT 'MANUAL' | Trigger category |
| `status` | VARCHAR(64) | NOT NULL, INDEXED | Compliance status enum (18 states) |
| `assessed_by` | VARCHAR(64) | NOT NULL | Evaluator user ID |
| `assessed_at` | TIMESTAMPTZ | NOT NULL | Timestamp assessment executed |
| `assessment_rationale` | TEXT | NULLABLE | Detailed evaluation rationale |
| `limitations` | JSONB | NOT NULL DEFAULT '[]' | Explicit limitations noted |
| `evidence_refs` | JSONB | NOT NULL DEFAULT '[]' | Evidence item IDs evaluated |
| `findings_count` | INTEGER | NOT NULL DEFAULT 0 | Total gaps discovered |
| `critical_findings_count` | INTEGER | NOT NULL DEFAULT 0 | High & critical gaps count |
| `policy_version_used` | VARCHAR(32) | NOT NULL DEFAULT 'v1.0.0' | Point-in-time policy version |
| `correlation_id` | VARCHAR(128) | NULLABLE | Distributed tracing ID |
| `idempotency_key` | VARCHAR(128) | NULLABLE, UNIQUE | Client idempotency token |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Creation timestamp |
| `metadata` | JSONB | NOT NULL DEFAULT '{}' | Extensible attributes |

#### 2.5 Table: `compliance_evidence_index`
Indexes supporting evidence across authoritative workflows.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `evidence_id` | VARCHAR(64) | PRIMARY KEY | Unique identifier (`gevd-uuid`) |
| `requirement_id` | VARCHAR(64) | NOT NULL, FK to `compliance_requirements`, INDEXED | Target requirement |
| `control_id` | VARCHAR(64) | NULLABLE, INDEXED | Associated control ID |
| `source_phase` | VARCHAR(32) | NOT NULL, INDEXED | Originating phase |
| `source_record_id` | VARCHAR(64) | NOT NULL, INDEXED | Originating system record key |
| `evidence_category` | VARCHAR(64) | NOT NULL, INDEXED | Functional category |
| `evidence_version` | VARCHAR(32) | NOT NULL DEFAULT 'v1.0.0' | Semantic version |
| `effective_timestamp` | TIMESTAMPTZ | NOT NULL | Timestamp evidence effective |
| `provenance_details` | JSONB | NOT NULL DEFAULT '{}' | Forensic provenance details |
| `validity_status` | VARCHAR(32) | NOT NULL, INDEXED | `VALID`, `STALE`, `INVALIDATED`, etc. |
| `checksum` | VARCHAR(64) | NULLABLE | Deterministic SHA256 checksum |
| `access_classification` | VARCHAR(32) | NOT NULL DEFAULT 'INTERNAL' | Confidentiality tier |
| `retention_class` | VARCHAR(64) | NOT NULL DEFAULT 'STANDARD_7_YEARS' | Retention classification |
| `is_accessible` | BOOLEAN | NOT NULL DEFAULT TRUE | Accessibility flag |
| `last_verified_at` | TIMESTAMPTZ | NULLABLE | Last reconciliation timestamp |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Registration timestamp |
| `metadata` | JSONB | NOT NULL DEFAULT '{}' | Extensible attributes |

#### 2.6 Table: `compliance_findings`
Stores identified compliance gaps and discrepancies.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `finding_id` | VARCHAR(64) | PRIMARY KEY | Unique identifier (`gfnd-uuid`) |
| `assessment_id` | VARCHAR(64) | NOT NULL, FK to `compliance_assessments`, INDEXED | Parent assessment |
| `requirement_id` | VARCHAR(64) | NOT NULL, FK to `compliance_requirements`, INDEXED | Target requirement |
| `control_id` | VARCHAR(64) | NULLABLE, INDEXED | Associated control |
| `gap_category` | VARCHAR(64) | NOT NULL, INDEXED | Gap category enum (18 categories) |
| `priority` | VARCHAR(32) | NOT NULL, INDEXED | Governance priority enum |
| `title` | VARCHAR(255) | NOT NULL | Summary title |
| `description` | TEXT | NOT NULL | Detailed finding narrative |
| `evidence_refs` | JSONB | NOT NULL DEFAULT '[]' | Supporting evidence IDs |
| `source_workflow_refs` | JSONB | NOT NULL DEFAULT '[]' | Upstream workflow references |
| `assigned_owner_id` | VARCHAR(64) | NULLABLE, INDEXED | Assigned owner user ID |
| `assigned_owner_role` | VARCHAR(64) | NULLABLE | Assigned owner role |
| `is_resolved` | BOOLEAN | NOT NULL DEFAULT FALSE, INDEXED | Resolution status |
| `resolution_rationale` | TEXT | NULLABLE | Documented resolution rationale |
| `resolved_by` | VARCHAR(64) | NULLABLE | User who resolved finding |
| `resolved_at` | TIMESTAMPTZ | NULLABLE | Resolution timestamp |
| `review_outcome` | VARCHAR(64) | NULLABLE | Review outcome enum |
| `reviewed_by` | VARCHAR(64) | NULLABLE | Reviewer user ID |
| `reviewed_at` | TIMESTAMPTZ | NULLABLE | Review timestamp |
| `review_rationale` | TEXT | NULLABLE | Review justification |
| `recommended_action` | TEXT | NULLABLE | Recommended corrective action |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Discovery timestamp |
| `metadata` | JSONB | NOT NULL DEFAULT '{}' | Extensible attributes |

#### 2.7 Table: `compliance_corrective_action_requests`
Stores corrective action requests transmitted to Phase 54 controlled action orchestration.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `action_request_id` | VARCHAR(64) | PRIMARY KEY | Unique identifier (`gca-uuid`) |
| `finding_id` | VARCHAR(64) | NOT NULL, FK to `compliance_findings`, INDEXED | Target finding |
| `requirement_id` | VARCHAR(64) | NOT NULL, FK to `compliance_requirements`, INDEXED | Target requirement |
| `target_phase` | VARCHAR(32) | NOT NULL DEFAULT 'PHASE_54_CONTROLLED_ACTION' | Target orchestration phase |
| `target_action_id` | VARCHAR(64) | NULLABLE | Phase 54 action identifier |
| `status` | VARCHAR(32) | NOT NULL, INDEXED | Action status enum |
| `reason` | TEXT | NOT NULL | Reason for corrective action |
| `required_outcome` | TEXT | NOT NULL | Desired remediation outcome |
| `requested_by` | VARCHAR(64) | NOT NULL | Submitting user ID |
| `requested_at` | TIMESTAMPTZ | NOT NULL | Submission timestamp |
| `phase54_action_ref` | VARCHAR(128) | NULLABLE | Reference to Phase 54 action |
| `phase55_eval_ref` | VARCHAR(128) | NULLABLE | Reference to Phase 55 effectiveness eval |
| `completion_evidence_refs` | JSONB | NOT NULL DEFAULT '[]' | Remediation evidence IDs |
| `effectiveness_outcome` | VARCHAR(64) | NULLABLE | Phase 55 outcome |
| `reassessment_id` | VARCHAR(64) | NULLABLE | Subsequent reassessment run ID |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Request creation timestamp |
| `updated_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Last update timestamp |
| `metadata` | JSONB | NOT NULL DEFAULT '{}' | Extensible attributes |

#### 2.8 Table: `regulatory_evidence_packages`
Stores generated evidence package archives for internal audits and regulatory prep.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `package_id` | VARCHAR(64) | PRIMARY KEY | Unique identifier (`gpkg-uuid`) |
| `framework_id` | VARCHAR(64) | NOT NULL, FK to `compliance_frameworks`, INDEXED | Associated framework |
| `framework_version` | VARCHAR(32) | NOT NULL DEFAULT 'v1.0.0' | Framework version |
| `organization_id` | VARCHAR(64) | NOT NULL, INDEXED | Tenant isolation |
| `facility_id` | VARCHAR(64) | NULLABLE, INDEXED | Facility isolation |
| `title` | VARCHAR(255) | NOT NULL | Package title |
| `description` | TEXT | NOT NULL | Summary description |
| `scope_summary` | TEXT | NOT NULL | Scope summary |
| `target_audience` | VARCHAR(64) | NOT NULL DEFAULT 'INTERNAL_AUDIT' | Audience enum |
| `status` | VARCHAR(32) | NOT NULL, INDEXED | Package status enum |
| `requirement_ids` | JSONB | NOT NULL DEFAULT '[]' | Packaged requirement IDs |
| `assessment_ids` | JSONB | NOT NULL DEFAULT '[]' | Packaged assessment IDs |
| `evidence_refs` | JSONB | NOT NULL DEFAULT '[]' | Packaged evidence IDs |
| `gap_ids` | JSONB | NOT NULL DEFAULT '[]' | Packaged unresolved gap IDs |
| `limitations` | JSONB | NOT NULL DEFAULT '[]' | Explicit limitations noted |
| `generated_by` | VARCHAR(64) | NOT NULL | Generator user ID |
| `generated_at` | TIMESTAMPTZ | NOT NULL | Generation timestamp |
| `download_count` | INTEGER | NOT NULL DEFAULT 0 | Download/access counter |
| `last_accessed_at` | TIMESTAMPTZ | NULLABLE | Last access timestamp |
| `integrity_hash` | VARCHAR(64) | NULLABLE | SHA256 manifest hash |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Package creation timestamp |
| `metadata` | JSONB | NOT NULL DEFAULT '{}' | Extensible attributes |

---

### 3. Recommended PostgreSQL Indexes

```sql
-- Framework & Requirement Isolation
CREATE INDEX idx_gfw_org_fac ON compliance_frameworks(organization_id, facility_id);
CREATE INDEX idx_greq_framework ON compliance_requirements(framework_id, lifecycle_status);
CREATE INDEX idx_greq_org_cat ON compliance_requirements(organization_id, category);

-- Control Mapping Traceability
CREATE INDEX idx_gmap_req ON requirement_control_mappings(requirement_id);
CREATE INDEX idx_gmap_phase_control ON requirement_control_mappings(control_owner_phase, control_id);

-- Assessment Evaluation & Queues
CREATE INDEX idx_gasm_req_time ON compliance_assessments(requirement_id, assessed_at DESC);
CREATE INDEX idx_gasm_org_status ON compliance_assessments(organization_id, status);
CREATE INDEX idx_gasm_idempotency ON compliance_assessments(idempotency_key) WHERE idempotency_key IS NOT NULL;

-- Evidence Management & Validity
CREATE INDEX idx_gevd_req ON compliance_evidence_index(requirement_id, validity_status);
CREATE INDEX idx_gevd_source ON compliance_evidence_index(source_phase, source_record_id);

-- Findings (Gaps) Tracking
CREATE INDEX idx_gfnd_asm ON compliance_findings(assessment_id);
CREATE INDEX idx_gfnd_req_unresolved ON compliance_findings(requirement_id) WHERE is_resolved = FALSE;
CREATE INDEX idx_gfnd_priority ON compliance_findings(priority, gap_category);

-- Corrective Action Requests
CREATE INDEX idx_gca_finding ON compliance_corrective_action_requests(finding_id);
CREATE INDEX idx_gca_status ON compliance_corrective_action_requests(status);

-- Evidence Packages
CREATE INDEX idx_gpkg_org ON regulatory_evidence_packages(organization_id, status);
```
