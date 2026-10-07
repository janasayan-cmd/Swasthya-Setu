"""Phase 58: Clinical Safety Change Verification, Release Evidence & Controlled Post-Rollout Closure Schemas.

Non-Negotiable Distinctions:
- VERIFICATION != ASSURANCE
- ASSURANCE != EFFECTIVENESS
- EFFECTIVENESS != ZERO RISK
- CLOSURE != PERMANENT SAFETY GUARANTEE
- AI != AUTHORITY
- EVIDENCE != PROOF OF NO HARM
- CLOSURE != DELETION OF HISTORY
- REOPENING != HISTORY DELETION
- CHANGE_APPROVER != IMPLEMENTER != FINAL_VERIFIER
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.safety_rollout import RolloutScope


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class VerificationLifecycleState(str, Enum):
    """Lifecycle states of formal post-rollout change verification."""

    PENDING = "PENDING"
    COLLECTING_EVIDENCE = "COLLECTING_EVIDENCE"
    EVIDENCE_INCOMPLETE = "EVIDENCE_INCOMPLETE"
    EVIDENCE_CONFLICTED = "EVIDENCE_CONFLICTED"
    VERIFICATION_IN_PROGRESS = "VERIFICATION_IN_PROGRESS"
    VERIFICATION_BLOCKED = "VERIFICATION_BLOCKED"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"
    VERIFIED = "VERIFIED"
    CONDITIONALLY_VERIFIED = "CONDITIONALLY_VERIFIED"
    CLOSURE_PENDING = "CLOSURE_PENDING"
    CLOSED = "CLOSED"
    REOPEN_REQUIRED = "REOPEN_REQUIRED"
    REOPENED = "REOPENED"

    # Alternative / Exception states
    FAILED = "FAILED"
    STALE = "STALE"
    SUPERSEDED = "SUPERSEDED"
    EXPIRED = "EXPIRED"
    REASSESSMENT_REQUIRED = "REASSESSMENT_REQUIRED"
    CONFLICTED = "CONFLICTED"


class EvidenceProvenanceType(str, Enum):
    """Traceable provenance categorization of evidence."""

    SOURCE_EVIDENCE = "SOURCE_EVIDENCE"
    DERIVED_EVIDENCE = "DERIVED_EVIDENCE"
    VERIFICATION_RESULT = "VERIFICATION_RESULT"
    HUMAN_REVIEW_RESULT = "HUMAN_REVIEW_RESULT"
    AI_ASSISTED_SUMMARY = "AI_ASSISTED_SUMMARY"


class EvidenceCategory(str, Enum):
    """Categories of evidence collected across authoritative backend phases."""

    APPROVAL_EVIDENCE = "APPROVAL_EVIDENCE"
    VERSION_EVIDENCE = "VERSION_EVIDENCE"
    DEPLOYMENT_EVIDENCE = "DEPLOYMENT_EVIDENCE"
    CONFIGURATION_EVIDENCE = "CONFIGURATION_EVIDENCE"
    FEATURE_FLAG_EVIDENCE = "FEATURE_FLAG_EVIDENCE"
    ROLLOUT_STAGE_EVIDENCE = "ROLLOUT_STAGE_EVIDENCE"
    SAFETY_CONTROL_EVIDENCE = "SAFETY_CONTROL_EVIDENCE"
    CHECKPOINT_EVIDENCE = "CHECKPOINT_EVIDENCE"
    TELEMETRY_EVIDENCE = "TELEMETRY_EVIDENCE"
    OBSERVATION_EVIDENCE = "OBSERVATION_EVIDENCE"
    ASSURANCE_EVIDENCE = "ASSURANCE_EVIDENCE"
    EFFECTIVENESS_EVIDENCE = "EFFECTIVENESS_EVIDENCE"
    INCIDENT_SIGNAL_EVIDENCE = "INCIDENT_SIGNAL_EVIDENCE"
    REVIEW_EVIDENCE = "REVIEW_EVIDENCE"
    ROLLBACK_EVIDENCE = "ROLLBACK_EVIDENCE"
    REASSESSMENT_EVIDENCE = "REASSESSMENT_EVIDENCE"


class AssuranceOutcomeStatus(str, Enum):
    """Phase 52 assurance evaluation outcome status."""

    ASSURANCE_PASS = "ASSURANCE_PASS"
    ASSURANCE_CONDITIONAL = "ASSURANCE_CONDITIONAL"
    ASSURANCE_PENDING = "ASSURANCE_PENDING"
    ASSURANCE_FAILED = "ASSURANCE_FAILED"
    ASSURANCE_REASSESSMENT_REQUIRED = "ASSURANCE_REASSESSMENT_REQUIRED"


class EffectivenessOutcomeStatus(str, Enum):
    """Phase 55 outcome effectiveness evaluation status."""

    EFFECTIVENESS_PENDING = "EFFECTIVENESS_PENDING"
    EFFECTIVENESS_SUFFICIENT = "EFFECTIVENESS_SUFFICIENT"
    EFFECTIVENESS_CONDITIONAL = "EFFECTIVENESS_CONDITIONAL"
    EFFECTIVENESS_FAILED = "EFFECTIVENESS_FAILED"
    EFFECTIVENESS_INCONCLUSIVE = "EFFECTIVENESS_INCONCLUSIVE"
    EFFECTIVENESS_REASSESSMENT_REQUIRED = "EFFECTIVENESS_REASSESSMENT_REQUIRED"


class HumanVerificationDecision(str, Enum):
    """Human verification decision outcomes."""

    VERIFY = "VERIFY"
    VERIFY_WITH_CONDITIONS = "VERIFY_WITH_CONDITIONS"
    REQUEST_MORE_EVIDENCE = "REQUEST_MORE_EVIDENCE"
    BLOCK = "BLOCK"
    REASSESS = "REASSESS"
    REOPEN = "REOPEN"
    ESCALATE = "ESCALATE"


# ---------------------------------------------------------------------------
# Supporting Models
# ---------------------------------------------------------------------------


class EvidenceReference(BaseModel):
    """Referenced evidence item preserving provenance without duplicating clinical truth."""

    model_config = ConfigDict(extra="forbid")

    evidence_id: str = Field(default_factory=lambda: f"evi-{uuid.uuid4().hex[:8]}")
    source_phase: str = Field(..., description="Source phase (Phase 51, 57, 48, 52, 55, 49, etc.)")
    source_record_id: str = Field(...)
    category: EvidenceCategory = Field(...)
    provenance_type: EvidenceProvenanceType = Field(...)
    source_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    version: str = Field(...)
    scope: Dict[str, Any] = Field(default_factory=dict)
    status: str = Field("VALID", description="VALID, INCOMPLETE, CONFLICTED, STALE")
    metadata_summary: Dict[str, Any] = Field(default_factory=dict)
    is_verified: bool = Field(True)


class VerificationCondition(BaseModel):
    """Governed condition attached to conditional verification."""

    model_config = ConfigDict(extra="forbid")

    condition_id: str = Field(default_factory=lambda: f"cnd-{uuid.uuid4().hex[:8]}")
    owner: str = Field(...)
    due_at: Optional[datetime] = Field(None)
    required_evidence: str = Field(...)
    completion_criteria: str = Field(...)
    escalation_rule: str = Field(...)
    status: str = Field("PENDING", description="PENDING, SATISFIED, BREACHED")


class PostClosureMonitoringRecord(BaseModel):
    """Registered post-closure observation requirements."""

    model_config = ConfigDict(extra="forbid")

    monitoring_id: str = Field(default_factory=lambda: f"pcm-{uuid.uuid4().hex[:8]}")
    monitoring_window_days: int = Field(30, ge=1, le=365)
    monitoring_owner: str = Field(...)
    expected_signals: List[str] = Field(default_factory=list)
    observation_threshold: str = Field(...)
    review_schedule: str = Field(...)
    registered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = Field("ACTIVE", description="ACTIVE, COMPLETED, TRIGGERED_REOPEN")


class HumanVerificationReviewRecord(BaseModel):
    """Audit record of human verification review decision."""

    model_config = ConfigDict(extra="forbid")

    review_id: str = Field(default_factory=lambda: f"hvr-{uuid.uuid4().hex[:8]}")
    reviewer_id: str = Field(...)
    reviewer_role: str = Field(...)
    decision: HumanVerificationDecision = Field(...)
    rationale: str = Field(..., min_length=10)
    reviewed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    conditions: List[str] = Field(default_factory=list)


class ReopenRecord(BaseModel):
    """Immutable audit record for reopening a previously closed change."""

    model_config = ConfigDict(extra="forbid")

    reopen_id: str = Field(default_factory=lambda: f"rop-{uuid.uuid4().hex[:8]}")
    previous_closure_id: Optional[str] = Field(None)
    reason: str = Field(..., min_length=10)
    triggering_evidence_id: Optional[str] = Field(None)
    actor_id: str = Field(...)
    actor_role: str = Field(...)
    reopened_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class VerificationHistoryEntry(BaseModel):
    """Immutable transition audit log entry."""

    model_config = ConfigDict(extra="forbid")

    entry_id: str = Field(default_factory=lambda: f"vhs-{uuid.uuid4().hex[:8]}")
    from_state: str = Field(...)
    to_state: str = Field(...)
    action: str = Field(...)
    actor_id: str = Field(...)
    actor_role: str = Field(...)
    reason: Optional[str] = Field(None)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Aggregate Verification Record
# ---------------------------------------------------------------------------


class SafetyVerificationRecord(BaseModel):
    """Authoritative release verification and closure governance record."""

    model_config = ConfigDict(extra="forbid")

    verification_id: str = Field(default_factory=lambda: f"vfy-{uuid.uuid4().hex[:12]}")
    rollout_id: str = Field(..., description="Source Phase 57 rollout ID")
    change_id: str = Field(..., description="Source Phase 51 change ID")
    change_proposal_id: Optional[str] = Field(None, description="Source Phase 56 proposal ID")
    approved_version: str = Field(...)
    deployed_version: str = Field(...)
    scope: RolloutScope = Field(...)
    verification_status: VerificationLifecycleState = Field(VerificationLifecycleState.PENDING)
    evidence_items: List[EvidenceReference] = Field(default_factory=list)
    assurance_status: AssuranceOutcomeStatus = Field(AssuranceOutcomeStatus.ASSURANCE_PENDING)
    effectiveness_status: EffectivenessOutcomeStatus = Field(EffectivenessOutcomeStatus.EFFECTIVENESS_PENDING)
    safety_control_status: str = Field("PENDING", description="PASSED, FAILED, UNKNOWN, PENDING")
    human_reviews: List[HumanVerificationReviewRecord] = Field(default_factory=list)
    conditions: List[VerificationCondition] = Field(default_factory=list)
    closure_eligible: bool = Field(False)
    blocking_reasons: List[str] = Field(default_factory=list)
    closed_at: Optional[datetime] = Field(None)
    closed_by: Optional[str] = Field(None)
    closure_notes: Optional[str] = Field(None)
    post_closure_monitoring: Optional[PostClosureMonitoringRecord] = Field(None)
    reopen_history: List[ReopenRecord] = Field(default_factory=list)
    history: List[VerificationHistoryEntry] = Field(default_factory=list)
    version: int = Field(1)
    created_by: str = Field(...)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# API Request & Response Models
# ---------------------------------------------------------------------------


class CreateVerificationRequest(BaseModel):
    """Request payload to initiate a change verification."""

    model_config = ConfigDict(extra="forbid")

    rollout_id: str = Field(...)
    change_id: str = Field(...)
    change_proposal_id: Optional[str] = Field(None)
    scope: RolloutScope = Field(...)
    approved_version: str = Field(...)
    deployed_version: str = Field(...)
    idempotency_key: Optional[str] = Field(None)


class CollectEvidenceRequest(BaseModel):
    """Request payload to trigger collection from authoritative sources."""

    model_config = ConfigDict(extra="forbid")

    force_refresh: bool = Field(False)


class RunVerificationRequest(BaseModel):
    """Request payload to execute verification evaluation."""

    model_config = ConfigDict(extra="forbid")

    require_strict_assurance: bool = Field(True)
    require_strict_effectiveness: bool = Field(True)


class SubmitReviewRequest(BaseModel):
    """Request payload for human reviewer decision."""

    model_config = ConfigDict(extra="forbid")

    decision: HumanVerificationDecision = Field(...)
    rationale: str = Field(..., min_length=10)
    conditions: Optional[List[str]] = Field(default_factory=list)
    is_ai_agent: bool = Field(False, description="Flag indicating caller is AI")


class FinalizeVerificationRequest(BaseModel):
    """Request payload to finalize verification."""

    model_config = ConfigDict(extra="forbid")

    notes: Optional[str] = Field(None)


class ControlledClosureRequest(BaseModel):
    """Request payload to execute controlled closure."""

    model_config = ConfigDict(extra="forbid")

    rationale: str = Field(..., min_length=10)
    monitoring_window_days: Optional[int] = Field(30, ge=1, le=365)
    monitoring_owner: Optional[str] = Field(None)
    expected_signals: Optional[List[str]] = Field(default_factory=list)


class ReopenVerificationRequest(BaseModel):
    """Request payload to reopen a closed change."""

    model_config = ConfigDict(extra="forbid")

    reason: str = Field(..., min_length=10)
    triggering_evidence_id: Optional[str] = Field(None)


class ReassessmentVerificationRequest(BaseModel):
    """Request payload to request reassessment."""

    model_config = ConfigDict(extra="forbid")

    reason: str = Field(..., min_length=10)


class ReanalysisVerificationRequest(BaseModel):
    """Request payload for batch reanalysis."""

    model_config = ConfigDict(extra="forbid")

    verification_ids: Optional[List[str]] = Field(None)
    reason: str = Field(..., min_length=10)


class VerificationStatusResponse(BaseModel):
    """Status overview response."""

    model_config = ConfigDict(extra="forbid")

    verification_id: str
    rollout_id: str
    change_id: str
    approved_version: str
    deployed_version: str
    verification_status: VerificationLifecycleState
    closure_eligible: bool
    blocking_reasons: List[str]
    version: int
    updated_at: datetime


class ClosureEligibilityResponse(BaseModel):
    """Detailed closure eligibility evaluation response."""

    model_config = ConfigDict(extra="forbid")

    verification_id: str
    eligible: bool
    status: str
    blocking_reasons: List[Dict[str, str]]
    conditions: List[VerificationCondition]
    required_actions: List[str]


class VerificationAssuranceResponse(BaseModel):
    """Linked Phase 52 assurance details."""

    model_config = ConfigDict(extra="forbid")

    verification_id: str
    assurance_status: AssuranceOutcomeStatus
    evidence_references: List[EvidenceReference]
    is_satisfactory: bool


class VerificationEffectivenessResponse(BaseModel):
    """Linked Phase 55 effectiveness details."""

    model_config = ConfigDict(extra="forbid")

    verification_id: str
    effectiveness_status: EffectivenessOutcomeStatus
    evidence_references: List[EvidenceReference]
    is_satisfactory: bool
