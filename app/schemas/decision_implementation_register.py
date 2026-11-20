"""Phase 73: Decision Implementation Register Schemas.

Defines schemas for:
- Centralized decision implementation records
- Implementation categories, priorities, and lifecycle status
- Register queries, updates, and approval workflows
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class ImplementationCategory(str, Enum):
    """Configurable categories of decision implementation activities."""

    GOVERNANCE_PROCESS_CHANGE = "GOVERNANCE_PROCESS_CHANGE"
    POLICY_UPDATE = "POLICY_UPDATE"
    CONTROL_IMPLEMENTATION = "CONTROL_IMPLEMENTATION"
    COMPLIANCE_REMEDIATION = "COMPLIANCE_REMEDIATION"
    CORRECTIVE_ACTION = "CORRECTIVE_ACTION"
    RISK_REVIEW_REFERRAL = "RISK_REVIEW_REFERRAL"
    AUDIT_FOLLOW_UP = "AUDIT_FOLLOW_UP"
    TRAINING_OR_COMPETENCY_ACTION = "TRAINING_OR_COMPETENCY_ACTION"
    SYSTEM_CONFIGURATION_CHANGE = "SYSTEM_CONFIGURATION_CHANGE"
    OPERATIONAL_WORKFLOW_CHANGE = "OPERATIONAL_WORKFLOW_CHANGE"
    OTHER = "OTHER"


class ImplementationPriority(str, Enum):
    """Urgency / priority of an implementation initiative."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class ImplementationStatus(str, Enum):
    """Lifecycle states of a decision implementation initiative."""

    DRAFT = "DRAFT"
    PLANNING = "PLANNING"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    IN_PROGRESS = "IN_PROGRESS"
    BLOCKED = "BLOCKED"
    PENDING_VERIFICATION = "PENDING_VERIFICATION"
    VERIFIED = "VERIFIED"
    RECONCILED = "RECONCILED"
    CLOSED = "CLOSED"
    CLOSED_WITH_FOLLOW_UP = "CLOSED_WITH_FOLLOW_UP"
    CLOSED_WITH_LIMITATIONS = "CLOSED_WITH_LIMITATIONS"
    CANCELLED_WITH_AUTHORIZATION = "CANCELLED_WITH_AUTHORIZATION"
    REQUIRES_FURTHER_ACTION = "REQUIRES_FURTHER_ACTION"


class DecisionImplementationRecord(BaseModel):
    """Domain record representing an authorized implementation initiative."""

    model_config = ConfigDict(extra="ignore")

    implementation_id: str = Field(default_factory=lambda: f"gdim-{uuid.uuid4().hex[:12]}")
    decision_id: str
    intake_id: str
    title: str
    description: str
    intended_outcome: str

    responsible_owner_id: str
    accountable_lead_id: str
    supporting_teams: List[str] = Field(default_factory=list)

    category: ImplementationCategory = ImplementationCategory.OPERATIONAL_WORKFLOW_CHANGE
    priority: ImplementationPriority = ImplementationPriority.MEDIUM
    status: ImplementationStatus = ImplementationStatus.DRAFT

    target_completion_date: datetime
    actual_completion_date: Optional[datetime] = None

    required_approvals: List[str] = Field(default_factory=list)
    closure_conditions: List[str] = Field(default_factory=list)

    organization_id: str
    facility_id: Optional[str] = None

    created_by: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)


# Request Models
class CreateImplementationRequest(BaseModel):
    """Request payload to register a new decision implementation."""

    model_config = ConfigDict(extra="ignore")

    decision_id: str
    title: str
    description: str
    intended_outcome: str
    responsible_owner_id: str
    accountable_lead_id: str
    supporting_teams: Optional[List[str]] = Field(default_factory=list)
    category: Optional[ImplementationCategory] = ImplementationCategory.OPERATIONAL_WORKFLOW_CHANGE
    priority: Optional[ImplementationPriority] = ImplementationPriority.MEDIUM
    target_completion_date: datetime
    facility_id: Optional[str] = None
    required_approvals: Optional[List[str]] = Field(default_factory=list)
    closure_conditions: Optional[List[str]] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class UpdateImplementationRequest(BaseModel):
    """Request payload to update an existing implementation record."""

    model_config = ConfigDict(extra="ignore")

    title: Optional[str] = None
    description: Optional[str] = None
    intended_outcome: Optional[str] = None
    responsible_owner_id: Optional[str] = None
    accountable_lead_id: Optional[str] = None
    supporting_teams: Optional[List[str]] = None
    category: Optional[ImplementationCategory] = None
    priority: Optional[ImplementationPriority] = None
    target_completion_date: Optional[datetime] = None
    closure_conditions: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None


class SubmitImplementationRequest(BaseModel):
    """Request payload to advance implementation from PLANNING to PENDING_APPROVAL."""

    model_config = ConfigDict(extra="ignore")

    submission_notes: Optional[str] = None


class ApproveImplementationRequest(BaseModel):
    """Request payload to formally approve an implementation plan and advance to APPROVED."""

    model_config = ConfigDict(extra="ignore")

    approval_rationale: str
