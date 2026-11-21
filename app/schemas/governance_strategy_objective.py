"""Phase 78: Clinical Safety Governance Strategic Objective Schemas.

Defines schemas and models for:
- Managing long-term strategic governance objectives
- Lifecycle progression from DRAFT to APPROVED, ACTIVE, and COMPLETED
- Separation of duties on objective review and approval
- Objective versioning and traceability to Phase 77, Phase 63, Phase 70, Phase 72
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


CLINICAL_SAFETY_STRATEGY_DISCLAIMER = (
    "Strategic roadmap and capability targets are internal planning and coordination instruments "
    "and do NOT constitute proof of clinical safety, regulatory compliance, or improved patient outcomes. "
    "Phase 78 does not replace authoritative workflows of Phases 49, 54, 55, 63, 67, 69, 70, 72, 73, 74, 75, 76, or 77."
)


class ObjectiveCategory(str, Enum):
    """Strategic governance theme or category."""
    LEADERSHIP_OVERSIGHT = "LEADERSHIP_OVERSIGHT"
    RISK_GOVERNANCE = "RISK_GOVERNANCE"
    INCIDENT_PREVENTION = "INCIDENT_PREVENTION"
    CLINICAL_ASSURANCE = "CLINICAL_ASSURANCE"
    CAPABILITY_DEVELOPMENT = "CAPABILITY_DEVELOPMENT"
    SYSTEMIC_TRANSFORMATION = "SYSTEMIC_TRANSFORMATION"


class ObjectivePriority(str, Enum):
    """Strategic priority level."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class PlanningHorizon(str, Enum):
    """Strategic planning horizon."""
    ONE_YEAR = "ONE_YEAR"
    THREE_YEAR = "THREE_YEAR"
    FIVE_YEAR = "FIVE_YEAR"


class ObjectiveStatus(str, Enum):
    """Lifecycle status of a strategic objective."""
    DRAFT = "DRAFT"
    UNDER_REVIEW = "UNDER_REVIEW"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    ACTIVE = "ACTIVE"
    ON_HOLD = "ON_HOLD"
    SUPERSEDED = "SUPERSEDED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class GovernanceStrategyObjectiveRecord(BaseModel):
    """Authoritative record for an approved clinical safety governance strategic objective."""
    model_config = ConfigDict(extra="forbid")

    objective_id: str
    tenant_id: str
    title: str
    description: str
    rationale: str
    category: ObjectiveCategory
    organizational_scope: Dict[str, Any] = Field(default_factory=dict)
    source_reference: Optional[str] = None
    related_phase77_gap_ids: List[str] = Field(default_factory=list)
    related_governance_risk_ids: List[str] = Field(default_factory=list)
    related_audit_finding_ids: List[str] = Field(default_factory=list)
    related_management_decision_ids: List[str] = Field(default_factory=list)
    intended_target_state: str
    priority: ObjectivePriority
    planning_horizon: PlanningHorizon
    responsible_governance_owner_id: str
    supporting_stakeholders: List[str] = Field(default_factory=list)
    dependencies: List[str] = Field(default_factory=list)
    success_indicators: List[str] = Field(default_factory=list)
    measurement_methodology: str
    baseline_reference: Optional[str] = None
    target_condition: str
    status: ObjectiveStatus
    created_by: str
    approved_by: Optional[str] = None
    approval_date: Optional[str] = None
    approval_reference: Optional[str] = None
    version: int = 1
    disclaimer: str = CLINICAL_SAFETY_STRATEGY_DISCLAIMER
    created_at: str
    updated_at: str


class CreateObjectiveRequest(BaseModel):
    """Request to create a new strategic governance objective in DRAFT status."""
    model_config = ConfigDict(extra="forbid")

    title: str
    description: str
    rationale: str
    category: ObjectiveCategory
    organizational_scope: Optional[Dict[str, Any]] = None
    source_reference: Optional[str] = None
    related_phase77_gap_ids: Optional[List[str]] = None
    related_governance_risk_ids: Optional[List[str]] = None
    related_audit_finding_ids: Optional[List[str]] = None
    related_management_decision_ids: Optional[List[str]] = None
    intended_target_state: str
    priority: ObjectivePriority = ObjectivePriority.HIGH
    planning_horizon: PlanningHorizon = PlanningHorizon.THREE_YEAR
    responsible_governance_owner_id: str
    supporting_stakeholders: Optional[List[str]] = None
    dependencies: Optional[List[str]] = None
    success_indicators: Optional[List[str]] = None
    measurement_methodology: str
    baseline_reference: Optional[str] = None
    target_condition: str


class UpdateObjectiveRequest(BaseModel):
    """Request to update a draft objective."""
    model_config = ConfigDict(extra="forbid")

    title: Optional[str] = None
    description: Optional[str] = None
    rationale: Optional[str] = None
    priority: Optional[ObjectivePriority] = None
    intended_target_state: Optional[str] = None
    target_condition: Optional[str] = None
    measurement_methodology: Optional[str] = None


class SubmitObjectiveRequest(BaseModel):
    """Request to submit an objective for governance review."""
    model_config = ConfigDict(extra="forbid")

    submission_notes: Optional[str] = None


class ApproveObjectiveRequest(BaseModel):
    """Request to approve an objective with separation of duties enforcement."""
    model_config = ConfigDict(extra="forbid")

    approval_reference: str = Field(..., description="Reference to Phase 72 executive review or governance decision")
    approver_notes: Optional[str] = None


class RetireObjectiveRequest(BaseModel):
    """Request to retire or supersede an objective."""
    model_config = ConfigDict(extra="forbid")

    reason: str
    superseded_by_objective_id: Optional[str] = None
