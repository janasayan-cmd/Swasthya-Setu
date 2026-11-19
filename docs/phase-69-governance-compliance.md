# Phase 69: Clinical Safety Governance Compliance Monitoring, Policy Conformance Assessment & Regulatory Evidence Management

## Document Type
Technical Architecture, API Specification & Clinical Safety Governance Compliance Monitoring Documentation

## Phase Overview
Phase 69 establishes the centralized clinical safety governance compliance monitoring and regulatory evidence management layer for HealthSetu.

Previous phases establish safety workflows, risk reviews, governance decisions, authorization verification, post-closure monitoring, and cross-workflow escalation. Phase 69 provides a governed mechanism to assess whether applicable governance and safety requirements are being actively followed, identify compliance gaps, maintain traceable supporting evidence, and coordinate corrective review through the appropriate authoritative workflow owners (such as Phase 54 controlled action orchestration and Phase 55 effectiveness evaluation).

---

## 1. Non-Negotiable Compliance Distinctions & Invariants

1. **A compliance assessment is not automatically a legal determination**: Internal governance assessments evaluate adherence to configured standards; they do not constitute legal advice or formal court rulings.
2. **A completed checklist does not prove that an organization is compliant**: Static checkboxes without verifiable underlying operational evidence have zero compliance weight.
3. **Evidence availability does not automatically establish that a control is effective**: Merely possessing a policy or an audit log does not prove the underlying safety control functioned effectively (Phase 55 evaluates effectiveness).
4. **A control marked implemented does not prove that it operated successfully**: Technical readiness is distinguished from operational execution.
5. **A compliance gap does not automatically establish regulatory misconduct**: Identified discrepancies represent governance findings requiring investigation, not intentional breaches.
6. **A missing document does not necessarily prove that the underlying activity did not occur**: Gaps represent evidentiary nonconformance, not retrospective historical rewrite.
7. **An automated compliance result does not replace authorized human review**: Algorithmic evaluations assist with indexing and classification, but authorized governance leads must conduct formal reviews.
8. **Passing an internal assessment does not establish regulatory approval or certification**: Internal evaluations cannot be represented as statutory or regulatory accreditations.
9. **A policy change must not silently rewrite historical assessment results**: Historical assessments are locked to the policy and framework version active at assessment execution time.
10. **A corrective action marked complete does not automatically establish effectiveness**: Corrective actions must undergo Phase 55 verification before compliance status can be restored.
11. **Compliance with a governance requirement does not establish clinical safety**: Administrative policy conformity does not substitute for clinical judgment or patient safety outcomes.
12. **Unknown, unavailable, contradictory, or insufficient evidence must not be treated as proof of compliance**: Omission of evidence deterministically produces `EVIDENCE_INSUFFICIENT` or `EVIDENCE_UNAVAILABLE`, never `COMPLIANT`.

---

## 2. Compliance Status Model (18 Controlled States)

Phase 69 defines 18 explicit compliance statuses:

- `NOT_ASSESSED`: Requirement registered but has not yet undergone initial compliance evaluation.
- `ASSESSMENT_PENDING`: Assessment scheduled or queued for evaluation.
- `ASSESSMENT_IN_PROGRESS`: Active assessment execution underway.
- `COMPLIANT`: All mapped controls verified against active, valid, and verified supporting evidence.
- `COMPLIANT_WITH_LIMITATIONS`: Requirement met with non-critical limitations explicitly noted (e.g., stale evidence pending refresh).
- `PARTIALLY_COMPLIANT`: Some controls satisfied, but non-critical requirements remain unfulfilled.
- `NON_COMPLIANT`: Critical control failures or complete requirement breach.
- `EVIDENCE_INSUFFICIENT`: Controls mapped but required supporting clinical/governance evidence is missing.
- `EVIDENCE_UNAVAILABLE`: Evidence exists but storage/dependency is unreachable or offline.
- `EVIDENCE_CONFLICTED`: Supporting evidence has been retracted, superseded, or invalidated.
- `CONTROL_NOT_IMPLEMENTED`: Requirement lacks any approved control mapping.
- `CONTROL_IMPLEMENTATION_UNVERIFIED`: Control is asserted but implementation verification failed.
- `CONTROL_EFFECTIVENESS_UNVERIFIED`: Control operates but Phase 55 operational effectiveness is unconfirmed.
- `REVIEW_REQUIRED`: Surfaced findings require specialist human governance review.
- `REASSESSMENT_REQUIRED`: Prior assessment superseded following corrective action or policy amendment.
- `DEPENDENCY_UNAVAILABLE`: Required upstream service (e.g., decision assurance or audit log) unreachable.
- `ASSESSMENT_FAILED`: Internal processing or evaluation engine error occurred.
- `SUPERSEDED`: Historical assessment superseded by a newer evaluation run.

---

## 3. Compliance Gap Taxonomy (18 Categories)

- `REQUIREMENT_NOT_IMPLEMENTED`
- `CONTROL_NOT_IMPLEMENTED`
- `CONTROL_NOT_VERIFIED`
- `CONTROL_EFFECTIVENESS_UNVERIFIED`
- `REQUIRED_EVIDENCE_MISSING`
- `REQUIRED_EVIDENCE_UNAVAILABLE`
- `EVIDENCE_INVALIDATED`
- `EVIDENCE_STALE`
- `POLICY_VERSION_MISMATCH`
- `REQUIREMENT_MAPPING_MISSING`
- `REQUIRED_REVIEW_OVERDUE`
- `APPROVAL_MISSING`
- `AUTHORIZATION_NONCONFORMANCE`
- `AUDIT_TRACEABILITY_GAP`
- `RETENTION_NONCONFORMANCE`
- `PRIVACY_CONTROL_EXCEPTION`
- `CROSS_WORKFLOW_INCONSISTENCY`
- `ASSESSMENT_DEPENDENCY_FAILURE`

---

## 4. Requirement-to-Control Traceability

Requirements map to controls owned by previous safety phases:
- Phase 24 (Privacy Controls)
- Phase 43 (Consent Management)
- Phase 48 (Safety Controls & Fail-Safe Behavior)
- Phase 49 (Incident Lifecycle)
- Phase 51 (Risk Acceptance)
- Phase 52 (Safety Assurance)
- Phase 54 (Controlled Action Orchestration)
- Phase 55 (Effectiveness Evaluation)
- Phase 58 (Release Verification & Closure)
- Phase 63 (Risk Review & Disposition)
- Phase 65 (Handoff Completion)
- Phase 66 (Post-Closure Integrity)
- Phase 67 (Governance Escalation)
- Phase 68 (Decision Assurance)

Each mapping specifies verification methodology (`AUTOMATED_AUDIT`, `DECISION_ASSURANCE`, `EFFECTIVENESS_EVALUATION`, `MANUAL_INSPECTION`, `EVIDENCE_SAMPLING`), expected evidence, and approving authority.

---

## 5. Regulatory & Governance Evidence Packages

Supports controlled generation of audit and regulatory preparation packages:
- Scoped strictly to specified frameworks, requirements, and assessments.
- Applies minimum necessary data principles: omits patient-identifiable healthcare data.
- Enforces access classification: `RESTRICTED` evidence is omitted unless explicitly authorized for governance leads.
- Generates SHA256 integrity hash over the package manifest.
- Audits all download and retrieval operations.

---

## 6. REST API Reference

Base Path: `/api/v1/governance-compliance`

### Specialized Queues
- `GET /queues/review-required`: Assessments requiring human specialist review.
- `GET /queues/overdue`: Requirements overdue for scheduled assessment.
- `GET /queues/evidence-required`: Assessments pending due to missing/inaccessible evidence.
- `GET /queues/reassessment-required`: Assessments pending post-corrective action re-evaluation.

### Aggregated Reports
- `GET /reports/compliance-summary`: High-level compliance status metrics.
- `GET /reports/compliance-gaps`: Categorized breakdown of identified compliance findings.
- `GET /reports/control-conformance`: Control mapping coverage across requirements.
- `GET /reports/evidence-completeness`: Evidence validity, freshness, and accessibility diagnostics.

### Frameworks & Requirements
- `POST /frameworks`: Register compliance framework.
- `GET /frameworks`: List registered frameworks.
- `GET /frameworks/{framework_id}`: Retrieve framework details.
- `POST /requirements`: Register requirement under framework.
- `GET /requirements`: List requirements.
- `GET /requirements/{requirement_id}`: Retrieve requirement details.
- `POST /requirements/{requirement_id}/approve`: Approve requirement.
- `POST /requirements/{requirement_id}/activate`: Activate approved requirement.
- `GET /requirements/{requirement_id}/controls`: List mapped controls.
- `GET /requirements/{requirement_id}/evidence`: List indexed evidence.
- `POST /requirements/{requirement_id}/evidence/reconcile`: Reconcile evidence.

### Control Mappings
- `POST /control-mappings`: Map requirement to authoritative control.

### Assessments
- `POST /assessments`: Trigger compliance assessment.
- `GET /assessments`: List assessments.
- `GET /assessments/{assessment_id}`: Retrieve assessment details.
- `POST /assessments/{assessment_id}/reassess`: Trigger reassessment.

### Findings & Corrective Actions
- `GET /findings`: List compliance findings.
- `GET /findings/{finding_id}`: Retrieve finding details.
- `POST /findings/{finding_id}/review`: Record human specialist review.
- `POST /findings/{finding_id}/resolve`: Mark finding resolved.
- `POST /findings/{finding_id}/corrective-actions`: Submit Phase 54 corrective action request.
- `GET /findings/{finding_id}/corrective-actions`: List corrective action requests.

### Evidence Packages
- `POST /evidence-packages`: Generate controlled evidence package.
- `GET /evidence-packages`: List evidence packages.
- `GET /evidence-packages/{package_id}`: Retrieve package and log access audit.
- `GET /evidence-packages/{package_id}/status`: Check package integrity hash and download status.
