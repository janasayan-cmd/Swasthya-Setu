# Phase 68: Clinical Safety Governance Decision Assurance, Authorization Integrity & Cross-Workflow Decision Traceability

## Document Type
Technical Architecture, API Specification & Clinical Safety Governance Decision Assurance Documentation

## Phase Overview
Phase 68 implements the governance decision assurance, authorization integrity, and cross-workflow decision traceability layer for HealthSetu's clinical safety platform.

Predecessor phases establish clinical safety signals, risk reviews, dispositions, handoffs, completion coordination, post-closure verification, and governance escalations (Phase 67). However, a recorded governance decision must also be demonstrably valid, appropriately authorized at the moment it was rendered, traceable to its supporting evidence, compliant with applicable policy at that point in time, and consistent across all dependent safety workflows.

Phase 68 establishes a controlled, non-destructive mechanism to verify the integrity and traceability of governance decisions across the HealthSetu safety ecosystem without overriding domain authority, duplicating database entities, or silently mutating historical records.

---

## 1. Non-Negotiable Governance Distinctions & Invariants

1. **A recorded decision is not automatically a valid decision**: Registering or storing an outcome does not prove its legal, clinical, or governance legitimacy.
2. **A valid authentication session does not prove historical authority**: Proving an actor's identity today or during the session does not prove they possessed authority to render that specific governance decision.
3. **A user's role does not automatically prove scope over a specific resource**: Being an `admin` or `doctor` in general does not confer authority over another tenant, facility, patient, or specialized governance committee.
4. **A successful authorization check at decision time does not guarantee persistent validity**: Subsequent revocations, policy deprecations, or discovery of fabricated credentials require decision reassessment.
5. **A complete audit record does not independently prove clinical appropriateness**: Provenance and audit logging confirm that an action took place; they do not substantiate medical correctness.
6. **A decision assurance result does not replace clinical review**: Phase 68 is a governance verification engine, not a diagnostic or treatment authority.
7. **A decision that fails assurance must not be silently deleted or rewritten**: Flawed decisions must remain visible with explicit integrity findings to preserve complete forensic traceability.
8. **A policy change must not silently rewrite the historical policy basis of an earlier decision**: Decisions are evaluated against the policy version in effect when the decision was executed.
9. **A recommendation to invalidate or review a decision does not itself revoke that decision**: Revocation or amendment is the sole prerogative of the authoritative source phase owner.
10. **Phase 68 must not independently change authoritative risk dispositions, incident states, completion states, or governance approvals**: The service strictly coordinates requests and surfaces findings.
11. **Unknown authorization evidence must not be treated as valid authorization**: When historical authorization records are missing or unrecorded, the status is deterministically classified as `HISTORICAL_UNVERIFIABLE`.
12. **Decision assurance is not equivalent to clinical safety assurance or effectiveness evaluation**: Phases 52 and 55 evaluate safety engineering and operational effectiveness; Phase 68 evaluates governance decision integrity.

---

## 2. Decision Assurance Lifecycle States

Phase 68 defines 21 explicit lifecycle states ensuring strict precedence and zero ambiguity:

- `REGISTERED`: Decision reference registered in the governance ledger; baseline validation complete.
- `PROVENANCE_PENDING`: Source phase linkage, immutable timestamps, and audit trail verification underway.
- `AUTHORIZATION_VERIFICATION_PENDING`: Evaluating decision-maker authority, scope, and separation of duties.
- `POLICY_VERIFICATION_PENDING`: Evaluating policy version, effective date, and applicability windows.
- `EVIDENCE_ASSURANCE_PENDING`: Evaluating status and provenance of supporting clinical evidence references.
- `CONSISTENCY_CHECK_PENDING`: Cross-referencing related decisions across dependent safety workflows.
- `EVALUATING`: Multi-dimensional evaluation execution actively in progress.
- `VERIFIED`: All mandatory checks satisfied; decision is fully traceable, authorized, compliant, and consistent.
- `VERIFIED_WITH_LIMITATIONS`: Verified, but non-critical minor findings or limitations were noted.
- `PROVENANCE_INCOMPLETE`: Missing source phase, source record ID, author attribution, or creation timestamp.
- `AUTHORIZATION_UNVERIFIABLE`: Historical authorization records or delegating credentials are missing or unrecorded.
- `AUTHORIZATION_INVALID`: Decision-maker was explicitly unauthorized, lacked facility scope, or possessed a revoked credential.
- `SEPARATION_OF_DUTIES_VIOLATION`: Self-approval detected (requester and approver share identity) or forbidden dual-role execution.
- `POLICY_MISMATCH`: Decision timestamp precedes policy effective date or violates applicable governance framework.
- `SOURCE_VERSION_MISMATCH`: Source record version does not match authoritative source system state.
- `EVIDENCE_INCOMPLETE`: Mandatory supporting evidence references are absent or unreachable.
- `EVIDENCE_CONFLICTED`: Supporting evidence has been retracted, superseded, or explicitly invalidated.
- `DECISION_CONFLICT`: Contradictory outcomes detected between related decisions without authoritative reconciliation.
- `REVIEW_REQUIRED`: Surfaced critical or high-severity findings requiring human governance specialist review.
- `OWNER_REVIEW_PENDING`: Formal request transmitted to authoritative workflow owner for review.
- `CORRECTION_REQUESTED`: Formal correction or revocation review request actively pending owner action.

---

## 3. Five Verification Dimensions

### 3.1 Decision Provenance Verification
Evaluates whether a registered decision can be traced to an authoritative origin:
- Verified presence of source phase, source record ID, and semantic source version.
- Immutable attribution of decision-maker identity, role, and automated service identity.
- Temporal coherence of decision timestamp (cannot be set in the future).
- Availability of underlying audit trail references.

### 3.2 Historical Authorization & Separation of Duties
Evaluates the legitimacy of the decision-maker at the moment the decision occurred:
- Verification of actor role against decision domain requirements.
- Scope containment: ensuring decision-maker had jurisdiction over the specific organization, facility, or patient.
- Prohibition of contemporary inference: historical authority is never assumed from current user permissions. Missing credentials evaluate to `HISTORICAL_UNVERIFIABLE`.
- Separation of duties: detects self-approvals (`requester_id == approver_id` or `decided_by_id == requester_id` where independent approval was required).

### 3.3 Policy Version and Applicability Verification
Evaluates whether the decision complied with the governance policy active at execution time:
- Effective date validation: decision cannot pre-date the policy effective date.
- Policy version freeze: policy references are immutable and not retroactively rewritten when newer policies deploy.
- Drift detection: flags decisions rendered under superseded or deprecated policy versions for advisory review without invalidating past legality.

### 3.4 Decision Evidence Assurance
Evaluates the integrity and trustworthiness of supporting documentation and clinical evidence:
- Standardized taxonomy:
  - `EVIDENCE_VALID`: Evidence verified, current, and accessible.
  - `EVIDENCE_MISSING`: Required evidence reference was omitted.
  - `EVIDENCE_UNAVAILABLE`: Evidence reference exists but storage/dependency is unreachable.
  - `EVIDENCE_STALE`: Evidence exceeded maximum allowed age for clinical decision-making.
  - `EVIDENCE_INVALIDATED`: Evidence was formally retracted or invalidated by upstream systems.
  - `EVIDENCE_CONFLICTED`: Conflicting evidence items referenced for the same decision.
  - `EVIDENCE_PROVENANCE_INCOMPLETE`: Supporting item lacks author or timestamp provenance.
  - `EVIDENCE_REVIEW_REQUIRED`: Unresolved evidence discrepancy requiring clinical audit.

### 3.5 Cross-Workflow Decision Consistency
Detects contradictions across interdependent safety workflows (Phases 49, 51, 52, 54, 55, 58, 63, 64, 65, 66, 67):
- Identifies conflicting outcomes: e.g., one workflow closes or accepts risk while another marks the same safety signal as active critical risk.
- Detects superseded dependencies: decisions relying on prior dispositions that were subsequently reopened or overturned.
- Governed neutrality: Phase 68 never automatically selects a "winner" between conflicting decisions; it generates integrity findings and records a `CrossWorkflowConsistencyCheckResult`.

---

## 4. Decision Correction & Revocation Coordination

When assurance identifies critical integrity defects, Phase 68 coordinates resolution with authoritative owners:
1. **Submission**: Authorized clinical admins or doctors submit a `CORRECTION` or `REVOCATION_REVIEW` request with detailed rationale and finding references.
2. **Owner Review**: The request is routed to the authoritative source phase owner (e.g., Phase 63 for risk dispositions, Phase 65 for completion reviews, Phase 67 for escalation decisions).
3. **Owner Response**: The authoritative owner accepts, rejects, supersedes, or amends the decision, providing an updated record version.
4. **Immutability**: Phase 68 never deletes or mutates the historical decision record; history is strictly appended.

---

## 5. REST API Endpoints

Base Path: `/api/v1/governance-decision-assurance`

### Specialized Queues
- `GET /queues/review-required`: Decisions requiring human review due to integrity findings.
- `GET /queues/authorization-unverifiable`: Decisions with missing historical authorization evidence.
- `GET /queues/policy-mismatch`: Decisions violating policy effective dates or frameworks.
- `GET /queues/decision-conflicts`: Decisions with cross-workflow contradictions.

### Aggregated Reporting
- `GET /reports/summary`: Tenant-scoped summary metrics and active finding counts.

### Assurance Findings
- `GET /findings`: List findings across decisions with category/severity filters.
- `GET /findings/{finding_id}`: Retrieve detailed finding record.
- `POST /findings/{finding_id}/review`: Record formal specialist review on a finding.
- `POST /findings/{finding_id}/resolve`: Resolve finding with documented rationale (Admin/Doctor).

### Governance Decision Register
- `POST /decisions`: Register an authoritative governance decision reference.
- `GET /decisions`: List registered decisions within tenant scope.
- `GET /decisions/{decision_id}`: Retrieve registered decision details.

### Decision Verification Execution & Inspection
- `POST /decisions/{decision_id}/verify`: Execute full multi-dimensional assurance run.
- `GET /decisions/{decision_id}/assurance`: Retrieve latest assurance evaluation run.
- `GET /decisions/{decision_id}/history`: Retrieve full history of assurance runs.
- `GET /decisions/{decision_id}/provenance`: Provenance verification details.
- `GET /decisions/{decision_id}/authorization`: Authorization & separation-of-duties details.
- `GET /decisions/{decision_id}/policy-compliance`: Policy applicability details.
- `GET /decisions/{decision_id}/evidence-integrity`: Evidence assurance status and details.
- `GET /decisions/{decision_id}/consistency-checks`: Cross-workflow consistency evaluation results.

### Correction & Revocation Requests
- `POST /decisions/{decision_id}/correction-requests`: Submit decision correction request.
- `POST /decisions/{decision_id}/revocation-review-requests`: Submit revocation review request.
- `GET /decisions/{decision_id}/correction-requests`: List correction requests for decision.
- `POST /correction-requests/{request_id}/respond`: Authoritative owner responds to request.
