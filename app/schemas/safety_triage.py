"""Phase 60: Clinical Safety Surveillance Analysis, Signal Triage & Governed Risk Escalation Schemas.

Non-Negotiable Architectural Invariants:
- SIGNAL != INCIDENT
- SIGNAL != HARM
- SIGNAL != ROOT CAUSE
- SIGNAL SEVERITY != PATIENT SEVERITY
- ANOMALY != CAUSALITY
- RISK INDICATOR != CONFIRMED RISK
- ESCALATION != CONFIRMED HARM
- PRIORITY != CLINICAL URGENCY
- AI CLASSIFICATION != GOVERNED DECISION
- AUTOMATED TRIAGE != AUTONOMOUS CLINICAL ACTION
- ROUTING DECISION != SAFETY DETERMINATION
- NO SIGNAL != NO RISK
- UNKNOWN != LOW RISK
- INSUFFICIENT_DATA != NORMAL
- CONFLICTED_EVIDENCE != SAFE
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TriageLifecycleState(str, Enum):
    """Lifecycle states of surveillance signal triage."""

    RECEIVED = "RECEIVED"
    VALIDATING = "VALIDATING"
    VALID = "VALID"
    TRIAGE_IN_PROGRESS = "TRIAGE_IN_PROGRESS"
    CLASSIFIED = "CLASSIFIED"
    SEVERITY_EVALUATED = "SEVERITY_EVALUATED"
    ROUTING_REQUIRED = "ROUTING_REQUIRED"
    ROUTED = "ROUTED"
    AWAITING_OUTCOME = "AWAITING_OUTCOME"
    RESOLVED = "RESOLVED"

    # Alternative / Branching States
    INVALID = "INVALID"
    DUPLICATE = "DUPLICATE"
    CONFLICTED = "CONFLICTED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    ESCALATION_REQUIRED = "ESCALATION_REQUIRED"
    REASSESSMENT_REQUIRED = "REASSESSMENT_REQUIRED"
    REOPEN_REQUIRED = "REOPEN_REQUIRED"
    INCIDENT_ROUTING_REQUIRED = "INCIDENT_ROUTING_REQUIRED"
    ASSURANCE_ROUTING_REQUIRED = "ASSURANCE_ROUTING_REQUIRED"
    EFFECTIVENESS_ROUTING_REQUIRED = "EFFECTIVENESS_ROUTING_REQUIRED"
    GOVERNANCE_ROUTING_REQUIRED = "GOVERNANCE_ROUTING_REQUIRED"
    ACTION_ROUTING_REQUIRED = "ACTION_ROUTING_REQUIRED"
    BLOCKED = "BLOCKED"
    STALE = "STALE"


class SignalClassification(str, Enum):
    """Governed operational and safety signal categories."""

    TECHNICAL = "TECHNICAL"
    SAFETY_CONTROL = "SAFETY_CONTROL"
    DATA_INTEGRITY = "DATA_INTEGRITY"
    PRIVACY = "PRIVACY"
    SECURITY = "SECURITY"
    WORKFLOW = "WORKFLOW"
    PROVIDER = "PROVIDER"
    CONFIGURATION = "CONFIGURATION"
    VERSION = "VERSION"
    EFFECTIVENESS = "EFFECTIVENESS"
    ASSURANCE = "ASSURANCE"
    CLINICAL_SAFETY_REFERENCE = "CLINICAL_SAFETY_REFERENCE"
    USER_REPORTED = "USER_REPORTED"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    UNKNOWN = "UNKNOWN"


class GovernedSignalSeverity(str, Enum):
    """Governed operational/routing severity levels.

    Note: Governed signal severity is strictly separated from clinical patient harm/injury.
    """

    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"


class UncertaintyState(str, Enum):
    """Evidence completeness and certainty quantification."""

    LOW_UNCERTAINTY = "LOW_UNCERTAINTY"
    MODERATE_UNCERTAINTY = "MODERATE_UNCERTAINTY"
    HIGH_UNCERTAINTY = "HIGH_UNCERTAINTY"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    CONFLICTED_EVIDENCE = "CONFLICTED_EVIDENCE"
    UNKNOWN = "UNKNOWN"


class EscalationRoutingPriority(str, Enum):
    """System-routing urgency priorities (distinct from clinical emergency triage)."""

    ROUTINE = "ROUTINE"
    REVIEW = "REVIEW"
    HIGH_PRIORITY_REVIEW = "HIGH_PRIORITY_REVIEW"
    URGENT_GOVERNANCE_REVIEW = "URGENT_GOVERNANCE_REVIEW"
    CRITICAL_ESCALATION = "CRITICAL_ESCALATION"
    UNKNOWN_PRIORITY = "UNKNOWN_PRIORITY"


class RoutingDestination(str, Enum):
    """Authoritative downstream phases for signal resolution."""

    CONTINUE_MONITORING = "CONTINUE_MONITORING"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    PHASE_58_REASSESSMENT = "PHASE_58_REASSESSMENT"
    PHASE_58_REOPEN_REVIEW = "PHASE_58_REOPEN_REVIEW"
    PHASE_49_INCIDENT_ROUTING = "PHASE_49_INCIDENT_ROUTING"
    PHASE_52_ASSURANCE_REVIEW = "PHASE_52_ASSURANCE_REVIEW"
    PHASE_55_EFFECTIVENESS_REVIEW = "PHASE_55_EFFECTIVENESS_REVIEW"
    PHASE_51_GOVERNANCE_REVIEW = "PHASE_51_GOVERNANCE_REVIEW"
    PHASE_54_CONTROLLED_ACTION = "PHASE_54_CONTROLLED_ACTION"
    PHASE_50_LEARNING = "PHASE_50_LEARNING"
    PHASE_56_IMPROVEMENT = "PHASE_56_IMPROVEMENT"
    MULTI_ROUTE = "MULTI_ROUTE"
    BLOCKED = "BLOCKED"


class HumanTriageReviewDecision(str, Enum):
    """Authorized human reviewer decisions."""

    ACKNOWLEDGE = "ACKNOWLEDGE"
    REQUEST_MORE_EVIDENCE = "REQUEST_MORE_EVIDENCE"
    CONTINUE = "CONTINUE"
    ESCALATE = "ESCALATE"
    REASSESS = "REASSESS"
    REOPEN_REVIEW = "REOPEN_REVIEW"
    ROUTE_TO_INCIDENT = "ROUTE_TO_INCIDENT"
    ROUTE_TO_ASSURANCE = "ROUTE_TO_ASSURANCE"
    ROUTE_TO_EFFECTIVENESS = "ROUTE_TO_EFFECTIVENESS"
    ROUTE_TO_GOVERNANCE = "ROUTE_TO_GOVERNANCE"
    ROUTE_TO_ACTION = "ROUTE_TO_ACTION"
    REJECT_CLASSIFICATION = "REJECT_CLASSIFICATION"


# ---------------------------------------------------------------------------
# Scope & Supporting Models
# ---------------------------------------------------------------------------


class TriageScope(BaseModel):
    """Explicit scope for signal context validation."""

    model_config = ConfigDict(extra="allow")

    environment: str = Field("production")
    organization_id: str = Field(...)
    facility_id: Optional[str] = Field(None)
    department_id: Optional[str] = Field(None)
    department: Optional[str] = Field(None)
    workflow: Optional[str] = Field(None)
    safety_control_id: Optional[str] = Field(None)
    tenant: Optional[str] = Field(None)
    provider: Optional[str] = Field(None)


class TriageSignalItem(BaseModel):
    """Individual signal linked into triage evaluation."""

    model_config = ConfigDict(extra="allow")

    signal_id: str = Field(...)
    source: str = Field("Phase 59")
    source_record_id: Optional[str] = Field(None)
    signal_type: str = Field(...)
    severity: str = Field("MEDIUM")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    scope: Dict[str, Any] = Field(default_factory=dict)
    version: str = Field("v1.0.0")
    provenance: Dict[str, Any] = Field(default_factory=dict)
    is_duplicate: bool = Field(False)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TriageEvidenceItem(BaseModel):
    """Traceable evidence reference supporting triage."""

    model_config = ConfigDict(extra="allow")

    evidence_id: str = Field(default_factory=lambda: f"evi-{uuid.uuid4().hex[:8]}")
    evidence_type: str = Field(...)
    source_phase: str = Field(...)
    reference_id: str = Field(...)
    description: str = Field(...)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RoutingDecisionRecord(BaseModel):
    """Explicit, auditable routing decision to an authoritative phase."""

    model_config = ConfigDict(extra="allow")

    route_id: str = Field(default_factory=lambda: f"rou-{uuid.uuid4().hex[:8]}")
    destination: RoutingDestination = Field(...)
    target_phase: str = Field(..., description="Target phase e.g. Phase 49, Phase 51, Phase 52, Phase 54, Phase 58")
    reason: str = Field(..., min_length=5)
    applicable_rule: str = Field("GOV-ROUTING-DEFAULT")
    requires_human_review: bool = Field(False)
    routed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = Field("ROUTED", description="PENDING, ROUTED, COMPLETED, REJECTED")


class TriageReviewRecord(BaseModel):
    """Audit record of human supervisor triage review."""

    model_config = ConfigDict(extra="allow")

    review_id: str = Field(default_factory=lambda: f"trv-{uuid.uuid4().hex[:8]}")
    reviewer_id: str = Field(...)
    reviewer_role: str = Field(...)
    decision: HumanTriageReviewDecision = Field(...)
    rationale: str = Field(..., min_length=5)
    reviewed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TriageHistoryEntry(BaseModel):
    """Immutable transition audit entry."""

    model_config = ConfigDict(extra="allow")

    entry_id: str = Field(default_factory=lambda: f"ths-{uuid.uuid4().hex[:8]}")
    from_state: str = Field(...)
    to_state: str = Field(...)
    action: str = Field(...)
    actor_id: str = Field(...)
    actor_role: str = Field(...)
    reason: Optional[str] = Field(None)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Aggregate Root
# ---------------------------------------------------------------------------


class SafetyTriageRecord(BaseModel):
    """Authoritative surveillance signal triage context."""

    model_config = ConfigDict(extra="allow")

    triage_id: str = Field(default_factory=lambda: f"trg-{uuid.uuid4().hex[:12]}")
    primary_signal_id: str = Field(...)
    monitoring_id: Optional[str] = Field(None)
    verification_id: Optional[str] = Field(None)
    change_id: Optional[str] = Field(None)
    rollout_id: Optional[str] = Field(None)
    organization_id: str = Field(...)
    scope: TriageScope = Field(...)
    version: str = Field("v1.0.0")
    lifecycle_state: TriageLifecycleState = Field(TriageLifecycleState.RECEIVED)
    classification: SignalClassification = Field(SignalClassification.UNKNOWN)
    governed_severity: GovernedSignalSeverity = Field(GovernedSignalSeverity.UNKNOWN)
    uncertainty_state: UncertaintyState = Field(UncertaintyState.UNKNOWN)
    priority: EscalationRoutingPriority = Field(EscalationRoutingPriority.UNKNOWN_PRIORITY)
    signals: List[TriageSignalItem] = Field(default_factory=list)
    evidence: List[TriageEvidenceItem] = Field(default_factory=list)
    routing_decisions: List[RoutingDecisionRecord] = Field(default_factory=list)
    reviews: List[TriageReviewRecord] = Field(default_factory=list)
    history: List[TriageHistoryEntry] = Field(default_factory=list)
    requires_human_review: bool = Field(False)
    is_escalated: bool = Field(False)
    reopen_triggered: bool = Field(False)
    notes: Optional[str] = Field(None)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_by: str = Field(...)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# API Request & Response Models
# ---------------------------------------------------------------------------


class CreateTriageRequest(BaseModel):
    """Payload to initiate safety signal triage."""

    model_config = ConfigDict(extra="ignore")

    triage_id: Optional[str] = Field(None)
    primary_signal_id: str = Field(...)
    monitoring_id: Optional[str] = Field(None)
    verification_id: Optional[str] = Field(None)
    change_id: Optional[str] = Field(None)
    rollout_id: Optional[str] = Field(None)
    version: Optional[str] = Field("v1.0.0")
    scope: TriageScope = Field(...)
    signal_data: Optional[Dict[str, Any]] = Field(None)
    related_signals: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    evidence_items: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    idempotency_key: Optional[str] = Field(None)


class ClassifySignalRequest(BaseModel):
    """Payload to classify the signal into a governed category."""

    model_config = ConfigDict(extra="ignore")

    classification: Optional[SignalClassification] = Field(None)
    rationale: Optional[str] = Field(None)
    is_ai_agent: bool = Field(False)
    ai_metadata: Optional[Dict[str, Any]] = Field(None)


class EvaluateSeverityRequest(BaseModel):
    """Payload to evaluate governed severity and uncertainty."""

    model_config = ConfigDict(extra="ignore")

    force_reevaluation: bool = Field(False)
    additional_evidence: Optional[List[Dict[str, Any]]] = Field(default_factory=list)


class EvaluateTriageRequest(BaseModel):
    """Payload to run end-to-end triage evaluation."""

    model_config = ConfigDict(extra="ignore")

    force_reevaluation: bool = Field(False)


class SubmitTriageReviewRequest(BaseModel):
    """Payload for human surveillance reviewer decision."""

    model_config = ConfigDict(extra="ignore")

    decision: HumanTriageReviewDecision = Field(...)
    rationale: str = Field(..., min_length=5)
    routing_destination: Optional[RoutingDestination] = Field(None)
    is_ai_agent: bool = Field(False)
    ai_metadata: Optional[Dict[str, Any]] = Field(None)


class ExecuteRoutingRequest(BaseModel):
    """Payload to execute authorized routing."""

    model_config = ConfigDict(extra="ignore")

    destination: RoutingDestination = Field(...)
    reason: str = Field(..., min_length=5)
    target_phase: Optional[str] = Field(None)


class RequestTriageReassessmentRequest(BaseModel):
    """Payload to request formal reassessment."""

    model_config = ConfigDict(extra="ignore")

    reason: str = Field(..., min_length=5)


class ReanalysisTriageRequest(BaseModel):
    """Payload for batch triage reanalysis."""

    model_config = ConfigDict(extra="ignore")

    triage_ids: Optional[List[str]] = Field(None)
    reason: Optional[str] = Field("Periodic governed triage reanalysis")


class TriageStatusResponse(BaseModel):
    """Status summary response."""

    model_config = ConfigDict(extra="allow")

    triage_id: str
    primary_signal_id: str
    lifecycle_state: TriageLifecycleState
    classification: SignalClassification
    governed_severity: GovernedSignalSeverity
    uncertainty_state: UncertaintyState
    priority: EscalationRoutingPriority
    requires_human_review: bool
    is_escalated: bool
    reopen_triggered: bool
    routes_count: int
    updated_at: datetime


class TriageEvaluationResponse(BaseModel):
    """End-to-end evaluation response."""

    model_config = ConfigDict(extra="allow")

    triage_id: str
    lifecycle_state: TriageLifecycleState
    classification: SignalClassification
    governed_severity: GovernedSignalSeverity
    uncertainty_state: UncertaintyState
    priority: EscalationRoutingPriority
    requires_human_review: bool
    routing_decisions: List[RoutingDecisionRecord]
    escalation_reason: Optional[str] = Field(None)
