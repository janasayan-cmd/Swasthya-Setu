"""Pydantic schemas for Clinical Order Review, Approval Gates & Controlled Authorization Management (Phase 40).

CRITICAL SAFETY PRINCIPLES:
- REVIEW != CLINICAL DECISION
- REVIEW != DIAGNOSIS / TREATMENT / PRESCRIPTION / TRIAGE
- APPROVAL REQUEST != APPROVAL
- APPROVAL != CLINICAL TRUTH / CLINICAL OUTCOME / PATIENT IMPROVEMENT
- AUTHORIZATION != EXECUTION
- AUTHORIZATION != PROVIDER ACCEPTANCE / ORDER COMPLETION
- AI CANNOT APPROVE, REJECT, OR BYPASS APPROVAL GATES
- SELF-APPROVAL IS DISALLOWED UNLESS EXPLICITLY PERMITTED BY POLICY
- MATERIAL TARGET CHANGES INVALIDATE APPROVAL AND TRIGGER RE-APPROVAL
- EXPIRED APPROVAL CANNOT AUTHORIZE EXECUTION
- HISTORICAL APPROVALS REMAIN IMMUTABLE AND AUDITABLE
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Approval Categories & Statuses (TRD Section 7, 8)
# ---------------------------------------------------------------------------

class ApprovalType(str, Enum):
    """Controlled categories of clinical and operational approvals."""
    ORDER_APPROVAL = "ORDER_APPROVAL"
    ORDER_SET_APPROVAL = "ORDER_SET_APPROVAL"
    REFERRAL_APPROVAL = "REFERRAL_APPROVAL"
    MEDICATION_ACTION_APPROVAL = "MEDICATION_ACTION_APPROVAL"
    DIAGNOSTIC_ACTION_APPROVAL = "DIAGNOSTIC_ACTION_APPROVAL"
    TEMPLATE_APPROVAL = "TEMPLATE_APPROVAL"
    PROTOCOL_APPROVAL = "PROTOCOL_APPROVAL"
    EXTERNAL_ACTION_APPROVAL = "EXTERNAL_ACTION_APPROVAL"
    OTHER_SUPPORTED_APPROVAL = "OTHER_SUPPORTED_APPROVAL"


class ApprovalStatus(str, Enum):
    """Lifecycle statuses for an approval request.

    INVARIANTS:
    - REQUESTED != APPROVED
    - IN_REVIEW != APPROVED
    - APPROVED != EXECUTED
    - EXECUTED != COMPLETED
    - COMPLETED != CLINICAL OUTCOME
    """
    REQUESTED = "REQUESTED"
    PENDING_REVIEW = "PENDING_REVIEW"
    IN_REVIEW = "IN_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    REVISION_REQUESTED = "REVISION_REQUESTED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    SUPERSEDED = "SUPERSEDED"
    FAILED = "FAILED"


class ApprovalDecisionType(str, Enum):
    """Explicit decision options available to an eligible reviewer."""
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    REQUEST_REVISION = "REQUEST_REVISION"


# ---------------------------------------------------------------------------
# Decision & Delegation Records (TRD Section 6, 18, 28)
# ---------------------------------------------------------------------------

class ApprovalDecisionRecord(BaseModel):
    """Immutable record of an individual reviewer's decision."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    decision_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    decision: ApprovalDecisionType
    approver_id: str = Field(description="Actor ID who rendered the decision")
    approver_role: str = Field(description="Role of approver at time of decision")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    reason: Optional[str] = Field(default=None, description="Clinical or administrative justification")
    notes: Optional[str] = Field(default=None)
    delegation_id: Optional[str] = Field(default=None, description="Delegation context ID if delegated")
    policy_version: int = Field(default=1, description="Policy version at decision time")
    target_version: Optional[str] = Field(default=None, description="Snapshot version of target action")


class ApprovalDelegationRecord(BaseModel):
    """Record tracking controlled delegation of review authority."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    delegation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    delegator_id: str
    delegatee_id: str
    organization_id: str
    facility_id: Optional[str] = None
    reason: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    is_active: bool = True


# ---------------------------------------------------------------------------
# Master Approval Record (TRD Section 6, 40)
# ---------------------------------------------------------------------------

class ApprovalRecord(BaseModel):
    """Persisted authoritative record of a clinical approval request and its lifecycle."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique Approval ID")
    target_type: str = Field(description="Target entity type (order, order_set_execution, template, etc.)")
    target_id: str = Field(description="Unique ID of the underlying clinical action")
    target_version: Optional[str] = Field(default=None, description="Version or snapshot hash of the target")
    target_snapshot_hash: Optional[str] = Field(default=None, description="Hash to detect material target modification")
    patient_id: str = Field(description="Patient identifier")
    requester_id: str = Field(description="User ID of the original requester")
    organization_id: str = Field(description="Organization scope")
    facility_id: Optional[str] = Field(default=None, description="Facility scope")
    approval_type: ApprovalType = Field(description="Category of approval")
    status: ApprovalStatus = Field(default=ApprovalStatus.REQUESTED, description="Current lifecycle state")
    policy_id: str = Field(default="default-policy", description="Policy identifier applied")
    policy_version: int = Field(default=1, description="Policy version applied")
    required_approvals_count: int = Field(default=1, description="Number of independent approvals required")
    current_approval_level: int = Field(default=1, description="Tier/Level in multi-level approvals")
    decisions: List[ApprovalDecisionRecord] = Field(default_factory=list, description="Historical decisions chain")
    assigned_reviewers: List[str] = Field(default_factory=list, description="Specific assigned reviewer IDs")
    assigned_roles: List[str] = Field(default_factory=list, description="Eligible approver roles")
    idempotency_key: str = Field(description="Client or workflow idempotency key")
    clinical_summary: Optional[str] = Field(default=None, description="Summary context for the reviewer")
    expires_at: Optional[datetime] = Field(default=None, description="Expiration timestamp")
    escalation_level: int = Field(default=0, description="Escalation count")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    decision_at: Optional[datetime] = Field(default=None, description="Timestamp of final approval decision")
    history: List[Dict[str, Any]] = Field(default_factory=list, description="Audit transition history")


# ---------------------------------------------------------------------------
# API Request / Response Schemas (TRD Section 31, 32, 33)
# ---------------------------------------------------------------------------

class ApprovalRequestCreate(BaseModel):
    """Payload to create an approval request for a candidate clinical action."""

    model_config = ConfigDict(populate_by_name=True)

    target_type: str = Field(description="Type of target action (e.g. 'order', 'order_set_execution')")
    target_id: str = Field(description="Target resource identifier")
    target_version: Optional[str] = Field(default="1", description="Target action revision or version")
    target_snapshot_hash: Optional[str] = Field(default=None, description="Content hash to detect changes")
    patient_id: str = Field(description="Patient identifier")
    approval_type: ApprovalType = Field(default=ApprovalType.ORDER_APPROVAL)
    clinical_summary: Optional[str] = Field(default=None, description="Concise clinical context for reviewer")
    organization_id: Optional[str] = None
    facility_id: Optional[str] = None
    idempotency_key: str = Field(description="Client-provided idempotency key")


class ApprovalDecisionRequest(BaseModel):
    """Payload to approve or reject a pending approval request."""

    model_config = ConfigDict(populate_by_name=True)

    reason: Optional[str] = Field(default=None, description="Clinical or administrative notes/reason")
    notes: Optional[str] = Field(default=None)
    delegation_id: Optional[str] = Field(default=None, description="Delegation reference if acting on behalf")


class ApprovalRevisionRequest(BaseModel):
    """Payload to request revisions on a pending action rather than outright rejecting."""

    model_config = ConfigDict(populate_by_name=True)

    reason: str = Field(description="Mandatory rationale for why revision is needed")
    required_changes: List[str] = Field(
        default_factory=list,
        description="List of specific changes required before re-submitting",
    )


class ApprovalDelegateRequest(BaseModel):
    """Payload to delegate review authority to another clinician."""

    model_config = ConfigDict(populate_by_name=True)

    delegate_to_user_id: str = Field(description="User ID of delegate clinician")
    reason: str = Field(description="Justification for delegation")
    valid_until: Optional[datetime] = Field(default=None, description="Expiration of delegation")


class ApprovalEscalateRequest(BaseModel):
    """Payload to manually escalate an overdue or complex approval request."""

    model_config = ConfigDict(populate_by_name=True)

    reason: str = Field(description="Reason for escalation")
    escalate_to_role: Optional[str] = Field(default=None, description="Target role (e.g. CLINICAL_DIRECTOR)")


class ApprovalCancelRequest(BaseModel):
    """Payload to cancel an approval request."""

    model_config = ConfigDict(populate_by_name=True)

    reason: str = Field(default="Cancelled by requester", description="Reason for cancellation")


class ApprovalFilter(BaseModel):
    """Query filters for searching approval records."""

    model_config = ConfigDict(populate_by_name=True)

    status: Optional[ApprovalStatus] = None
    approval_type: Optional[ApprovalType] = None
    patient_id: Optional[str] = None
    requester_id: Optional[str] = None
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    limit: int = 50
    offset: int = 0


class ApprovalListResponse(BaseModel):
    """Paginated response containing approval records."""

    model_config = ConfigDict(populate_by_name=True)

    items: List[ApprovalRecord] = Field(default_factory=list)
    total: int
    page: int = 1
    page_size: int = 50
