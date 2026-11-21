"""Phase 75: Governance Change Portfolio Registration Schemas.

Defines schemas and models for:
- Registering and organizing multiple authorized governance change initiatives into portfolios
- Portfolio scoping across organizations, facilities, departments, and teams
- Portfolio lifecycle management (draft, submit, review, approve, activate, suspend, archive)
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class PortfolioStatus(str, Enum):
    """Lifecycle states of a governance change portfolio."""
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    ACTIVE = "ACTIVE"
    ON_HOLD = "ON_HOLD"
    UNDER_REASSESSMENT = "UNDER_REASSESSMENT"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    ARCHIVED = "ARCHIVED"


class PortfolioPriority(str, Enum):
    """Governance priority level for portfolio-level oversight."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class GovernanceChangePortfolioRecord(BaseModel):
    """Authoritative record for a governance change portfolio."""
    model_config = ConfigDict(extra="forbid")

    portfolio_id: str
    tenant_id: str
    name: str
    description: str
    governance_purpose: str
    portfolio_owner_id: str
    executive_sponsor_id: Optional[str] = None
    participating_organizations: List[str] = Field(default_factory=list)
    participating_facilities: List[str] = Field(default_factory=list)
    participating_departments: List[str] = Field(default_factory=list)
    participating_teams: List[str] = Field(default_factory=list)
    priority: PortfolioPriority = PortfolioPriority.MEDIUM
    planned_start_date: str
    target_review_date: str
    status: PortfolioStatus = PortfolioStatus.DRAFT
    inclusion_criteria: List[str] = Field(default_factory=list)
    exclusion_criteria: List[str] = Field(default_factory=list)
    related_management_review_ids: List[str] = Field(default_factory=list)
    version: int = 1
    created_by: str
    submitted_by: Optional[str] = None
    submitted_at: Optional[str] = None
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    approval_comments: Optional[str] = None
    created_at: str
    updated_at: str


class CreatePortfolioRequest(BaseModel):
    """Request payload to create a new governance change portfolio."""
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=3, max_length=255)
    description: str = Field(..., min_length=5)
    governance_purpose: str = Field(..., min_length=5)
    portfolio_owner_id: str
    executive_sponsor_id: Optional[str] = None
    participating_organizations: List[str] = Field(default_factory=list)
    participating_facilities: List[str] = Field(default_factory=list)
    participating_departments: List[str] = Field(default_factory=list)
    participating_teams: List[str] = Field(default_factory=list)
    priority: PortfolioPriority = PortfolioPriority.MEDIUM
    planned_start_date: str
    target_review_date: str
    inclusion_criteria: List[str] = Field(default_factory=list)
    exclusion_criteria: List[str] = Field(default_factory=list)
    related_management_review_ids: List[str] = Field(default_factory=list)


class UpdatePortfolioRequest(BaseModel):
    """Request payload to update portfolio metadata and scope."""
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(None, min_length=3, max_length=255)
    description: Optional[str] = Field(None, min_length=5)
    governance_purpose: Optional[str] = Field(None, min_length=5)
    portfolio_owner_id: Optional[str] = None
    executive_sponsor_id: Optional[str] = None
    participating_organizations: Optional[List[str]] = None
    participating_facilities: Optional[List[str]] = None
    participating_departments: Optional[List[str]] = None
    participating_teams: Optional[List[str]] = None
    priority: Optional[PortfolioPriority] = None
    target_review_date: Optional[str] = None
    inclusion_criteria: Optional[List[str]] = None
    exclusion_criteria: Optional[List[str]] = None
    change_reason: Optional[str] = None


class SubmitPortfolioRequest(BaseModel):
    """Request payload to submit a portfolio for governance review."""
    model_config = ConfigDict(extra="forbid")

    submission_notes: Optional[str] = None


class ApprovePortfolioRequest(BaseModel):
    """Request payload to approve a submitted portfolio."""
    model_config = ConfigDict(extra="forbid")

    approval_comments: Optional[str] = None


class SuspendPortfolioRequest(BaseModel):
    """Request payload to suspend an active portfolio."""
    model_config = ConfigDict(extra="forbid")

    suspension_reason: str = Field(..., min_length=5)


class ArchivePortfolioRequest(BaseModel):
    """Request payload to archive a completed or cancelled portfolio."""
    model_config = ConfigDict(extra="forbid")

    archival_justification: str = Field(..., min_length=5)
