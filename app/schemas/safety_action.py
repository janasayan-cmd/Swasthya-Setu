"""Phase 54: Clinical Safety Oversight Decision Support, Escalation & Controlled Action Orchestration Schemas.

Domain boundaries strictly enforced:
- FINDING != ACTION
- RECOMMENDATION != DECISION
- APPROVAL != EXECUTION
- EXECUTION != COMPLETION
- COMPLETION != EFFECTIVENESS
- EFFECTIVENESS != RISK ELIMINATION
- ESCALATION != INCIDENT CONFIRMATION
- TASK COMPLETION != SAFETY VALIDATION
- AI SUGGESTION != HUMAN DECISION
- Never allow autonomous diagnosis, prescription, or clinical record alteration.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class FindingSourceType(str, Enum):
    """Authoritative sources for safety oversight findings."""

    SAFETY_REPORT = "SAFETY_REPORT"                     # Phase 53
    ASSURANCE_EVALUATION = "ASSURANCE_EVALUATION"       # Phase 52
    GOVERNANCE_FINDING = "GOVERNANCE_FINDING"           # Phase 51
    LEARNING_RECOMMENDATION = "LEARNING_RECOMMENDATION" # Phase 50
    INCIDENT = "INCIDENT"                               # Phase 49
    SAFETY_GATE_FAILURE = "SAFETY_GATE_FAILURE"         # Phase 48
    DATA_QUALITY_FINDING = "DATA_QUALITY_FINDING"       # Phase 26
    CONFIGURATION_DRIFT = "CONFIGURATION_DRIFT"         # Phase 25
    MONITORING_ALERT = "MONITORING_ALERT"               # Phase 18
    DECISION_TRACE = "DECISION_TRACE"                   # Phase 47
    HUMAN_SAFETY_REPORT = "HUMAN_SAFETY_REPORT"


class ActionabilityState(str, Enum):
    """Policy-driven classification of finding actionability."""

    INFORMATIONAL = "INFORMATIONAL"
    MONITOR = "MONITOR"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    REASSESSMENT_REQUIRED = "REASSESSMENT_REQUIRED"
    CORRECTIVE_ACTION_REQUIRED = "CORRECTIVE_ACTION_REQUIRED"
    PREVENTIVE_ACTION_REQUIRED = "PREVENTIVE_ACTION_REQUIRED"
    SAFETY_CHANGE_REQUIRED = "SAFETY_CHANGE_REQUIRED"
    INCIDENT_REVIEW_REQUIRED = "INCIDENT_REVIEW_REQUIRED"
    URGENT_ESCALATION_REQUIRED = "URGENT_ESCALATION_REQUIRED"
    NO_ACTION_REQUIRED = "NO_ACTION_REQUIRED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class ActionPriority(str, Enum):
    """Action priority derived strictly from server-side policy and evidence."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ActionLifecycleState(str, Enum):
    """Governed lifecycle states of a safety action."""

    IDENTIFIED = "IDENTIFIED"
    VALIDATING = "VALIDATING"
    ACTIONABILITY_DETERMINED = "ACTIONABILITY_DETERMINED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    APPROVED = "APPROVED"
    READY = "READY"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETION_PENDING = "COMPLETION_PENDING"
    COMPLETED = "COMPLETED"
    EFFECTIVENESS_VALIDATION = "EFFECTIVENESS_VALIDATION"
    VERIFIED = "VERIFIED"
    MONITORING = "MONITORING"
    CLOSED = "CLOSED"

    # Secondary / Exceptional States
    DEFERRED = "DEFERRED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"
    SUPERSEDED = "SUPERSEDED"
    REOPENED = "REOPENED"
    ESCALATED = "ESCALATED"
    REQUIRES_REASSESSMENT = "REQUIRES_REASSESSMENT"


class ActionType(str, Enum):
    """Supported governed action categories."""

    REVIEW = "REVIEW"
    MONITOR = "MONITOR"
    RISK_REASSESSMENT = "RISK_REASSESSMENT"
    CONTROL_REVALIDATION = "CONTROL_REVALIDATION"
    CONFIGURATION_REVIEW = "CONFIGURATION_REVIEW"
    SAFETY_CHANGE = "SAFETY_CHANGE"
    PROVIDER_REVIEW = "PROVIDER_REVIEW"
    WORKFLOW_REVIEW = "WORKFLOW_REVIEW"
    DATA_QUALITY_REVIEW = "DATA_QUALITY_REVIEW"
    RECONCILIATION = "RECONCILIATION"
    CORRECTIVE_ACTION = "CORRECTIVE_ACTION"
    PREVENTIVE_ACTION = "PREVENTIVE_ACTION"
    INCIDENT_REVIEW = "INCIDENT_REVIEW"
    TASK_CREATION = "TASK_CREATION"
    WORKFLOW_EXECUTION = "WORKFLOW_EXECUTION"
    NOTIFICATION = "NOTIFICATION"
    HUMAN_ESCALATION = "HUMAN_ESCALATION"
    ADDITIONAL_EVIDENCE_COLLECTION = "ADDITIONAL_EVIDENCE_COLLECTION"
    RETEST = "RETEST"
    ROLLBACK_REVIEW = "ROLLBACK_REVIEW"


class ActionOwnerDomain(str, Enum):
    """Authorized organizational ownership domains for action execution."""

    SAFETY_GOVERNANCE = "SAFETY_GOVERNANCE"
    CLINICAL_SAFETY_TEAM = "CLINICAL_SAFETY_TEAM"
    AUTHORIZED_CLINICIAN = "AUTHORIZED_CLINICIAN"
    ORGANIZATION_ADMIN = "ORGANIZATION_ADMIN"
    FACILITY_ADMIN = "FACILITY_ADMIN"
    ENGINEERING_OWNER = "ENGINEERING_OWNER"
    SECURITY_OWNER = "SECURITY_OWNER"
    PRIVACY_OWNER = "PRIVACY_OWNER"
    INTEGRATION_PROVIDER_OWNER = "INTEGRATION_PROVIDER_OWNER"
    DATA_QUALITY_OWNER = "DATA_QUALITY_OWNER"
    WORKFLOW_OWNER = "WORKFLOW_OWNER"


class ActionApprovalDecision(str, Enum):
    """Possible outcomes of human governance review on a safety action."""

    APPROVE = "APPROVE"
    REJECT = "REJECT"
    REQUEST_MORE_EVIDENCE = "REQUEST_MORE_EVIDENCE"
    DEFER = "DEFER"
    ESCALATE = "ESCALATE"
    MODIFY = "MODIFY"


class ActionApprovalState(str, Enum):
    """Status of approval envelope."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"
    STALE = "STALE"


class ActionEffectivenessState(str, Enum):
    """Structured evaluation of whether an action restored or improved control safety."""

    NOT_EVALUATED = "NOT_EVALUATED"
    PENDING_OBSERVATION = "PENDING_OBSERVATION"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    EFFECTIVE_OBSERVED = "EFFECTIVE_OBSERVED"
    PARTIALLY_EFFECTIVE = "PARTIALLY_EFFECTIVE"
    NO_CLEAR_IMPROVEMENT = "NO_CLEAR_IMPROVEMENT"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"
    INCONCLUSIVE = "INCONCLUSIVE"


class EscalationLevel(str, Enum):
    """Policy-defined escalation routing tiers."""

    INTERNAL = "INTERNAL"
    ORGANIZATIONAL = "ORGANIZATIONAL"
    FACILITY = "FACILITY"
    CLINICAL_SAFETY = "CLINICAL_SAFETY"
    ENGINEERING = "ENGINEERING"
    SECURITY = "SECURITY"
    PRIVACY = "PRIVACY"
    PROVIDER = "PROVIDER"
    GOVERNANCE = "GOVERNANCE"
    INCIDENT_REVIEW = "INCIDENT_REVIEW"


class AIAssistanceState(str, Enum):
    """AI governance state within safety action decision support."""

    NONE = "NONE"
    AI_SUGGESTED = "AI_SUGGESTED"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"
    HUMAN_ACCEPTED = "HUMAN_ACCEPTED"
    HUMAN_MODIFIED = "HUMAN_MODIFIED"
    HUMAN_REJECTED = "HUMAN_REJECTED"


class TargetSubsystem(str, Enum):
    """Authoritative downstream subsystem that owns execution."""

    PHASE_36_TASK = "PHASE_36_TASK"
    PHASE_37_WORKFLOW = "PHASE_37_WORKFLOW"
    PHASE_48_SAFETY = "PHASE_48_SAFETY"
    PHASE_49_INCIDENT = "PHASE_49_INCIDENT"
    PHASE_50_LEARNING = "PHASE_50_LEARNING"
    PHASE_51_GOVERNANCE = "PHASE_51_GOVERNANCE"
    PHASE_52_ASSURANCE = "PHASE_52_ASSURANCE"
    PHASE_29_NOTIFICATION = "PHASE_29_NOTIFICATION"
    MANUAL_REVIEW = "MANUAL_REVIEW"


# ---------------------------------------------------------------------------
# Component Schemas
# ---------------------------------------------------------------------------


class SafetyFindingReference(BaseModel):
    """Authoritative reference to the source oversight finding."""

    model_config = ConfigDict(extra="ignore")

    source_type: FindingSourceType
    source_id: str
    source_version: Optional[str] = None
    finding_title: str
    finding_details: Optional[Dict[str, Any]] = None
    observed_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SafetyActionScope(BaseModel):
    """Bounded organizational and subsystem scope."""

    model_config = ConfigDict(extra="ignore")

    organization_id: Optional[str] = None
    facility_id: Optional[str] = None
    department_id: Optional[str] = None
    control_id: Optional[str] = None
    workflow_id: Optional[str] = None


class AIAssistanceMetadata(BaseModel):
    """Traceability for AI-assisted decision support."""

    model_config = ConfigDict(extra="ignore")

    model_name: Optional[str] = None
    model_version: Optional[str] = None
    suggested_action_type: Optional[ActionType] = None
    suggested_priority: Optional[ActionPriority] = None
    rationale: Optional[str] = None
    generated_at: Optional[datetime] = None
    state: AIAssistanceState = AIAssistanceState.NONE


class ActionApprovalRecord(BaseModel):
    """Explicit human approval record required prior to action execution."""

    model_config = ConfigDict(extra="ignore")

    approval_id: str = Field(default_factory=lambda: f"appr-{uuid.uuid4().hex[:12]}")
    action_version: int
    approver_id: str
    approver_role: str
    decision: ActionApprovalDecision
    reason: str
    limitations: Optional[str] = None
    approved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    state: ActionApprovalState = ActionApprovalState.APPROVED


class ActionAssignmentRecord(BaseModel):
    """Assignment record defining authorized operational ownership."""

    model_config = ConfigDict(extra="ignore")

    assignment_id: str = Field(default_factory=lambda: f"asgn-{uuid.uuid4().hex[:12]}")
    owner_id: str
    owner_role: str
    owner_domain: ActionOwnerDomain
    assigned_by_id: str
    assigned_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    accepted_at: Optional[datetime] = None
    assignment_notes: Optional[str] = None


class ActionEscalationRecord(BaseModel):
    """Record of policy-driven escalation."""

    model_config = ConfigDict(extra="ignore")

    escalation_id: str = Field(default_factory=lambda: f"esc-{uuid.uuid4().hex[:12]}")
    escalation_level: EscalationLevel
    escalated_by_id: str
    reason: str
    urgency_justification: Optional[str] = None
    escalated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_urgent: bool = False


class ActionEffectivenessRecord(BaseModel):
    """Evaluation of whether completed action restored or improved safety."""

    model_config = ConfigDict(extra="ignore")

    effectiveness_id: str = Field(default_factory=lambda: f"eff-{uuid.uuid4().hex[:12]}")
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    evaluator_id: str
    effectiveness_state: ActionEffectivenessState = ActionEffectivenessState.NOT_EVALUATED
    assurance_evaluation_id: Optional[str] = None  # Link to Phase 52 closed loop
    evidence_summary: Optional[str] = None
    notes: Optional[str] = None


class ActionHistoryEntry(BaseModel):
    """Immutable audit trail entry for action transitions."""

    model_config = ConfigDict(extra="ignore")

    entry_id: str = Field(default_factory=lambda: f"hist-{uuid.uuid4().hex[:12]}")
    action_id: str
    version: int
    previous_state: ActionLifecycleState
    new_state: ActionLifecycleState
    actor_id: str
    actor_role: str
    transition_reason: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Main Entity Schema
# ---------------------------------------------------------------------------


class SafetyActionRecord(BaseModel):
    """Governed safety action record orchestrating responses to oversight findings."""

    model_config = ConfigDict(extra="ignore")

    action_id: str = Field(default_factory=lambda: f"act-{uuid.uuid4().hex[:12]}")
    version: int = 1
    material_version: int = 1
    title: str
    description: str
    action_type: ActionType
    lifecycle_state: ActionLifecycleState = ActionLifecycleState.IDENTIFIED
    actionability: ActionabilityState = ActionabilityState.REVIEW_REQUIRED
    priority: ActionPriority = ActionPriority.MEDIUM
    is_urgent: bool = False
    
    # Scope & Finding
    scope: SafetyActionScope = Field(default_factory=SafetyActionScope)
    finding: SafetyFindingReference
    target_subsystem: TargetSubsystem = TargetSubsystem.MANUAL_REVIEW

    # Governance & Execution components
    approval: Optional[ActionApprovalRecord] = None
    assignment: Optional[ActionAssignmentRecord] = None
    escalation: Optional[ActionEscalationRecord] = None
    effectiveness: Optional[ActionEffectivenessRecord] = None
    ai_assistance: Optional[AIAssistanceMetadata] = None

    # Tenancy & Identifiers
    organization_id: Optional[str] = None
    facility_id: Optional[str] = None
    created_by_id: str
    created_by_role: str
    idempotency_key: Optional[str] = None

    # Temporal & Operational tracking
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    verified_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    due_at: Optional[datetime] = None

    # Execution telemetry & links
    external_task_id: Optional[str] = None     # Phase 36 task reference
    external_workflow_id: Optional[str] = None # Phase 37 workflow reference
    external_change_id: Optional[str] = None   # Phase 51 change reference
    external_incident_id: Optional[str] = None # Phase 49 incident reference
    retry_count: int = 0
    max_retries: int = 3
    is_rolled_back: bool = False
    rollback_reason: Optional[str] = None

    disclaimer: str = Field(
        default=(
            "Safety actions are governed operational responses to control findings. "
            "TASK COMPLETION != SAFETY VALIDATION. "
            "ACTION != CLINICAL DIAGNOSIS OR TREATMENT. "
            "EFFECTIVENESS != RISK ELIMINATION."
        )
    )


# ---------------------------------------------------------------------------
# Request & Response Payload Schemas
# ---------------------------------------------------------------------------


class SafetyActionCreateRequest(BaseModel):
    """Request payload to initiate a governed safety action candidate."""

    model_config = ConfigDict(extra="forbid")

    finding: SafetyFindingReference
    action_type: ActionType
    title: str = Field(..., min_length=3, max_length=255)
    description: str = Field(..., min_length=5, max_length=2000)
    scope: Optional[SafetyActionScope] = None
    idempotency_key: Optional[str] = None
    due_in_hours: Optional[int] = Field(default=72, ge=1, le=8760)


class SafetyActionClassifyRequest(BaseModel):
    """Request to classify or override finding actionability."""

    model_config = ConfigDict(extra="forbid")

    actionability: Optional[ActionabilityState] = None
    priority: Optional[ActionPriority] = None
    classification_notes: Optional[str] = None


class SafetyActionApproveRequest(BaseModel):
    """Submission payload for formal human approval."""

    model_config = ConfigDict(extra="forbid")

    action_version: int
    decision: ActionApprovalDecision
    reason: str = Field(..., min_length=5, max_length=1000)
    limitations: Optional[str] = None
    validity_hours: Optional[int] = Field(default=168, ge=1, le=720) # Up to 30 days


class SafetyActionAssignRequest(BaseModel):
    """Payload to assign authorized operational owner."""

    model_config = ConfigDict(extra="forbid")

    owner_id: str
    owner_role: str
    owner_domain: ActionOwnerDomain
    notes: Optional[str] = None


class SafetyActionExecuteRequest(BaseModel):
    """Trigger execution through authoritative downstream subsystem."""

    model_config = ConfigDict(extra="forbid")

    target_subsystem: Optional[TargetSubsystem] = None
    execution_payload: Optional[Dict[str, Any]] = None


class SafetyActionCompleteRequest(BaseModel):
    """Acknowledge completion of operational action."""

    model_config = ConfigDict(extra="forbid")

    completion_summary: str = Field(..., min_length=5, max_length=1000)
    artifacts: Optional[List[str]] = None


class SafetyActionVerifyRequest(BaseModel):
    """Independent verification of action implementation."""

    model_config = ConfigDict(extra="forbid")

    verification_notes: str = Field(..., min_length=5, max_length=1000)
    verified: bool


class SafetyActionEscalateRequest(BaseModel):
    """Policy-backed escalation request."""

    model_config = ConfigDict(extra="forbid")

    escalation_level: EscalationLevel
    reason: str = Field(..., min_length=5, max_length=1000)
    server_urgency_requested: bool = False


class SafetyActionReassessRequest(BaseModel):
    """Request to re-evaluate control assurance following an action."""

    model_config = ConfigDict(extra="forbid")

    reassessment_reason: str = Field(..., min_length=5, max_length=1000)
    route_to_phase52: bool = True


class SafetyActionRollbackRequest(BaseModel):
    """Rollback execution if action causes unexpected degradation."""

    model_config = ConfigDict(extra="forbid")

    action_version: int
    rollback_reason: str = Field(..., min_length=5, max_length=1000)


class SafetyActionRetryRequest(BaseModel):
    """Bounded, policy-checked retry of failed action."""

    model_config = ConfigDict(extra="forbid")

    retry_reason: str = Field(..., min_length=5, max_length=1000)


class SafetyActionCloseRequest(BaseModel):
    """Formal closure request verifying safety prerequisites."""

    model_config = ConfigDict(extra="forbid")

    closure_summary: str = Field(..., min_length=5, max_length=1000)
    confirm_effectiveness: bool = True


class SafetyActionReopenRequest(BaseModel):
    """Reopen closed action when new evidence or regression appears."""

    model_config = ConfigDict(extra="forbid")

    reopen_reason: str = Field(..., min_length=5, max_length=1000)
