"""Phase 56: Clinical Safety Assurance Feedback, Control Adaptation & Governed Continuous Improvement Schemas.

Non-Negotiable Distinctions:
- EFFECTIVENESS RESULT != CHANGE REQUEST
- CHANGE REQUEST != CHANGE APPROVAL
- CHANGE APPROVAL != CHANGE IMPLEMENTATION
- CHANGE IMPLEMENTATION != CHANGE VALIDATION
- CHANGE VALIDATION != EFFECTIVENESS
- CONTROL ADAPTATION != AUTOMATIC SELF-MODIFICATION
- AI RECOMMENDATION != SAFETY CHANGE
- REGRESSION != PATIENT HARM
- CONTINUOUS IMPROVEMENT != AUTONOMOUS SELF-MODIFICATION
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ImprovementSignalType(str, Enum):
    """Categorized improvement signals from post-action effectiveness & assurance."""

    EFFECTIVE_CONTROL = "EFFECTIVE_CONTROL"
    PARTIAL_EFFECTIVENESS = "PARTIAL_EFFECTIVENESS"
    NO_CLEAR_IMPROVEMENT = "NO_CLEAR_IMPROVEMENT"
    INEFFECTIVE_ACTION = "INEFFECTIVE_ACTION"
    CONTROL_DEGRADATION = "CONTROL_DEGRADATION"
    CONTROL_REGRESSION = "CONTROL_REGRESSION"
    RECURRING_FAILURE = "RECURRING_FAILURE"
    REPEATED_REASSESSMENT = "REPEATED_REASSESSMENT"
    REPEATED_INCIDENT_PATTERN = "REPEATED_INCIDENT_PATTERN"
    REPEATED_SAFETY_SIGNAL = "REPEATED_SAFETY_SIGNAL"
    EVIDENCE_GAP = "EVIDENCE_GAP"
    DATA_QUALITY_PROBLEM = "DATA_QUALITY_PROBLEM"
    CONFIGURATION_DRIFT = "CONFIGURATION_DRIFT"
    WORKFLOW_DEGRADATION = "WORKFLOW_DEGRADATION"
    PROVIDER_DEGRADATION = "PROVIDER_DEGRADATION"
    HUMAN_REVIEW_GAP = "HUMAN_REVIEW_GAP"
    POLICY_GAP = "POLICY_GAP"
    CONTROL_COVERAGE_GAP = "CONTROL_COVERAGE_GAP"
    CONTROL_DESIGN_GAP = "CONTROL_DESIGN_GAP"
    IMPLEMENTATION_GAP = "IMPLEMENTATION_GAP"
    MONITORING_GAP = "MONITORING_GAP"
    VALIDATION_GAP = "VALIDATION_GAP"
    UNEXPECTED_BEHAVIOR = "UNEXPECTED_BEHAVIOR"
    NEW_RISK_SIGNAL = "NEW_RISK_SIGNAL"


class ImprovementResponseType(str, Enum):
    """Governed response paths for continuous improvement."""

    CONTINUE_MONITORING = "CONTINUE_MONITORING"
    NO_CHANGE_REQUIRED = "NO_CHANGE_REQUIRED"
    REASSESS = "REASSESS"
    COLLECT_MORE_EVIDENCE = "COLLECT_MORE_EVIDENCE"
    CREATE_TASK = "CREATE_TASK"
    CREATE_REVIEW = "CREATE_REVIEW"
    CREATE_SAFETY_ACTION = "CREATE_SAFETY_ACTION"
    CREATE_CHANGE_REQUEST = "CREATE_CHANGE_REQUEST"
    REQUEST_GOVERNANCE_REVIEW = "REQUEST_GOVERNANCE_REVIEW"
    REQUEST_RISK_REASSESSMENT = "REQUEST_RISK_REASSESSMENT"
    REQUEST_INCIDENT_REVIEW = "REQUEST_INCIDENT_REVIEW"
    REQUEST_SAFETY_ASSURANCE = "REQUEST_SAFETY_ASSURANCE"
    REQUEST_OVERSIGHT_REPORT = "REQUEST_OVERSIGHT_REPORT"
    REQUEST_ROLLBACK_REVIEW = "REQUEST_ROLLBACK_REVIEW"
    ESCALATE = "ESCALATE"
    DEFER = "DEFER"


class SafetyChangeCategory(str, Enum):
    """Governed categories for safety control modification."""

    CONTROL_CONFIGURATION_CHANGE = "CONTROL_CONFIGURATION_CHANGE"
    SAFETY_RULE_CHANGE = "SAFETY_RULE_CHANGE"
    WORKFLOW_CHANGE = "WORKFLOW_CHANGE"
    PROVIDER_CONFIGURATION_CHANGE = "PROVIDER_CONFIGURATION_CHANGE"
    INTEGRATION_CHANGE = "INTEGRATION_CHANGE"
    DATA_VALIDATION_CHANGE = "DATA_VALIDATION_CHANGE"
    RECONCILIATION_CHANGE = "RECONCILIATION_CHANGE"
    MONITORING_CHANGE = "MONITORING_CHANGE"
    ALERT_CONFIGURATION_CHANGE = "ALERT_CONFIGURATION_CHANGE"
    HUMAN_REVIEW_CONTROL_CHANGE = "HUMAN_REVIEW_CONTROL_CHANGE"
    POLICY_CHANGE = "POLICY_CHANGE"
    FEATURE_FLAG_CHANGE = "FEATURE_FLAG_CHANGE"
    ROLLBACK = "ROLLBACK"
    DOCUMENT_PROCESSING_CONTROL_CHANGE = "DOCUMENT_PROCESSING_CONTROL_CHANGE"
    AI_GUARDRAIL_CHANGE = "AI_GUARDRAIL_CHANGE"
    NOTIFICATION_CONTROL_CHANGE = "NOTIFICATION_CONTROL_CHANGE"
    ACCESS_CONTROL_CHANGE = "ACCESS_CONTROL_CHANGE"


class ImprovementPriority(str, Enum):
    """Governed priority levels."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ImprovementLifecycleState(str, Enum):
    """Lifecycle states of continuous safety improvement opportunities."""

    SIGNAL_IDENTIFIED = "SIGNAL_IDENTIFIED"
    CLASSIFIED = "CLASSIFIED"
    ANALYZING = "ANALYZING"
    CHANGE_PROPOSED = "CHANGE_PROPOSED"
    IMPACT_ASSESSED = "IMPACT_ASSESSED"
    CHANGE_READY = "CHANGE_READY"
    GOVERNANCE_ROUTED = "GOVERNANCE_ROUTED"
    IMPLEMENTING = "IMPLEMENTING"
    VALIDATING = "VALIDATING"
    MONITORING = "MONITORING"
    CLOSED = "CLOSED"
    REOPENED = "REOPENED"
    DEFERRED = "DEFERRED"
    ESCALATED = "ESCALATED"
    CANCELLED = "CANCELLED"


class RolloutStage(str, Enum):
    """Controlled rollout stages."""

    PREPARATION = "PREPARATION"
    CANARY = "CANARY"
    LIMITED = "LIMITED"
    EXPANDED = "EXPANDED"
    FULL = "FULL"
    ROLLED_BACK = "ROLLED_BACK"
    PAUSED = "PAUSED"


class EscalationTarget(str, Enum):
    """Escalation destinations."""

    SAFETY_GOVERNANCE = "SAFETY_GOVERNANCE"
    CLINICAL_SAFETY = "CLINICAL_SAFETY"
    ENGINEERING = "ENGINEERING"
    SECURITY = "SECURITY"
    PRIVACY = "PRIVACY"
    ORGANIZATION = "ORGANIZATION"
    FACILITY = "FACILITY"
    PROVIDER = "PROVIDER"
    INCIDENT_REVIEW = "INCIDENT_REVIEW"
    RISK_REVIEW = "RISK_REVIEW"
    ASSURANCE_REVIEW = "ASSURANCE_REVIEW"
    OVERSIGHT_REVIEW = "OVERSIGHT_REVIEW"


class HumanReviewOutcome(str, Enum):
    """Review outcomes."""

    ACCEPT = "ACCEPT"
    ACCEPT_WITH_LIMITATIONS = "ACCEPT_WITH_LIMITATIONS"
    REQUEST_MORE_EVIDENCE = "REQUEST_MORE_EVIDENCE"
    REQUEST_REASSESSMENT = "REQUEST_REASSESSMENT"
    ESCALATE = "ESCALATE"
    REJECT = "REJECT"
    DEFER = "DEFER"


# ---------------------------------------------------------------------------
# Scope & Records
# ---------------------------------------------------------------------------


class ImprovementScope(BaseModel):
    """Scope of safety improvement."""

    model_config = ConfigDict(extra="forbid")

    organization_id: str = Field(..., description="Organization identifier")
    facility_id: Optional[str] = Field(None, description="Facility identifier")
    department_id: Optional[str] = Field(None, description="Department identifier")
    environment: str = Field("production", description="Operating environment")


class ImprovementEvidenceReference(BaseModel):
    """Reference to evidence item in authoritative subsystems."""

    model_config = ConfigDict(extra="forbid")

    evidence_id: str = Field(default_factory=lambda: f"evr-{uuid.uuid4().hex[:8]}")
    source_phase: str = Field(..., description="Subsystem / Phase (e.g. Phase 55, Phase 52, Phase 48)")
    source_id: str = Field(..., description="Identifier in source system")
    summary: str = Field(..., min_length=5)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ImpactAssessmentRecord(BaseModel):
    """Assessment of prospective safety change across multiple operational dimensions."""

    model_config = ConfigDict(extra="forbid")

    assessment_id: str = Field(default_factory=lambda: f"imp-{uuid.uuid4().hex[:8]}")
    safety_impact: str = Field(..., min_length=5)
    clinical_workflow_impact: str = Field(..., min_length=5)
    privacy_impact: str = Field(..., min_length=5)
    security_impact: str = Field(..., min_length=5)
    operational_impact: str = Field(..., min_length=5)
    rollback_complexity: str = Field(..., min_length=5)
    affected_controls: List[str] = Field(default_factory=list)
    assessed_by: str = Field(...)
    assessed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = Field("COMPLETED")


class ChangeDependency(BaseModel):
    """Explicit dependency prerequisite for safety change."""

    model_config = ConfigDict(extra="forbid")

    dependency_id: str = Field(default_factory=lambda: f"dep-{uuid.uuid4().hex[:8]}")
    dependency_type: str = Field(..., description="CONTROL_VERSION, POLICY_VERSION, FEATURE_FLAG, PROVIDER")
    target_name: str = Field(...)
    required_version: str = Field(...)
    current_version: str = Field(...)
    is_satisfied: bool = Field(True)


class ChangeProposalRecord(BaseModel):
    """Governed safety change proposal routing into Phase 51."""

    model_config = ConfigDict(extra="forbid")

    proposal_id: str = Field(default_factory=lambda: f"prp-{uuid.uuid4().hex[:8]}")
    improvement_id: str = Field(...)
    change_category: SafetyChangeCategory = Field(...)
    problem_statement: str = Field(..., min_length=10)
    proposed_solution: str = Field(..., min_length=10)
    expected_outcome: str = Field(..., min_length=10)
    success_criteria: List[str] = Field(default_factory=list)
    rollback_plan: str = Field(..., min_length=10)
    validation_plan: str = Field(..., min_length=10)
    observation_plan: str = Field(..., min_length=10)
    dependencies: List[ChangeDependency] = Field(default_factory=list)
    impact_assessment: Optional[ImpactAssessmentRecord] = Field(None)
    is_ready: bool = Field(False)
    phase51_change_request_id: Optional[str] = Field(None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ImprovementHistoryEntry(BaseModel):
    """Immutable transition audit entry."""

    model_config = ConfigDict(extra="forbid")

    entry_id: str = Field(default_factory=lambda: f"his-{uuid.uuid4().hex[:8]}")
    from_state: str = Field(...)
    to_state: str = Field(...)
    action: str = Field(...)
    actor_id: str = Field(...)
    actor_role: str = Field(...)
    reason: Optional[str] = Field(None)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ImprovementRoutingRecord(BaseModel):
    """Feedback routing record."""

    model_config = ConfigDict(extra="forbid")

    routing_id: str = Field(default_factory=lambda: f"rt-{uuid.uuid4().hex[:8]}")
    destination_phase: str = Field(..., description="Phase 51, 52, 53, 54, 50, 49, 48")
    signal_type: str = Field(...)
    payload_summary: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = Field("SENT")


# ---------------------------------------------------------------------------
# Aggregate Improvement Record
# ---------------------------------------------------------------------------


class SafetyImprovementRecord(BaseModel):
    """Authoritative continuous improvement record."""

    model_config = ConfigDict(extra="forbid")

    improvement_id: str = Field(default_factory=lambda: f"imp-{uuid.uuid4().hex[:12]}")
    source_evaluation_id: str = Field(..., description="Phase 55 effectiveness evaluation ID")
    source_action_id: str = Field(..., description="Phase 54 safety action ID")
    scope: ImprovementScope = Field(...)
    signal_type: ImprovementSignalType = Field(...)
    response_type: ImprovementResponseType = Field(...)
    lifecycle_state: ImprovementLifecycleState = Field(ImprovementLifecycleState.SIGNAL_IDENTIFIED)
    priority: ImprovementPriority = Field(ImprovementPriority.MEDIUM)
    is_recurring: bool = Field(False)
    recurrence_count: int = Field(0)
    is_regression: bool = Field(False)
    evidence_references: List[ImprovementEvidenceReference] = Field(default_factory=list)
    change_proposal: Optional[ChangeProposalRecord] = Field(None)
    history: List[ImprovementHistoryEntry] = Field(default_factory=list)
    routings: List[ImprovementRoutingRecord] = Field(default_factory=list)
    version: int = Field(1)
    created_by: str = Field(...)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    closed_at: Optional[datetime] = Field(None)
    reopened_count: int = Field(0)


# ---------------------------------------------------------------------------
# API Request & Response Schemas
# ---------------------------------------------------------------------------


class CreateImprovementRequest(BaseModel):
    """Request to initiate improvement tracking from an effectiveness result."""

    model_config = ConfigDict(extra="forbid")

    source_evaluation_id: str = Field(...)
    source_action_id: Optional[str] = Field(None)
    scope: Optional[ImprovementScope] = Field(None)
    signal_type: Optional[ImprovementSignalType] = Field(None)
    response_type: Optional[ImprovementResponseType] = Field(None)
    priority: Optional[ImprovementPriority] = Field(None)
    idempotency_key: Optional[str] = Field(None)


class ClassifyImprovementRequest(BaseModel):
    """Request to classify or reclassify improvement opportunity."""

    model_config = ConfigDict(extra="forbid")

    signal_type: ImprovementSignalType = Field(...)
    response_type: ImprovementResponseType = Field(...)
    priority: Optional[ImprovementPriority] = Field(None)
    rationale: str = Field(..., min_length=10)


class CreateChangeProposalRequest(BaseModel):
    """Request to formulate a governed safety change proposal."""

    model_config = ConfigDict(extra="forbid")

    change_category: SafetyChangeCategory = Field(...)
    problem_statement: str = Field(..., min_length=10)
    proposed_solution: str = Field(..., min_length=10)
    expected_outcome: str = Field(..., min_length=10)
    rollback_plan: str = Field(..., min_length=10)
    validation_plan: str = Field(..., min_length=10)
    observation_plan: str = Field(..., min_length=10)
    success_criteria: Optional[List[str]] = Field(default_factory=list)
    dependencies: Optional[List[ChangeDependency]] = Field(default_factory=list)


class RequestImpactAssessmentRequest(BaseModel):
    """Request to conduct impact assessment on change proposal."""

    model_config = ConfigDict(extra="forbid")

    safety_impact: str = Field(..., min_length=5)
    clinical_workflow_impact: str = Field(..., min_length=5)
    privacy_impact: str = Field(..., min_length=5)
    security_impact: str = Field(..., min_length=5)
    operational_impact: str = Field(..., min_length=5)
    rollback_complexity: str = Field(..., min_length=5)
    affected_controls: Optional[List[str]] = Field(default_factory=list)


class RouteGovernanceRequest(BaseModel):
    """Request to dispatch change proposal to Phase 51 governance."""

    model_config = ConfigDict(extra="forbid")

    rationale: str = Field(..., min_length=10)


class ReassessmentRequest(BaseModel):
    """Request reassessment of improvement opportunity."""

    model_config = ConfigDict(extra="forbid")

    reason: str = Field(..., min_length=10)


class EscalateRequest(BaseModel):
    """Request policy escalation."""

    model_config = ConfigDict(extra="forbid")

    target: EscalationTarget = Field(...)
    reason: str = Field(..., min_length=10)


class ReopenRequest(BaseModel):
    """Request reopening an improvement opportunity."""

    model_config = ConfigDict(extra="forbid")

    reason: str = Field(..., min_length=10)


class CloseRequest(BaseModel):
    """Request closure of an improvement opportunity."""

    model_config = ConfigDict(extra="forbid")

    rationale: str = Field(..., min_length=10)


class ReanalysisRequest(BaseModel):
    """Trigger batch reanalysis across improvement records."""

    model_config = ConfigDict(extra="forbid")

    improvement_ids: Optional[List[str]] = Field(None)
    reason: str = Field(..., min_length=10)


class ReadinessResponse(BaseModel):
    """Readiness assessment response."""

    model_config = ConfigDict(extra="forbid")

    improvement_id: str
    is_ready: bool
    opportunity_valid: bool
    evidence_sufficient: bool
    scope_valid: bool
    impact_assessed: bool
    dependencies_valid: bool
    rollback_defined: bool
    validation_defined: bool
    observation_defined: bool
    blockers: List[str]


class StatusResponse(BaseModel):
    """Lightweight status response."""

    model_config = ConfigDict(extra="forbid")

    improvement_id: str
    lifecycle_state: ImprovementLifecycleState
    signal_type: ImprovementSignalType
    response_type: ImprovementResponseType
    priority: ImprovementPriority
    is_recurring: bool
    is_regression: bool
    version: int
    updated_at: datetime
