"""Phase 52: Clinical Safety Assurance Schemas.

Defines the authoritative domain types for continuous control effectiveness
management: lifecycle states, evaluation records, assurance scope, evidence
references, AI governance, domain events, and assurance metrics.

Core principle: NO boolean "is safe" — only bounded, evidence-based assurance
of specific control behavior at a specific time with defined scope.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Assurance Lifecycle States
# ---------------------------------------------------------------------------


class AssuranceLifecycleState(str, Enum):
    """Primary lifecycle states for a control assurance evaluation."""

    SCHEDULED = "SCHEDULED"
    ELIGIBILITY_CHECK = "ELIGIBILITY_CHECK"
    OBSERVATION_COLLECTION = "OBSERVATION_COLLECTION"
    EVIDENCE_ASSESSMENT = "EVIDENCE_ASSESSMENT"
    EFFECTIVENESS_EVALUATION = "EFFECTIVENESS_EVALUATION"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    UNDER_REVIEW = "UNDER_REVIEW"
    ASSURANCE_ACCEPTED = "ASSURANCE_ACCEPTED"
    MONITORING = "MONITORING"

    # Alternative / failure states
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    SUPERSEDED = "SUPERSEDED"
    REASSESSMENT_REQUIRED = "REASSESSMENT_REQUIRED"
    REOPENED = "REOPENED"


# ---------------------------------------------------------------------------
# Control Effectiveness States
# ---------------------------------------------------------------------------


class ControlEffectivenessState(str, Enum):
    """Fine-grained operational effectiveness states.

    These MUST NOT collapse to a simple boolean. Clinical safety assurance
    requires uncertainty preservation.
    """

    NOT_EVALUATED = "NOT_EVALUATED"
    EVIDENCE_PENDING = "EVIDENCE_PENDING"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    OBSERVATION_AVAILABLE = "OBSERVATION_AVAILABLE"
    EFFECTIVENESS_UNCLEAR = "EFFECTIVENESS_UNCLEAR"
    EFFECTIVE_OBSERVED = "EFFECTIVE_OBSERVED"
    PARTIALLY_EFFECTIVE = "PARTIALLY_EFFECTIVE"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    SUPERSEDED = "SUPERSEDED"
    REQUIRES_REASSESSMENT = "REQUIRES_REASSESSMENT"


# ---------------------------------------------------------------------------
# Control Execution Observation States
# ---------------------------------------------------------------------------


class ControlExecutionState(str, Enum):
    """Observed execution state of a safety control during evaluation window."""

    CONTROL_NOT_TRIGGERED = "CONTROL_NOT_TRIGGERED"
    CONTROL_TRIGGERED = "CONTROL_TRIGGERED"
    CONTROL_COMPLETED = "CONTROL_COMPLETED"
    CONTROL_BLOCKED_ACTION = "CONTROL_BLOCKED_ACTION"
    CONTROL_BYPASSED = "CONTROL_BYPASSED"
    CONTROL_FAILED = "CONTROL_FAILED"
    CONTROL_TIMEOUT = "CONTROL_TIMEOUT"
    CONTROL_UNAVAILABLE = "CONTROL_UNAVAILABLE"
    CONTROL_NOT_OBSERVABLE = "CONTROL_NOT_OBSERVABLE"


# ---------------------------------------------------------------------------
# Degradation States
# ---------------------------------------------------------------------------


class DegradationState(str, Enum):
    """Graduated control degradation levels."""

    STABLE = "STABLE"
    DEGRADED = "DEGRADED"
    SIGNIFICANTLY_DEGRADED = "SIGNIFICANTLY_DEGRADED"
    FAILED = "FAILED"


# ---------------------------------------------------------------------------
# Evidence Quality States
# ---------------------------------------------------------------------------


class EvidenceQualityState(str, Enum):
    """Quality classification of a piece of assurance evidence.

    MISSING != PASS  |  PARTIAL != COMPLETE  |  STALE != CURRENT
    CONFLICTED != SAFE  |  UNVERIFIED != VERIFIED  |  INVALID != SUCCESS
    """

    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    MISSING = "MISSING"
    STALE = "STALE"
    CONFLICTED = "CONFLICTED"
    UNVERIFIED = "UNVERIFIED"
    INVALID = "INVALID"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"
    INSUFFICIENT = "INSUFFICIENT"


# ---------------------------------------------------------------------------
# Evidence Source Types
# ---------------------------------------------------------------------------


class EvidenceSourceType(str, Enum):
    """Authoritative evidence source categories."""

    SAFETY_GATE_EVALUATION = "SAFETY_GATE_EVALUATION"
    DECISION_TRACE = "DECISION_TRACE"
    WORKFLOW_EXECUTION = "WORKFLOW_EXECUTION"
    TASK_COMPLETION = "TASK_COMPLETION"
    PROVIDER_RESPONSE = "PROVIDER_RESPONSE"
    PROVIDER_AVAILABILITY = "PROVIDER_AVAILABILITY"
    VALIDATION_RESULT = "VALIDATION_RESULT"
    CONFIGURATION_STATE = "CONFIGURATION_STATE"
    FEATURE_FLAG_STATE = "FEATURE_FLAG_STATE"
    DEPLOYMENT_METADATA = "DEPLOYMENT_METADATA"
    DATA_QUALITY_EVENT = "DATA_QUALITY_EVENT"
    RECONCILIATION_RESULT = "RECONCILIATION_RESULT"
    NOTIFICATION_DELIVERY = "NOTIFICATION_DELIVERY"
    SAFETY_INCIDENT = "SAFETY_INCIDENT"
    NEAR_MISS = "NEAR_MISS"
    BLOCKED_ACTION = "BLOCKED_ACTION"
    CORRECTIVE_ACTION = "CORRECTIVE_ACTION"
    SAFETY_LEARNING_ANALYSIS = "SAFETY_LEARNING_ANALYSIS"
    MONITORING_METRIC = "MONITORING_METRIC"
    AUTHORIZED_HUMAN_REVIEW = "AUTHORIZED_HUMAN_REVIEW"
    SYNTHETIC_SAFETY_TEST = "SYNTHETIC_SAFETY_TEST"
    REGRESSION_TEST = "REGRESSION_TEST"
    INTEGRATION_TEST = "INTEGRATION_TEST"
    PRODUCTION_OBSERVATION = "PRODUCTION_OBSERVATION"


# ---------------------------------------------------------------------------
# Assurance Review Decision Types
# ---------------------------------------------------------------------------


class AssuranceReviewDecision(str, Enum):
    """Possible outcomes of a human assurance review."""

    ACCEPT_EFFECTIVENESS = "ACCEPT_EFFECTIVENESS"
    ACCEPT_WITH_LIMITATIONS = "ACCEPT_WITH_LIMITATIONS"
    REQUIRE_MORE_EVIDENCE = "REQUIRE_MORE_EVIDENCE"
    MARK_DEGRADED = "MARK_DEGRADED"
    MARK_FAILED = "MARK_FAILED"
    REASSESS_RISK = "REASSESS_RISK"
    CREATE_SAFETY_CHANGE = "CREATE_SAFETY_CHANGE"
    CREATE_INCIDENT_REVIEW = "CREATE_INCIDENT_REVIEW"
    REJECT_EVALUATION = "REJECT_EVALUATION"


# ---------------------------------------------------------------------------
# Assurance Routing Types
# ---------------------------------------------------------------------------


class AssuranceRouteTarget(str, Enum):
    """Downstream systems that can receive failed/degraded control routing."""

    PHASE_48_SAFETY_ENFORCEMENT = "PHASE_48_SAFETY_ENFORCEMENT"
    PHASE_49_INCIDENT_MANAGEMENT = "PHASE_49_INCIDENT_MANAGEMENT"
    PHASE_50_SAFETY_LEARNING = "PHASE_50_SAFETY_LEARNING"
    PHASE_51_RISK_REASSESSMENT = "PHASE_51_RISK_REASSESSMENT"
    PHASE_51_SAFETY_CHANGE = "PHASE_51_SAFETY_CHANGE"
    PHASE_25_CONFIGURATION = "PHASE_25_CONFIGURATION"
    PHASE_36_TASK = "PHASE_36_TASK"
    PHASE_37_WORKFLOW = "PHASE_37_WORKFLOW"
    MONITORING_ONLY = "MONITORING_ONLY"


# ---------------------------------------------------------------------------
# AI Governance
# ---------------------------------------------------------------------------


class AssuranceAIStatus(str, Enum):
    """AI material lifecycle status within assurance evaluation."""

    HUMAN_AUTHORED = "HUMAN_AUTHORED"
    AI_SUGGESTED = "AI_SUGGESTED"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"
    HUMAN_ACCEPTED = "HUMAN_ACCEPTED"
    HUMAN_MODIFIED = "HUMAN_MODIFIED"
    HUMAN_REJECTED = "HUMAN_REJECTED"


# ---------------------------------------------------------------------------
# Control Category
# ---------------------------------------------------------------------------


class ControlCategory(str, Enum):
    """Categories of safety controls that can be evaluated."""

    MEDICATION_SAFETY_GATE = "MEDICATION_SAFETY_GATE"
    TRIAGE_SAFETY_GATE = "TRIAGE_SAFETY_GATE"
    HUMAN_REVIEW_REQUIREMENT = "HUMAN_REVIEW_REQUIREMENT"
    CONSENT_ENFORCEMENT = "CONSENT_ENFORCEMENT"
    AUTHORIZATION_RESTRICTION = "AUTHORIZATION_RESTRICTION"
    STALE_DATA_PROTECTION = "STALE_DATA_PROTECTION"
    PROVIDER_FALLBACK = "PROVIDER_FALLBACK"
    PROVIDER_AVAILABILITY_SAFEGUARD = "PROVIDER_AVAILABILITY_SAFEGUARD"
    AI_SAFETY_RESTRICTION = "AI_SAFETY_RESTRICTION"
    DOCUMENT_VALIDATION_SAFEGUARD = "DOCUMENT_VALIDATION_SAFEGUARD"
    RECONCILIATION_SAFEGUARD = "RECONCILIATION_SAFEGUARD"
    WORKFLOW_APPROVAL_GATE = "WORKFLOW_APPROVAL_GATE"
    NOTIFICATION_ESCALATION_CONTROL = "NOTIFICATION_ESCALATION_CONTROL"
    INTEROPERABILITY_VALIDATION = "INTEROPERABILITY_VALIDATION"
    DATA_QUALITY_CONTROL = "DATA_QUALITY_CONTROL"
    CONFIGURATION_RESTRICTION = "CONFIGURATION_RESTRICTION"
    FEATURE_FLAG_SAFETY_CONTROL = "FEATURE_FLAG_SAFETY_CONTROL"
    DEPLOYMENT_SAFETY_CONTROL = "DEPLOYMENT_SAFETY_CONTROL"
    SECURITY_CONTROL = "SECURITY_CONTROL"
    PRIVACY_CONTROL = "PRIVACY_CONTROL"
    CONCURRENCY_VERSION_CONTROL = "CONCURRENCY_VERSION_CONTROL"
    ROLLBACK_CONTROL = "ROLLBACK_CONTROL"
    MONITORING_CONTROL = "MONITORING_CONTROL"


# ---------------------------------------------------------------------------
# Domain Event Types
# ---------------------------------------------------------------------------


class AssuranceDomainEventType(str, Enum):
    """Domain events emitted by Phase 52 assurance lifecycle."""

    SCHEDULED = "safety_assurance.scheduled"
    STARTED = "safety_assurance.started"
    EVIDENCE_COLLECTED = "safety_assurance.evidence_collected"
    EVIDENCE_INSUFFICIENT = "safety_assurance.evidence_insufficient"
    EVALUATED = "safety_assurance.evaluated"
    EFFECTIVE = "safety_assurance.effective"
    DEGRADED = "safety_assurance.degraded"
    FAILED = "safety_assurance.failed"
    REVIEW_REQUIRED = "safety_assurance.review_required"
    ACCEPTED = "safety_assurance.accepted"
    REJECTED = "safety_assurance.rejected"
    REASSESSMENT_REQUIRED = "safety_assurance.reassessment_required"
    REGRESSION_DETECTED = "safety_assurance.regression_detected"
    BYPASS_DETECTED = "safety_assurance.bypass_detected"
    INCIDENT_ROUTE_REQUIRED = "safety_assurance.incident_route_required"
    RISK_REASSESSMENT_REQUIRED = "safety_assurance.risk_reassessment_required"
    CHANGE_REQUIRED = "safety_assurance.change_required"
    REOPENED = "safety_assurance.reopened"
    SUPERSEDED = "safety_assurance.superseded"


# ---------------------------------------------------------------------------
# Assurance Scope
# ---------------------------------------------------------------------------


class AssuranceScopeRecord(BaseModel):
    """Defines the bounded scope of a control assurance evaluation.

    Evidence must not be generalized across incompatible scopes.
    """

    model_config = ConfigDict(extra="ignore")

    system: Optional[str] = None
    organization_id: Optional[str] = None
    facility_id: Optional[str] = None
    department_id: Optional[str] = None
    workflow_id: Optional[str] = None
    control_id: str
    control_version: str
    provider_id: Optional[str] = None
    provider_config_version: Optional[str] = None
    feature_flag_id: Optional[str] = None
    feature_flag_version: Optional[str] = None
    deployment_version: Optional[str] = None
    rule_version: Optional[str] = None
    ai_model_version: Optional[str] = None
    safety_policy_version: Optional[str] = None
    observation_start: datetime
    observation_end: datetime
    resource_category: Optional[str] = None

    scope_description: Optional[str] = Field(
        None,
        description="Human-readable scope boundary clarification (not PHI).",
    )


# ---------------------------------------------------------------------------
# Evidence Reference
# ---------------------------------------------------------------------------


class EvidenceReference(BaseModel):
    """A reference to an authoritative evidence record.

    Phase 52 stores references, not raw clinical data, minimizing PHI exposure.
    """

    model_config = ConfigDict(extra="ignore")

    evidence_id: str = Field(default_factory=lambda: f"evid-{uuid.uuid4().hex[:12]}")
    source_type: EvidenceSourceType
    source_id: str
    source_version: Optional[str] = None
    observation_timestamp: datetime
    recorded_timestamp: Optional[datetime] = None
    provenance: Optional[str] = None
    scope_tag: Optional[str] = None
    evaluation_context: Optional[str] = None
    quality_state: EvidenceQualityState = EvidenceQualityState.UNVERIFIED
    reliability_note: Optional[str] = None
    is_safety_critical: bool = False


# ---------------------------------------------------------------------------
# Effectiveness Score Dimensions
# ---------------------------------------------------------------------------


class EffectivenessScoreDimensions(BaseModel):
    """Structured operational assurance indicator dimensions.

    A score is an OPERATIONAL ASSURANCE INDICATOR ONLY.
    It MUST NOT be presented as probability of patient safety,
    clinical certainty, guarantee of effectiveness, or risk elimination.

    Rates require valid denominators. Raw counts are NOT rates.
    """

    model_config = ConfigDict(extra="ignore")

    # Execution coverage: executions / eligible_executions
    eligible_executions: Optional[int] = None
    observed_executions: Optional[int] = None
    execution_coverage_rate: Optional[float] = Field(
        None,
        description="observed_executions / eligible_executions. None if denominator unavailable.",
    )
    execution_coverage_rate_available: bool = True

    # Valid-result rate
    total_results: Optional[int] = None
    valid_results: Optional[int] = None
    valid_result_rate: Optional[float] = None
    valid_result_rate_available: bool = True

    # Failure rate
    observed_failures: Optional[int] = None
    failure_rate: Optional[float] = None
    failure_rate_available: bool = True

    # Bypass rate
    observed_bypasses: Optional[int] = None
    bypass_rate: Optional[float] = None
    bypass_rate_available: bool = True

    # Evidence completeness (0.0–1.0)
    evidence_completeness_score: Optional[float] = None

    # Version consistency (all observations used same control version)
    version_consistent: Optional[bool] = None

    # Provider reliability
    provider_success_rate: Optional[float] = None
    provider_success_rate_available: bool = True

    # Review compliance
    required_reviews_completed: Optional[int] = None
    required_reviews_total: Optional[int] = None
    review_compliance_rate: Optional[float] = None

    # Recurrence indicators from safety learning
    recurrence_signals_observed: int = 0

    score_limitations: List[str] = Field(
        default_factory=list,
        description="Explicit limitations of this score.",
    )
    score_disclaimer: str = Field(
        default=(
            "This score is an operational assurance indicator only. "
            "It does not represent probability of patient safety, clinical certainty, "
            "guarantee of effectiveness, or risk elimination."
        )
    )


# ---------------------------------------------------------------------------
# Assurance Evaluation Record
# ---------------------------------------------------------------------------


class AssuranceEvaluationRecord(BaseModel):
    """Authoritative record of a single control assurance evaluation."""

    model_config = ConfigDict(extra="ignore")

    evaluation_id: str = Field(default_factory=lambda: f"asev-{uuid.uuid4().hex[:14]}")
    idempotency_key: Optional[str] = None

    # Control identity — must always be present
    control_id: str
    control_name: Optional[str] = None
    control_category: ControlCategory
    control_version: str
    control_description: Optional[str] = None

    # Scope
    scope: AssuranceScopeRecord

    # Lifecycle
    lifecycle_state: AssuranceLifecycleState = AssuranceLifecycleState.SCHEDULED
    effectiveness_state: ControlEffectivenessState = ControlEffectivenessState.NOT_EVALUATED
    execution_state: ControlExecutionState = ControlExecutionState.CONTROL_NOT_OBSERVABLE
    degradation_state: DegradationState = DegradationState.STABLE

    # Evidence
    evidence_references: List[EvidenceReference] = Field(default_factory=list)
    evidence_quality: EvidenceQualityState = EvidenceQualityState.MISSING
    evidence_source_availability: Optional[str] = Field(
        None,
        description="PARTIAL | COMPLETE | UNAVAILABLE — not a clinical safety guarantee.",
    )
    evidence_completeness_note: Optional[str] = None

    # Effectiveness
    effectiveness_score: Optional[EffectivenessScoreDimensions] = None
    effectiveness_summary: Optional[str] = Field(
        None,
        description="Non-PHI human-readable summary of assurance finding.",
    )
    effectiveness_limitations: List[str] = Field(default_factory=list)
    uncertainty_preserved: bool = True

    # Bypass / regression signals
    bypass_detected: bool = False
    bypass_count: int = 0
    bypass_notes: Optional[str] = None

    regression_detected: bool = False
    regression_compared_to_version: Optional[str] = None
    regression_notes: Optional[str] = None

    # Expected vs observed behavior
    expected_behavior_source: Optional[str] = Field(
        None,
        description="Authoritative source of expected behavior (policy/gate/workflow/config).",
    )
    expected_behavior_description: Optional[str] = None
    observed_behavior_description: Optional[str] = None
    behavior_aligned: Optional[bool] = None

    # Configuration / version verification
    config_version_consistent: Optional[bool] = None
    provider_version_consistent: Optional[bool] = None
    feature_flag_state_verified: Optional[bool] = None
    deployment_version_verified: Optional[bool] = None

    # Organization / facility context
    organization_id: Optional[str] = None
    facility_id: Optional[str] = None
    initiated_by_actor_id: Optional[str] = None
    initiated_by_role: Optional[str] = None

    # AI involvement (always marked, never authoritative)
    ai_status: AssuranceAIStatus = AssuranceAIStatus.HUMAN_AUTHORED
    ai_model_provider: Optional[str] = None
    ai_model_version: Optional[str] = None
    ai_prompt_template_version: Optional[str] = None
    ai_request_id: Optional[str] = None
    ai_summary_draft: Optional[str] = Field(
        None,
        description="AI-generated summary draft. REQUIRES human review. Not an assurance decision.",
    )
    ai_evidence_gap_suggestions: List[str] = Field(default_factory=list)

    # Review
    review_required: bool = False
    review_required_reason: Optional[str] = None
    reviewer_id: Optional[str] = None
    reviewer_role: Optional[str] = None
    reviewer_authorization_basis: Optional[str] = None
    review_decision: Optional[AssuranceReviewDecision] = None
    review_summary: Optional[str] = None
    review_limitations: List[str] = Field(default_factory=list)
    review_required_follow_up: Optional[str] = None
    reviewed_at: Optional[datetime] = None

    # Routing
    routed_to: Optional[AssuranceRouteTarget] = None
    routed_reference_id: Optional[str] = None
    routing_reason: Optional[str] = None

    # Reassessment
    reassessment_trigger: Optional[str] = None
    reassessment_required_by: Optional[datetime] = None
    previous_evaluation_id: Optional[str] = None
    superseded_by_evaluation_id: Optional[str] = None

    # Temporal tracking
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    evidence_collected_at: Optional[datetime] = None
    evaluated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Concurrency
    version: int = 1

    # Job reference (Phase 22)
    job_id: Optional[str] = None

    # Audit
    request_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Assurance Evaluation Request / Response
# ---------------------------------------------------------------------------


class AssuranceEvaluationRequest(BaseModel):
    """Request to initiate a control assurance evaluation."""

    model_config = ConfigDict(extra="ignore")

    control_id: str = Field(..., description="Authoritative identity of the control to evaluate.")
    control_version: str = Field(..., description="Expected control version under evaluation.")
    control_category: ControlCategory

    organization_id: Optional[str] = Field(
        None,
        description="Scope restriction — server validates against authenticated actor.",
    )
    facility_id: Optional[str] = None
    department_id: Optional[str] = None
    workflow_id: Optional[str] = None

    observation_start: datetime = Field(..., description="Observation window start (UTC).")
    observation_end: datetime = Field(..., description="Observation window end (UTC).")

    provider_id: Optional[str] = None
    feature_flag_id: Optional[str] = None
    deployment_version: Optional[str] = None
    safety_policy_version: Optional[str] = None

    idempotency_key: Optional[str] = Field(
        None,
        description="Unique key to prevent duplicate evaluation creation.",
    )

    evaluation_reason: Optional[str] = Field(
        None,
        description="Non-PHI reason for initiating assurance evaluation.",
    )

    # Fields that MUST be ignored if provided by client:
    # actor_id, reviewer_id, effectiveness_state, control_state, risk_state
    # These are derived server-side from authenticated context.


class AssuranceEvaluationStatusResponse(BaseModel):
    """Lightweight status response for async polling."""

    model_config = ConfigDict(extra="ignore")

    evaluation_id: str
    lifecycle_state: AssuranceLifecycleState
    effectiveness_state: ControlEffectivenessState
    degradation_state: DegradationState
    bypass_detected: bool
    regression_detected: bool
    review_required: bool
    job_id: Optional[str] = None
    updated_at: datetime
    version: int


# ---------------------------------------------------------------------------
# Assurance Review Request
# ---------------------------------------------------------------------------


class AssuranceReviewRequest(BaseModel):
    """Request body for a human assurance review submission."""

    model_config = ConfigDict(extra="ignore")

    evaluation_version: int = Field(
        ...,
        description="Optimistic concurrency version of the evaluation under review.",
    )
    decision: AssuranceReviewDecision
    review_summary: str = Field(
        ...,
        min_length=10,
        description="Human reviewer's narrative summary (not a clinical diagnosis).",
    )
    review_limitations: List[str] = Field(
        default_factory=list,
        description="Explicit limitations acknowledged by reviewer.",
    )
    required_follow_up: Optional[str] = None
    ai_material_reviewed: bool = Field(
        default=False,
        description="Confirms reviewer acknowledged any AI-suggested material.",
    )

    # Fields that MUST be ignored / derived server-side:
    # reviewer_id, reviewer_role, authorization_basis, review_timestamp


class AssuranceAcceptRequest(BaseModel):
    """Request to formally accept an assurance evaluation result."""

    model_config = ConfigDict(extra="ignore")

    evaluation_version: int
    acceptance_rationale: str = Field(..., min_length=10)
    acknowledged_limitations: List[str] = Field(default_factory=list)


class AssuranceRejectRequest(BaseModel):
    """Request to reject an assurance evaluation (requires re-evaluation)."""

    model_config = ConfigDict(extra="ignore")

    evaluation_version: int
    rejection_reason: str = Field(..., min_length=10)


class AssuranceReassessRequest(BaseModel):
    """Request to trigger reassessment of a previously accepted control."""

    model_config = ConfigDict(extra="ignore")

    trigger_reason: str = Field(..., min_length=10)
    trigger_source: Optional[str] = None
    new_observation_start: Optional[datetime] = None
    new_observation_end: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Degradation Record
# ---------------------------------------------------------------------------


class DegradationRecord(BaseModel):
    """Record of detected control degradation over time."""

    model_config = ConfigDict(extra="ignore")

    degradation_id: str = Field(default_factory=lambda: f"deg-{uuid.uuid4().hex[:12]}")
    control_id: str
    control_version: str
    evaluation_id: str
    degradation_state: DegradationState
    degradation_signal: str = Field(
        ...,
        description="Observable signal that triggered degradation detection (not patient harm).",
    )
    metric_name: Optional[str] = None
    observed_value: Optional[float] = None
    threshold_value: Optional[float] = None
    threshold_source: Optional[str] = Field(
        None,
        description="Policy/config reference for threshold — not hardcoded.",
    )
    organization_id: Optional[str] = None
    facility_id: Optional[str] = None
    detected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    observation_start: Optional[datetime] = None
    observation_end: Optional[datetime] = None
    routed_to: Optional[AssuranceRouteTarget] = None
    route_reference_id: Optional[str] = None
    disclaimer: str = Field(
        default=(
            "Control degradation does not automatically indicate patient harm, "
            "clinical error, or root cause. Route per safety policy."
        )
    )


# ---------------------------------------------------------------------------
# Regression Record
# ---------------------------------------------------------------------------


class RegressionRecord(BaseModel):
    """Record of a control regression where a previously effective control deteriorated."""

    model_config = ConfigDict(extra="ignore")

    regression_id: str = Field(default_factory=lambda: f"reg-{uuid.uuid4().hex[:12]}")
    control_id: str
    current_evaluation_id: str
    reference_evaluation_id: str
    current_control_version: str
    reference_control_version: str
    regression_description: str
    regression_signals: List[str] = Field(default_factory=list)
    organization_id: Optional[str] = None
    facility_id: Optional[str] = None
    detected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_version_comparable: bool = Field(
        ...,
        description="False if comparison across incompatible versions is not valid.",
    )
    incompatibility_note: Optional[str] = None
    routed_to: Optional[AssuranceRouteTarget] = None
    route_reference_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Bypass Detection Record
# ---------------------------------------------------------------------------


class BypassRecord(BaseModel):
    """Record of a detected or suspected control bypass."""

    model_config = ConfigDict(extra="ignore")

    bypass_id: str = Field(default_factory=lambda: f"byp-{uuid.uuid4().hex[:12]}")
    control_id: str
    control_version: str
    evaluation_id: str
    bypass_signal: str = Field(
        ...,
        description="Signal indicating possible bypass (not confirmed incident).",
    )
    bypass_description: Optional[str] = None
    organization_id: Optional[str] = None
    facility_id: Optional[str] = None
    detected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    observation_timestamp: Optional[datetime] = None
    requires_incident_routing: bool = False
    routed_to: Optional[AssuranceRouteTarget] = None
    route_reference_id: Optional[str] = None
    safety_signal_note: str = Field(
        default=(
            "A bypass is a safety signal and NOT automatically a clinical incident. "
            "Route confirmed events per Phase 49 policy."
        )
    )


# ---------------------------------------------------------------------------
# Assurance Domain Event
# ---------------------------------------------------------------------------


class AssuranceDomainEvent(BaseModel):
    """Domain event payload emitted for assurance lifecycle transitions."""

    model_config = ConfigDict(extra="ignore")

    event_id: str = Field(default_factory=lambda: f"aevt-{uuid.uuid4().hex[:14]}")
    event_type: AssuranceDomainEventType
    evaluation_id: str
    control_id: str
    control_version: str
    lifecycle_state: AssuranceLifecycleState
    effectiveness_state: ControlEffectivenessState
    organization_id: Optional[str] = None
    facility_id: Optional[str] = None
    # PHI is deliberately excluded from events
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Assurance Dashboard / Aggregate
# ---------------------------------------------------------------------------


class AssuranceDashboardSummary(BaseModel):
    """Non-PHI aggregate assurance metrics for dashboard exposure."""

    model_config = ConfigDict(extra="ignore")

    organization_id: Optional[str] = None
    facility_id: Optional[str] = None
    as_of: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    controls_total: int = 0
    controls_effective: int = 0
    controls_partially_effective: int = 0
    controls_degraded: int = 0
    controls_failed: int = 0
    controls_insufficient_evidence: int = 0
    controls_pending_review: int = 0
    controls_superseded: int = 0

    evidence_gaps_detected: int = 0
    regressions_detected: int = 0
    bypasses_detected: int = 0
    overdue_reassessments: int = 0
    provider_related_degradations: int = 0
    configuration_drifts_detected: int = 0
    pending_safety_changes: int = 0

    disclaimer: str = Field(
        default=(
            "This summary reflects operational assurance indicators. "
            "It does not certify permanent clinical safety or eliminate risk."
        )
    )


# ---------------------------------------------------------------------------
# Control Assurance Summary (per control)
# ---------------------------------------------------------------------------


class ControlAssuranceSummary(BaseModel):
    """Summarized assurance posture for a specific control."""

    model_config = ConfigDict(extra="ignore")

    control_id: str
    control_name: Optional[str] = None
    control_category: ControlCategory
    control_version: str
    current_effectiveness_state: ControlEffectivenessState
    current_degradation_state: DegradationState
    last_evaluation_id: Optional[str] = None
    last_evaluated_at: Optional[datetime] = None
    last_accepted_at: Optional[datetime] = None
    next_reassessment_due: Optional[datetime] = None
    bypass_count_recent: int = 0
    regression_count_recent: int = 0
    pending_review: bool = False
    organization_id: Optional[str] = None
    facility_id: Optional[str] = None
