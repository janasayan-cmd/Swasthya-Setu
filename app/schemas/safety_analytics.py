"""Phase 61: Clinical Safety Surveillance Analytics, Signal Correlation & Governed Risk Intelligence Schemas.

Non-Negotiable Architectural Invariants:
- SIGNAL != INCIDENT
- SIGNAL != HARM
- SIGNAL != ROOT CAUSE
- PATTERN != CAUSALITY
- CORRELATION != CAUSATION
- TREND != CLINICAL DETERIORATION
- RISK INDICATOR != CONFIRMED RISK
- ANOMALY != SAFETY FAILURE
- RECURRENCE != ROOT CAUSE
- FREQUENCY != SEVERITY
- SYSTEM RISK != PATIENT RISK
- ANALYTICS != CLINICAL DECISION
- AI DETECTION != GOVERNED DETERMINATION
- ANALYTIC PRIORITY != CLINICAL URGENCY
- ESCALATION != CONFIRMED HARM
- UNKNOWN != LOW RISK
- INSUFFICIENT_DATA != NORMAL
- CONFLICTED_EVIDENCE != SAFE
- ABSENCE OF RISK INDICATOR != ABSENCE OF RISK
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class AnalysisLifecycleState(str, Enum):
    """Lifecycle states of longitudinal surveillance analytics runs."""

    CREATED = "CREATED"
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    TIMEOUT = "TIMEOUT"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    ESCALATION_REQUIRED = "ESCALATION_REQUIRED"
    REASSESSMENT_REQUIRED = "REASSESSMENT_REQUIRED"
    ROUTED = "ROUTED"
    SUPERSEDED = "SUPERSEDED"
    STALE = "STALE"


class AnalysisScopeType(str, Enum):
    """Permitted bounded analytical scopes."""

    SIGNAL = "SIGNAL"
    PATIENT_SAFETY_EVENT = "PATIENT_SAFETY_EVENT"
    ENCOUNTER = "ENCOUNTER"
    WORKFLOW = "WORKFLOW"
    PROVIDER = "PROVIDER"
    FACILITY = "FACILITY"
    ORGANIZATION = "ORGANIZATION"
    SAFETY_CONTROL = "SAFETY_CONTROL"
    RELEASE = "RELEASE"
    VERSION = "VERSION"
    CONFIGURATION = "CONFIGURATION"
    FEATURE_FLAG = "FEATURE_FLAG"
    MODEL_VERSION = "MODEL_VERSION"
    INTEGRATION = "INTEGRATION"
    TIME_WINDOW = "TIME_WINDOW"
    ROLLOUT = "ROLLOUT"
    CHANGE = "CHANGE"
    SYSTEM_WIDE = "SYSTEM_WIDE"


class ObservationWindowType(str, Enum):
    """Configurable surveillance observation windows."""

    LAST_24_HOURS = "LAST_24_HOURS"
    LAST_7_DAYS = "LAST_7_DAYS"
    LAST_30_DAYS = "LAST_30_DAYS"
    LAST_90_DAYS = "LAST_90_DAYS"
    LAST_180_DAYS = "LAST_180_DAYS"
    CUSTOM_WINDOW = "CUSTOM_WINDOW"


class SignalEligibilityStatus(str, Enum):
    """Evaluation status of an input signal entering Phase 61 analysis."""

    ELIGIBLE = "ELIGIBLE"
    INELIGIBLE = "INELIGIBLE"
    STALE = "STALE"
    DUPLICATE = "DUPLICATE"
    CONFLICTED = "CONFLICTED"
    INSUFFICIENT_CONTEXT = "INSUFFICIENT_CONTEXT"
    PRIVACY_RESTRICTED = "PRIVACY_RESTRICTED"
    SCOPE_MISMATCH = "SCOPE_MISMATCH"
    VERSION_MISMATCH = "VERSION_MISMATCH"
    INVALID_PROVENANCE = "INVALID_PROVENANCE"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class RecurrenceState(str, Enum):
    """Observed recurrence states across related signals."""

    NOT_RECURRING = "NOT_RECURRING"
    POSSIBLE_RECURRENCE = "POSSIBLE_RECURRENCE"
    RECURRENT = "RECURRENT"
    HIGH_RECURRENCE = "HIGH_RECURRENCE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    CONFLICTED = "CONFLICTED"


class TrendDirection(str, Enum):
    """Directional trend detected over the observation window."""

    INCREASING = "INCREASING"
    DECREASING = "DECREASING"
    STABLE = "STABLE"
    VOLATILE = "VOLATILE"
    SPIKE = "SPIKE"
    DROP = "DROP"
    PERIODIC = "PERIODIC"
    NO_TREND = "NO_TREND"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    CONFLICTED = "CONFLICTED"


class CorrelationState(str, Enum):
    """Governed correlation finding between signals."""

    CORRELATED = "CORRELATED"
    POSSIBLY_CORRELATED = "POSSIBLY_CORRELATED"
    NOT_CORRELATED = "NOT_CORRELATED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    CONFLICTED = "CONFLICTED"


class PatternClass(str, Enum):
    """Governed pattern classification."""

    REPEATED_FAILURE = "REPEATED_FAILURE"
    TEMPORAL_CLUSTER = "TEMPORAL_CLUSTER"
    VERSION_CLUSTER = "VERSION_CLUSTER"
    WORKFLOW_CLUSTER = "WORKFLOW_CLUSTER"
    FACILITY_CLUSTER = "FACILITY_CLUSTER"
    PROVIDER_CLUSTER = "PROVIDER_CLUSTER"
    INTEGRATION_CLUSTER = "INTEGRATION_CLUSTER"
    SAFETY_CONTROL_CLUSTER = "SAFETY_CONTROL_CLUSTER"
    ROLLOUT_CLUSTER = "ROLLOUT_CLUSTER"
    POST_CHANGE_PATTERN = "POST_CHANGE_PATTERN"
    RECURRENT_SIGNAL_PATTERN = "RECURRENT_SIGNAL_PATTERN"
    MULTI_DIMENSION_PATTERN = "MULTI_DIMENSION_PATTERN"
    UNKNOWN_PATTERN = "UNKNOWN_PATTERN"


class PatternLifecycleState(str, Enum):
    """Lifecycle states of a detected multi-signal pattern."""

    DETECTED = "DETECTED"
    VALIDATING = "VALIDATING"
    VALIDATED = "VALIDATED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"
    STALE = "STALE"
    CONFLICTED = "CONFLICTED"
    CLOSED = "CLOSED"


class RiskIndicatorType(str, Enum):
    """Types of emerging risk indicators warranting governed attention."""

    REPEATED_HIGH_SEVERITY_SIGNAL = "REPEATED_HIGH_SEVERITY_SIGNAL"
    INCREASING_FAILURE_RATE = "INCREASING_FAILURE_RATE"
    SAFETY_CONTROL_DEGRADATION = "SAFETY_CONTROL_DEGRADATION"
    POST_CHANGE_REGRESSION_PATTERN = "POST_CHANGE_REGRESSION_PATTERN"
    RECURRING_VERSION_SPECIFIC_PATTERN = "RECURRING_VERSION_SPECIFIC_PATTERN"
    FACILITY_CONCENTRATED_PATTERN = "FACILITY_CONCENTRATED_PATTERN"
    INTEGRATION_DEGRADATION_PATTERN = "INTEGRATION_DEGRADATION_PATTERN"
    ASSURANCE_REGRESSION_INDICATOR = "ASSURANCE_REGRESSION_INDICATOR"
    EFFECTIVENESS_REGRESSION_INDICATOR = "EFFECTIVENESS_REGRESSION_INDICATOR"
    REOPEN_PATTERN = "REOPEN_PATTERN"
    UNRESOLVED_SIGNAL_CLUSTER = "UNRESOLVED_SIGNAL_CLUSTER"
    UNKNOWN_RISK_INDICATOR = "UNKNOWN_RISK_INDICATOR"


class RiskIndicatorLifecycleState(str, Enum):
    """Lifecycle states for governed risk indicators."""

    DETECTED = "DETECTED"
    VALIDATING = "VALIDATING"
    VALIDATED = "VALIDATED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    LOW_PRIORITY_REVIEW = "LOW_PRIORITY_REVIEW"
    HIGH_PRIORITY_REVIEW = "HIGH_PRIORITY_REVIEW"
    ESCALATION_REQUIRED = "ESCALATION_REQUIRED"
    ROUTED = "ROUTED"
    MONITORING = "MONITORING"
    REASSESSMENT_REQUIRED = "REASSESSMENT_REQUIRED"
    INCIDENT_REVIEW_REQUIRED = "INCIDENT_REVIEW_REQUIRED"
    ASSURANCE_REVIEW_REQUIRED = "ASSURANCE_REVIEW_REQUIRED"
    EFFECTIVENESS_REVIEW_REQUIRED = "EFFECTIVENESS_REVIEW_REQUIRED"
    GOVERNANCE_REVIEW_REQUIRED = "GOVERNANCE_REVIEW_REQUIRED"
    ACTION_REVIEW_REQUIRED = "ACTION_REVIEW_REQUIRED"
    RESOLVED = "RESOLVED"
    REJECTED = "REJECTED"
    STALE = "STALE"
    CONFLICTED = "CONFLICTED"
    SUPERSEDED = "SUPERSEDED"


class AnalyticalUncertaintyState(str, Enum):
    """Analytical certainty and evidence sufficiency quantification."""

    LOW_UNCERTAINTY = "LOW_UNCERTAINTY"
    MODERATE_UNCERTAINTY = "MODERATE_UNCERTAINTY"
    HIGH_UNCERTAINTY = "HIGH_UNCERTAINTY"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    CONFLICTED_EVIDENCE = "CONFLICTED_EVIDENCE"
    UNKNOWN = "UNKNOWN"


class HumanAnalyticsReviewDecision(str, Enum):
    """Governed human analytics review outcomes."""

    ACKNOWLEDGE = "ACKNOWLEDGE"
    REQUEST_MORE_EVIDENCE = "REQUEST_MORE_EVIDENCE"
    CONTINUE_MONITORING = "CONTINUE_MONITORING"
    REASSESS = "REASSESS"
    ESCALATE = "ESCALATE"
    ROUTE_TO_INCIDENT = "ROUTE_TO_INCIDENT"
    ROUTE_TO_ASSURANCE = "ROUTE_TO_ASSURANCE"
    ROUTE_TO_EFFECTIVENESS = "ROUTE_TO_EFFECTIVENESS"
    ROUTE_TO_GOVERNANCE = "ROUTE_TO_GOVERNANCE"
    ROUTE_TO_ACTION = "ROUTE_TO_ACTION"
    REJECT_ANALYSIS = "REJECT_ANALYSIS"
    MARK_FALSE_PATTERN = "MARK_FALSE_PATTERN"


class AnalyticsRoutingDestination(str, Enum):
    """Authoritative downstream destinations for analytical findings."""

    CONTINUE_MONITORING = "CONTINUE_MONITORING"
    PHASE_60_REASSESSMENT = "PHASE_60_REASSESSMENT"
    PHASE_59_SURVEILLANCE = "PHASE_59_SURVEILLANCE"
    PHASE_49_INCIDENT_REVIEW = "PHASE_49_INCIDENT_REVIEW"
    PHASE_52_ASSURANCE_REVIEW = "PHASE_52_ASSURANCE_REVIEW"
    PHASE_55_EFFECTIVENESS_REVIEW = "PHASE_55_EFFECTIVENESS_REVIEW"
    PHASE_51_GOVERNANCE_REVIEW = "PHASE_51_GOVERNANCE_REVIEW"
    PHASE_54_CONTROLLED_ACTION_REVIEW = "PHASE_54_CONTROLLED_ACTION_REVIEW"
    PHASE_50_SAFETY_LEARNING = "PHASE_50_SAFETY_LEARNING"
    PHASE_56_SAFETY_IMPROVEMENT = "PHASE_56_SAFETY_IMPROVEMENT"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    MULTI_ROUTE = "MULTI_ROUTE"
    BLOCKED = "BLOCKED"


class AnalysisType(str, Enum):
    """Types of surveillance analytics performed in a run."""

    TEMPORAL = "TEMPORAL"
    RECURRENCE = "RECURRENCE"
    TREND = "TREND"
    DISTRIBUTION = "DISTRIBUTION"
    CONCENTRATION = "CONCENTRATION"
    CORRELATION = "CORRELATION"
    PATTERN = "PATTERN"
    RISK_INDICATOR = "RISK_INDICATOR"
    FULL = "FULL"


# ---------------------------------------------------------------------------
# Scope and Window Models
# ---------------------------------------------------------------------------


class AnalysisScope(BaseModel):
    """Bounded operational scope for longitudinal safety analytics."""

    model_config = ConfigDict(extra="ignore")

    scope_type: AnalysisScopeType = AnalysisScopeType.ORGANIZATION
    organization_id: str
    facility_id: Optional[str] = None
    department: Optional[str] = None
    workflow: Optional[str] = None
    safety_control_id: Optional[str] = None
    version: Optional[str] = None
    environment: str = "production"
    provider: Optional[str] = None
    integration: Optional[str] = None
    rollout_id: Optional[str] = None
    change_id: Optional[str] = None


class ObservationWindow(BaseModel):
    """Configurable surveillance observation time boundaries."""

    model_config = ConfigDict(extra="ignore")

    window_type: ObservationWindowType = ObservationWindowType.LAST_30_DAYS
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_hours: Optional[float] = 720.0  # default 30 days


# ---------------------------------------------------------------------------
# Signal & Finding Entities
# ---------------------------------------------------------------------------


class EligibleSignalReference(BaseModel):
    """Reference to an authorized Phase 60 signal evaluated for analytical inclusion."""

    model_config = ConfigDict(extra="ignore")

    signal_id: str
    triage_id: Optional[str] = None
    source: str = "Phase 60"
    provenance: Dict[str, Any] = Field(default_factory=dict)
    classification: str = "UNKNOWN"
    governed_severity: str = "UNKNOWN"
    uncertainty: str = "LOW_UNCERTAINTY"
    observed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    version: str = "v1.0.0"
    eligibility_status: SignalEligibilityStatus = SignalEligibilityStatus.ELIGIBLE
    eligibility_reason: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RecurrenceFinding(BaseModel):
    """Result of recurrence analysis on repeated signals."""

    model_config = ConfigDict(extra="ignore")

    dimension: str
    dimension_key: str
    state: RecurrenceState = RecurrenceState.NOT_RECURRING
    signal_count: int = 1
    signal_ids: List[str] = Field(default_factory=list)
    first_observed_at: Optional[datetime] = None
    last_observed_at: Optional[datetime] = None
    confidence: float = 1.0
    uncertainty: AnalyticalUncertaintyState = AnalyticalUncertaintyState.LOW_UNCERTAINTY
    notes: Optional[str] = None


class TrendFinding(BaseModel):
    """Directional trend detected over the surveillance window."""

    model_config = ConfigDict(extra="ignore")

    metric_name: str
    direction: TrendDirection = TrendDirection.STABLE
    baseline_value: float = 0.0
    observed_value: float = 0.0
    percentage_change: Optional[float] = 0.0
    observation_window_hours: float = 720.0
    confidence: float = 1.0
    uncertainty: AnalyticalUncertaintyState = AnalyticalUncertaintyState.LOW_UNCERTAINTY
    method: str = "WINDOW_RATE_COMPARISON"
    evidence_references: List[str] = Field(default_factory=list)


class DistributionFinding(BaseModel):
    """Distribution analysis across authorized non-PHI dimensions."""

    model_config = ConfigDict(extra="ignore")

    dimension: str
    counts: Dict[str, int] = Field(default_factory=dict)
    percentages: Dict[str, float] = Field(default_factory=dict)
    total_signals: int = 0


class ConcentrationFinding(BaseModel):
    """Concentration of signals within an authorized scope boundary."""

    model_config = ConfigDict(extra="ignore")

    dimension: str
    concentrated_key: str
    proportion: float = 0.0
    is_disproportionate: bool = False
    benchmark_proportion: Optional[float] = None
    analytical_note: str = (
        "Concentration indicates analytical distribution and does not establish causality."
    )


class CorrelationFinding(BaseModel):
    """Observed cross-signal correlation across shared operational attributes."""

    model_config = ConfigDict(extra="ignore")

    correlation_id: str = Field(default_factory=lambda: f"cor-{uuid.uuid4().hex[:8]}")
    signal_a_id: str
    signal_b_id: str
    dimension: str
    state: CorrelationState = CorrelationState.CORRELATED
    confidence: float = 1.0
    uncertainty: AnalyticalUncertaintyState = AnalyticalUncertaintyState.LOW_UNCERTAINTY
    evidence_summary: str = "Signals share identical operational attributes."
    analytical_note: str = (
        "Correlation indicates shared operational attributes and does not prove causation."
    )


class SafetyPatternFinding(BaseModel):
    """Detected multi-signal surveillance pattern."""

    model_config = ConfigDict(extra="ignore")

    pattern_id: str = Field(default_factory=lambda: f"pat-{uuid.uuid4().hex[:8]}")
    pattern_class: PatternClass = PatternClass.UNKNOWN_PATTERN
    lifecycle_state: PatternLifecycleState = PatternLifecycleState.DETECTED
    source_signal_ids: List[str] = Field(default_factory=list)
    dimensions: List[str] = Field(default_factory=list)
    observation_window_hours: float = 720.0
    confidence: float = 1.0
    uncertainty: AnalyticalUncertaintyState = AnalyticalUncertaintyState.LOW_UNCERTAINTY
    requires_human_review: bool = True
    evidence_references: List[str] = Field(default_factory=list)
    notes: Optional[str] = None


class SafetyRiskIndicatorFinding(BaseModel):
    """Emerging risk indicator generated from analytical surveillance findings."""

    model_config = ConfigDict(extra="ignore")

    indicator_id: str = Field(default_factory=lambda: f"ind-{uuid.uuid4().hex[:8]}")
    indicator_type: RiskIndicatorType = RiskIndicatorType.UNKNOWN_RISK_INDICATOR
    lifecycle_state: RiskIndicatorLifecycleState = RiskIndicatorLifecycleState.DETECTED
    governed_severity: str = "MODERATE"
    confidence: float = 1.0
    uncertainty: AnalyticalUncertaintyState = AnalyticalUncertaintyState.LOW_UNCERTAINTY
    warrants_governed_attention: bool = True
    associated_pattern_ids: List[str] = Field(default_factory=list)
    associated_signal_ids: List[str] = Field(default_factory=list)
    recommended_routes: List[AnalyticsRoutingDestination] = Field(default_factory=list)
    requires_human_review: bool = True
    notes: Optional[str] = None


class AnalyticalEvidenceReference(BaseModel):
    """Immutable evidence reference backing analytical conclusions."""

    model_config = ConfigDict(extra="ignore")

    evidence_id: str = Field(default_factory=lambda: f"evd-{uuid.uuid4().hex[:8]}")
    evidence_type: str
    reference_uri: str
    hash_checksum: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    description: str


class AnalyticsReviewRecord(BaseModel):
    """Human review record for governed analytical findings."""

    model_config = ConfigDict(extra="ignore")

    review_id: str = Field(default_factory=lambda: f"rev-{uuid.uuid4().hex[:8]}")
    reviewed_by: str
    reviewer_role: str
    decision: HumanAnalyticsReviewDecision
    reason: str
    resulting_routes: List[AnalyticsRoutingDestination] = Field(default_factory=list)
    reviewed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_ai_agent: bool = False


class AnalyticsRoutingRecord(BaseModel):
    """Governed routing action sending analytical finding to authoritative phase."""

    model_config = ConfigDict(extra="ignore")

    routing_id: str = Field(default_factory=lambda: f"rtg-{uuid.uuid4().hex[:8]}")
    destination: AnalyticsRoutingDestination
    status: str = "ROUTED"
    routed_by: str
    reason: str
    routed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    target_reference: Optional[str] = None
    target_phase: str = "PHASE_UNKNOWN"


class AnalysisHistoryEntry(BaseModel):
    """Immutable audit entry in the analysis lifecycle."""

    model_config = ConfigDict(extra="ignore")

    entry_id: str = Field(default_factory=lambda: f"hst-{uuid.uuid4().hex[:8]}")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    action: str
    actor_id: str
    actor_role: str
    previous_state: Optional[str] = None
    new_state: str
    details: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Primary Aggregate Record
# ---------------------------------------------------------------------------


class SafetyAnalysisRecord(BaseModel):
    """Aggregate record representing a longitudinal safety analytics run."""

    model_config = ConfigDict(extra="ignore")

    analysis_id: str = Field(default_factory=lambda: f"anl-{uuid.uuid4().hex[:10]}")
    organization_id: str
    scope: AnalysisScope
    observation_window: ObservationWindow = Field(default_factory=ObservationWindow)
    lifecycle_state: AnalysisLifecycleState = AnalysisLifecycleState.CREATED
    analysis_types: List[AnalysisType] = Field(
        default_factory=lambda: [AnalysisType.FULL]
    )

    eligible_signals: List[EligibleSignalReference] = Field(default_factory=list)
    excluded_signals: List[EligibleSignalReference] = Field(default_factory=list)

    recurrence_findings: List[RecurrenceFinding] = Field(default_factory=list)
    trend_findings: List[TrendFinding] = Field(default_factory=list)
    distribution_findings: List[DistributionFinding] = Field(default_factory=list)
    concentration_findings: List[ConcentrationFinding] = Field(default_factory=list)
    correlation_findings: List[CorrelationFinding] = Field(default_factory=list)
    pattern_findings: List[SafetyPatternFinding] = Field(default_factory=list)
    risk_indicators: List[SafetyRiskIndicatorFinding] = Field(default_factory=list)

    evidence_references: List[AnalyticalEvidenceReference] = Field(default_factory=list)
    reviews: List[AnalyticsReviewRecord] = Field(default_factory=list)
    routings: List[AnalyticsRoutingRecord] = Field(default_factory=list)
    history: List[AnalysisHistoryEntry] = Field(default_factory=list)

    overall_uncertainty: AnalyticalUncertaintyState = (
        AnalyticalUncertaintyState.LOW_UNCERTAINTY
    )
    requires_human_review: bool = False
    requires_escalation: bool = False
    requires_reassessment: bool = False

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None

    idempotency_key: Optional[str] = None
    version: str = "v1.0.0"


# ---------------------------------------------------------------------------
# API Request & Response Schemas
# ---------------------------------------------------------------------------


class CreateAnalysisRequest(BaseModel):
    """Request payload to initiate a longitudinal safety analytics run."""

    model_config = ConfigDict(extra="ignore")

    analysis_id: Optional[str] = None
    scope: Optional[AnalysisScope] = None
    observation_window: Optional[ObservationWindow] = None
    analysis_types: Optional[List[AnalysisType]] = None
    signals: Optional[List[Dict[str, Any]]] = None
    purpose: str = "SURVEILLANCE_ANALYTICS"
    idempotency_key: Optional[str] = None
    version: str = "v1.0.0"


class ExecuteAnalysisRequest(BaseModel):
    """Payload to trigger analysis pipeline calculation."""

    model_config = ConfigDict(extra="ignore")

    analysis_types: Optional[List[AnalysisType]] = None
    is_async: bool = False


class ReanalyzeRequest(BaseModel):
    """Payload to re-run analysis under updated parameters or versions."""

    model_config = ConfigDict(extra="ignore")

    reason: str
    updated_version: Optional[str] = None
    is_async: bool = False


class ReviewAnalysisRequest(BaseModel):
    """Payload for human surveillance analytics review."""

    model_config = ConfigDict(extra="ignore")

    decision: HumanAnalyticsReviewDecision
    reason: str
    resulting_routes: Optional[List[AnalyticsRoutingDestination]] = None
    is_ai: bool = False


class RouteAnalysisRequest(BaseModel):
    """Payload to route governed analytical findings to authoritative phases."""

    model_config = ConfigDict(extra="ignore")

    destinations: List[AnalyticsRoutingDestination]
    reason: str
    target_reference: Optional[str] = None


class ReassessAnalysisRequest(BaseModel):
    """Payload to request Phase 60 reassessment of source signals."""

    model_config = ConfigDict(extra="ignore")

    reason: str
    signal_ids: Optional[List[str]] = None
