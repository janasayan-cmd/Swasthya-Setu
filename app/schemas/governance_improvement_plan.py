"""Phase 77: Governance Capability Improvement Plan Schemas.

Defines schemas for strategic continuous governance improvement plans,
milestones, and handoffs to authoritative workflows (Phases 54, 63, 72, 73, 75).
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.governance_maturity_framework import (
    CLINICAL_SAFETY_DISCLAIMER,
    MaturityDimensionEnum,
    MaturityLevelEnum,
)


class ImprovementPlanStatus(str, Enum):
    """Lifecycle status of a governance capability improvement plan."""
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    MONITORING = "MONITORING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class ImprovementMilestoneStatus(str, Enum):
    """Status of an individual improvement milestone."""
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    ACHIEVED = "ACHIEVED"
    BLOCKED = "BLOCKED"
    DEFERRED = "DEFERRED"


class ImprovementMilestone(BaseModel):
    """Milestone definition within a governance improvement plan."""
    model_config = ConfigDict(extra="forbid")

    milestone_id: str
    title: str
    target_date: str
    status: ImprovementMilestoneStatus = ImprovementMilestoneStatus.PENDING
    completion_evidence: Optional[str] = None
    notes: Optional[str] = None


class GovernanceImprovementPlanRecord(BaseModel):
    """Authoritative record for a strategic governance improvement plan."""
    model_config = ConfigDict(extra="forbid")

    plan_id: str
    tenant_id: str
    title: str
    description: str
    target_dimensions: List[MaturityDimensionEnum]
    baseline_level: MaturityLevelEnum
    target_level: MaturityLevelEnum
    scope: Dict[str, Any] = Field(default_factory=dict)
    status: ImprovementPlanStatus
    accountable_owner_id: str
    milestones: List[ImprovementMilestone] = Field(default_factory=list)
    linked_gap_ids: List[str] = Field(default_factory=list)
    external_handoffs: List[Dict[str, Any]] = Field(default_factory=list)
    created_by: str
    target_completion_date: str
    disclaimer: str = CLINICAL_SAFETY_DISCLAIMER
    created_at: str
    updated_at: str


class CreateImprovementPlanRequest(BaseModel):
    """Request to create a new governance capability improvement plan."""
    model_config = ConfigDict(extra="forbid")

    title: str
    description: str
    target_dimensions: List[MaturityDimensionEnum]
    baseline_level: MaturityLevelEnum
    target_level: MaturityLevelEnum
    scope: Optional[Dict[str, Any]] = None
    accountable_owner_id: str
    target_completion_date: str
    linked_gap_ids: Optional[List[str]] = None
    milestones: Optional[List[ImprovementMilestone]] = None


class UpdateMilestoneRequest(BaseModel):
    """Request to update an improvement milestone status."""
    model_config = ConfigDict(extra="forbid")

    status: ImprovementMilestoneStatus
    completion_evidence: Optional[str] = None
    notes: Optional[str] = None


class RouteImprovementActionRequest(BaseModel):
    """Request to route an improvement action to an external authoritative workflow."""
    model_config = ConfigDict(extra="forbid")

    target_workflow: str = Field(..., description="Target phase e.g. PHASE_54_CAPA, PHASE_63_RISK, PHASE_72_MANAGEMENT_REVIEW, PHASE_73_IMPLEMENTATION, PHASE_75_PORTFOLIO")
    action_title: str
    action_description: str
    assigned_lead_id: str
    target_date: str
