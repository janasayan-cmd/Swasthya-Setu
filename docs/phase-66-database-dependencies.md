# Phase 66: Database Dependencies & Persistence Contracts

## Document Type
Database Schema Coordination & Persistence Requirements

## Ownership Boundary Notice
The database teammate owns database schemas, ORM models, migrations, constraints, indexes, and persistence-layer changes.
The backend implementation interfaces through repository abstractions and does not duplicate or independently recreate database structures.

---

## 1. Logical Persistence Requirements

Phase 66 requires persistent tracking of post-closure verification executions, findings, reviews, monitoring policies, and lifecycle reconciliations.

### Table 1: `safety_post_closure_verifications`
- `verification_id`: `VARCHAR(64) PRIMARY KEY`
- `completion_id`: `VARCHAR(64) NOT NULL REFERENCES safety_workflow_completions(completion_id)`
- `organization_id`: `VARCHAR(64) NOT NULL`
- `facility_id`: `VARCHAR(64) NOT NULL`
- `state`: `VARCHAR(32) NOT NULL` (e.g. `PENDING`, `RUNNING`, `VERIFIED`, `REOPEN_RECOMMENDED`, `CONFLICTED`)
- `historical_completion_state`: `VARCHAR(32) NOT NULL`
- `current_coordination_state`: `VARCHAR(32) NOT NULL`
- `reassessment_required`: `BOOLEAN NOT NULL DEFAULT FALSE`
- `reopen_recommended`: `BOOLEAN NOT NULL DEFAULT FALSE`
- `reopen_authorized`: `BOOLEAN NOT NULL DEFAULT FALSE`
- `reopened`: `BOOLEAN NOT NULL DEFAULT FALSE`
- `policy_version`: `VARCHAR(32) NOT NULL`
- `findings_count`: `INTEGER NOT NULL DEFAULT 0`
- `material_findings_count`: `INTEGER NOT NULL DEFAULT 0`
- `limitations`: `JSONB DEFAULT '[]'`
- `rationale`: `TEXT`
- `evaluated_checks`: `JSONB DEFAULT '{}'`
- `evidence_references`: `JSONB DEFAULT '[]'`
- `retry_count`: `INTEGER NOT NULL DEFAULT 0`
- `max_retries`: `INTEGER NOT NULL DEFAULT 3`
- `idempotency_key`: `VARCHAR(128) UNIQUE`
- `correlation_id`: `VARCHAR(64) NOT NULL`
- `triggered_by`: `VARCHAR(64) NOT NULL`
- `triggered_by_role`: `VARCHAR(32) NOT NULL`
- `created_at`: `TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()`
- `updated_at`: `TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()`
- `completed_at`: `TIMESTAMP WITH TIME ZONE`
- `history`: `JSONB DEFAULT '[]'`
- `version`: `INTEGER NOT NULL DEFAULT 1`

**Recommended Indexes**:
- `ix_post_closure_verif_completion_id` ON `safety_post_closure_verifications(completion_id)`
- `ix_post_closure_verif_org_state` ON `safety_post_closure_verifications(organization_id, state)`
- `ix_post_closure_verif_idempotency` ON `safety_post_closure_verifications(idempotency_key)` WHERE `idempotency_key IS NOT NULL`

---

### Table 2: `safety_integrity_findings`
- `finding_id`: `VARCHAR(64) PRIMARY KEY`
- `completion_id`: `VARCHAR(64) NOT NULL REFERENCES safety_workflow_completions(completion_id)`
- `verification_id`: `VARCHAR(64) NOT NULL REFERENCES safety_post_closure_verifications(verification_id)`
- `organization_id`: `VARCHAR(64) NOT NULL`
- `facility_id`: `VARCHAR(64) NOT NULL`
- `category`: `VARCHAR(48) NOT NULL` (e.g. `SOURCE_DISPOSITION_CHANGED`, `DESTINATION_WORKFLOW_REOPENED`)
- `severity`: `VARCHAR(16) NOT NULL` (e.g. `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, `INFORMATIONAL`)
- `source_system`: `VARCHAR(64) NOT NULL`
- `authoritative_record_ref`: `VARCHAR(128) NOT NULL`
- `expected_state`: `TEXT NOT NULL`
- `observed_state`: `TEXT NOT NULL`
- `relevant_version_refs`: `JSONB DEFAULT '{}'`
- `detected_at`: `TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()`
- `provenance`: `VARCHAR(64) NOT NULL`
- `is_material`: `BOOLEAN NOT NULL DEFAULT TRUE`
- `policy_reference`: `VARCHAR(32) NOT NULL`
- `recommended_next_action`: `VARCHAR(64) NOT NULL`
- `required_authorization`: `VARCHAR(64)`
- `lifecycle_state`: `VARCHAR(32) NOT NULL DEFAULT 'DETECTED'`
- `review_notes`: `TEXT`
- `reviewed_by`: `VARCHAR(64)`
- `reviewed_by_role`: `VARCHAR(32)`
- `reviewed_at`: `TIMESTAMP WITH TIME ZONE`
- `dismissal_rationale`: `TEXT`
- `resolution_evidence`: `TEXT`
- `resolved_by`: `VARCHAR(64)`
- `resolved_by_role`: `VARCHAR(32)`
- `resolved_at`: `TIMESTAMP WITH TIME ZONE`
- `resolution_notes`: `TEXT`
- `audit_reference`: `VARCHAR(64) NOT NULL`
- `metadata`: `JSONB DEFAULT '{}'`

**Recommended Indexes**:
- `ix_integrity_findings_completion_id` ON `safety_integrity_findings(completion_id)`
- `ix_integrity_findings_verification_id` ON `safety_integrity_findings(verification_id)`
- `ix_integrity_findings_org_state` ON `safety_integrity_findings(organization_id, lifecycle_state)`

---

### Table 3: `safety_post_closure_monitoring_status`
- `completion_id`: `VARCHAR(64) PRIMARY KEY REFERENCES safety_workflow_completions(completion_id)`
- `organization_id`: `VARCHAR(64) NOT NULL`
- `facility_id`: `VARCHAR(64) NOT NULL`
- `monitoring_active`: `BOOLEAN NOT NULL DEFAULT TRUE`
- `policy_config`: `JSONB NOT NULL DEFAULT '{}'`
- `last_verification_id`: `VARCHAR(64)`
- `last_verification_state`: `VARCHAR(32)`
- `last_verified_at`: `TIMESTAMP WITH TIME ZONE`
- `next_scheduled_verification_at`: `TIMESTAMP WITH TIME ZONE`
- `open_findings_count`: `INTEGER NOT NULL DEFAULT 0`
- `critical_findings_count`: `INTEGER NOT NULL DEFAULT 0`
- `reassessment_required`: `BOOLEAN NOT NULL DEFAULT FALSE`
- `reopen_recommended`: `BOOLEAN NOT NULL DEFAULT FALSE`
- `reopened`: `BOOLEAN NOT NULL DEFAULT FALSE`

---

### Table 4: `safety_completion_reassessments`
- `reassessment_id`: `VARCHAR(64) PRIMARY KEY`
- `completion_id`: `VARCHAR(64) NOT NULL REFERENCES safety_workflow_completions(completion_id)`
- `organization_id`: `VARCHAR(64) NOT NULL`
- `facility_id`: `VARCHAR(64) NOT NULL`
- `requested_by`: `VARCHAR(64) NOT NULL`
- `requested_by_role`: `VARCHAR(32) NOT NULL`
- `reason`: `TEXT NOT NULL`
- `finding_refs`: `JSONB DEFAULT '[]'`
- `status`: `VARCHAR(32) NOT NULL DEFAULT 'PENDING'`
- `created_at`: `TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()`
- `resolved_at`: `TIMESTAMP WITH TIME ZONE`

---

### Table 5: `safety_completion_reopening_coordinations`
- `coordination_id`: `VARCHAR(64) PRIMARY KEY`
- `completion_id`: `VARCHAR(64) NOT NULL REFERENCES safety_workflow_completions(completion_id)`
- `organization_id`: `VARCHAR(64) NOT NULL`
- `facility_id`: `VARCHAR(64) NOT NULL`
- `requested_by`: `VARCHAR(64) NOT NULL`
- `requested_by_role`: `VARCHAR(32) NOT NULL`
- `authorized_by`: `VARCHAR(64)`
- `authorized_by_role`: `VARCHAR(32)`
- `reopen_trigger`: `VARCHAR(48) NOT NULL`
- `reason`: `TEXT NOT NULL`
- `reopen_rationale`: `TEXT NOT NULL`
- `finding_refs`: `JSONB DEFAULT '[]'`
- `authorized`: `BOOLEAN NOT NULL DEFAULT FALSE`
- `executed`: `BOOLEAN NOT NULL DEFAULT FALSE`
- `phase65_reopen_record`: `JSONB`
- `created_at`: `TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()`
- `updated_at`: `TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()`
