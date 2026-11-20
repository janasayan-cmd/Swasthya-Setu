"""Phase 72: Management Review Decisions, Commitments & Follow-Through Schemas.

Defines schemas for:
- Meeting discussion recording and minute keeping
- Management decisions, categories, authority validation, and supersession
- Management commitments, lifecycle states, owner assignment, progress tracking
- Verification of completed actions and escalation of overdue commitments
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class ManagementDecisionCategory(str, Enum):
    """Formal categories of management decisions."""

    POLICY_ADOPTION_OR_REVISION = "POLICY_ADOPTION_OR_REVISION"
    RESOURCE_ALLOCATION = "RESOURCE_ALLOCATION"
    SYSTEM_MODIFICATION = "SYSTEM_MODIFICATION"
    PROCESS_CHANGE = "PROCESS_CHANGE"
    CORRECTIVE_ACTION_INITIATION = "CORRECTIVE_ACTION_INITIATION"
    RISK_ACCEPTANCE = "RISK_ACCEPTANCE"
    RISK_ESCALATION = "RISK_ESCALATION"
    AUDIT_REFERRAL = "AUDIT_REFERRAL"
    GOVERNANCE_EXCEPTION_RESOLUTION = "GOVERNANCE_EXCEPTION_RESOLUTION"
    COMPLIANCE_REMEDY = "COMPLIANCE_REMEDY"
    OTHER_MANAGEMENT_ACTION = "OTHER_MANAGEMENT_ACTION"


class ManagementDecisionStatus(str, Enum):
    """Lifecycle status of a management decision."""

    DRAFT = "DRAFT"
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    DEFERRED = "DEFERRED"
    SUPERSEDED = "SUPERSEDED"
    IMPLEMENTED = "IMPLEMENTED"


class CommitmentStatus(str, Enum):
    """Lifecycle status of an actionable management commitment."""

    OPEN = "OPEN"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    UNDER_REVIEW = "UNDER_REVIEW"
    PENDING_VERIFICATION = "PENDING_VERIFICATION"
    VERIFIED = "VERIFIED"
    OVERDUE = "OVERDUE"
    ESCALATED = "ESCALATED"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


class CommitmentPriority(str, Enum):
    """Priority level for an action commitment."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class DiscussionRecord(BaseModel):
    """Domain model tracking a recorded discussion during review meeting."""

    model_config = ConfigDict(extra="ignore")

    discussion_id: str = Field(default_factory=lambda: f"gmds-{uuid.uuid4().hex[:12]}")
    review_id: str
    agenda_item_id: Optional[str] = None
    speaker_id: str
    speaker_name: Optional[str] = None
    topic: str
    discussion_notes: str
    key_points: List[str] = Field(default_factory=list)
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ManagementDecisionRecord(BaseModel):
    """Domain record representing an authoritative executive decision."""

    model_config = ConfigDict(extra="ignore")

    decision_id: str = Field(default_factory=lambda: f"gmdc-{uuid.uuid4().hex[:12]}")
    review_id: str
    agenda_item_id: Optional[str] = None
    title: str
    category: ManagementDecisionCategory = ManagementDecisionCategory.PROCESS_CHANGE
    status: ManagementDecisionStatus = ManagementDecisionStatus.APPROVED
    rationale: str

    decided_by_id: str
    decided_by_role: str
    decided_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    supporting_evidence_refs: List[str] = Field(default_factory=list)
    supersedes_decision_id: Optional[str] = None
    superseded_by_id: Optional[str] = None
    superseded_reason: Optional[str] = None

    commitments_count: int = 0
    organization_id: str
    facility_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ManagementCommitmentRecord(BaseModel):
    """Domain record tracking an assigned actionable follow-through commitment."""

    model_config = ConfigDict(extra="ignore")

    commitment_id: str = Field(default_factory=lambda: f"gmcm-{uuid.uuid4().hex[:12]}")
    decision_id: str
    review_id: str
    title: str
    description: str

    responsible_owner_id: str
    accountable_lead_id: str
    status: CommitmentStatus = CommitmentStatus.ASSIGNED
    priority: CommitmentPriority = CommitmentPriority.MEDIUM
    due_date: datetime

    progress_percentage: int = 0
    progress_notes: List[Dict[str, Any]] = Field(default_factory=list)
    completion_evidence_refs: List[str] = Field(default_factory=list)

    verified_by: Optional[str] = None
    verified_at: Optional[datetime] = None
    verification_notes: Optional[str] = None

    # Linkages to authoritative external workflow engines
    linked_capa_id: Optional[str] = None  # Phase 54
    linked_effectiveness_id: Optional[str] = None  # Phase 55
    linked_risk_review_id: Optional[str] = None  # Phase 63
    linked_escalation_id: Optional[str] = None  # Phase 67

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CommitmentEscalationRecord(BaseModel):
    """Domain record representing an escalation of an overdue or blocked commitment."""

    model_config = ConfigDict(extra="ignore")

    escalation_id: str = Field(default_factory=lambda: f"gmes-{uuid.uuid4().hex[:12]}")
    commitment_id: str
    review_id: str
    escalated_by: str
    escalated_to: str
    escalation_reason: str
    urgency: str = "HIGH"
    escalated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None


# Request Models
class CreateDiscussionRecordRequest(BaseModel):
    """Request payload to record discussion during meeting."""

    model_config = ConfigDict(extra="ignore")

    agenda_item_id: Optional[str] = None
    topic: str
    discussion_notes: str
    key_points: Optional[List[str]] = Field(default_factory=list)
    speaker_name: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class CreateManagementDecisionRequest(BaseModel):
    """Request payload to formalize a management decision."""

    model_config = ConfigDict(extra="ignore")

    agenda_item_id: Optional[str] = None
    title: str
    category: ManagementDecisionCategory
    rationale: str
    supporting_evidence_refs: Optional[List[str]] = Field(default_factory=list)
    supersedes_decision_id: Optional[str] = None
    facility_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ApproveDecisionRequest(BaseModel):
    """Request payload to approve a proposed decision."""

    model_config = ConfigDict(extra="ignore")

    approval_notes: Optional[str] = None


class DeferDecisionRequest(BaseModel):
    """Request payload to defer a decision to a later review."""

    model_config = ConfigDict(extra="ignore")

    deferral_reason: str


class SupersedeDecisionRequest(BaseModel):
    """Request payload to supersede an existing decision."""

    model_config = ConfigDict(extra="ignore")

    superseding_decision_id: str
    superseded_reason: str


class CreateManagementCommitmentRequest(BaseModel):
    """Request payload to create an actionable follow-through commitment."""

    model_config = ConfigDict(extra="ignore")

    decision_id: str
    title: str
    description: str
    responsible_owner_id: str
    accountable_lead_id: str
    priority: Optional[CommitmentPriority] = CommitmentPriority.MEDIUM
    due_date: datetime
    linked_capa_id: Optional[str] = None
    linked_effectiveness_id: Optional[str] = None
    linked_risk_review_id: Optional[str] = None
    linked_escalation_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class UpdateCommitmentProgressRequest(BaseModel):
    """Request payload to report progress on a commitment."""

    model_config = ConfigDict(extra="ignore")

    progress_percentage: int = Field(ge=0, le=100)
    note: str
    completion_evidence_refs: Optional[List[str]] = None


class SubmitCommitmentVerificationRequest(BaseModel):
    """Request payload to submit a commitment for formal verification."""

    model_config = ConfigDict(extra="ignore")

    completion_evidence_refs: List[str]
    summary_of_implementation: str


class VerifyCommitmentRequest(BaseModel):
    """Request payload to verify or reject a completed commitment."""

    model_config = ConfigDict(extra="ignore")

    verified: bool
    verification_notes: str


class EscalateCommitmentRequest(BaseModel):
    """Request payload to escalate an overdue or blocked commitment."""

    model_config = ConfigDict(extra="ignore")

    escalated_to: str
    escalation_reason: str
    urgency: Optional[str] = "HIGH"
