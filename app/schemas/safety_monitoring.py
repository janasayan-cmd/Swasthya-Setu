"""Phase 59: Clinical Safety Post-Closure Surveillance, Reopen Triggers & Longitudinal Control Monitoring Schemas.

Non-Negotiable Distinctions:
- MONITORING != SAFETY GUARANTEE
- SIGNAL != INCIDENT
- SIGNAL != HARM
- ANOMALY != CAUSALITY
- THRESHOLD BREACH != CLINICAL HARM
- CORRELATION != CAUSATION
- REOPEN TRIGGER != CONFIRMED FAILURE
- ESCALATION != CONFIRMED INCIDENT
- ABSENCE OF SIGNAL != PROOF OF SAFETY
- AI DETECTION != HUMAN DETERMINATION
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class MonitoringLifecycleState(str, Enum):
    """Lifecycle states of post-closure surveillance."""

    REGISTERED = "REGISTERED"
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    OBSERVING = "OBSERVING"
    CHECKPOINT_PENDING = "CHECKPOINT_PENDING"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    SIGNAL_DETECTED = "SIGNAL_DETECTED"
    SIGNAL_VALIDATING = "SIGNAL_VALIDATING"
    REASSESSMENT_REQUIRED = "REASSESSMENT_REQUIRED"
    REOPEN_REQUIRED = "REOPEN_REQUIRED"
    ESCALATION_REQUIRED = "ESCALATION_REQUIRED"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"
    SUPERSEDED = "SUPERSEDED"

    # Alternative / Fault states
    FAILED = "FAILED"
    STALE = "STALE"
    CONFLICTED = "CONFLICTED"
    DEPENDENCY_UNAVAILABLE = "DEPENDENCY_UNAVAILABLE"


class MonitoringWindowType(str, Enum):
    """Window duration and measurement type."""

    TIME_BASED = "TIME_BASED"
    EVENT_BASED = "EVENT_BASED"
    SIGNAL_BASED = "SIGNAL_BASED"
    CHECKPOINT_BASED = "CHECKPOINT_BASED"


class SafetySignalType(str, Enum):
    """Normalized surveillance signal classifications."""

    ERROR_RATE_INCREASE = "ERROR_RATE_INCREASE"
    LATENCY_INCREASE = "LATENCY_INCREASE"
    SAFETY_CONTROL_FAILURE = "SAFETY_CONTROL_FAILURE"
    SAFETY_GATE_FAILURE = "SAFETY_GATE_FAILURE"
    UNEXPECTED_BEHAVIOR = "UNEXPECTED_BEHAVIOR"
    VERSION_MISMATCH = "VERSION_MISMATCH"
    CONFIGURATION_MISMATCH = "CONFIGURATION_MISMATCH"
    PROVIDER_DEGRADATION = "PROVIDER_DEGRADATION"
    DATA_INTEGRITY_SIGNAL = "DATA_INTEGRITY_SIGNAL"
    PRIVACY_SIGNAL = "PRIVACY_SIGNAL"
    SECURITY_SIGNAL = "SECURITY_SIGNAL"
    WORKFLOW_FAILURE = "WORKFLOW_FAILURE"
    ALERT_SPIKE = "ALERT_SPIKE"
    INCIDENT_REFERENCE = "INCIDENT_REFERENCE"
    EFFECTIVENESS_REGRESSION = "EFFECTIVENESS_REGRESSION"
    ASSURANCE_REGRESSION = "ASSURANCE_REGRESSION"
    USER_REPORTED_SIGNAL = "USER_REPORTED_SIGNAL"
    HUMAN_REVIEW_SIGNAL = "HUMAN_REVIEW_SIGNAL"


class ThresholdEvaluationStatus(str, Enum):
    """Evaluation status against governed surveillance thresholds."""

    NOT_TRIGGERED = "NOT_TRIGGERED"
    APPROACHING_THRESHOLD = "APPROACHING_THRESHOLD"
    THRESHOLD_REACHED = "THRESHOLD_REACHED"
    THRESHOLD_EXCEEDED = "THRESHOLD_EXCEEDED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    UNKNOWN = "UNKNOWN"
    CONFLICTED = "CONFLICTED"
    EVALUATION_FAILED = "EVALUATION_FAILED"


class CheckpointCategory(str, Enum):
    """Checkpoint categories for longitudinal monitoring."""

    INITIAL_POST_CLOSURE = "INITIAL_POST_CLOSURE"
    EARLY_OBSERVATION = "EARLY_OBSERVATION"
    MID_MONITORING = "MID_MONITORING"
    FINAL_MONITORING = "FINAL_MONITORING"
    TRIGGERED_REVIEW = "TRIGGERED_REVIEW"
    POST_REOPEN = "POST_REOPEN"
    POST_REASSESSMENT = "POST_REASSESSMENT"


class CheckpointOutcome(str, Enum):
    """Checkpoint evaluation outcome decisions."""

    PASS_CONTINUE = "PASS_CONTINUE"
    CONTINUE_WITH_MONITORING = "CONTINUE_WITH_MONITORING"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    THRESHOLD_TRIGGERED = "THRESHOLD_TRIGGERED"
    REASSESSMENT_REQUIRED = "REASSESSMENT_REQUIRED"
    REOPEN_REQUIRED = "REOPEN_REQUIRED"
    ESCALATION_REQUIRED = "ESCALATION_REQUIRED"
    PAUSED = "PAUSED"
    FAILED = "FAILED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class HumanSurveillanceReviewDecision(str, Enum):
    """Outcomes from human surveillance evaluation."""

    ACKNOWLEDGE = "ACKNOWLEDGE"
    CONTINUE = "CONTINUE"
    REQUEST_MORE_DATA = "REQUEST_MORE_DATA"
    REASSESS = "REASSESS"
    REOPEN_REVIEW = "REOPEN_REVIEW"
    ESCALATE = "ESCALATE"
    ROUTE_TO_INCIDENT = "ROUTE_TO_INCIDENT"
    ROUTE_TO_ASSURANCE = "ROUTE_TO_ASSURANCE"
    ROUTE_TO_EFFECTIVENESS = "ROUTE_TO_EFFECTIVENESS"
    ROUTE_TO_GOVERNANCE = "ROUTE_TO_GOVERNANCE"


# ---------------------------------------------------------------------------
# Scope & Supporting Models
# ---------------------------------------------------------------------------


class MonitoringScope(BaseModel):
    """Explicit scope for longitudinal surveillance."""

    model_config = ConfigDict(extra="allow")

    environment: str = Field("production")
    organization_id: str = Field(...)
    facility_id: Optional[str] = Field(None)
    department_id: Optional[str] = Field(None)
    department: Optional[str] = Field(None)
    workflow: Optional[str] = Field(None)
    target_workflows: List[str] = Field(default_factory=list)
    safety_control_id: Optional[str] = Field(None)
    target_controls: List[str] = Field(default_factory=list)


class SurveillanceSignalRecord(BaseModel):
    """Normalized surveillance signal representation."""

    model_config = ConfigDict(extra="allow")

    signal_id: str = Field(default_factory=lambda: f"sig-{uuid.uuid4().hex[:8]}")
    source: Optional[str] = Field(None)
    source_phase: Optional[str] = Field(None)
    source_record_id: str = Field(...)
    signal_type: SafetySignalType = Field(...)
    severity: str = Field("MEDIUM", description="LOW, MEDIUM, HIGH, CRITICAL")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    scope: Dict[str, Any] = Field(default_factory=dict)
    version: str = Field(...)
    provenance: Dict[str, Any] = Field(default_factory=dict)
    deduplication_key: str = Field(...)
    status: str = Field("NORMALIZED", description="NORMALIZED, VALIDATED, DISMISSED, ROUTED")
    is_duplicate: bool = Field(False)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MonitoringCheckpoint(BaseModel):
    """Discrete longitudinal surveillance checkpoint."""

    model_config = ConfigDict(extra="allow")

    checkpoint_id: str = Field(default_factory=lambda: f"mcp-{uuid.uuid4().hex[:8]}")
    category: CheckpointCategory = Field(...)
    name: Optional[str] = Field(None)
    expected_state: Optional[str] = Field("OBSERVING_HEALTHY")
    observed_state: Optional[str] = Field(None)
    outcome: CheckpointOutcome = Field(CheckpointOutcome.PASS_CONTINUE)
    evaluated_at: Optional[datetime] = Field(None)
    evaluated_by: Optional[str] = Field(None)
    notes: Optional[str] = Field(None)


class MonitoringTriggerRecord(BaseModel):
    """Reopen or escalation trigger detected during post-closure monitoring."""

    model_config = ConfigDict(extra="allow")

    trigger_id: str = Field(default_factory=lambda: f"trg-{uuid.uuid4().hex[:8]}")
    trigger_type: str = Field(..., description="REOPEN_TRIGGER, ESCALATION_TRIGGER, REASSESSMENT_TRIGGER")
    target_destination: str = Field(..., description="Phase 58, Phase 49, Phase 51, Phase 52, Phase 55, Phase 54")
    target_phase: Optional[str] = Field("PHASE_58")
    lifecycle_state: Optional[str] = Field("REOPEN_REQUIRED")
    reason: str = Field(..., min_length=5)
    signal_references: List[str] = Field(default_factory=list)
    triggered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = Field("DETECTED", description="DETECTED, REVIEW_REQUIRED, ROUTED, DISMISSED")


class MonitoringReviewRecord(BaseModel):
    """Audit record of human surveillance review decision."""

    model_config = ConfigDict(extra="allow")

    review_id: str = Field(default_factory=lambda: f"mrv-{uuid.uuid4().hex[:8]}")
    reviewer_id: str = Field(...)
    reviewer_role: str = Field(...)
    decision: HumanSurveillanceReviewDecision = Field(...)
    rationale: Optional[str] = Field(None)
    notes: Optional[str] = Field(None)
    routing_destination: Optional[str] = Field(None)
    reviewed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MonitoringHistoryEntry(BaseModel):
    """Immutable transition audit entry."""

    model_config = ConfigDict(extra="allow")

    entry_id: str = Field(default_factory=lambda: f"mhs-{uuid.uuid4().hex[:8]}")
    from_state: str = Field(...)
    to_state: str = Field(...)
    action: str = Field(...)
    actor_id: str = Field(...)
    actor_role: str = Field(...)
    reason: Optional[str] = Field(None)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Aggregate Record
# ---------------------------------------------------------------------------


class SafetyMonitoringRecord(BaseModel):
    """Authoritative post-closure surveillance context."""

    model_config = ConfigDict(extra="allow")

    monitoring_id: str = Field(default_factory=lambda: f"mon-{uuid.uuid4().hex[:12]}")
    verification_id: str = Field(..., description="Source Phase 58 verification ID")
    rollout_id: str = Field(..., description="Source Phase 57 rollout ID")
    change_id: str = Field(..., description="Source Phase 51 change ID")
    monitored_version: str = Field(...)
    application_version: Optional[str] = Field(None)
    monitoring_plan_name: Optional[str] = Field(None)
    description: Optional[str] = Field(None)
    organization_id: Optional[str] = Field(None)
    scope: MonitoringScope = Field(...)
    lifecycle_state: MonitoringLifecycleState = Field(MonitoringLifecycleState.REGISTERED)
    window_type: MonitoringWindowType = Field(MonitoringWindowType.TIME_BASED)
    window_duration_days: int = Field(30)
    window_duration_hours: Optional[int] = Field(None)
    started_at: Optional[datetime] = Field(None)
    completed_at: Optional[datetime] = Field(None)
    expires_at: Optional[datetime] = Field(None)
    observation_sources: List[str] = Field(default_factory=list)
    signals: List[SurveillanceSignalRecord] = Field(default_factory=list)
    checkpoints: List[MonitoringCheckpoint] = Field(default_factory=list)
    triggers: List[MonitoringTriggerRecord] = Field(default_factory=list)
    reviews: List[MonitoringReviewRecord] = Field(default_factory=list)
    history: List[MonitoringHistoryEntry] = Field(default_factory=list)
    thresholds: List[Dict[str, Any]] = Field(default_factory=list)
    threshold_config: Dict[str, Any] = Field(
        default_factory=lambda: {
            "error_rate_threshold": 0.05,
            "max_critical_signals": 0,
            "max_warning_signals": 5,
        }
    )
    is_paused: bool = Field(False)
    pause_reason: Optional[str] = Field(None)
    version: int = Field(1)
    created_by: str = Field(...)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# API Request & Response Models
# ---------------------------------------------------------------------------


class CreateMonitoringRequest(BaseModel):
    """Payload to register post-closure surveillance."""

    model_config = ConfigDict(extra="ignore")

    monitoring_id: Optional[str] = Field(None)
    verification_id: str = Field(...)
    rollout_id: str = Field(...)
    change_id: str = Field(...)
    monitored_version: Optional[str] = Field(None)
    application_version: Optional[str] = Field(None)
    monitoring_plan_name: Optional[str] = Field(None)
    description: Optional[str] = Field(None)
    scope: MonitoringScope = Field(...)
    window_type: Optional[MonitoringWindowType] = Field(MonitoringWindowType.TIME_BASED)
    window_duration_days: Optional[int] = Field(30)
    window_duration_hours: Optional[int] = Field(None)
    observation_sources: Optional[List[str]] = Field(default_factory=list)
    thresholds: Optional[List[Dict[str, Any]]] = Field(None)
    threshold_config: Optional[Dict[str, Any]] = Field(None)
    checkpoints: Optional[List[Dict[str, Any]]] = Field(None)
    idempotency_key: Optional[str] = Field(None)


CreateSafetyMonitoringRequest = CreateMonitoringRequest


class IngestSignalRequest(BaseModel):
    """Payload to ingest an observed surveillance signal."""

    model_config = ConfigDict(extra="ignore")

    source: Optional[str] = Field(None)
    source_phase: Optional[str] = Field(None)
    source_record_id: str = Field(...)
    signal_type: SafetySignalType = Field(...)
    severity: Optional[str] = Field("MEDIUM")
    version: Optional[str] = Field(None)
    application_version: Optional[str] = Field(None)
    scope: Optional[Dict[str, Any]] = Field(default_factory=dict)
    payload: Optional[Dict[str, Any]] = Field(default_factory=dict)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class EvaluateSurveillanceRequest(BaseModel):
    """Payload to trigger surveillance evaluation against thresholds."""

    model_config = ConfigDict(extra="ignore")

    force_reevaluation: bool = Field(False)


class RunCheckpointRequest(BaseModel):
    """Payload to run checkpoint evaluation."""

    model_config = ConfigDict(extra="ignore")

    checkpoint_id: Optional[str] = Field(None)
    category: Optional[CheckpointCategory] = Field(None)
    observed_state: Optional[str] = Field(None)
    notes: Optional[str] = Field(None)


class SubmitSurveillanceReviewRequest(BaseModel):
    """Payload for human surveillance reviewer decision."""

    model_config = ConfigDict(extra="ignore")

    decision: HumanSurveillanceReviewDecision = Field(...)
    rationale: Optional[str] = Field(None)
    notes: Optional[str] = Field(None)
    routing_destination: Optional[str] = Field(None)
    is_ai_agent: bool = Field(False, description="Flag indicating caller is AI")
    ai_metadata: Optional[Dict[str, Any]] = Field(None)


class CreateReopenReviewRequest(BaseModel):
    """Payload to generate governed reopen review for Phase 58."""

    model_config = ConfigDict(extra="ignore")

    reason: str = Field(..., min_length=5)
    signal_ids: Optional[List[str]] = Field(default_factory=list)


class RequestReassessmentRequest(BaseModel):
    """Payload to request longitudinal reassessment."""

    model_config = ConfigDict(extra="ignore")

    reason: str = Field(..., min_length=5)


class PauseMonitoringRequest(BaseModel):
    """Payload to pause surveillance."""

    model_config = ConfigDict(extra="ignore")

    reason: str = Field(..., min_length=5)


class ResumeMonitoringRequest(BaseModel):
    """Payload to resume paused surveillance."""

    model_config = ConfigDict(extra="ignore")

    rationale: Optional[str] = Field("Resuming surveillance following condition revalidation")


class CompleteMonitoringRequest(BaseModel):
    """Payload to conclude surveillance."""

    model_config = ConfigDict(extra="ignore")

    rationale: Optional[str] = Field(None)
    summary: Optional[str] = Field(None)


class ReanalysisSurveillanceRequest(BaseModel):
    """Payload for batch surveillance reanalysis."""

    model_config = ConfigDict(extra="ignore")

    monitoring_ids: Optional[List[str]] = Field(None)
    reason: Optional[str] = Field("Periodic governed surveillance reanalysis")


class MonitoringStatusResponse(BaseModel):
    """Status summary response."""

    model_config = ConfigDict(extra="allow")

    monitoring_id: str
    verification_id: str
    change_id: str
    monitored_version: str
    lifecycle_state: MonitoringLifecycleState
    is_paused: bool
    signal_count: int
    trigger_count: int
    version: int
    updated_at: datetime


class SurveillanceEvaluationResponse(BaseModel):
    """Surveillance evaluation result response."""

    model_config = ConfigDict(extra="allow")

    monitoring_id: str
    lifecycle_state: Optional[MonitoringLifecycleState] = Field(None)
    evaluation_status: ThresholdEvaluationStatus
    threshold_triggered: bool
    critical_signals_count: int
    warning_signals_count: int
    recommended_action: str
    threshold_evaluations: List[Dict[str, Any]] = Field(default_factory=list)
    active_triggers: List[MonitoringTriggerRecord] = Field(default_factory=list)
