"""Phase 55: Clinical Safety Oversight Action Effectiveness, Outcome Validation & Continuous Feedback Schemas.

Governing Principles:
- ACTION COMPLETION != ACTION EFFECTIVENESS
- ACTION EFFECTIVENESS != RISK ELIMINATION
- ACTION EFFECTIVENESS != PATIENT SAFETY GUARANTEE
- OBSERVED IMPROVEMENT != CAUSAL PROOF
- NO OBSERVED FAILURE != PROOF OF SAFETY
- INSUFFICIENT EVIDENCE != FAILURE
- SHORT-TERM IMPROVEMENT != SUSTAINED EFFECTIVENESS
- AI ASSESSMENT != ASSURANCE DECISION
- HUMAN REVIEW != AUTOMATIC APPROVAL
- CLOSURE != PERMANENT SAFETY
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class EffectivenessLifecycleState(str, Enum):
    """Lifecycle states of post-action effectiveness evaluation."""

    COMPLETION_RECEIVED = "COMPLETION_RECEIVED"
    SCOPE_VALIDATION = "SCOPE_VALIDATION"
    OBJECTIVE_IDENTIFICATION = "OBJECTIVE_IDENTIFICATION"
    CRITERIA_RESOLUTION = "CRITERIA_RESOLUTION"
    WINDOW_DEFINED = "WINDOW_DEFINED"
    EVIDENCE_COLLECTION = "EVIDENCE_COLLECTION"
    EVIDENCE_VALIDATION = "EVIDENCE_VALIDATION"
    COMPARISON = "COMPARISON"
    EFFECTIVENESS_ASSESSMENT = "EFFECTIVENESS_ASSESSMENT"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    EFFECTIVENESS_ACCEPTED = "EFFECTIVENESS_ACCEPTED"
    MONITORING = "MONITORING"
    SUSTAINED_VALIDATION = "SUSTAINED_VALIDATION"
    CLOSED = "CLOSED"

    # Alternative / Terminal states
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    DEFERRED = "DEFERRED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    PARTIALLY_EFFECTIVE = "PARTIALLY_EFFECTIVE"
    NO_CLEAR_IMPROVEMENT = "NO_CLEAR_IMPROVEMENT"
    DEGRADED = "DEGRADED"
    REGRESSED = "REGRESSED"
    INCONCLUSIVE = "INCONCLUSIVE"
    STALE = "STALE"
    SUPERSEDED = "SUPERSEDED"
    REQUIRES_REASSESSMENT = "REQUIRES_REASSESSMENT"
    REOPENED = "REOPENED"
    CANCELLED = "CANCELLED"


class EffectivenessState(str, Enum):
    """Controlled effectiveness states."""

    NOT_EVALUATED = "NOT_EVALUATED"
    EVIDENCE_PENDING = "EVIDENCE_PENDING"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    EFFECTIVENESS_UNCLEAR = "EFFECTIVENESS_UNCLEAR"
    EFFECTIVE_OBSERVED = "EFFECTIVE_OBSERVED"
    PARTIALLY_EFFECTIVE = "PARTIALLY_EFFECTIVE"
    NO_CLEAR_IMPROVEMENT = "NO_CLEAR_IMPROVEMENT"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"
    REGRESSED = "REGRESSED"
    INCONCLUSIVE = "INCONCLUSIVE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    SUPERSEDED = "SUPERSEDED"
    REQUIRES_REASSESSMENT = "REQUIRES_REASSESSMENT"


class EffectivenessCriterionCategory(str, Enum):
    """Supported categories for effectiveness criteria."""

    CONTROL_EXECUTION_RATE = "CONTROL_EXECUTION_RATE"
    FAILURE_RATE = "FAILURE_RATE"
    ERROR_RATE = "ERROR_RATE"
    BLOCK_RATE = "BLOCK_RATE"
    BYPASS_RATE = "BYPASS_RATE"
    REVIEW_COMPLETION_RATE = "REVIEW_COMPLETION_RATE"
    DATA_COMPLETENESS = "DATA_COMPLETENESS"
    DATA_CONSISTENCY = "DATA_CONSISTENCY"
    RECONCILIATION_SUCCESS = "RECONCILIATION_SUCCESS"
    WORKFLOW_COMPLETION = "WORKFLOW_COMPLETION"
    WORKFLOW_FAILURE = "WORKFLOW_FAILURE"
    PROVIDER_AVAILABILITY = "PROVIDER_AVAILABILITY"
    PROVIDER_FALLBACK_SUCCESS = "PROVIDER_FALLBACK_SUCCESS"
    NOTIFICATION_DELIVERY = "NOTIFICATION_DELIVERY"
    NOTIFICATION_ACKNOWLEDGEMENT = "NOTIFICATION_ACKNOWLEDGEMENT"
    TASK_COMPLETION = "TASK_COMPLETION"
    RESPONSE_TIME = "RESPONSE_TIME"
    PROCESSING_TIME = "PROCESSING_TIME"
    REGRESSION_RATE = "REGRESSION_RATE"
    RECURRENCE_RATE = "RECURRENCE_RATE"
    INCIDENT_FREQUENCY = "INCIDENT_FREQUENCY"
    SAFETY_SIGNAL_FREQUENCY = "SAFETY_SIGNAL_FREQUENCY"
    CONTROL_VALIDATION_RESULT = "CONTROL_VALIDATION_RESULT"
    CONFIGURATION_CONFORMANCE = "CONFIGURATION_CONFORMANCE"
    VERSION_CONFORMANCE = "VERSION_CONFORMANCE"
    HUMAN_REVIEW_COMPLIANCE = "HUMAN_REVIEW_COMPLIANCE"
    POLICY_COMPLIANCE = "POLICY_COMPLIANCE"


class ObservationWindowType(str, Enum):
    """Observation window configurations."""

    IMMEDIATE = "IMMEDIATE"
    FIXED_DURATION = "FIXED_DURATION"
    EVENT_COUNT = "EVENT_COUNT"
    ROLLING = "ROLLING"
    RECURRING = "RECURRING"
    SCHEDULED_REASSESSMENT = "SCHEDULED_REASSESSMENT"
    THRESHOLD_TRIGGERED = "THRESHOLD_TRIGGERED"


class EvidenceQualityState(str, Enum):
    """Evidence quality classification."""

    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    MISSING = "MISSING"
    STALE = "STALE"
    CONFLICTED = "CONFLICTED"
    UNVERIFIED = "UNVERIFIED"
    INVALID = "INVALID"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"
    INSUFFICIENT = "INSUFFICIENT"


class HumanReviewOutcome(str, Enum):
    """Outcomes from human oversight review."""

    ACCEPT = "ACCEPT"
    ACCEPT_WITH_LIMITATIONS = "ACCEPT_WITH_LIMITATIONS"
    REQUEST_MORE_EVIDENCE = "REQUEST_MORE_EVIDENCE"
    REASSESS = "REASSESS"
    REJECT = "REJECT"
    ESCALATE = "ESCALATE"
    REOPEN = "REOPEN"


class UncertaintyLevel(str, Enum):
    """Degree of uncertainty in the evaluated evidence."""

    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    UNRESOLVED = "UNRESOLVED"


# ---------------------------------------------------------------------------
# Scope & Objectives
# ---------------------------------------------------------------------------


class EffectivenessScope(BaseModel):
    """Scope of effectiveness validation."""

    model_config = ConfigDict(extra="forbid")

    organization_id: str = Field(..., description="Organization identifier")
    facility_id: Optional[str] = Field(None, description="Facility identifier")
    department_id: Optional[str] = Field(None, description="Department identifier")
    environment: str = Field("production", description="Environment under evaluation")


class SafetyObjective(BaseModel):
    """Bounded, testable safety objective for post-action validation."""

    model_config = ConfigDict(extra="forbid")

    objective_id: str = Field(default_factory=lambda: f"obj-{uuid.uuid4().hex[:8]}")
    description: str = Field(..., min_length=10, description="Bounded safety objective description")
    target_finding_type: str = Field(..., description="Source finding type addressed")
    target_control_id: Optional[str] = Field(None, description="Impacted safety control ID")
    bounded_failure_mode: str = Field(..., min_length=5, description="Specific failure mode to reduce/prevent")
    is_evidence_testable: bool = Field(True, description="Whether objective can be validated with evidence")


class EffectivenessCriterion(BaseModel):
    """Predefined metric or state criterion for effectiveness evaluation."""

    model_config = ConfigDict(extra="forbid")

    criterion_id: str = Field(default_factory=lambda: f"crit-{uuid.uuid4().hex[:8]}")
    category: EffectivenessCriterionCategory = Field(...)
    metric_name: str = Field(..., description="Name of the metric or check")
    description: str = Field(..., description="Description of the expected behavior")
    expected_threshold: Optional[float] = Field(None, description="Numeric target threshold (e.g. 0.99 for 99%)")
    expected_state: Optional[str] = Field(None, description="Expected state string (e.g. 'CONFORMANT')")
    operator: str = Field(">=", description="Comparison operator: '>=', '<=', '==', '!=', 'DECREASE', 'MATCH'")
    unit: Optional[str] = Field(None, description="Unit of measurement")
    observation_period_hours: Optional[int] = Field(24, description="Required observation duration in hours")
    min_sample_size: Optional[int] = Field(1, description="Minimum events/sample size required")
    evaluation_policy_id: Optional[str] = Field(None, description="Policy rule reference")


class ObservationWindow(BaseModel):
    """Observation window parameters."""

    model_config = ConfigDict(extra="forbid")

    window_type: ObservationWindowType = Field(ObservationWindowType.FIXED_DURATION)
    duration_hours: Optional[int] = Field(24, description="Duration in hours for fixed/rolling windows")
    min_event_count: Optional[int] = Field(None, description="Minimum count of executions required")
    start_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    end_time: Optional[datetime] = Field(None, description="Window closing timestamp")
    is_closed: bool = Field(False, description="Whether the window has formally closed")


class BaselineMeasurement(BaseModel):
    """Pre-action baseline context for comparative evaluation."""

    model_config = ConfigDict(extra="forbid")

    baseline_id: str = Field(default_factory=lambda: f"base-{uuid.uuid4().hex[:8]}")
    time_range_start: datetime = Field(...)
    time_range_end: datetime = Field(...)
    metric_name: str = Field(...)
    baseline_value: float = Field(...)
    sample_size: int = Field(..., ge=0)
    scope: EffectivenessScope = Field(...)
    version: str = Field("v1")


class PostActionEvidenceItem(BaseModel):
    """Normalized evidence record from authoritative subsystems."""

    model_config = ConfigDict(extra="forbid")

    evidence_id: str = Field(default_factory=lambda: f"evi-{uuid.uuid4().hex[:8]}")
    source_system: str = Field(..., description="Authoritative subsystem (e.g. Phase 18, Phase 48, Phase 52)")
    source_id: str = Field(..., description="Subsystem specific identifier")
    source_version: Optional[str] = Field(None, description="Version of source item")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    scope: EffectivenessScope = Field(...)
    evidence_type: str = Field(..., description="Classification of evidence data")
    quality_state: EvidenceQualityState = Field(EvidenceQualityState.COMPLETE)
    provenance: Dict[str, Any] = Field(default_factory=dict, description="Provenance audit metadata")
    data_payload: Dict[str, Any] = Field(default_factory=dict, description="Evidence payload without raw PHI")


class ConfoundingChange(BaseModel):
    """Environmental or operational change during observation window."""

    model_config = ConfigDict(extra="forbid")

    change_id: str = Field(default_factory=lambda: f"cnf-{uuid.uuid4().hex[:8]}")
    change_type: str = Field(..., description="DEPLOYMENT, CONFIG_CHANGE, PROVIDER_OUTAGE, POLICY_UPDATE")
    description: str = Field(...)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    potential_impact: str = Field(...)


class ExpectedVsObservedComparison(BaseModel):
    """Comparison result of expected criterion vs observed post-action state."""

    model_config = ConfigDict(extra="forbid")

    criterion_id: str = Field(...)
    metric_name: str = Field(...)
    expected_target: str = Field(...)
    observed_value: Any = Field(...)
    numerator: Optional[float] = Field(None)
    denominator: Optional[float] = Field(None)
    unit: Optional[str] = Field(None)
    baseline_value: Optional[float] = Field(None)
    is_conforming: bool = Field(False)
    difference_description: Optional[str] = Field(None)
    confounding_factors: List[str] = Field(default_factory=list)
    uncertainty_level: UncertaintyLevel = Field(UncertaintyLevel.LOW)


class HumanReviewRecord(BaseModel):
    """Record of human oversight review on effectiveness assessment."""

    model_config = ConfigDict(extra="forbid")

    review_id: str = Field(default_factory=lambda: f"rev-{uuid.uuid4().hex[:8]}")
    reviewer_id: str = Field(...)
    reviewer_role: str = Field(...)
    decision: HumanReviewOutcome = Field(...)
    rationale: str = Field(..., min_length=10)
    limitations: Optional[str] = Field(None)
    evidence_references: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RoutingRecord(BaseModel):
    """Closed-loop feedback dispatch record to downstream phases."""

    model_config = ConfigDict(extra="forbid")

    routing_id: str = Field(default_factory=lambda: f"rt-{uuid.uuid4().hex[:8]}")
    destination_phase: str = Field(..., description="Phase 52, Phase 53, Phase 50, Phase 51, Phase 49, Phase 54")
    signal_type: str = Field(...)
    payload_summary: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = Field("SENT")


# ---------------------------------------------------------------------------
# Aggregate Evaluation Record
# ---------------------------------------------------------------------------


class EffectivenessEvaluationRecord(BaseModel):
    """Authoritative aggregate evaluation record."""

    model_config = ConfigDict(extra="forbid")

    evaluation_id: str = Field(default_factory=lambda: f"eff-{uuid.uuid4().hex[:12]}")
    action_id: str = Field(..., description="Referenced Phase 54 safety action ID")
    scope: EffectivenessScope = Field(...)
    lifecycle_state: EffectivenessLifecycleState = Field(EffectivenessLifecycleState.COMPLETION_RECEIVED)
    effectiveness_state: EffectivenessState = Field(EffectivenessState.NOT_EVALUATED)
    safety_objective: SafetyObjective = Field(...)
    criteria: List[EffectivenessCriterion] = Field(default_factory=list)
    observation_window: ObservationWindow = Field(...)
    baseline: Optional[BaselineMeasurement] = Field(None)
    evidence_items: List[PostActionEvidenceItem] = Field(default_factory=list)
    comparisons: List[ExpectedVsObservedComparison] = Field(default_factory=list)
    confounding_changes: List[ConfoundingChange] = Field(default_factory=list)
    reviews: List[HumanReviewRecord] = Field(default_factory=list)
    routings: List[RoutingRecord] = Field(default_factory=list)
    version: int = Field(1)
    is_sustained: bool = Field(False)
    regression_detected: bool = Field(False)
    requires_human_review: bool = Field(False)
    created_by: str = Field(...)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    closed_at: Optional[datetime] = Field(None)
    reopened_count: int = Field(0)


# ---------------------------------------------------------------------------
# API Request & Response Schemas
# ---------------------------------------------------------------------------


class CreateEvaluationRequest(BaseModel):
    """Request payload to initiate effectiveness evaluation."""

    model_config = ConfigDict(extra="forbid")

    action_id: str = Field(...)
    scope: Optional[EffectivenessScope] = Field(None)
    safety_objective: Optional[SafetyObjective] = Field(None)
    criteria: Optional[List[EffectivenessCriterion]] = Field(None)
    observation_window_type: Optional[ObservationWindowType] = Field(None)
    duration_hours: Optional[int] = Field(24, ge=1)
    min_event_count: Optional[int] = Field(None, ge=1)
    idempotency_key: Optional[str] = Field(None)


class CollectEvidenceRequest(BaseModel):
    """Request payload to submit post-action observations."""

    model_config = ConfigDict(extra="forbid")

    evidence_items: List[PostActionEvidenceItem] = Field(default_factory=list)
    source_system: Optional[str] = Field(None)
    confounding_changes: Optional[List[ConfoundingChange]] = Field(None)


class FinalizeEvaluationRequest(BaseModel):
    """Request payload to finalize effectiveness determination."""

    model_config = ConfigDict(extra="forbid")

    reassess_if_needed: bool = Field(True)


class SubmitReviewRequest(BaseModel):
    """Request payload for human oversight decision."""

    model_config = ConfigDict(extra="forbid")

    decision: HumanReviewOutcome = Field(...)
    rationale: str = Field(..., min_length=10)
    limitations: Optional[str] = Field(None)
    is_ai_agent: bool = Field(False, description="Flag indicating if caller is an AI agent")


class AcceptEvaluationRequest(BaseModel):
    """Request payload to accept evaluated effectiveness."""

    model_config = ConfigDict(extra="forbid")

    rationale: str = Field(..., min_length=10)
    limitations: Optional[str] = Field(None)


class RejectEvaluationRequest(BaseModel):
    """Request payload to reject evaluated effectiveness."""

    model_config = ConfigDict(extra="forbid")

    rationale: str = Field(..., min_length=10)


class ReassessmentRequest(BaseModel):
    """Request payload to request formal reassessment."""

    model_config = ConfigDict(extra="forbid")

    reason: str = Field(..., min_length=10)
    additional_context: Optional[Dict[str, Any]] = Field(None)


class ReopenEvaluationRequest(BaseModel):
    """Request payload to reopen closed/monitoring evaluation."""

    model_config = ConfigDict(extra="forbid")

    reason: str = Field(..., min_length=10)
    new_evidence: Optional[List[PostActionEvidenceItem]] = Field(None)


class ReanalysisRequest(BaseModel):
    """Request payload to trigger batch reanalysis."""

    model_config = ConfigDict(extra="forbid")

    evaluation_ids: Optional[List[str]] = Field(None)
    reason: str = Field(..., min_length=10)


class EvaluationStatusResponse(BaseModel):
    """Status summary response."""

    model_config = ConfigDict(extra="forbid")

    evaluation_id: str
    action_id: str
    lifecycle_state: EffectivenessLifecycleState
    effectiveness_state: EffectivenessState
    is_sustained: bool
    regression_detected: bool
    requires_human_review: bool
    version: int
    updated_at: datetime


class EvaluationEvidenceResponse(BaseModel):
    """Evidence details response."""

    model_config = ConfigDict(extra="forbid")

    evaluation_id: str
    evidence_count: int
    evidence_items: List[PostActionEvidenceItem]
    confounding_changes: List[ConfoundingChange]


class EvaluationCriteriaResponse(BaseModel):
    """Criteria details response."""

    model_config = ConfigDict(extra="forbid")

    evaluation_id: str
    safety_objective: SafetyObjective
    criteria: List[EffectivenessCriterion]
    observation_window: ObservationWindow
    baseline: Optional[BaselineMeasurement]


class EvaluationHistoryResponse(BaseModel):
    """History and review records response."""

    model_config = ConfigDict(extra="forbid")

    evaluation_id: str
    reviews: List[HumanReviewRecord]
    routings: List[RoutingRecord]
    reopened_count: int
    created_at: datetime
    updated_at: datetime
    closed_at: Optional[datetime]


class EvaluationComparisonResponse(BaseModel):
    """Comparison of expected vs observed state."""

    model_config = ConfigDict(extra="forbid")

    evaluation_id: str
    comparisons: List[ExpectedVsObservedComparison]
    confounding_changes: List[ConfoundingChange]


class EvaluationEffectivenessResponse(BaseModel):
    """Effectiveness determination response."""

    model_config = ConfigDict(extra="forbid")

    evaluation_id: str
    action_id: str
    effectiveness_state: EffectivenessState
    lifecycle_state: EffectivenessLifecycleState
    is_sustained: bool
    regression_detected: bool
    causality_disclaimer: str = (
        "Observed post-action metric improvement does not establish causal proof "
        "or eliminate residual clinical risk."
    )
    comparisons_summary: Dict[str, Any]
