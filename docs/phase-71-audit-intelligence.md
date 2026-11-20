# Phase 71: Clinical Safety Governance Audit Finding Analytics, Repeat-Issue Detection & Systemic Risk Insight

## Document Type
Technical Architecture, API Specification & Clinical Safety Governance Audit Intelligence Documentation

## Phase Overview
Phase 71 implements the Clinical Safety Governance Audit Intelligence layer for HealthSetu.

Building upon the independent audit planning, execution, and findings foundation established in Phase 70, Phase 71 transforms authorized audit records into structured, traceable governance intelligence. It identifies recurring weaknesses, cross-audit patterns, systemic vulnerability candidates, and corrective action recurrences across HealthSetu's clinical safety and governance workflows.

---

## 1. Non-Negotiable Audit Intelligence Invariants

1. **Analytical decision support, not clinical risk declaration**: Phase 71 is an analytical and decision-support layer. It must not independently declare that a clinical safety risk exists, that a control is ineffective, or that an organization is non-compliant.
2. **Phase 55 retains effectiveness authority**: The system does not declare a corrective action failed merely because a similar finding appeared later. Phase 55 effectiveness reviews remain authoritative.
3. **No automatic merging or historical mutation**: Detecting a repeat finding or cross-audit pattern never mutates historical audit records or merges findings. Historical provenance is immutable.
4. **Reduction in findings does not prove improved safety**: A decrease in findings may result from reduced audit scope, incomplete coverage, or shifts in audit focus. Analytical outputs explicitly disclose audit volume context.
5. **Deterministic priority scores, not clinical risk scores**: Analytical priority scores are derived using approved, versioned weighting rules for governance triage; they must never be presented as authoritative clinical risk assessments.
6. **Mandatory human review for insight disposition**: Every repeat candidate, cross-audit pattern, and systemic issue candidate must undergo authorized human governance review before confirmation, escalation, or risk review referral.
7. **Cross-phase governance referrals retain end-to-end traceability**: Referrals to Phase 54 (CAPA), Phase 55 (Effectiveness), Phase 63 (Risk Review), Phase 67 (Escalation), Phase 69 (Compliance), Phase 70 (Follow-up Audit), and Phase 49 (Incident) preserve source insight, destination workflow, requesting actor, and rationale.
8. **Transparent data quality disclosure**: Incomplete, stale, or contradictory source data is explicitly disclosed using standard data quality statuses (`COMPLETE`, `PARTIALLY_COMPLETE`, `INCOMPLETE`, `STALE`), never silently substituted or zeroed out.
9. **Strict tenant isolation and patient privacy**: All analytics enforce tenant isolation via `organization_id` and `facility_id`. Patient identifiers are never exposed in governance analytics.
10. **Reproducible management review reporting**: Management reports must be strictly reproducible from the underlying source data and the configuration version active at generation time.
11. **Configurable, versioned analytical rules**: Repeat matching thresholds, severity weights, and scoring factors are versioned, approved, and auditable. Deprecated configurations remain traceable.
12. **Status-filtered aggregation accuracy**: Draft and withdrawn findings are excluded from confirmed aggregations to prevent distorted statistics or double counting.

---

## 2. Repeat-Finding Detection Methodology

### Matching Dimensions
- `CATEGORY`: Exact match on finding category (e.g. `CONTROL_GAP`, `PROCESS_DEVIATION`).
- `CONTROL`: Exact match on `criterion_id` or underlying compliance control mapping.
- `CORRECTIVE_ACTION_REF`: Match on linked Phase 54 corrective action reference.
- `SEMANTIC_SIMILARITY`: Keyword and token overlap across finding statements and observed conditions.
- `PROCESS`: Match on governance process domain.

### Confidence Tiers
- `CONFIRMED_REPEAT`: Verified by authorized governance reviewer.
- `LIKELY_REPEAT`: High composite score ($\ge 0.80$) across multiple matching dimensions.
- `POSSIBLE_REPEAT`: Moderate composite score ($\ge 0.60$) requiring human inspection.
- `REQUIRES_REVIEW`: Borderline match requiring reviewer attention.
- `NOT_A_REPEAT`: Explicitly rejected by reviewer with documented rationale.

---

## 3. Cross-Audit Pattern Categories

- `CONTROL_WEAKNESS_CONCENTRATION`: Same safety control or criterion fails across 2 or more distinct audits.
- `CROSS_FACILITY_DEVIATION`: Similar findings observed across multiple physical facilities or operating units.
- `RECURRING_DOCUMENTATION_GAP`: Recurrent omissions in mandatory risk documentation.
- `EVIDENCE_QUALITY_DEFICIT`: Repeated instances of insufficient, contradictory, or unverifiable evidence.
- `AUTHORIZATION_FAILURE_PATTERN`: Repeated departures from required delegation-of-authority workflows.
- `POST_CAPA_RECURRENCE`: Findings recurring after Phase 54 action implementation.
- `TRACEABILITY_BREAKDOWN`: Decisions or handoffs lacking end-to-end auditability.

---

## 4. Systemic Issue Candidate Scoring

Priority score calculation uses approved, versioned configuration weights:

$$\text{Priority Score} = w_{\text{sev}} \cdot S_{\text{max}} + w_{\text{rec}} \cdot F_{\text{rec}} + w_{\text{fac}} \cdot F_{\text{fac}} + w_{\text{dur}} \cdot F_{\text{dur}}$$

- $S_{\text{max}}$: Severity weight (`CRITICAL`: 10, `URGENT`: 7, `HIGH`: 5, `ELEVATED`: 3, `ROUTINE`: 1).
- $F_{\text{rec}}$: Recurrence factor ($\min(N_{\text{findings}}, 5) \times 1.5$).
- $F_{\text{fac}}$: Facility spread factor ($\min(N_{\text{facilities}}, 4) \times 1.25$).
- $F_{\text{dur}}$: Duration factor ($\min(\text{open days}, 180) / 30$).

---

## 5. Corrective Action Recurrence Taxonomy

- `NO_RECURRENCE_OBSERVED`: No related findings observed following CAPA implementation.
- `RECURRENCE_CONFIRMED`: Subsequent related findings confirmed following Phase 55 effectiveness review link.
- `RECURRENCE_SUSPECTED`: Subsequent related findings identified while initial finding was closed.
- `IMPLEMENTED_UNVERIFIED`: Action linked but initial finding remains open with related observations.
- `NOT_IMPLEMENTED`: Corrective action planned or pending implementation.

---

## 6. REST API Specification

Base Path: `/api/v1/governance-audit-intelligence`

### 6.1 Historical Findings Analytics
- `GET /analytics/overview`: Multi-dimensional summary across reporting periods.
- `GET /analytics/findings`: Filtered findings summary.
- `GET /analytics/findings/trends`: Time-series trends (new findings, repeats, backlog, CAPA recurrence).
- `GET /analytics/findings/by-severity`: Findings grouped by severity tier.
- `GET /analytics/findings/by-category`: Findings grouped by category.
- `GET /analytics/findings/by-control`: Findings grouped by criterion/control.
- `GET /analytics/findings/by-organization`: Findings grouped by facility.
- `GET /analytics/audit-coverage`: Audit coverage summary by status and category.

### 6.2 Repeat-Finding Detection
- `POST /repeat-findings/detect`: Trigger deterministic repeat finding scan.
- `GET /repeat-findings`: List repeat finding candidates.
- `GET /repeat-findings/{candidate_id}`: Retrieve candidate details.
- `POST /repeat-findings/{candidate_id}/review`: Record human review disposition.
- `POST /repeat-findings/{candidate_id}/confirm`: Confirm repeat candidate.
- `POST /repeat-findings/{candidate_id}/reject`: Reject repeat candidate.

### 6.3 Cross-Audit Patterns
- `POST /patterns/detect`: Trigger pattern detection across audits.
- `GET /patterns`: List identified patterns.
- `GET /patterns/{pattern_id}`: Retrieve pattern details.
- `POST /patterns/{pattern_id}/review`: Review pattern.
- `POST /patterns/{pattern_id}/refer`: Refer pattern to Phase 54, 63, 67, 69, or 70.

### 6.4 Systemic Issue Candidates
- `POST /systemic-issue-candidates/detect`: Trigger candidate generation and priority scoring.
- `GET /systemic-issue-candidates`: List systemic issue candidates.
- `GET /systemic-issue-candidates/{candidate_id}`: Retrieve candidate details.
- `POST /systemic-issue-candidates/{candidate_id}/review`: Record review decision.
- `POST /systemic-issue-candidates/{candidate_id}/confirm`: Confirm candidate.
- `POST /systemic-issue-candidates/{candidate_id}/reject`: Reject candidate.
- `POST /systemic-issue-candidates/{candidate_id}/refer`: Refer systemic issue to authoritative workflows.

### 6.5 Corrective Action Recurrence
- `GET /corrective-actions/recurrence`: List CAPA recurrence records.
- `GET /corrective-actions/recurrence/{finding_id}`: Retrieve recurrence status for specific finding.

### 6.6 Management Review Reporting
- `POST /management-reports/generate`: Generate reproducible review preparation report (`201 Created`).
- `GET /management-reports`: List management reports within tenant scope.
- `GET /management-reports/{report_id}`: Retrieve management report.
- `POST /management-reports/{report_id}/approve`: Formally approve management report.
- `GET /management-reports/{report_id}/export`: Export structured, audited report package.

### 6.7 Analytical Configuration
- `POST /configurations`: Create new analytical configuration version (`201 Created`).
- `GET /configurations`: List configuration versions.
- `GET /configurations/{configuration_id}`: Retrieve configuration details.
- `POST /configurations/{configuration_id}/approve`: Approve and activate configuration.
- `POST /configurations/{configuration_id}/deprecate`: Deprecate configuration version.
