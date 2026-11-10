# Phase 66: Clinical Safety Workflow Completion Verification, Post-Closure Integrity Monitoring & Governed Lifecycle Reconciliation

## Document Type
Technical Architecture, API Specification & Clinical Safety Governance Documentation

## Phase Overview
Phase 66 implements the governed post-completion verification and lifecycle reconciliation layer for HealthSetu's clinical safety workflow ecosystem.

Phase 65 determines whether a safety workflow completion coordination record satisfies its requirements and whether its closure is authorized. Phase 66 independently coordinates the verification of that completion against authoritative downstream workflow states and subsequently monitors whether the completion remains valid over time.

---

## 1. Non-Negotiable Safety Distinctions & Invariants

1. **Phase 65 closure != Risk eliminated**: Closure signifies that exit gate requirements were satisfied at a historical point in time.
2. **Valid historical closure != Indefinitely valid**: Conditions, evidence, or outcomes may change post-closure.
3. **Post-closure verification != Clinical safety certification**: Verification checks integrity against authoritative sources; it does not replace clinical judgment.
4. **Change in authoritative source != Automatic reopening**: Detected changes require governed materiality evaluation.
5. **Detected discrepancy != Clinical error**: Discrepancies represent administrative or workflow state changes, not clinical malpractice.
6. **Missing dependency response != Workflow success or failure**: Inaccessible dependencies return `DEPENDENCY_UNAVAILABLE` rather than defaulting to safe.
7. **Successful reconciliation != Review/assurance replacement**: Integrity verification complements, but does not substitute, clinical risk acceptance (Phase 51), assurance (Phase 52), or effectiveness evaluation (Phase 55).
8. **System-generated recommendation != Authorized governance decision**: System recommendations (`REOPEN_RECOMMENDED`) require authorized human clinician or administrator action.
9. **Historical closure remains auditable**: Historical closure records are preserved across stales, conflicts, and reopenings.
10. **No silent rewrites**: Historical decisions are never rewritten or erased.

Unknown, contradictory, unavailable, or insufficient evidence is never interpreted as proof of continued safety.

---

## 2. Verification Lifecycle States

- `NOT_SCHEDULED`: Initial unmonitored state.
- `SCHEDULED`: Scheduled for periodic reverification.
- `PENDING`: Awaiting verification execution.
- `RUNNING`: Integrity checks currently in progress.
- `VERIFIED`: All mandatory checks satisfied against current authoritative sources.
- `VERIFIED_WITH_LIMITATIONS`: Verified with non-material limitations documented.
- `CHANGE_DETECTED`: Non-critical upstream/downstream changes detected.
- `REASSESSMENT_REQUIRED`: Material changes require formal reassessment under current policy.
- `REOPEN_RECOMMENDED`: Critical findings recommend governed reopening review.
- `REOPEN_AUTHORIZATION_PENDING`: Reopening requested, awaiting authorization.
- `REOPENED`: Formally reopened via Phase 65 authoritative interface.
- `STALE`: Outdated or unverified against expired monitoring windows.
- `CONFLICTED`: Direct contradiction between completion records and downstream authoritative states.
- `EVIDENCE_INVALID`: Required supporting evidence was invalidated or withdrawn.
- `DEPENDENCY_UNAVAILABLE`: Upstream/downstream repository could not be accessed.
- `VERIFICATION_FAILED`: Execution error during verification.
- `CANCELLED`: Verification cancelled.
- `SUPERSEDED`: Replaced by a more recent verification execution.

---

## 3. Post-Closure Integrity Checks

- **Check A (Completion Integrity)**: Confirms completion record, closure record, and authorization evidence exist, are valid, and completion package is internally consistent.
- **Check B (Source Disposition Integrity - Phase 63)**: Verifies source disposition exists, is valid, and has not been superseded, invalidated, or reopened.
- **Check C (Handoff & Destination Integrity - Phase 64)**: Verifies downstream handoffs are complete, not blocked/reopened, and outcome versions match.
- **Check D (Evidence Integrity)**: Verifies required evidence references remain valid and accessible; detects withdrawn or invalidated evidence.
- **Check E (Follow-up Integrity)**: Evaluates mandatory follow-up obligations; detects overdue, blocked, or failed follow-ups.
- **Check F (Safety Signal Integrity - Phase 59 & 60)**: Surfaces critical post-closure surveillance signals from Phase 59 that impact closure assumptions.
- **Check G (Policy Version Integrity)**: Compares completion policy version against current governance policy version.

---

## 4. API Endpoints

All endpoints are mounted under `/api/v1/safety-workflow-completions`:

### Filtered Operational Listings
- `GET /api/v1/safety-workflow-completions/post-closure-verifications/pending`: List pending or running verifications across the tenant.
- `GET /api/v1/safety-workflow-completions/post-closure-verifications/failed`: List failed, conflicted, or dependency-interrupted verifications.
- `GET /api/v1/safety-workflow-completions/integrity-findings/review-required`: List findings awaiting clinician or administrative review.

### Verification Executions
- `POST /api/v1/safety-workflow-completions/{completion_id}/post-closure-verifications`: Trigger post-closure verification run.
- `GET /api/v1/safety-workflow-completions/{completion_id}/post-closure-verifications`: List historical verification runs for a completion.
- `GET /api/v1/safety-workflow-completions/{completion_id}/post-closure-verifications/{verification_id}`: Get details of a specific verification execution.
- `POST /api/v1/safety-workflow-completions/{completion_id}/post-closure-verifications/{verification_id}/retry`: Retry an incomplete or failed verification.

### Integrity Findings
- `GET /api/v1/safety-workflow-completions/{completion_id}/integrity-findings`: List integrity findings for a completion.
- `GET /api/v1/safety-workflow-completions/{completion_id}/integrity-findings/{finding_id}`: Get finding details.
- `POST /api/v1/safety-workflow-completions/{completion_id}/integrity-findings/{finding_id}/review`: Review a finding (`CONFIRM`, `DISMISS`, `REQUEST_REASSESSMENT`, `REQUEST_REOPEN`).
- `POST /api/v1/safety-workflow-completions/{completion_id}/integrity-findings/{finding_id}/resolve`: Resolve a finding with supporting evidence.

### Monitoring, Reassessment, Reopening & History
- `GET /api/v1/safety-workflow-completions/{completion_id}/monitoring-status`: Get operational monitoring status and policy config.
- `POST /api/v1/safety-workflow-completions/{completion_id}/reassessment-requests`: Submit a policy-controlled reassessment request.
- `POST /api/v1/safety-workflow-completions/{completion_id}/reopening-requests`: Submit a reopening request and coordinate authorized reopening via Phase 65.
- `GET /api/v1/safety-workflow-completions/{completion_id}/post-closure-history`: Retrieve comprehensive audit history and preserved closure evidence.
