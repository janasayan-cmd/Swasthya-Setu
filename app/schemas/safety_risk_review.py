"""Phase 63: Clinical Safety Risk Review Schemas.

Defines the core review lifecycle states, review records, history entries,
and API request/response models.
Non-Negotiable Invariants:
- RISK CONTEXT != RISK ACCEPTANCE
- RISK REVIEW != INCIDENT INVESTIGATION
- RISK DISPOSITION != CLINICAL ACTION
- AI RECOMMENDATION != GOVERNED DECISION
- NO_FURTHER_REVIEW_AT_THIS_TIME != SAFE / NO_RISK / RISK_ACCEPTED
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.safety_review_evidence import EvidenceReference, EvidenceSufficiencyState
from app.schemas.safety_review_package import SafetyReviewPackage
from app.schemas.safety_review_question import UnresolvedQuestionRecord
from app.schemas.safety_risk_disposition import RiskDispositionRecord, RiskDispositionType
from app.schemas.safety_risk_follow_up import RiskFollowUpRecord
from app.schemas.safety_risk_readiness import DecisionReadinessEvaluation, DecisionReadinessState
from app.schemas.safety_risk_review_action import ReviewActionRecord
from app.schemas.safety_routing import RiskRoutingRecord


class ReviewLifecycleState(str, Enum):
    """Lifecycle states of governed risk reviews in Phase 63."""

    CREATED = "CREATED"
    VALIDATING = "VALIDATING"
    READINESS_CHECK = "READINESS_CHECK"
    NOT_READY = "NOT_READY"
    READY = "READY"
    REVIEW_PENDING = "REVIEW_PENDING"
    REVIEW_IN_PROGRESS = "REVIEW_IN_PROGRESS"
    EVIDENCE_REQUESTED = "EVIDENCE_REQUESTED"
    EVIDENCE_RECEIVED = "EVIDENCE_RECEIVED"
    CONFLICT_REVIEW = "CONFLICT_REVIEW"
    DECISION_PENDING = "DECISION_PENDING"
    DISPOSITION_RECORDED = "DISPOSITION_RECORDED"
    ROUTING_REQUIRED = "ROUTING_REQUIRED"
    ROUTED = "ROUTED"
    FOLLOW_UP_REQUIRED = "FOLLOW_UP_REQUIRED"
    MONITORING = "MONITORING"
    COMPLETED = "COMPLETED"
    REASSESSMENT_REQUIRED = "REASSESSMENT_REQUIRED"
    REOPEN_REQUIRED = "REOPEN_REQUIRED"
    BLOCKED = "BLOCKED"
    STALE = "STALE"
    SUPERSEDED = "SUPERSEDED"
    CANCELLED = "CANCELLED"


# Valid forward transitions map
VALID_REVIEW_TRANSITIONS: Dict[ReviewLifecycleState, List[ReviewLifecycleState]] = {
    ReviewLifecycleState.CREATED: [
        ReviewLifecycleState.VALIDATING,
        ReviewLifecycleState.READINESS_CHECK,
        ReviewLifecycleState.BLOCKED,
        ReviewLifecycleState.CANCELLED,
    ],
    ReviewLifecycleState.VALIDATING: [
        ReviewLifecycleState.READINESS_CHECK,
        ReviewLifecycleState.NOT_READY,
        ReviewLifecycleState.BLOCKED,
        ReviewLifecycleState.STALE,
        ReviewLifecycleState.CANCELLED,
    ],
    ReviewLifecycleState.READINESS_CHECK: [
        ReviewLifecycleState.READY,
        ReviewLifecycleState.NOT_READY,
        ReviewLifecycleState.REVIEW_PENDING,
        ReviewLifecycleState.EVIDENCE_REQUESTED,
        ReviewLifecycleState.CONFLICT_REVIEW,
        ReviewLifecycleState.BLOCKED,
        ReviewLifecycleState.STALE,
        ReviewLifecycleState.REASSESSMENT_REQUIRED,
    ],
    ReviewLifecycleState.NOT_READY: [
        ReviewLifecycleState.READINESS_CHECK,
        ReviewLifecycleState.EVIDENCE_REQUESTED,
        ReviewLifecycleState.BLOCKED,
        ReviewLifecycleState.CANCELLED,
    ],
    ReviewLifecycleState.READY: [
        ReviewLifecycleState.REVIEW_PENDING,
        ReviewLifecycleState.REVIEW_IN_PROGRESS,
        ReviewLifecycleState.EVIDENCE_REQUESTED,
        ReviewLifecycleState.BLOCKED,
    ],
    ReviewLifecycleState.REVIEW_PENDING: [
        ReviewLifecycleState.REVIEW_IN_PROGRESS,
        ReviewLifecycleState.EVIDENCE_REQUESTED,
        ReviewLifecycleState.CONFLICT_REVIEW,
        ReviewLifecycleState.BLOCKED,
        ReviewLifecycleState.CANCELLED,
    ],
    ReviewLifecycleState.REVIEW_IN_PROGRESS: [
        ReviewLifecycleState.EVIDENCE_REQUESTED,
        ReviewLifecycleState.CONFLICT_REVIEW,
        ReviewLifecycleState.DECISION_PENDING,
        ReviewLifecycleState.DISPOSITION_RECORDED,
        ReviewLifecycleState.REASSESSMENT_REQUIRED,
        ReviewLifecycleState.BLOCKED,
    ],
    ReviewLifecycleState.EVIDENCE_REQUESTED: [
        ReviewLifecycleState.EVIDENCE_RECEIVED,
        ReviewLifecycleState.REVIEW_IN_PROGRESS,
        ReviewLifecycleState.BLOCKED,
        ReviewLifecycleState.STALE,
    ],
    ReviewLifecycleState.EVIDENCE_RECEIVED: [
        ReviewLifecycleState.READINESS_CHECK,
        ReviewLifecycleState.REVIEW_IN_PROGRESS,
        ReviewLifecycleState.CONFLICT_REVIEW,
        ReviewLifecycleState.DECISION_PENDING,
    ],
    ReviewLifecycleState.CONFLICT_REVIEW: [
        ReviewLifecycleState.REVIEW_IN_PROGRESS,
        ReviewLifecycleState.EVIDENCE_REQUESTED,
        ReviewLifecycleState.DECISION_PENDING,
        ReviewLifecycleState.REASSESSMENT_REQUIRED,
        ReviewLifecycleState.BLOCKED,
    ],
    ReviewLifecycleState.DECISION_PENDING: [
        ReviewLifecycleState.DISPOSITION_RECORDED,
        ReviewLifecycleState.REVIEW_IN_PROGRESS,
        ReviewLifecycleState.EVIDENCE_REQUESTED,
        ReviewLifecycleState.BLOCKED,
    ],
    ReviewLifecycleState.DISPOSITION_RECORDED: [
        ReviewLifecycleState.ROUTING_REQUIRED,
        ReviewLifecycleState.ROUTED,
        ReviewLifecycleState.FOLLOW_UP_REQUIRED,
        ReviewLifecycleState.MONITORING,
        ReviewLifecycleState.COMPLETED,
        ReviewLifecycleState.REASSESSMENT_REQUIRED,
    ],
    ReviewLifecycleState.ROUTING_REQUIRED: [
        ReviewLifecycleState.ROUTED,
        ReviewLifecycleState.FOLLOW_UP_REQUIRED,
        ReviewLifecycleState.MONITORING,
        ReviewLifecycleState.COMPLETED,
        ReviewLifecycleState.BLOCKED,
    ],
    ReviewLifecycleState.ROUTED: [
        ReviewLifecycleState.FOLLOW_UP_REQUIRED,
        ReviewLifecycleState.MONITORING,
        ReviewLifecycleState.COMPLETED,
    ],
    ReviewLifecycleState.FOLLOW_UP_REQUIRED: [
        ReviewLifecycleState.MONITORING,
        ReviewLifecycleState.COMPLETED,
        ReviewLifecycleState.REASSESSMENT_REQUIRED,
        ReviewLifecycleState.REOPEN_REQUIRED,
    ],
    ReviewLifecycleState.MONITORING: [
        ReviewLifecycleState.COMPLETED,
        ReviewLifecycleState.REASSESSMENT_REQUIRED,
        ReviewLifecycleState.REOPEN_REQUIRED,
    ],
    ReviewLifecycleState.COMPLETED: [
        ReviewLifecycleState.REOPEN_REQUIRED,
        ReviewLifecycleState.REASSESSMENT_REQUIRED,
        ReviewLifecycleState.SUPERSEDED,
    ],
    ReviewLifecycleState.REASSESSMENT_REQUIRED: [
        ReviewLifecycleState.SUPERSEDED,
        ReviewLifecycleState.CREATED,
        ReviewLifecycleState.REVIEW_PENDING,
    ],
    ReviewLifecycleState.REOPEN_REQUIRED: [
        ReviewLifecycleState.REVIEW_IN_PROGRESS,
        ReviewLifecycleState.READINESS_CHECK,
    ],
    ReviewLifecycleState.BLOCKED: [
        ReviewLifecycleState.READINESS_CHECK,
        ReviewLifecycleState.CANCELLED,
    ],
    ReviewLifecycleState.STALE: [
        ReviewLifecycleState.REASSESSMENT_REQUIRED,
        ReviewLifecycleState.CANCELLED,
    ],
    ReviewLifecycleState.SUPERSEDED: [],
    ReviewLifecycleState.CANCELLED: [],
}


class ReviewHistoryEntry(BaseModel):
    """Immutable audit trail entry for review lifecycle transitions and operations."""

    model_config = ConfigDict(extra="ignore")

    entry_id: str = Field(default_factory=lambda: f"hist-{uuid.uuid4().hex[:12]}")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    from_state: Optional[ReviewLifecycleState] = None
    to_state: Optional[ReviewLifecycleState] = None
    actor_id: str
    actor_role: str
    action: str
    details: Dict[str, Any] = Field(default_factory=dict)


class SafetyRiskReviewRecord(BaseModel):
    """Primary domain model representing a governed safety risk review."""

    model_config = ConfigDict(extra="ignore")

    review_id: str = Field(default_factory=lambda: f"srr-{uuid.uuid4().hex[:12]}")
    assessment_id: str
    organization_id: str
    facility_id: str

    state: ReviewLifecycleState = ReviewLifecycleState.CREATED
    readiness: Optional[DecisionReadinessEvaluation] = None
    evidence_sufficiency: EvidenceSufficiencyState = EvidenceSufficiencyState.UNKNOWN

    scope: Dict[str, Any] = Field(default_factory=dict)
    application_version: str = "v1.0.0"
    configuration_version: str = "v1.0.0"
    safety_control_version: str = "v1.0.0"
    risk_context_version: str = "v1.0.0"
    provenance: str = "PHASE_62_GOVERNED_RISK_ASSESSMENT"

    created_by: str = "system"
    current_reviewer_id: Optional[str] = None
    current_reviewer_role: Optional[str] = None

    review_package: Optional[SafetyReviewPackage] = None
    evidence_items: List[EvidenceReference] = Field(default_factory=list)
    questions: List[UnresolvedQuestionRecord] = Field(default_factory=list)
    actions: List[ReviewActionRecord] = Field(default_factory=list)
    dispositions: List[RiskDispositionRecord] = Field(default_factory=list)
    current_disposition: Optional[RiskDispositionType] = None
    routings: List[RiskRoutingRecord] = Field(default_factory=list)
    follow_ups: List[RiskFollowUpRecord] = Field(default_factory=list)

    history: List[ReviewHistoryEntry] = Field(default_factory=list)

    # Concurrency control & version tags
    version_tag: int = 1
    idempotency_key: Optional[str] = None

    # Flags
    requires_escalation: bool = False
    requires_reassessment: bool = False
    is_reopened: bool = False
    reopen_count: int = 0
    reopen_reason: Optional[str] = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Request & Response Schemas
# ---------------------------------------------------------------------------


class CreateSafetyRiskReviewRequest(BaseModel):
    """Request payload to initiate a governed risk review from Phase 62 risk context."""

    model_config = ConfigDict(extra="ignore")

    assessment_id: str
    organization_id: Optional[str] = None
    facility_id: Optional[str] = None
    scope: Optional[Dict[str, Any]] = None
    application_version: Optional[str] = "v1.0.0"
    configuration_version: Optional[str] = "v1.0.0"
    safety_control_version: Optional[str] = "v1.0.0"
    risk_context_version: Optional[str] = "v1.0.0"
    idempotency_key: Optional[str] = None
    purpose: str = "GOVERNED_RISK_REVIEW"


class SafetyRiskReviewResponse(BaseModel):
    """Detailed response representation of a risk review."""

    model_config = ConfigDict(extra="ignore")

    review_id: str
    assessment_id: str
    organization_id: str
    facility_id: str
    state: ReviewLifecycleState
    evidence_sufficiency: EvidenceSufficiencyState
    current_disposition: Optional[RiskDispositionType] = None
    version_tag: int
    created_at: datetime
    updated_at: datetime


class SafetyRiskReviewStatusResponse(BaseModel):
    """Lifecycle status summary of a risk review."""

    model_config = ConfigDict(extra="ignore")

    review_id: str
    state: ReviewLifecycleState
    readiness_state: Optional[DecisionReadinessState] = None
    is_ready_for_review: bool = False
    open_questions_count: int = 0
    evidence_count: int = 0
    current_disposition: Optional[RiskDispositionType] = None
    updated_at: datetime


class ReopenReviewRequest(BaseModel):
    """Request payload to reopen a completed review."""

    model_config = ConfigDict(extra="ignore")

    reason: str
    new_evidence_reference: Optional[str] = None
    idempotency_key: Optional[str] = None


class ReassessReviewRequest(BaseModel):
    """Request payload to request reassessment of a review."""

    model_config = ConfigDict(extra="ignore")

    reason: str
    idempotency_key: Optional[str] = None


class ReanalyzeReviewRequest(BaseModel):
    """Request payload to request controlled reanalysis."""

    model_config = ConfigDict(extra="ignore")

    reason: str
    idempotency_key: Optional[str] = None
