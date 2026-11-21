"""Phase 75: Portfolio Initiative Registration & Lineage Schemas.

Defines schemas and models for:
- Registering authorized governance change initiatives into portfolios
- Preserving traceability to Phase 72 decisions, Phase 73 implementations, and Phase 74 adoptions
- Initiative coordination lifecycle and lineage responses
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.governance_change_portfolio import PortfolioPriority


class InitiativeCoordinationStatus(str, Enum):
    """Coordination status of an initiative within a portfolio."""
    PROPOSED = "PROPOSED"
    ACCEPTED = "ACCEPTED"
    COORDINATING = "COORDINATING"
    BLOCKED = "BLOCKED"
    COMPLETED = "COMPLETED"
    WITHDRAWN = "WITHDRAWN"


class PortfolioInitiativeRecord(BaseModel):
    """Authoritative record for an initiative coordinated under a portfolio."""
    model_config = ConfigDict(extra="forbid")

    initiative_id: str
    portfolio_id: str
    tenant_id: str
    decision_id: str = Field(..., description="Phase 72 approved governance decision reference")
    implementation_id: str = Field(..., description="Phase 73 implementation record reference")
    adoption_registration_id: Optional[str] = Field(None, description="Phase 74 adoption registration reference, if applicable")
    title: str
    initiative_description: str
    intended_operational_change: str
    participating_facilities: List[str] = Field(default_factory=list)
    participating_departments: List[str] = Field(default_factory=list)
    participating_teams: List[str] = Field(default_factory=list)
    accountable_owner_id: str
    planned_start_date: str
    planned_target_date: str
    priority: PortfolioPriority = PortfolioPriority.MEDIUM
    coordination_status: InitiativeCoordinationStatus = InitiativeCoordinationStatus.PROPOSED
    source_implementation_status: Optional[str] = None
    source_adoption_status: Optional[str] = None
    is_blocked: bool = False
    blocked_reason: Optional[str] = None
    created_by: str
    created_at: str
    updated_at: str


class RegisterInitiativeRequest(BaseModel):
    """Request payload to register an authorized governance initiative into a portfolio."""
    model_config = ConfigDict(extra="forbid")

    decision_id: str = Field(..., min_length=2)
    implementation_id: str = Field(..., min_length=2)
    adoption_registration_id: Optional[str] = None
    title: str = Field(..., min_length=3, max_length=255)
    initiative_description: str = Field(..., min_length=5)
    intended_operational_change: str = Field(..., min_length=5)
    participating_facilities: List[str] = Field(default_factory=list)
    participating_departments: List[str] = Field(default_factory=list)
    participating_teams: List[str] = Field(default_factory=list)
    accountable_owner_id: str
    planned_start_date: str
    planned_target_date: str
    priority: PortfolioPriority = PortfolioPriority.MEDIUM


class RemoveInitiativeRequest(BaseModel):
    """Request payload to remove an initiative from portfolio coordination."""
    model_config = ConfigDict(extra="forbid")

    removal_reason: str = Field(..., min_length=5)


class InitiativeLineageResponse(BaseModel):
    """Full decision-to-portfolio governance lineage response."""
    model_config = ConfigDict(extra="forbid")

    initiative_id: str
    portfolio_id: str
    tenant_id: str
    decision_id: str
    implementation_id: str
    adoption_registration_id: Optional[str] = None
    title: str
    coordination_status: str
    source_implementation_status: Optional[str] = None
    source_adoption_status: Optional[str] = None
    dependencies_count: int = 0
    conflicts_count: int = 0
    lineage_nodes: List[Dict[str, Any]] = Field(default_factory=list)
