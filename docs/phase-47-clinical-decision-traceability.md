# HealthSetu — Phase 47: Clinical Decision Traceability, Explanation & Human Oversight Management

## 1. Overview & Core Mission

HealthSetu Phase 47 establishes backend infrastructure to ensure every clinically relevant system-generated decision, recommendation, alert, classification, workflow outcome, and AI-assisted output is fully traceable, explainable, and governed by human oversight.

The system answers:
- What decision or recommendation was produced?
- Which service, rule set, or model produced it?
- What inputs were considered (by version and reference)?
- Was human oversight required?
- Was it reviewed, accepted, rejected, modified, or superseded?
- Did the system apply the outcome, and what downstream action occurred?
- Can the decision be investigated later without mutating patient records?

### Core Invariants:
```
DECISION TRACEABILITY ≠ AUDIT LOGGING
EXPLANATION ≠ CLINICAL JUSTIFICATION
AI OUTPUT ≠ CLINICAL DECISION
RECOMMENDATION ≠ ACTION
SUGGESTION ≠ APPROVAL
APPROVAL ≠ EXECUTION
EXECUTION ≠ CLINICAL OUTCOME
RULE MATCH ≠ DIAGNOSIS
RISK CLASSIFICATION ≠ DIAGNOSIS
ALERT ≠ CLINICAL ACTION
AI CONFIDENCE ≠ CLINICAL CERTAINTY
MODEL OUTPUT ≠ HUMAN VERIFICATION
HUMAN REVIEW ≠ AUTOMATIC APPROVAL
REVIEW REQUEST ≠ REVIEW COMPLETION
DECISION RECORD ≠ CLINICAL RECORD
DECISION HISTORY ≠ AUDIT HISTORY
EXPLANATION ≠ EVIDENCE
PROVENANCE ≠ EXPLANATION
CURRENT DECISION ≠ HISTORICAL DECISION
SYSTEM RECOMMENDATION ≠ PRESCRIPTION
SYSTEM RECOMMENDATION ≠ MEDICATION CHANGE
SYSTEM RECOMMENDATION ≠ DIAGNOSIS
SYSTEM RECOMMENDATION ≠ TRIAGE AUTHORITY
NO SYSTEM COMPONENT MAY SILENTLY TURN AN AI OUTPUT OR RULE RESULT INTO AN UNAUTHORIZED CLINICAL ACTION.
```

---

## 2. Decision Traceability Model

Every clinically relevant system output records:
- `decision_id`: Unique trace identifier
- `decision_type`: Controlled enum (e.g. `TRIAGE_CLASSIFICATION`, `MEDICATION_SAFETY_WARNING`, `CARE_PLAN_RECOMMENDATION`)
- `patient_id` & `resource_reference`: Target clinical scope
- `resource_version`: Evaluated record version at generation time (Phase 46 integration)
- `inputs`: Pointers to input versions and integrity hashes (avoiding raw PHI duplication)
- `rule_metadata`: Rule set, rule version, and matched rule identifiers
- `model_metadata`: Model identifier, provider, prompt/schema versions, confidence
- `requires_human_oversight`: Strict gate flag
- `status`: Lifecycle state (`GENERATED`, `REVIEW_REQUIRED`, `APPROVED`, `APPLIED`, `SUPERSEDED`, etc.)
- `downstream_action`: Link to triggered alert, task, or workflow

---

## 3. Human Oversight & Review Workflow

```
System Output Generated
          │
          ▼
[1] High-Risk / AI Suggestion? ──► Status: REVIEW_REQUIRED
          │
          ▼
[2] Clinician Review (POST /decisions/{id}/review)
    ├─ APPROVED ──────────► Status: APPROVED
    ├─ REJECTED ──────────► Status: REJECTED
    └─ MODIFIED ──────────► Payload adjusted, Status: APPROVED
          │
          ▼
[3] Application Gate (POST /decisions/{id}/apply)
    ├─ Check Human Approval
    ├─ Check Expiration
    └─ Check Context Staleness (Phase 46 recheck)
          │
          ▼
[4] Applied to Clinical Workflow (Status: APPLIED)
```

---

## 4. Stale Decision Context Protection

A decision generated against an older clinical record version cannot be silently applied if the underlying record has progressed:
- E.g., Medication safety warning generated against Medication Record v5.
- If medication list is now v6, attempting application fails with `409 DECISION_CONTEXT_STALE` or `DECISION_VERSION_CONFLICT`.
- Re-evaluation is required.

---

## 5. Explanation Architecture

- **Patient-Facing Mode**: Understandable, safe terminology, clear disclaimers, no unsupported diagnostic assertions, omits raw rule codes and internal technical prompts.
- **Clinician-Facing Mode**: Full technical traceability, matched rules, model versions, confidence metrics, input references, and human review history.
- **Strict Privacy Rule**: Hidden chain-of-thought and internal private prompts are never exposed.
