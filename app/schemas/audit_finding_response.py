"""Phase 70: Audit Findings & Auditee Response Schemas.

Defines schemas for:
- Audit findings and classifications (CONTROL_GAP, PROCESS_DEVIATION, etc.)
- Confirmed vs disputed findings
- Auditee responses and management action plans
- Linking findings to Phase 54 corrective action orchestration
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class AuditFindingCategory(str, Enum):
    """Classification of audit finding."""

    CONTROL_GAP = "CONTROL_GAP"
    PROCESS_DEVIATION = "PROCESS_DEVIATION"
    DOCUMENTATION_GAP = "DOCUMENTATION_GAP"
    EVIDENCE_GAP = "EVIDENCE_GAP"
    GOVERNANCE_WEAKNESS = "GOVERNANCE_WEAKNESS"
    AUTHORIZATION_ISSUE = "AUTHORIZATION_ISSUE"
    TRACEABILITY_GAP = "TRACEABILITY_GAP"
    REPEAT_FINDING = "REPEAT_FINDING"
    POTENTIAL_SYSTEMIC_ISSUE = "POTENTIAL_SYSTEMIC_ISSUE"
    OTHER = "OTHER"


class AuditFindingSeverity(str, Enum):
    """Severity tier for audit findings."""

    ROUTINE = "ROUTINE"
    ELEVATED = "ELEVATED"
    HIGH = "HIGH"
    URGENT = "URGENT"
    CRITICAL = "CRITICAL"


class AuditFindingStatus(str, Enum):
    """Lifecycle status of an audit finding."""

    DRAFT = "DRAFT"
    UNDER_REVIEW = "UNDER_REVIEW"
    CONFIRMED = "CONFIRMED"
    DISPUTED = "DISPUTED"
    RESPONSE_PENDING = "RESPONSE_PENDING"
    ACTION_REQUIRED = "ACTION_REQUIRED"
    FOLLOW_UP_PENDING = "FOLLOW_UP_PENDING"
    VERIFIED = "VERIFIED"
    CLOSED = "CLOSED"
    WITHDRAWN = "WITHDRAWN"


class AuditeeResponseType(str, Enum):
    """Auditee stance on an audit finding."""

    ACKNOWLEDGED = "ACKNOWLEDGED"
    ACCEPTED = "ACCEPTED"
    DISPUTED = "DISPUTED"


class AuditFindingRecord(BaseModel):
    """Domain model tracking an audit observation or finding."""

    model_config = ConfigDict(extra="ignore")

    finding_id: str = Field(default_factory=lambda: f"gafd-{uuid.uuid4().hex[:12]}")
    audit_id: str
    criterion_id: Optional[str] = None
    test_id: Optional[str] = None

    category: AuditFindingCategory = AuditFindingCategory.CONTROL_GAP
    severity: AuditFindingSeverity = AuditFindingSeverity.HIGH
    status: AuditFindingStatus = AuditFindingStatus.DRAFT

    finding_statement: str
    observed_condition: str
    expected_condition: str
    gap_description: str
    potential_impact: Optional[str] = None

    evidence_refs: List[str] = Field(default_factory=list)
    responsible_owner_id: Optional[str] = None
    responsible_owner_role: Optional[str] = None

    is_confirmed: bool = False
    confirmed_by: Optional[str] = None
    confirmed_at: Optional[datetime] = None

    is_disputed: bool = False
    dispute_rationale: Optional[str] = None

    corrective_action_ref: Optional[str] = None  # Link to Phase 54 action
    phase55_eval_ref: Optional[str] = None  # Link to Phase 55 effectiveness eval

    is_closed: bool = False
    closed_by: Optional[str] = None
    closed_at: Optional[datetime] = None
    closure_rationale: Optional[str] = None

    created_by: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AuditeeResponseRecord(BaseModel):
    """Domain model capturing auditee response and proposed remediation."""

    model_config = ConfigDict(extra="ignore")

    response_id: str = Field(default_factory=lambda: f"garp-{uuid.uuid4().hex[:12]}")
    finding_id: str
    auditee_id: str
    auditee_role: str
    response_type: AuditeeResponseType = AuditeeResponseType.ACCEPTED
    response_statement: str
    explanation: Optional[str] = None
    supporting_evidence_refs: List[str] = Field(default_factory=list)

    proposed_corrective_action: Optional[str] = None
    proposed_completion_date: Optional[datetime] = None

    submitted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    auditor_review_decision: Optional[str] = None  # ACCEPTED, REJECTED, CLARIFICATION_REQUIRED
    auditor_review_comments: Optional[str] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ===========================================================================
# Request Models
# ===========================================================================

class CreateAuditFindingRequest(BaseModel):
    """Request payload to record an audit observation or finding."""

    model_config = ConfigDict(extra="ignore")

    criterion_id: Optional[str] = None
    test_id: Optional[str] = None
    category: AuditFindingCategory
    severity: AuditFindingSeverity
    finding_statement: str
    observed_condition: str
    expected_condition: str
    gap_description: str
    potential_impact: Optional[str] = None
    evidence_refs: Optional[List[str]] = Field(default_factory=list)
    responsible_owner_id: Optional[str] = None
    responsible_owner_role: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ConfirmAuditFindingRequest(BaseModel):
    """Request payload for lead auditor or governance lead to confirm a finding."""

    model_config = ConfigDict(extra="ignore")

    confirmation_rationale: str


class DisputeAuditFindingRequest(BaseModel):
    """Request payload to dispute a finding."""

    model_config = ConfigDict(extra="ignore")

    dispute_rationale: str
    supporting_evidence_refs: Optional[List[str]] = Field(default_factory=list)


class SubmitAuditeeResponseRequest(BaseModel):
    """Request payload for auditee to respond to a confirmed finding."""

    model_config = ConfigDict(extra="ignore")

    response_type: AuditeeResponseType
    response_statement: str
    explanation: Optional[str] = None
    supporting_evidence_refs: Optional[List[str]] = Field(default_factory=list)
    proposed_corrective_action: Optional[str] = None
    proposed_completion_date: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ReviewAuditeeResponseRequest(BaseModel):
    """Request payload for auditor to evaluate an auditee response."""

    model_config = ConfigDict(extra="ignore")

    decision: str  # ACCEPTED, REJECTED, CLARIFICATION_REQUIRED
    review_comments: str


class LinkCorrectiveActionRequest(BaseModel):
    """Request payload to link an authoritative Phase 54 corrective action."""

    model_config = ConfigDict(extra="ignore")

    phase54_action_ref: str
    phase55_eval_ref: Optional[str] = None
    notes: Optional[str] = None
