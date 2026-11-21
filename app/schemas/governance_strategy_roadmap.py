"""Phase 78: Governance Strategic Roadmap Schemas.

Defines schemas and models for:
- Multi-year version-controlled clinical safety governance roadmaps
- Change provenance and revision tracking (never overwriting approved baselines)
- Separation of duties on roadmap approval
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.governance_strategy_objective import (
    CLINICAL_SAFETY_STRATEGY_DISCLAIMER,
    PlanningHorizon,
)


class RoadmapStatus(str, Enum):
    """Lifecycle status of a strategic roadmap."""
    DRAFT = "DRAFT"
    UNDER_REVIEW = "UNDER_REVIEW"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    SUPERSEDED = "SUPERSEDED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class RoadmapVersionChangeRecord(BaseModel):
    """Audit record for a material version revision to an approved roadmap."""
    model_config = ConfigDict(extra="forbid")

    change_id: str
    previous_version: int
    new_version: int
    change_reason: str
    requesting_user_id: str
    affected_objective_ids: List[str] = Field(default_factory=list)
    affected_milestone_ids: List[str] = Field(default_factory=list)
    approval_reference: str
    approved_by: str
    timestamp: str


class GovernanceStrategyRoadmapRecord(BaseModel):
    """Authoritative record for a multi-year clinical safety governance roadmap."""
    model_config = ConfigDict(extra="forbid")

    roadmap_id: str
    tenant_id: str
    title: str
    description: str
    organizational_scope: Dict[str, Any] = Field(default_factory=dict)
    planning_horizon: PlanningHorizon
    start_date: str
    end_date: str
    strategic_objective_ids: List[str] = Field(default_factory=list)
    strategic_priority_ids: List[str] = Field(default_factory=list)
    milestone_ids: List[str] = Field(default_factory=list)
    resource_proposal_ids: List[str] = Field(default_factory=list)
    status: RoadmapStatus
    owner_id: str
    current_version: int = 1
    approved_version: Optional[int] = None
    approved_by: Optional[str] = None
    approval_date: Optional[str] = None
    approval_reference: Optional[str] = None
    change_history: List[RoadmapVersionChangeRecord] = Field(default_factory=list)
    disclaimer: str = CLINICAL_SAFETY_STRATEGY_DISCLAIMER
    created_at: str
    updated_at: str


class CreateRoadmapRequest(BaseModel):
    """Request to create a new strategic roadmap in DRAFT status."""
    model_config = ConfigDict(extra="forbid")

    title: str
    description: str
    organizational_scope: Optional[Dict[str, Any]] = None
    planning_horizon: PlanningHorizon = PlanningHorizon.THREE_YEAR
    start_date: str
    end_date: str
    owner_id: str
    strategic_objective_ids: Optional[List[str]] = None
    strategic_priority_ids: Optional[List[str]] = None


class UpdateRoadmapRequest(BaseModel):
    """Request to update a draft roadmap."""
    model_config = ConfigDict(extra="forbid")

    title: Optional[str] = None
    description: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    strategic_objective_ids: Optional[List[str]] = None
    strategic_priority_ids: Optional[List[str]] = None


class SubmitRoadmapRequest(BaseModel):
    """Request to submit a draft roadmap for governance approval."""
    model_config = ConfigDict(extra="forbid")

    submission_notes: Optional[str] = None


class ApproveRoadmapRequest(BaseModel):
    """Request to approve a submitted roadmap with separation of duties enforcement."""
    model_config = ConfigDict(extra="forbid")

    approval_reference: str = Field(..., description="Reference to Phase 72 executive management decision")
    approver_notes: Optional[str] = None


class ReviseRoadmapRequest(BaseModel):
    """Request to formally revise an approved roadmap, incrementing the version and archiving the prior baseline."""
    model_config = ConfigDict(extra="forbid")

    change_reason: str
    approval_reference: str
    affected_objective_ids: Optional[List[str]] = None
    affected_milestone_ids: Optional[List[str]] = None
