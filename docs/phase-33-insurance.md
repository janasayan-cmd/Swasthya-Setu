# Phase 33: Insurance, Coverage & Policy Management

## 1. Overview & Clinical Invariant Rules

Phase 33 implements the operational and financial infrastructure for patient health insurance, claims processing, eligibility verification, benefit breakdowns, prior authorization, and payer gateway mediation.

### Core Invariants
- **INSURANCE ≠ CLINICAL DECISION**
- **INSURANCE ELIGIBILITY ≠ CLINICAL ELIGIBILITY**
- **PAYER RESPONSE ≠ CLINICAL TRUTH**
- **CLAIM STATUS ≠ PATIENT TREATMENT STATUS**
- **CLAIM APPROVAL ≠ CLINICAL APPROVAL**
- **CLAIM DENIAL ≠ CLINICAL DENIAL**
- **PRE-AUTHORIZATION ≠ CLINICAL AUTHORITY**
- **INSURANCE DATA ≠ VERIFIED CLINICAL DATA**

Insurance coverage failure or denial must **NEVER** automatically cancel patient care, triage, or clinical treatment unless configured by an approved operational policy.

---

## 2. Patient vs Subscriber Architectural Distinction

In health insurance workflows:
- **Patient**: The individual receiving healthcare services.
- **Subscriber**: The policyholder / primary insured member contractually bound to the payer.
- The patient may be the subscriber themselves, a spouse, a child, or an authorized dependent.
- The backend stores and validates `SubscriberInfo` separately from patient profile records without assuming identity equivalence.

---

## 3. Sensitive Identifiers & Privacy Controls

Insurance policies contain sensitive PII and financial numbers:
- `policy_number`
- `member_id`
- `group_number`
- `subscriber_id`

### Privacy Safeguards:
1. **Masking in Standard Views & Telemetry**: Identifiers are masked using `mask_identifier()` (e.g. `******1234`) in logs, traces, and customer notifications.
2. **BOLA / IDOR Barriers**: Patients can only inspect their own insurance coverage; attempting cross-patient queries immediately returns HTTP 403 Forbidden.
3. **No Clinical Bleed**: Insurance diagnosis codes do not automatically update patient clinical records or create verified conditions without clinical review.
