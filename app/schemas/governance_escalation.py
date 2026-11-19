"""Phase 67: Governance Escalation Schemas.

Defines domain models and request/response contracts for governance escalations,
lifecycle transitions, routing, ownership, assignment, and acknowledgement.

Mandatory Governance Invariants:
1. Escalation acknowledgement does not mean that the underlying issue has been resolved.
2. Assignment does not mean that an authorized decision has been made.
3. An escalation closed administratively does not establish clinical safety.
4. Automated routing must never bypass role-based authorization or separation-of-duties requirements.
5. An escalation deadline being met does not establish that the underlying safety concern was adequately addressed.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.governance_exception import (
    ExceptionCategory,
    GovernancePriority,
)


class EscalationLifecycleState(str, Enum):
    """Explicit lifecycle states for Phase 67 governance escalations."""

    DETECTED = "DETECTED"
    VALIDATING = "VALIDATING"
    CLASSIFICATION_PENDING = "CLASSIFICATION_PENDING"
    CLASSIFIED = "CLASSIFIED"
    ROUTING_PENDING = "ROUTING_PENDING"
    ROUTED = "ROUTED"
    ACKNOWLEDGEMENT_PENDING = "ACKNOWLEDGEMENT_PENDING"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    OWNERSHIP_PENDING = "OWNERSHIP_PENDING"
    ASSIGNED = "ASSIGNED"
    REVIEW_PENDING = "REVIEW_PENDING"
    REVIEW_IN_PROGRESS = "REVIEW_IN_PROGRESS"
    DECISION_PENDING = "DECISION_PENDING"
    ACTION_REQUIRED = "ACTION_REQUIRED"
    RESOLUTION_PENDING = "RESOLUTION_PENDING"
    RESOLUTION_REVIEW_PENDING = "RESOLUTION_REVIEW_PENDING"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"
    REOPEN_REQUIRED = "REOPEN_REQUIRED"
    REOPENED = "REOPENED"
    BLOCKED = "BLOCKED"
    OVERDUE = "OVERDUE"
    CONFLICTED = "CONFLICTED"
    DEPENDENCY_UNAVAILABLE = "DEPENDENCY_UNAVAILABLE"
    CANCELLED = "CANCELLED"
    SUPERSEDED = "SUPERSEDED"


class RoutingDomain(str, Enum):
    """Functional domains for routing safety governance escalations."""

    CLINICAL_SAFETY = "CLINICAL_SAFETY"
    MEDICATION_SAFETY = "MEDICATION_SAFETY"
    SYSTEM_INTEGRITY = "SYSTEM_INTEGRITY"
    INCIDENT_GOVERNANCE = "INCIDENT_GOVERNANCE"
    ASSURANCE_COMPLIANCE = "ASSURANCE_COMPLIANCE"
    WORKFLOW_COORDINATION = "WORKFLOW_COORDINATION"


class GovernanceEscalationRecord(BaseModel):
    """Domain model representing a cross-workflow governance escalation."""

    model_config = ConfigDict(extra="ignore")

    escalation_id: str = Field(default_factory=lambda: f"gesc-{uuid.uuid4().hex[:12]}")
    title: str
    summary: str
    primary_category: ExceptionCategory
    governance_priority: GovernancePriority = GovernancePriority.UNCLASSIFIED
    lifecycle_state: EscalationLifecycleState = EscalationLifecycleState.DETECTED

    # Tenant scoping
    organization_id: str
    facility_id: str
    patient_id: Optional[str] = None

    # Routing & Ownership
    routing_domain: RoutingDomain = RoutingDomain.WORKFLOW_COORDINATION
    escalation_level: int = 1
    assigned_owner_id: Optional[str] = None
    assigned_owner_role: Optional[str] = None
    assigned_at: Optional[datetime] = None
    assigned_by: Optional[str] = None
    secondary_reviewer_id: Optional[str] = None
    governance_committee_ref: Optional[str] = None
    specialist_role_required: Optional[str] = None

    # Acknowledgement
    is_acknowledged: bool = False
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    acknowledgement_deadline: Optional[datetime] = None

    # Deadlines
    initial_review_deadline: Optional[datetime] = None
    decision_deadline: Optional[datetime] = None
    resolution_deadline: Optional[datetime] = None
    is_overdue: bool = False
    overdue_duration_seconds: Optional[int] = None
    extensions_count: int = 0

    # Cross-workflow tracking
    aggregated_exception_ids: List[str] = Field(default_factory=list)
    related_workflow_ids: List[str] = Field(default_factory=list)
    conflicting_decision_ids: List[str] = Field(default_factory=list)
    dependency_refs: List[str] = Field(default_factory=list)

    # Resolution & Closure
    resolution_rationale: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    closure_rationale: Optional[str] = None
    closed_at: Optional[datetime] = None
    closed_by: Optional[str] = None

    # Reopening metadata
    is_reopened: bool = False
    reopen_count: int = 0
    reopened_at: Optional[datetime] = None
    reopened_by: Optional[str] = None
    reopen_trigger_source: Optional[str] = None
    reopen_rationale: Optional[str] = None

    # Policy and audit
    policy_reference: str = "gov-escalation-policy-v1"
    policy_version: str = "v1.0.0"
    created_by: str = "system"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    idempotency_key: Optional[str] = None
    correlation_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CreateGovernanceEscalationRequest(BaseModel):
    """Request payload to create a new governance escalation."""

    model_config = ConfigDict(extra="ignore")

    title: str
    summary: str
    primary_category: ExceptionCategory
    governance_priority: Optional[GovernancePriority] = GovernancePriority.UNCLASSIFIED
    routing_domain: Optional[RoutingDomain] = RoutingDomain.WORKFLOW_COORDINATION
    patient_id: Optional[str] = None
    initial_exception_id: Optional[str] = None
    related_workflow_ids: Optional[List[str]] = Field(default_factory=list)
    dependency_refs: Optional[List[str]] = Field(default_factory=list)
    policy_reference: Optional[str] = "gov-escalation-policy-v1"
    policy_version: Optional[str] = "v1.0.0"
    idempotency_key: Optional[str] = None
    correlation_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ClassifyEscalationRequest(BaseModel):
    """Request payload to evaluate and record governance priority and classification."""

    model_config = ConfigDict(extra="ignore")

    override_priority: Optional[GovernancePriority] = None
    rationale: Optional[str] = None
    policy_version: Optional[str] = "v1.0.0"


class RouteEscalationRequest(BaseModel):
    """Request payload to route an escalation to a governance domain or hierarchy."""

    model_config = ConfigDict(extra="ignore")

    routing_domain: RoutingDomain
    escalation_level: Optional[int] = 1
    specialist_role_required: Optional[str] = None
    governance_committee_ref: Optional[str] = None
    rationale: str


class AssignEscalationRequest(BaseModel):
    """Request payload to assign an owner to an escalation."""

    model_config = ConfigDict(extra="ignore")

    assigned_owner_id: str
    assigned_owner_role: str
    secondary_reviewer_id: Optional[str] = None
    rationale: str


class ReassignEscalationRequest(BaseModel):
    """Request payload to reassign an escalation to a new owner."""

    model_config = ConfigDict(extra="ignore")

    new_owner_id: str
    new_owner_role: str
    reassignment_reason: str


class AcknowledgeEscalationRequest(BaseModel):
    """Request payload for an assigned owner to acknowledge an escalation."""

    model_config = ConfigDict(extra="ignore")

    acknowledgement_notes: Optional[str] = "Escalation assignment acknowledged."


class EscalationHistoryRecord(BaseModel):
    """Audit entry documenting an escalation state transition or action."""

    model_config = ConfigDict(extra="ignore")

    history_id: str = Field(default_factory=lambda: f"ghist-{uuid.uuid4().hex[:12]}")
    escalation_id: str
    from_state: EscalationLifecycleState
    to_state: EscalationLifecycleState
    action: str
    performed_by: str
    performed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    rationale: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)


class EscalationHistoryResponse(BaseModel):
    """Response payload containing escalation audit transition history."""

    model_config = ConfigDict(extra="ignore")

    escalation_id: str
    total_events: int
    history: List[EscalationHistoryRecord]
