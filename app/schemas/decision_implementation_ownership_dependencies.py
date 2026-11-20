"""Phase 73: Implementation Ownership & Dependency Management Schemas.

Defines schemas for:
- Role assignments, acceptance tracking, and separation of duties enforcement
- Prerequisites and dependency tracking across Phase 49-72 workflows
- Circular dependency prevention and authorized waiver governance
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class AssignmentRole(str, Enum):
    """Specific functional ownership role in implementation coordination."""

    EXECUTIVE_SPONSOR = "EXECUTIVE_SPONSOR"
    DECISION_OWNER = "DECISION_OWNER"
    IMPLEMENTATION_LEAD = "IMPLEMENTATION_LEAD"
    WORK_ITEM_OWNER = "WORK_ITEM_OWNER"
    SUPPORTING_TEAM_MEMBER = "SUPPORTING_TEAM_MEMBER"
    INDEPENDENT_VERIFIER = "INDEPENDENT_VERIFIER"
    GOVERNANCE_REVIEWER = "GOVERNANCE_REVIEWER"
    ESCALATION_OWNER = "ESCALATION_OWNER"


class AcceptanceStatus(str, Enum):
    """Acceptance state of an assigned responsibility."""

    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"
    DELEGATED = "DELEGATED"


class ImplementationAssignmentRecord(BaseModel):
    """Domain record representing an individual ownership assignment."""

    model_config = ConfigDict(extra="ignore")

    assignment_id: str = Field(default_factory=lambda: f"gdas-{uuid.uuid4().hex[:12]}")
    implementation_id: str
    user_id: str
    user_name: Optional[str] = None
    role: AssignmentRole
    acceptance_status: AcceptanceStatus = AcceptanceStatus.PENDING

    delegated_to_id: Optional[str] = None
    scope_of_responsibility: str = "Standard implementation ownership"
    assigned_by: str
    assigned_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    accepted_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DependencyType(str, Enum):
    """Types of dependencies that may gate implementation progress."""

    DECISION_PREREQUISITE = "DECISION_PREREQUISITE"
    POLICY_APPROVAL = "POLICY_APPROVAL"
    CORRECTIVE_ACTION = "CORRECTIVE_ACTION"
    RISK_REVIEW = "RISK_REVIEW"
    COMPLIANCE_REASSESSMENT = "COMPLIANCE_REASSESSMENT"
    AUDIT_FOLLOW_UP = "AUDIT_FOLLOW_UP"
    TECHNICAL_DEPLOYMENT = "TECHNICAL_DEPLOYMENT"
    TRAINING_COMPLETION = "TRAINING_COMPLETION"
    EXTERNAL_APPROVAL = "EXTERNAL_APPROVAL"


class DependencyStatus(str, Enum):
    """Evaluation status of an implementation dependency."""

    NOT_STARTED = "NOT_STARTED"
    PENDING = "PENDING"
    SATISFIED = "SATISFIED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    WAIVED_WITH_AUTHORIZATION = "WAIVED_WITH_AUTHORIZATION"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ImplementationDependencyRecord(BaseModel):
    """Domain record representing a prerequisite or gating dependency."""

    model_config = ConfigDict(extra="ignore")

    dependency_id: str = Field(default_factory=lambda: f"gddp-{uuid.uuid4().hex[:12]}")
    implementation_id: str
    dependency_type: DependencyType
    source_workflow: str
    source_record_id: str
    required_state: str = "COMPLETED"
    status: DependencyStatus = DependencyStatus.PENDING

    responsible_owner_id: Optional[str] = None
    blocking_reason: Optional[str] = None
    waiver_authorized_by: Optional[str] = None
    waiver_rationale: Optional[str] = None
    waived_at: Optional[datetime] = None

    last_verified_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)


# Request Models
class CreateAssignmentRequest(BaseModel):
    """Request payload to assign a responsibility."""

    model_config = ConfigDict(extra="ignore")

    user_id: str
    user_name: Optional[str] = None
    role: AssignmentRole
    scope_of_responsibility: Optional[str] = "Standard implementation ownership"
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class UpdateAssignmentRequest(BaseModel):
    """Request payload to update role or delegation."""

    model_config = ConfigDict(extra="ignore")

    role: Optional[AssignmentRole] = None
    delegated_to_id: Optional[str] = None
    scope_of_responsibility: Optional[str] = None


class AcceptAssignmentRequest(BaseModel):
    """Request payload to accept, decline, or delegate assignment."""

    model_config = ConfigDict(extra="ignore")

    acceptance_status: AcceptanceStatus
    delegated_to_id: Optional[str] = None
    comments: Optional[str] = None


class CreateDependencyRequest(BaseModel):
    """Request payload to link a dependency."""

    model_config = ConfigDict(extra="ignore")

    dependency_type: DependencyType
    source_workflow: str
    source_record_id: str
    required_state: Optional[str] = "COMPLETED"
    responsible_owner_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ReconcileDependencyRequest(BaseModel):
    """Request payload to update dependency state against destination record."""

    model_config = ConfigDict(extra="ignore")

    new_status: DependencyStatus
    notes: Optional[str] = None


class WaiveDependencyRequest(BaseModel):
    """Request payload to authorize a formal waiver on a dependency."""

    model_config = ConfigDict(extra="ignore")

    waiver_rationale: str
