# Phase 67: Clinical Safety Governance Escalation, Cross-Workflow Exception Resolution & Controlled Decision Coordination

## Document Type
Technical Architecture, API Specification & Clinical Safety Governance Documentation

## Phase Overview
Phase 67 implements the centralized governance escalation, cross-workflow exception resolution, and controlled decision coordination layer for HealthSetu's clinical safety platform.

Previous phases establish clinical safety signals, risk reviews, dispositions, handoffs, completion coordination, and post-closure verifications. However, complex safety situations involve unresolved findings, conflicting authoritative decisions, failed actions, overdue reviews, and cross-phase dependencies. Phase 67 provides a governed mechanism to ingest, aggregate, prioritize, escalate, assign, track, and coordinate resolution of these cross-workflow exceptions without losing provenance or duplicating database entities.

---

## 1. Non-Negotiable Governance Distinctions & Invariants

1. **An escalation is not automatically a confirmed incident**: An escalation tracks workflow and governance exceptions; incident management is strictly owned by Phase 49.
2. **A high-priority exception does not independently establish clinical severity**: Governance priorities represent routing and response urgency, not medical diagnoses.
3. **Escalation acknowledgement does not mean that the underlying issue has been resolved**: Acknowledgement confirms receipt of ownership, not resolution.
4. **Assignment does not mean that an authorized decision has been made**: Assignment designates responsibility for investigation and review.
5. **A recommendation does not constitute approval**: System recommendations or specialist suggestions require formal authorized decision recording.
6. **An escalation closed administratively does not establish clinical safety**: Administrative closure confirms workflow reconciliation, never clinical risk elimination.
7. **Resolving one finding does not automatically resolve related findings**: Every aggregated exception must be individually resolved or reviewed.
8. **A conflict between workflows must not be silently resolved by choosing the newest or most convenient record**: All contradictory records and versions must be preserved.
9. **A governance escalation cannot override an authoritative decision owned by another phase**: Phase 67 coordinates cross-phase resolution rather than superseding domain authority.
10. **Missing, unavailable, or contradictory information must remain visible**: Omissions are explicitly marked with `DEPENDENCY_UNAVAILABLE` or `CONFLICTED`.
11. **Automated routing must never bypass role-based authorization or separation-of-duties requirements**: The creator of an escalation cannot self-close without independent review.
12. **An escalation deadline being met does not establish that the underlying safety concern was adequately addressed**: Deadlines measure response timeliness, not safety outcomes.

---

## 2. Escalation Lifecycle States

- `DETECTED`: Initial raw exception captured or escalation initialized.
- `VALIDATING`: Source references, tenant scope, and provenance under verification.
- `CLASSIFICATION_PENDING`: Awaiting priority evaluation.
- `CLASSIFIED`: Governance priority deterministically evaluated.
- `ROUTING_PENDING`: Awaiting functional domain routing.
- `ROUTED`: Routed to appropriate domain and hierarchy level.
- `ACKNOWLEDGEMENT_PENDING`: Designated owner assigned, awaiting acknowledgement.
- `ACKNOWLEDGED`: Assigned owner acknowledged receipt and responsibility.
- `OWNERSHIP_PENDING`: Unassigned or requiring owner reassignment.
- `ASSIGNED`: Owner formally assigned with calculated response deadlines.
- `REVIEW_PENDING`: Queued for formal governance review.
- `REVIEW_IN_PROGRESS`: Formal governance evaluation actively underway.
- `DECISION_PENDING`: Review completed with recommendation, awaiting authoritative decision.
- `ACTION_REQUIRED`: Authoritative decision issued; mandatory actions/requirements executing.
- `RESOLUTION_PENDING`: All actions underway, awaiting reconciliation.
- `RESOLUTION_REVIEW_PENDING`: Reconciled outcomes under final verification.
- `RESOLVED`: All mandatory resolution requirements satisfied or authorized waived.
- `CLOSED`: Controlled administrative closure completed with separation of duties.
- `REOPEN_REQUIRED`: Material change detected requiring governed reopening.
- `REOPENED`: Reopened for re-evaluation while preserving complete prior closure history.
- `BLOCKED`: Precluded from progress due to external blocker.
- `OVERDUE`: Breached acknowledgement, review, or decision deadline.
- `CONFLICTED`: Contradictory authoritative decisions recorded across workflows.
- `DEPENDENCY_UNAVAILABLE`: Required upstream/downstream phase unreachable.
- `CANCELLED`: Cancelled with documented audit rationale.
- `SUPERSEDED`: Replaced by a more comprehensive coordination group.

---

## 3. Exception Classification Taxonomy

- `UNRESOLVED_SAFETY_FINDING`: Open finding spanning clinical reviews or risk assessments.
- `MATERIAL_INTEGRITY_CHANGE`: Authoritative upstream or downstream record altered post-completion.
- `CONFLICTING_AUTHORITATIVE_DECISIONS`: Contradictory states between two authoritative phases.
- `RISK_DISPOSITION_REVIEW_REQUIRED`: Disposition in Phase 63 requires reassessment.
- `HANDOFF_OUTCOME_CONFLICT`: Phase 64 handoff outcome contradicts destination state.
- `COMPLETION_REQUIREMENT_BLOCKED`: Phase 65 exit gate blocked by external dependency.
- `POST_CLOSURE_REASSESSMENT_REQUIRED`: Phase 66 verification discovered material change.
- `REQUIRED_APPROVAL_OVERDUE`: Formal clinical or administrative approval overdue.
- `GOVERNANCE_ACTION_FAILED`: Phase 54 controlled safety action execution failed.
- `EFFECTIVENESS_REVIEW_FAILED`: Phase 55 safety action failed effectiveness validation.
- `ASSURANCE_REVIEW_BLOCKED`: Phase 52 clinical safety assurance review blocked.
- `INCIDENT_ESCALATION_REQUIRED`: Phase 49 safety incident requires cross-workflow governance intervention.
- `SURVEILLANCE_THRESHOLD_ESCALATION`: Phase 59 surveillance breached critical safety threshold.
- `AUTHORIZATION_CONFLICT`: Contradictory clinician or administrative authorization.
- `EVIDENCE_INTEGRITY_EXCEPTION`: Required clinical evidence missing, invalidated, or withdrawn.
- `POLICY_COMPLIANCE_EXCEPTION`: Governance policy breach requiring coordination.
- `DEPENDENCY_UNAVAILABLE`: External dependency unavailable for verification.
- `MANUAL_GOVERNANCE_REVIEW`: Authorized clinician or risk manager manual escalation submission.

---

## 4. API Endpoints Specification

Base Path: `/api/v1/governance-escalations`

### Queue Monitoring Endpoints
- `GET /queues/unassigned`: List escalations awaiting owner assignment.
- `GET /queues/overdue`: List active escalations breaching policy deadlines.
- `GET /queues/awaiting-acknowledgement`: List assigned escalations pending acknowledgement.
- `GET /queues/review-required`: List escalations currently requiring formal review.
- `GET /queues/conflicted`: List escalations with active cross-workflow decision conflicts.

### Core Lifecycle & Detail Endpoints
- `POST /`: Create a new governance escalation.
- `GET /`: List tenant escalations with priority, state, and facility filters.
- `POST /ingest-exception`: Ingest raw cross-workflow exception with idempotent deduplication.
- `GET /{escalation_id}`: Retrieve detailed escalation domain model.
- `GET /{escalation_id}/status`: Retrieve lightweight lifecycle status summary.
- `GET /{escalation_id}/history`: Retrieve immutable audit transition history.
- `GET /{escalation_id}/related-workflows`: List linked cross-phase workflow identifiers.
- `GET /{escalation_id}/dependencies`: List explicit cross-workflow dependency references.

### Aggregation & Exception Management
- `GET /{escalation_id}/exceptions`: List exceptions grouped under escalation.
- `POST /{escalation_id}/exceptions`: Correlate and aggregate exceptions into escalation.
- `POST /{escalation_id}/exceptions/separate`: Separate an incorrectly grouped exception.

### Routing, Assignment & Deadlines
- `POST /{escalation_id}/classify`: Deterministically classify governance priority level.
- `POST /{escalation_id}/route`: Route escalation to governance domain and hierarchy level.
- `POST /{escalation_id}/assign`: Assign primary owner and compute deadlines.
- `POST /{escalation_id}/reassign`: Reassign ownership with auditable rationale.
- `POST /{escalation_id}/acknowledge`: Designated owner acknowledges assignment.
- `POST /{escalation_id}/extend-deadline`: Authorize deadline extension with rationale.

### Reviews, Decisions & Conflicts
- `POST /{escalation_id}/reviews`: Record formal governance review execution.
- `GET /{escalation_id}/reviews`: List recorded governance reviews.
- `POST /{escalation_id}/decisions`: Record authoritative governance decision.
- `GET /{escalation_id}/decisions`: List recorded governance decisions.
- `GET /{escalation_id}/conflicts`: List cross-workflow decision conflicts.
- `POST /{escalation_id}/conflicts/{conflict_id}/resolve`: Resolve recorded decision conflict.

### Resolution & Closure
- `GET /{escalation_id}/resolution-requirements`: List resolution requirements.
- `POST /{escalation_id}/resolution-requirements/{requirement_id}/reconcile`: Reconcile requirement status against authoritative source.
- `POST /{escalation_id}/resolve`: Resolve escalation (verifies all mandatory requirements satisfied).
- `POST /{escalation_id}/close`: Controlled administrative closure (enforces separation of duties).
- `POST /{escalation_id}/reopen`: Governed reopening preserving prior closure audit history.
