# Phase 48: Clinical Decision Safety Controls, Guardrails & Fail-Safe Enforcement

## Technical Architecture & Invariants Document

### 1. Overview & Objective
Phase 48 establishes the backend enforcement layer that prevents unsafe, unauthorized, stale, incomplete, ambiguous, or improperly generated system outputs from becoming clinical actions.

While Phase 47 established traceability, explanation formatting, and human review boundaries, Phase 48 enforces runtime execution guardrails and fail-safe defaults across the clinical lifecycle.

### 2. Core Safety Invariants
- **`FAILURE ≠ SUCCESS`**: Any failure or timeout in upstream providers (e.g., medication safety, triage engines) defaults strictly to a safe fail state (`UNAVAILABLE` / `BLOCKED`), never to "CLEAR" or "SAFE".
- **`NO DATA ≠ NO RISK`**: Missing clinical symptoms, allergies, or vitals remain explicitly incomplete (`INSUFFICIENT_INFORMATION`). Missing chest pain indicators must never be converted into "No chest pain".
- **`STALE ≠ CURRENT`**: Decisions evaluated against record version $V_k$ cannot apply if the underlying record has progressed to version $V_n$ ($n > k$); raises `ClinicalContextStaleException` / `DecisionStaleException`.
- **`CONFLICTED ≠ RESOLVED`**: Conflicting provider evaluations, discrepancies between patient-reported vs authoritative EHR data, or triage rule engine vs AI suggestions produce explicit `CONFLICTED` / `REVIEW_REQUIRED` states. No component may silently pick one result.
- **`AI OUTPUT ≠ CLINICAL AUTHORITY`**: AI outputs cannot autonomously diagnose, prescribe, modify medication, verify clinical truth, grant consent, or dispatch emergency services.
- **`HUMAN REVIEW REQUIRED ≠ APPROVED`**: A high-risk decision requiring human oversight cannot be applied until an authorized clinician explicitly reviews and approves it.
- **`NO CLIENT-CONTROLLED SAFETY BYPASS`**: Client-provided parameters (`skip_safety=True`, `force_apply=True`, `emergency=True`, `ignore_review=True`) are actively rejected with `SafetyBypassAttemptBlockedException`.
- **`UNSAFE RETRY PREVENTION`**: Sensitive operations track execution states to guard against duplicate application on network timeouts or replayed worker tasks (`UnsafeRetryException`, `ReconciliationRequiredException`).

### 3. Architecture & Service Stack
- `SafetyGateService` (`app/services/safety_gate_service.py`): Central coordinator orchestrating safety checks, precondition verification, and audit logging.
- `SafetyPolicyService` (`app/services/safety_policy_service.py`): Versioned policy management (`1.0.0`) governing mandatory controls and prohibited actions. Protects historical decisions from retrospective policy tampering.
- `SafetyValidationService` (`app/services/safety_validation_service.py`): Validates input completeness, guards against prompt injection, detects client bypass attempts, and enforces AI boundaries.
- `SafetyContextService` (`app/services/safety_context_service.py`): Checks actor privileges and validates resource freshness against Phase 46 `VersioningRepository`.
- `SafetyConflictService` (`app/services/safety_conflict_service.py`): Detects and surfaces multi-provider disagreements and triage override conflicts.
- `SafetyFallbackService` (`app/services/safety_fallback_service.py`): Manages provider circuit breakers (`CLOSED`, `OPEN`, `HALF_OPEN`) and approved fallback routing.
- `SafetyRetryService` (`app/services/safety_retry_service.py`): Enforces operational idempotency and mandates clinical reconciliation for indeterminate timeout outcomes.

### 4. API Endpoints
- `POST /api/v1/safety/evaluate`: Execute safety gate evaluation for a proposed operation or decision.
- `GET /api/v1/safety/checks/{check_id}`: Retrieve historical safety check record by ID.
- `GET /api/v1/decisions/{decision_id}/safety`: Retrieve all safety checks evaluated for a decision.
- `GET /api/v1/resources/{resource_type}/{resource_id}/safety-status`: Retrieve current safety status and active conflicts for a clinical resource.
- `GET /api/v1/safety/policies`: Introspect registered clinical safety policies.
