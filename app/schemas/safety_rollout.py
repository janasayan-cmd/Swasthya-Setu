"""Phase 57: Clinical Safety Change Validation, Controlled Rollout Governance & Post-Deployment Safety Verification Schemas.

Non-Negotiable Distinctions:
- CHANGE APPROVAL != IMPLEMENTATION AUTHORIZATION
- IMPLEMENTATION != DEPLOYMENT VERIFICATION
- DEPLOYMENT VERIFICATION != SAFETY VERIFICATION
- SAFETY VERIFICATION != EFFECTIVENESS
- CANARY SUCCESS != GLOBAL SAFETY
- ROLLBACK != HISTORY DELETION
- PAUSE != FAILURE
- VALIDATION FAILURE != PATIENT HARM
- AI RECOMMENDATION != DEPLOYMENT AUTHORIZATION
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class RolloutLifecycleState(str, Enum):
    """Lifecycle states of controlled safety rollout."""

    APPROVED = "APPROVED"
    READINESS_CHECK = "READINESS_CHECK"
    READY = "READY"
    PREPARING = "PREPARING"
    ROLLOUT_AUTHORIZED = "ROLLOUT_AUTHORIZED"
    CANARY = "CANARY"
    CANARY_VALIDATION = "CANARY_VALIDATION"
    LIMITED_ROLLOUT = "LIMITED_ROLLOUT"
    LIMITED_VALIDATION = "LIMITED_VALIDATION"
    EXPANDED_ROLLOUT = "EXPANDED_ROLLOUT"
    EXPANDED_VALIDATION = "EXPANDED_VALIDATION"
    FULL_ROLLOUT = "FULL_ROLLOUT"
    POST_DEPLOYMENT_VALIDATION = "POST_DEPLOYMENT_VALIDATION"
    ASSURANCE_PENDING = "ASSURANCE_PENDING"
    EFFECTIVENESS_PENDING = "EFFECTIVENESS_PENDING"
    COMPLETED = "COMPLETED"

    # Alternative / Terminal states
    BLOCKED = "BLOCKED"
    PAUSED = "PAUSED"
    FAILED = "FAILED"
    ROLLBACK_REQUIRED = "ROLLBACK_REQUIRED"
    ROLLING_BACK = "ROLLING_BACK"
    ROLLED_BACK = "ROLLED_BACK"
    REASSESSMENT_REQUIRED = "REASSESSMENT_REQUIRED"
    SUPERSEDED = "SUPERSEDED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    STALE = "STALE"
    CONFLICTED = "CONFLICTED"


class RolloutStage(str, Enum):
    """Controlled progression stages."""

    PREPARATION = "PREPARATION"
    CANARY = "CANARY"
    LIMITED = "LIMITED"
    EXPANDED = "EXPANDED"
    FULL = "FULL"


class CheckpointCategory(str, Enum):
    """Safety checkpoint checkpoints."""

    PRE_DEPLOYMENT = "PRE_DEPLOYMENT"
    POST_DEPLOYMENT = "POST_DEPLOYMENT"
    POST_CANARY = "POST_CANARY"
    POST_LIMITED = "POST_LIMITED"
    POST_EXPANSION = "POST_EXPANSION"
    POST_FULL = "POST_FULL"
    POST_ROLLBACK = "POST_ROLLBACK"


class CheckpointStatus(str, Enum):
    """Evaluation status of a checkpoint."""

    PENDING = "PENDING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    SKIPPED = "SKIPPED"


class ApprovalStatus(str, Enum):
    """Status of change approval revalidation."""

    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"
    STALE = "STALE"
    INVALID = "INVALID"


class DependencyStatus(str, Enum):
    """Pre-rollout dependency health state."""

    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    DEGRADED = "DEGRADED"
    INCOMPATIBLE = "INCOMPATIBLE"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"


class HumanOversightDecision(str, Enum):
    """Human oversight gate outcomes."""

    APPROVE_STAGE = "APPROVE_STAGE"
    HOLD = "HOLD"
    REQUEST_MORE_EVIDENCE = "REQUEST_MORE_EVIDENCE"
    PAUSE = "PAUSE"
    ROLLBACK_REVIEW = "ROLLBACK_REVIEW"
    REASSESS = "REASSESS"
    ESCALATE = "ESCALATE"
    REJECT = "REJECT"


# ---------------------------------------------------------------------------
# Scope & Records
# ---------------------------------------------------------------------------


class RolloutScope(BaseModel):
    """Explicit scope for rollout deployment."""

    model_config = ConfigDict(extra="forbid")

    environment: str = Field("production", description="Target environment")
    organization_id: str = Field(...)
    facility_id: Optional[str] = Field(None)
    department_id: Optional[str] = Field(None)
    target_workflows: List[str] = Field(default_factory=list)
    target_controls: List[str] = Field(default_factory=list)


class ApprovalVerificationRecord(BaseModel):
    """Revalidated approval audit context."""

    model_config = ConfigDict(extra="forbid")

    approver_id: str = Field(...)
    approver_role: str = Field(...)
    approval_status: ApprovalStatus = Field(ApprovalStatus.APPROVED)
    change_version: str = Field(...)
    approved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = Field(None)
    is_valid: bool = Field(True)


class RolloutDependency(BaseModel):
    """Subsystem or configuration dependency."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(...)
    dependency_type: str = Field(..., description="DATABASE, CONFIGURATION, FEATURE_FLAG, PROVIDER, API")
    required_version: str = Field(...)
    current_version: str = Field(...)
    status: DependencyStatus = Field(DependencyStatus.AVAILABLE)


class SafetyControlVerificationRecord(BaseModel):
    """Post-deployment runtime verification of active safety controls."""

    model_config = ConfigDict(extra="forbid")

    control_id: str = Field(...)
    control_name: str = Field(...)
    is_active: bool = Field(True)
    execution_verified: bool = Field(True)
    verified_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    evidence_id: Optional[str] = Field(None)


class ValidationCheckpoint(BaseModel):
    """Discrete validation checkpoint within a rollout stage."""

    model_config = ConfigDict(extra="forbid")

    checkpoint_id: str = Field(default_factory=lambda: f"chk-{uuid.uuid4().hex[:8]}")
    category: CheckpointCategory = Field(...)
    stage: RolloutStage = Field(...)
    expected_state: str = Field(...)
    observed_state: Optional[str] = Field(None)
    status: CheckpointStatus = Field(CheckpointStatus.PENDING)
    criteria: str = Field(...)
    evaluated_at: Optional[datetime] = Field(None)
    notes: Optional[str] = Field(None)


class RolloutHistoryEntry(BaseModel):
    """Immutable transition audit record."""

    model_config = ConfigDict(extra="forbid")

    entry_id: str = Field(default_factory=lambda: f"his-{uuid.uuid4().hex[:8]}")
    from_stage: Optional[str] = Field(None)
    to_stage: Optional[str] = Field(None)
    from_state: str = Field(...)
    to_state: str = Field(...)
    action: str = Field(...)
    actor_id: str = Field(...)
    actor_role: str = Field(...)
    reason: Optional[str] = Field(None)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RolloutRoutingRecord(BaseModel):
    """Closed-loop feedback dispatch record to downstream phases."""

    model_config = ConfigDict(extra="forbid")

    routing_id: str = Field(default_factory=lambda: f"rt-{uuid.uuid4().hex[:8]}")
    destination_phase: str = Field(..., description="Phase 52, Phase 55, Phase 56, Phase 48, Phase 51")
    signal_type: str = Field(...)
    payload_summary: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = Field("SENT")


# ---------------------------------------------------------------------------
# Aggregate Rollout Record
# ---------------------------------------------------------------------------


class SafetyRolloutRecord(BaseModel):
    """Authoritative controlled rollout record."""

    model_config = ConfigDict(extra="forbid")

    rollout_id: str = Field(default_factory=lambda: f"rol-{uuid.uuid4().hex[:12]}")
    change_id: str = Field(..., description="Phase 51 safety change request ID")
    change_proposal_id: Optional[str] = Field(None, description="Phase 56 proposal reference")
    scope: RolloutScope = Field(...)
    approved_version: str = Field(..., description="Version signed off by Phase 51 governance")
    target_version: str = Field(..., description="Version targeted for deployment")
    current_stage: RolloutStage = Field(RolloutStage.PREPARATION)
    lifecycle_state: RolloutLifecycleState = Field(RolloutLifecycleState.APPROVED)
    approval: ApprovalVerificationRecord = Field(...)
    dependencies: List[RolloutDependency] = Field(default_factory=list)
    checkpoints: List[ValidationCheckpoint] = Field(default_factory=list)
    safety_controls_verified: List[SafetyControlVerificationRecord] = Field(default_factory=list)
    history: List[RolloutHistoryEntry] = Field(default_factory=list)
    routings: List[RolloutRoutingRecord] = Field(default_factory=list)
    rollback_plan: str = Field(..., min_length=10)
    validation_plan: str = Field(..., min_length=10)
    observation_plan: str = Field(..., min_length=10)
    is_paused: bool = Field(False)
    is_rolled_back: bool = Field(False)
    pause_reason: Optional[str] = Field(None)
    rollback_reason: Optional[str] = Field(None)
    version: int = Field(1)
    created_by: str = Field(...)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = Field(None)
    reopened_count: int = Field(0)


# ---------------------------------------------------------------------------
# API Request & Response Schemas
# ---------------------------------------------------------------------------


class CreateRolloutRequest(BaseModel):
    """Request payload to initiate a controlled rollout."""

    model_config = ConfigDict(extra="forbid")

    change_id: str = Field(...)
    change_proposal_id: Optional[str] = Field(None)
    scope: RolloutScope = Field(...)
    approved_version: str = Field(...)
    target_version: str = Field(...)
    approval: ApprovalVerificationRecord = Field(...)
    rollback_plan: str = Field(..., min_length=10)
    validation_plan: str = Field(..., min_length=10)
    observation_plan: str = Field(..., min_length=10)
    dependencies: Optional[List[RolloutDependency]] = Field(default_factory=list)
    idempotency_key: Optional[str] = Field(None)


class ValidateReadinessRequest(BaseModel):
    """Request payload to recheck pre-rollout readiness gates."""

    model_config = ConfigDict(extra="forbid")

    recheck_dependencies: bool = Field(True)


class StartRolloutRequest(BaseModel):
    """Request payload to transition from READY to CANARY stage."""

    model_config = ConfigDict(extra="forbid")

    canary_scope_percentage: Optional[int] = Field(5, ge=1, le=25)


class AdvanceStageRequest(BaseModel):
    """Request payload to advance from current stage to next stage."""

    model_config = ConfigDict(extra="forbid")

    target_stage: RolloutStage = Field(...)
    rationale: str = Field(..., min_length=10)
    is_ai_agent: bool = Field(False, description="Flag indicating if caller is AI")


class ValidateStageRequest(BaseModel):
    """Request payload to submit validation evidence for the active stage."""

    model_config = ConfigDict(extra="forbid")

    checkpoint_id: str = Field(...)
    observed_state: str = Field(...)
    status: CheckpointStatus = Field(...)
    evidence_notes: Optional[str] = Field(None)


class PauseRolloutRequest(BaseModel):
    """Request payload to pause active rollout."""

    model_config = ConfigDict(extra="forbid")

    reason: str = Field(..., min_length=10)


class ResumeRolloutRequest(BaseModel):
    """Request payload to resume paused rollout."""

    model_config = ConfigDict(extra="forbid")

    rationale: str = Field(..., min_length=10)


class RollbackRequest(BaseModel):
    """Request payload to trigger emergency or governed rollback."""

    model_config = ConfigDict(extra="forbid")

    reason: str = Field(..., min_length=10)
    target_version: str = Field(...)


class ValidateRollbackRequest(BaseModel):
    """Request payload to verify successful rollback completion."""

    model_config = ConfigDict(extra="forbid")

    verified_version: str = Field(...)
    safety_controls_intact: bool = Field(...)
    evidence_notes: Optional[str] = Field(None)


class ReassessmentRequest(BaseModel):
    """Request payload to trigger formal reassessment."""

    model_config = ConfigDict(extra="forbid")

    reason: str = Field(..., min_length=10)


class CompleteRolloutRequest(BaseModel):
    """Request payload to mark rollout completed following observation."""

    model_config = ConfigDict(extra="forbid")

    observation_evidence_id: Optional[str] = Field(None)
    rationale: str = Field(..., min_length=10)


class ReopenRolloutRequest(BaseModel):
    """Request payload to reopen a rollout."""

    model_config = ConfigDict(extra="forbid")

    reason: str = Field(..., min_length=10)


class ReanalysisRequest(BaseModel):
    """Request payload for batch reanalysis."""

    model_config = ConfigDict(extra="forbid")

    rollout_ids: Optional[List[str]] = Field(None)
    reason: str = Field(..., min_length=10)


class RolloutStatusResponse(BaseModel):
    """Status summary response."""

    model_config = ConfigDict(extra="forbid")

    rollout_id: str
    change_id: str
    current_stage: RolloutStage
    lifecycle_state: RolloutLifecycleState
    approved_version: str
    target_version: str
    is_paused: bool
    is_rolled_back: bool
    version: int
    updated_at: datetime


class RolloutReadinessResponse(BaseModel):
    """Readiness audit response."""

    model_config = ConfigDict(extra="forbid")

    rollout_id: str
    is_ready: bool
    approval_valid: bool
    version_matched: bool
    dependencies_satisfied: bool
    plans_defined: bool
    blockers: List[str]


class RolloutCheckpointsResponse(BaseModel):
    """Checkpoints details response."""

    model_config = ConfigDict(extra="forbid")

    rollout_id: str
    current_stage: RolloutStage
    checkpoints: List[ValidationCheckpoint]
    passed_count: int
    failed_count: int
    pending_count: int


class RolloutEvidenceResponse(BaseModel):
    """Evidence and safety control verification details."""

    model_config = ConfigDict(extra="forbid")

    rollout_id: str
    safety_controls_verified: List[SafetyControlVerificationRecord]
    routings: List[RolloutRoutingRecord]
