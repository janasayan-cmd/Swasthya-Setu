# Phase 71: Clinical Safety Governance Audit Intelligence
## Database Dependencies Specification

**Document Version:** 1.0.0  
**Phase:** 71 (Clinical Safety Governance Audit Finding Analytics, Repeat-Issue Detection & Systemic Risk Insight)  
**Boundary:** Backend application layer contract requirements for the database team.  
**Notice:** Backend does NOT create migrations, alter schemas, or manage DDL. This document defines the exact PostgreSQL entities, fields, constraints, and indexes required by HealthSetu backend services.

---

### 1. Conceptual Architecture & Isolation Boundary

Phase 71 transforms authorized audit records into structured governance intelligence, identifying recurring weaknesses, cross-audit patterns, systemic issues, and CAPA recurrences.
- Entities are tenant-isolated via `organization_id` and optionally `facility_id`.
- Complete versioning of analytical configurations, review history, and referral provenance is immutably preserved.
- Analytical outputs reference authoritative source records (Phase 70 audits/findings, Phase 69 compliance, Phase 54 CAPA, Phase 55 effectiveness) without mutating historical audit records.

---

### 2. Required Database Entities

#### 2.1 Table: `audit_analytics_configurations`
Stores versioned analytical configurations for repeat matching, scoring, and thresholds.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `configuration_id` | VARCHAR(64) | PRIMARY KEY | Unique identifier (`gcfg-uuid`) |
| `version` | VARCHAR(32) | NOT NULL, INDEXED | Semantic version (`v1.0.0`) |
| `name` | VARCHAR(255) | NOT NULL | Configuration title |
| `description` | TEXT | NOT NULL | Configuration scope and rules |
| `repeat_matching_rules` | JSONB | NOT NULL DEFAULT '{}' | Rules for repeat matching |
| `severity_weights` | JSONB | NOT NULL DEFAULT '{}' | Weights for severity tiers |
| `pattern_detection_thresholds` | JSONB | NOT NULL DEFAULT '{}' | Thresholds for pattern detection |
| `priority_scoring_factors` | JSONB | NOT NULL DEFAULT '{}' | Factor weights for priority score |
| `is_active` | BOOLEAN | NOT NULL DEFAULT FALSE, INDEXED | Active flag |
| `is_deprecated` | BOOLEAN | NOT NULL DEFAULT FALSE, INDEXED | Deprecation flag |
| `approved_by` | VARCHAR(64) | NULLABLE | Approver user ID |
| `approved_at` | TIMESTAMPTZ | NULLABLE | Approval timestamp |
| `created_by` | VARCHAR(64) | NOT NULL | Author user ID |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Creation timestamp |
| `organization_id` | VARCHAR(64) | NOT NULL, INDEXED | Tenant isolation |
| `metadata` | JSONB | NOT NULL DEFAULT '{}' | Extensible attributes |

#### 2.2 Table: `audit_repeat_finding_candidates`
Stores detected repeat finding candidates and their human review dispositions.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `candidate_id` | VARCHAR(64) | PRIMARY KEY | Unique identifier (`grfc-uuid`) |
| `current_finding_id` | VARCHAR(64) | NOT NULL, INDEXED | Target finding ID |
| `current_finding_statement` | TEXT | NOT NULL | Target statement |
| `current_audit_id` | VARCHAR(64) | NOT NULL, INDEXED | Parent audit ID |
| `category` | VARCHAR(64) | NOT NULL, INDEXED | Finding category |
| `severity` | VARCHAR(32) | NOT NULL, INDEXED | Severity tier |
| `historical_finding_ids` | JSONB | NOT NULL DEFAULT '[]' | Matched historical finding IDs |
| `matching_dimensions` | JSONB | NOT NULL DEFAULT '[]' | Matched dimensions list |
| `matching_rationale` | TEXT | NOT NULL | Explanation of match |
| `confidence` | VARCHAR(32) | NOT NULL, INDEXED | Confidence enum |
| `confidence_score` | NUMERIC(4,2) | NOT NULL DEFAULT 0.50 | Quantitative matching score |
| `detection_timestamp` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Detection timestamp |
| `detection_method` | VARCHAR(64) | NOT NULL | Detection method used |
| `reporting_period` | VARCHAR(64) | NOT NULL | Reporting period |
| `review_status` | VARCHAR(32) | NOT NULL, INDEXED | Review status enum |
| `reviewed_by` | VARCHAR(64) | NULLABLE | Reviewing user ID |
| `reviewed_at` | TIMESTAMPTZ | NULLABLE | Review timestamp |
| `review_rationale` | TEXT | NULLABLE | Human review rationale |
| `organization_id` | VARCHAR(64) | NOT NULL, INDEXED | Tenant isolation |
| `facility_id` | VARCHAR(64) | NULLABLE, INDEXED | Facility isolation |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Creation timestamp |
| `metadata` | JSONB | NOT NULL DEFAULT '{}' | Extensible attributes |

#### 2.3 Table: `audit_patterns`
Stores identified cross-audit patterns.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `pattern_id` | VARCHAR(64) | PRIMARY KEY | Unique identifier (`gpat-uuid`) |
| `pattern_name` | VARCHAR(255) | NOT NULL | Pattern title |
| `pattern_category` | VARCHAR(64) | NOT NULL, INDEXED | Pattern category enum |
| `related_audit_ids` | JSONB | NOT NULL DEFAULT '[]' | Associated audit IDs |
| `related_finding_ids` | JSONB | NOT NULL DEFAULT '[]' | Associated finding IDs |
| `affected_controls` | JSONB | NOT NULL DEFAULT '[]' | Impacted controls |
| `affected_processes` | JSONB | NOT NULL DEFAULT '[]' | Impacted processes |
| `affected_facilities` | JSONB | NOT NULL DEFAULT '[]' | Impacted facilities |
| `matching_criteria` | JSONB | NOT NULL DEFAULT '{}' | Matching criteria metadata |
| `time_period` | VARCHAR(64) | NOT NULL | Reporting period |
| `potential_impact` | TEXT | NOT NULL | Potential clinical safety impact |
| `analytical_explanation` | TEXT | NOT NULL | Analytical findings explanation |
| `review_status` | VARCHAR(32) | NOT NULL, INDEXED | Review status enum |
| `reviewed_by` | VARCHAR(64) | NULLABLE | Reviewing user ID |
| `reviewed_at` | TIMESTAMPTZ | NULLABLE | Review timestamp |
| `review_rationale` | TEXT | NULLABLE | Review notes |
| `referral_refs` | JSONB | NOT NULL DEFAULT '[]' | Governance referral records |
| `organization_id` | VARCHAR(64) | NOT NULL, INDEXED | Tenant isolation |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Creation timestamp |
| `metadata` | JSONB | NOT NULL DEFAULT '{}' | Extensible attributes |

#### 2.4 Table: `systemic_issue_candidates`
Stores systemic vulnerability candidates and calculated priority scores.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `candidate_id` | VARCHAR(64) | PRIMARY KEY | Unique identifier (`gsys-uuid`) |
| `title` | VARCHAR(255) | NOT NULL | Candidate title |
| `description` | TEXT | NOT NULL | Analytical description |
| `status` | VARCHAR(32) | NOT NULL, INDEXED | Lifecycle status enum |
| `priority_score` | NUMERIC(5,2) | NOT NULL DEFAULT 0.0, INDEXED | Calculated priority score |
| `score_factors` | JSONB | NOT NULL DEFAULT '{}' | Score factor breakdown |
| `supporting_finding_ids` | JSONB | NOT NULL DEFAULT '[]' | Supporting findings |
| `supporting_audit_ids` | JSONB | NOT NULL DEFAULT '[]' | Supporting audits |
| `supporting_pattern_ids` | JSONB | NOT NULL DEFAULT '[]' | Supporting patterns |
| `matching_rationale` | TEXT | NOT NULL | Matching explanation |
| `scoring_methodology` | VARCHAR(64) | NOT NULL | Scoring formula used |
| `configuration_version` | VARCHAR(32) | NOT NULL | Configuration version |
| `affected_controls` | JSONB | NOT NULL DEFAULT '[]' | Affected controls |
| `affected_processes` | JSONB | NOT NULL DEFAULT '[]' | Affected processes |
| `affected_facilities` | JSONB | NOT NULL DEFAULT '[]' | Affected facilities |
| `data_quality_status` | VARCHAR(32) | NOT NULL | Quality classification |
| `known_limitations` | JSONB | NOT NULL DEFAULT '[]' | Analytical limitations |
| `reviewed_by` | VARCHAR(64) | NULLABLE | Reviewer user ID |
| `reviewed_at` | TIMESTAMPTZ | NULLABLE | Review timestamp |
| `review_rationale` | TEXT | NULLABLE | Review rationale |
| `referral_refs` | JSONB | NOT NULL DEFAULT '[]' | Outbound referrals |
| `organization_id` | VARCHAR(64) | NOT NULL, INDEXED | Tenant isolation |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Creation timestamp |
| `metadata` | JSONB | NOT NULL DEFAULT '{}' | Extensible attributes |

#### 2.5 Table: `capa_recurrences`
Stores recurrence analysis linking findings to Phase 54 and Phase 55 records.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `recurrence_id` | VARCHAR(64) | PRIMARY KEY | Unique identifier (`gcpr-uuid`) |
| `initial_finding_id` | VARCHAR(64) | NOT NULL, INDEXED | Initial finding reference |
| `corrective_action_ref` | VARCHAR(64) | NOT NULL, INDEXED | Linked Phase 54 action ID |
| `phase55_eval_ref` | VARCHAR(64) | NULLABLE, INDEXED | Linked Phase 55 evaluation ID |
| `action_title` | VARCHAR(255) | NULLABLE | Action summary |
| `recurrence_status` | VARCHAR(64) | NOT NULL, INDEXED | Recurrence classification enum |
| `action_implementation_date` | TIMESTAMPTZ | NULLABLE | Implementation timestamp |
| `effectiveness_outcome` | VARCHAR(64) | NULLABLE | Phase 55 effectiveness result |
| `subsequent_related_finding_ids` | JSONB | NOT NULL DEFAULT '[]' | Subsequent findings |
| `temporal_context` | TEXT | NOT NULL | Timeframe context |
| `analytical_notes` | TEXT | NOT NULL | Analytical notes |
| `organization_id` | VARCHAR(64) | NOT NULL, INDEXED | Tenant isolation |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Creation timestamp |
| `metadata` | JSONB | NOT NULL DEFAULT '{}' | Extensible attributes |

#### 2.6 Table: `audit_management_reports`
Stores reproducible management review preparation reports.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `report_id` | VARCHAR(64) | PRIMARY KEY | Unique identifier (`gmgt-uuid`) |
| `title` | VARCHAR(255) | NOT NULL | Report title |
| `executive_summary` | TEXT | NOT NULL | High-level executive summary |
| `reporting_period_start` | TIMESTAMPTZ | NULLABLE | Period start |
| `reporting_period_end` | TIMESTAMPTZ | NULLABLE | Period end |
| `audit_coverage_summary` | JSONB | NOT NULL DEFAULT '{}' | Audit coverage stats |
| `findings_summary` | JSONB | NOT NULL DEFAULT '{}' | Findings distribution |
| `repeat_findings_summary` | JSONB | NOT NULL DEFAULT '{}' | Repeat finding stats |
| `systemic_issues_summary` | JSONB | NOT NULL DEFAULT '{}' | Systemic issues stats |
| `capa_recurrence_summary` | JSONB | NOT NULL DEFAULT '{}' | CAPA recurrence stats |
| `governance_trends` | JSONB | NOT NULL DEFAULT '{}' | Time-series trend data |
| `recommended_review_areas` | JSONB | NOT NULL DEFAULT '[]' | Recommended focus areas |
| `calculation_methodology` | VARCHAR(64) | NOT NULL | Calculation methodology |
| `configuration_version` | VARCHAR(32) | NOT NULL | Configuration version used |
| `inclusion_exclusion_rules` | JSONB | NOT NULL DEFAULT '[]' | Rules applied |
| `data_quality_status` | VARCHAR(32) | NOT NULL | Completeness status |
| `known_data_limitations` | JSONB | NOT NULL DEFAULT '[]' | Disclosed limitations |
| `is_approved` | BOOLEAN | NOT NULL DEFAULT FALSE, INDEXED | Approval status |
| `approved_by` | VARCHAR(64) | NULLABLE | Approver user ID |
| `approved_at` | TIMESTAMPTZ | NULLABLE | Approval timestamp |
| `approval_comments` | TEXT | NULLABLE | Approver comments |
| `created_by` | VARCHAR(64) | NOT NULL | Author user ID |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Creation timestamp |
| `organization_id` | VARCHAR(64) | NOT NULL, INDEXED | Tenant isolation |
| `facility_id` | VARCHAR(64) | NULLABLE, INDEXED | Facility isolation |
| `metadata` | JSONB | NOT NULL DEFAULT '{}' | Extensible attributes |

---

### 3. Recommended PostgreSQL Indexes

```sql
-- Indexes for Analytics Configurations
CREATE INDEX idx_audit_cfg_org_active ON audit_analytics_configurations(organization_id, is_active, is_deprecated);
CREATE INDEX idx_audit_cfg_ver ON audit_analytics_configurations(version);

-- Indexes for Repeat Finding Candidates
CREATE INDEX idx_audit_rep_org_fac ON audit_repeat_finding_candidates(organization_id, facility_id);
CREATE INDEX idx_audit_rep_current ON audit_repeat_finding_candidates(current_finding_id);
CREATE INDEX idx_audit_rep_status ON audit_repeat_finding_candidates(review_status);
CREATE INDEX idx_audit_rep_confidence ON audit_repeat_finding_candidates(confidence);

-- Indexes for Patterns
CREATE INDEX idx_audit_pat_org_cat ON audit_patterns(organization_id, pattern_category);
CREATE INDEX idx_audit_pat_status ON audit_patterns(review_status);

-- Indexes for Systemic Candidates
CREATE INDEX idx_audit_sys_org_status ON systemic_issue_candidates(organization_id, status);
CREATE INDEX idx_audit_sys_score ON systemic_issue_candidates(priority_score DESC);

-- Indexes for CAPA Recurrences
CREATE INDEX idx_audit_capa_org ON capa_recurrences(organization_id, recurrence_status);
CREATE INDEX idx_audit_capa_initial ON capa_recurrences(initial_finding_id);
CREATE INDEX idx_audit_capa_action ON capa_recurrences(corrective_action_ref);

-- Indexes for Management Reports
CREATE INDEX idx_audit_mgmt_org_fac ON audit_management_reports(organization_id, facility_id);
CREATE INDEX idx_audit_mgmt_approved ON audit_management_reports(is_approved);
```
