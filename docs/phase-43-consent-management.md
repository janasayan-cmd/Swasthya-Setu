# Phase 43 — Patient Consent, Sharing Authorization & Clinical Data Access Control

## 1. Executive Summary & Objective

Phase 43 operationalizes explicit, auditable, resource-aware patient consent and data-sharing authorization for HealthSetu. It establishes a centralized access evaluation engine governing what clinical information may be shared, with whom, for what purpose, for what scope, for how long, and under what conditions.

This phase extends the foundational contracts from Phase 3 (Identity, Authorization & Consent) and Phase 24 (Data Governance & Retention) without creating competing schemas or duplicating patient/provider records.

---

## 2. Core Non-Negotiable Invariants

1. **Consent is an Access-Control Input, NOT Clinical Authority:**
   - `CONSENT ≠ DIAGNOSIS`
   - `CONSENT ≠ TREATMENT`
   - `CONSENT ≠ PRESCRIPTION`
   - `CONSENT ≠ MEDICATION CHANGE`
   - `CONSENT ≠ TRIAGE`
   - `CONSENT ≠ EMERGENCY DISPATCH`
2. **Consent State Rules:**
   - `CONSENT REQUESTED ≠ CONSENT GRANTED` (Requests are non-authorizing until approved)
   - `CONSENT GRANTED ≠ INFORMATION VERIFIED`
   - `CONSENT GRANTED ≠ CLINICAL APPROVAL`
   - `CONSENT EXPIRED ≠ CONSENT RENEWED` (No silent extensions or renewals)
   - `CONSENT WITHDRAWN ≠ DATA AUTOMATICALLY ERASED` (Historical records and audit trials preserved under Phase 24)
   - `CONSENT ≠ UNLIMITED ACCESS`
3. **Action & Resource Differentiation:**
   - `READ ≠ UPDATE`
   - `READ ≠ SHARE`
   - `SHARE ≠ EXPORT`
   - `COMMUNICATE ≠ CLINICAL_ORDER`
4. **AI Boundary:**
   - `AI INTERPRETATION ≠ CONSENT AUTHORITY`
   - AI cannot create, grant, deny, or withdraw consent.
   - AI cannot declare emergency access or break-glass authorization.
5. **Deny-by-Default:**
   - If consent data, status, recipient, or purpose is missing, unknown, or ambiguous: **ACCESS DENIED**.
6. **Execution-Time Verification:**
   - `CONSENT GRANTED AT QUEUE TIME ≠ AT EXECUTION TIME`
   - Asynchronous jobs (export/sharing) must re-evaluate consent status just before executing.

---

## 3. Architecture & Components

```
                          RESOURCE REQUEST
                                 │
                                 ▼
                          AUTHENTICATION
                                 │
                                 ▼
                        ACTOR IDENTIFICATION
                                 │
                                 ▼
                     PATIENT / RESOURCE CONTEXT
                                 │
                                 ▼
                        ROLE / RELATIONSHIP
                                 │
                                 ▼
                    ORGANIZATION / FACILITY SCOPE
                                 │
                                 ▼
                             PURPOSE
                                 │
                                 ▼
                        CONSENT REQUIREMENT
                                 │
                                 ▼
                           CONSENT STATUS
                                 │
                                 ▼
                          RESOURCE SCOPE
                                 │
                                 ▼
                           ACTION SCOPE
                                 │
                                 ▼
                           TIME VALIDITY
                                 │
                                 ▼
                               POLICY
                                 │
                                 ▼
                            ALLOW / DENY
                                 │
                                 ▼
                              AUDIT
                                 │
                                 ▼
                     AUTHORIZED RESOURCE ACCESS
```

### Key Modules:
- **`app/services/consent_access_service.py`**: Central evaluation engine (`evaluate_access`) implementing deny-by-default, purpose matching, resource scope matching, action scope validation, organization/facility boundaries, and break-glass token issuance/validation.
- **`app/services/consent_service.py`**: Patient consent lifecycle management: `grant_consent`, `deny_consent`, `withdraw_consent`, `renew_consent`, versioning, and provenance history.
- **`app/services/consent_request_service.py`**: Clinician/provider consent requests: `create_request`, `approve_request` (auto-activates consent), `deny_request`, with strict patient isolation.
- **`app/workers/consent_worker.py`**: Background expiration processing (transitions `ACTIVE` to `EXPIRED` without deleting clinical records) and JIT re-evaluation for queued exports.
- **`app/api/v1/endpoints/consents.py`**: Consent REST endpoints (lifecycle, history, patient listing).
- **`app/api/v1/endpoints/consent_requests.py`**: Consent request endpoints.
- **`app/api/v1/endpoints/access_evaluation.py`**: Access evaluation & Break-glass endpoints.

---

## 4. Emergency & Break-Glass Access Boundaries

- Break-glass access cannot be triggered by patient messages containing "emergency" or text heuristics.
- AI is strictly prohibited from invoking break-glass.
- Break-glass requires an explicit call to `POST /api/v1/access/break-glass` with:
  - Authorized clinician role (`DOCTOR`, `CLINICIAN`, `NURSE`, `ADMIN`).
  - Meaningful clinical emergency justification (`>= 10` characters).
  - Time-bounded token generation (`BREAK_GLASS_EXPIRATION_HOURS = 24`).
  - Enhanced audit logging (`BREAK_GLASS_REQUESTED`, `BREAK_GLASS_GRANTED`).
