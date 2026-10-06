# Database Team Dependencies — Phase 49: Clinical Safety Incident Management

## Document Type
Database Schema Specification & Handoff Contract

## Database Ownership
The database teammate owns all PostgreSQL table schemas, indexes, foreign keys, migrations, and concurrency controls.
The backend teammate strictly consumes the agreed schema via repository abstractions and does not invent competing databases or tables.

---

## 1. Required Tables

### 1.1 `clinical_safety_signals`
Stores incoming safety signals emitted from runtime safety gates, external providers, decision traces, and workflows.

| Column | Type | Constraints / Description |
|---|---|---|
| `id` | VARCHAR(64) | PRIMARY KEY (`sig-...`) |
| `source` | VARCHAR(32) | NOT NULL (`SYSTEM`, `CLINICIAN`, `PATIENT`, `MONITORING`, `AI_SAFETY_GATE`, `EXTERNAL_PROVIDER`, etc.) |
| `incident_type` | VARCHAR(32) | NOT NULL (`CLINICAL_SAFETY`, `MEDICATION_SAFETY`, `AI_SAFETY`, etc.) |
| `summary` | TEXT | NOT NULL (fact-based summary) |
| `description` | TEXT | NULLABLE |
| `severity_candidate` | VARCHAR(16) | NOT NULL DEFAULT `'MEDIUM'` (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`) |
| `impact_candidate` | VARCHAR(32) | NOT NULL DEFAULT `'UNKNOWN'` (`NO_KNOWN_IMPACT`, `POTENTIAL_IMPACT`, `NEAR_MISS`, `CONFIRMED_IMPACT`, `UNKNOWN`) |
| `decision_id` | VARCHAR(64) | NULLABLE (Foreign key reference to `decision_traces.id`) |
| `safety_check_id` | VARCHAR(64) | NULLABLE |
| `workflow_id` | VARCHAR(64) | NULLABLE |
| `task_id` | VARCHAR(64) | NULLABLE |
| `alert_id` | VARCHAR(64) | NULLABLE |
| `patient_id` | VARCHAR(64) | NULLABLE (Indexed) |
| `resource_type` | VARCHAR(64) | NULLABLE |
| `resource_id` | VARCHAR(64) | NULLABLE |
| `resource_version` | INT | NULLABLE |
| `correlation_id` | VARCHAR(255) | NULLABLE (Indexed for window deduplication) |
| `metadata` | JSONB | NOT NULL DEFAULT `'{}'` |
| `detected_at` | TIMESTAMPTZ | NOT NULL DEFAULT CURRENT_TIMESTAMP |

**Recommended Indexes**:
- `CREATE INDEX idx_safety_signals_correlation ON clinical_safety_signals (correlation_id, detected_at);`
- `CREATE INDEX idx_safety_signals_patient ON clinical_safety_signals (patient_id);`

---

### 1.2 `clinical_safety_incidents`
Stores authoritative safety incident records tracking lifecycle, triage, containment, and closure.

| Column | Type | Constraints / Description |
|---|---|---|
| `id` | VARCHAR(64) | PRIMARY KEY (`inc-...`) |
| `title` | VARCHAR(255) | NOT NULL |
| `description` | TEXT | NOT NULL |
| `incident_type` | VARCHAR(32) | NOT NULL |
| `status` | VARCHAR(32) | NOT NULL DEFAULT `'DETECTED'` (`DETECTED`, `TRIAGED`, `OPEN`, `INVESTIGATING`, `CONTAINMENT_REQUIRED`, `CONTAINED`, `RESOLVED`, `CLOSED`, `REOPENED`, `DUPLICATE`) |
| `severity` | VARCHAR(16) | NOT NULL DEFAULT `'MEDIUM'` |
| `impact_status` | VARCHAR(32) | NOT NULL DEFAULT `'UNKNOWN'` |
| `source` | VARCHAR(32) | NOT NULL |
| `patient_id` | VARCHAR(64) | NULLABLE (Indexed) |
| `resource_type` | VARCHAR(64) | NULLABLE |
| `resource_id` | VARCHAR(64) | NULLABLE |
| `resource_version` | INT | NULLABLE |
| `decision_id` | VARCHAR(64) | NULLABLE |
| `safety_check_id` | VARCHAR(64) | NULLABLE |
| `workflow_id` | VARCHAR(64) | NULLABLE |
| `task_id` | VARCHAR(64) | NULLABLE |
| `alert_id` | VARCHAR(64) | NULLABLE |
| `provider_request_id` | VARCHAR(64) | NULLABLE |
| `signal_ids` | TEXT[] | NOT NULL DEFAULT ARRAY[]::TEXT[] |
| `assigned_investigator_id` | VARCHAR(64) | NULLABLE |
| `assigned_investigator_role` | VARCHAR(64) | NULLABLE |
| `containment_status` | VARCHAR(32) | NULLABLE |
| `containment_action` | TEXT | NULLABLE |
| `root_cause_category` | VARCHAR(64) | NULLABLE |
| `root_cause_confirmed` | BOOLEAN | NOT NULL DEFAULT FALSE |
| `duplicate_of_id` | VARCHAR(64) | NULLABLE (Foreign key self-reference) |
| `occurred_at` | TIMESTAMPTZ | NOT NULL |
| `detected_at` | TIMESTAMPTZ | NOT NULL |
| `recorded_at` | TIMESTAMPTZ | NOT NULL |
| `contained_at` | TIMESTAMPTZ | NULLABLE |
| `resolved_at` | TIMESTAMPTZ | NULLABLE |
| `closed_at` | TIMESTAMPTZ | NULLABLE |
| `reopened_at` | TIMESTAMPTZ | NULLABLE |
| `closure_reason` | TEXT | NULLABLE |
| `resolution_summary` | TEXT | NULLABLE |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT CURRENT_TIMESTAMP |
| `updated_at` | TIMESTAMPTZ | NOT NULL DEFAULT CURRENT_TIMESTAMP |

**Recommended Indexes**:
- `CREATE INDEX idx_clinical_incidents_patient ON clinical_safety_incidents (patient_id);`
- `CREATE INDEX idx_clinical_incidents_status ON clinical_safety_incidents (status);`
- `CREATE INDEX idx_clinical_incidents_decision ON clinical_safety_incidents (decision_id);`

---

### 1.3 `clinical_incident_evidence_references`
Stores pointers to evidence without duplicating raw PHI.

| Column | Type | Constraints / Description |
|---|---|---|
| `id` | VARCHAR(64) | PRIMARY KEY (`ev-...`) |
| `incident_id` | VARCHAR(64) | NOT NULL REFERENCES `clinical_safety_incidents(id)` |
| `evidence_type` | VARCHAR(32) | NOT NULL (`DECISION_TRACE`, `AUDIT_EVENT`, `VERSION_HISTORY`, `PROVIDER_RESPONSE`, etc.) |
| `reference_id` | VARCHAR(128) | NOT NULL |
| `summary` | TEXT | NOT NULL |
| `source_system` | VARCHAR(64) | NOT NULL |
| `snapshot_hash` | VARCHAR(64) | NULLABLE (SHA-256 integrity hash) |
| `metadata` | JSONB | NOT NULL DEFAULT `'{}'` (No PHI permitted) |
| `recorded_at` | TIMESTAMPTZ | NOT NULL DEFAULT CURRENT_TIMESTAMP |
| `recorded_by_id` | VARCHAR(64) | NULLABLE |

**Recommended Indexes**:
- `CREATE INDEX idx_evidence_incident ON clinical_incident_evidence_references (incident_id);`

---

### 1.4 `clinical_incident_hypotheses`
Tracks root-cause hypotheses and investigation findings.

| Column | Type | Constraints / Description |
|---|---|---|
| `id` | VARCHAR(64) | PRIMARY KEY (`hyp-...`) |
| `incident_id` | VARCHAR(64) | NOT NULL REFERENCES `clinical_safety_incidents(id)` |
| `category` | VARCHAR(32) | NOT NULL (`SOFTWARE_DEFECT`, `PROVIDER_FAILURE`, `CONFIGURATION_ERROR`, etc.) |
| `title` | VARCHAR(255) | NOT NULL |
| `statement` | TEXT | NOT NULL |
| `status` | VARCHAR(32) | NOT NULL DEFAULT `'PROPOSED'` (`PROPOSED`, `SUPPORTED`, `REJECTED`, `INCONCLUSIVE`, `CONFIRMED`) |
| `proposed_by_id` | VARCHAR(64) | NOT NULL |
| `proposed_by_role` | VARCHAR(64) | NOT NULL |
| `supporting_evidence_ids` | TEXT[] | NOT NULL DEFAULT ARRAY[]::TEXT[] |
| `contradicting_evidence_ids` | TEXT[] | NOT NULL DEFAULT ARRAY[]::TEXT[] |
| `investigator_notes` | TEXT | NULLABLE |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT CURRENT_TIMESTAMP |
| `updated_at` | TIMESTAMPTZ | NOT NULL DEFAULT CURRENT_TIMESTAMP |

**Recommended Indexes**:
- `CREATE INDEX idx_hypotheses_incident ON clinical_incident_hypotheses (incident_id);`

---

### 1.5 `clinical_incident_corrective_actions`
Tracks remedial and preventive action plans.

| Column | Type | Constraints / Description |
|---|---|---|
| `id` | VARCHAR(64) | PRIMARY KEY (`act-...`) |
| `incident_id` | VARCHAR(64) | NOT NULL REFERENCES `clinical_safety_incidents(id)` |
| `action_type` | VARCHAR(32) | NOT NULL (`CODE_FIX`, `PROVIDER_CORRECTION`, `CLINICAL_RECORD_CORRECTION`, etc.) |
| `is_preventive` | BOOLEAN | NOT NULL DEFAULT FALSE |
| `title` | VARCHAR(255) | NOT NULL |
| `description` | TEXT | NOT NULL |
| `status` | VARCHAR(32) | NOT NULL DEFAULT `'CREATED'` (`CREATED`, `ASSIGNED`, `IN_PROGRESS`, `COMPLETED`, `VERIFIED`, `CLOSED`, `CANCELLED`) |
| `assigned_to_id` | VARCHAR(64) | NULLABLE |
| `assigned_to_role` | VARCHAR(64) | NULLABLE |
| `linked_task_id` | VARCHAR(64) | NULLABLE (Phase 36 task ID) |
| `linked_version_id` | VARCHAR(64) | NULLABLE (Phase 46 clinical record version reference) |
| `resolution_details` | TEXT | NULLABLE |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT CURRENT_TIMESTAMP |
| `completed_at` | TIMESTAMPTZ | NULLABLE |
| `verified_at` | TIMESTAMPTZ | NULLABLE |
| `verified_by_id` | VARCHAR(64) | NULLABLE |

**Recommended Indexes**:
- `CREATE INDEX idx_actions_incident ON clinical_incident_corrective_actions (incident_id);`
