"""Phase 75: Portfolio Issues, Routing & Management Reviews Schemas.

Defines schemas and models for:
- Cross-initiative issues coordination and routing to authoritative workflows
- Portfolio review packages and advisory management review referrals
- Explicit governance boundaries preserving source workflow authority
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class PortfolioIssueRecord(BaseModel):
    """Authoritative record for an issue spanning multiple portfolio initiatives."""
    model_config = ConfigDict(extra="forbid")

    issue_id: str
    portfolio_id: str
    tenant_id: str
    related_initiative_ids: List[str] = Field(default_factory=list)
    title: str
    description: str
    category: str  # DEPENDENCY_FAILURE, SCHEDULE_CONFLICT, RESOURCE_SHORTAGE, GOVERNANCE_DISCREPANCY, DRIFT_ACCUMULATION
    severity: str = "MEDIUM"  # LOW, MEDIUM, HIGH, CRITICAL
    owner_id: str
    status: str = "OPEN"  # OPEN, IN_REVIEW, ROUTED, ESCALATED, RESOLVED
    routed_destination: Optional[str] = None  # PHASE_49_INCIDENTS, PHASE_54_CAPA, PHASE_63_RISK_REVIEW, PHASE_67_GOVERNANCE_EXCEPTION, PHASE_72_MANAGEMENT_REVIEW, PHASE_74_ADOPTION
    destination_reference: Optional[str] = None
    routing_notes: Optional[str] = None
    escalated_by: Optional[str] = None
    escalated_at: Optional[str] = None
    created_by: str
    created_at: str
    updated_at: str


class CreatePortfolioIssueRequest(BaseModel):
    """Request payload to log a cross-initiative issue."""
    model_config = ConfigDict(extra="forbid")

    related_initiative_ids: List[str] = Field(default_factory=list)
    title: str = Field(..., min_length=3, max_length=255)
    description: str = Field(..., min_length=5)
    category: str = Field(default="DEPENDENCY_FAILURE")
    severity: str = Field(default="MEDIUM")
    owner_id: str


class RoutePortfolioIssueRequest(BaseModel):
    """Request payload to route an issue to an authoritative workflow."""
    model_config = ConfigDict(extra="forbid")

    routed_destination: str = Field(..., min_length=3)
    destination_reference: str = Field(..., min_length=2)
    routing_notes: str = Field(..., min_length=5)


class EscalatePortfolioIssueRequest(BaseModel):
    """Request payload to escalate an issue to governance leadership."""
    model_config = ConfigDict(extra="forbid")

    escalation_reason: str = Field(..., min_length=5)
    target_governance_authority: str = Field(default="EXECUTIVE_SAFETY_COMMITTEE")


# -----------------------------------------------------------------------------
# Portfolio Reviews
# -----------------------------------------------------------------------------


class PortfolioReviewRecord(BaseModel):
    """Structured portfolio review package prepared for governance oversight."""
    model_config = ConfigDict(extra="forbid")

    review_id: str
    portfolio_id: str
    tenant_id: str
    review_title: str
    review_period: str
    participants: List[str] = Field(default_factory=list)
    summary_snapshot: Dict[str, Any] = Field(default_factory=dict)
    recommendations: List[str] = Field(
        default_factory=list,
        description="Advisory recommendations only. Does not independently modify source governance decisions."
    )
    referred_to_management_review: bool = False
    management_review_reference: Optional[str] = None
    referral_notes: Optional[str] = None
    status: str = "DRAFT"  # DRAFT, SUBMITTED, APPROVED, REFERRED
    chair_id: str
    submitted_by: Optional[str] = None
    approved_by: Optional[str] = None
    created_at: str
    updated_at: str


class CreatePortfolioReviewRequest(BaseModel):
    """Request payload to initiate a portfolio review."""
    model_config = ConfigDict(extra="forbid")

    review_title: str = Field(..., min_length=3, max_length=255)
    review_period: str = Field(..., min_length=3)
    participants: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)


class SubmitPortfolioReviewRequest(BaseModel):
    """Request payload to submit a portfolio review."""
    model_config = ConfigDict(extra="forbid")

    submission_notes: Optional[str] = None


class ApprovePortfolioReviewRequest(BaseModel):
    """Request payload to approve a portfolio review package."""
    model_config = ConfigDict(extra="forbid")

    approval_comments: Optional[str] = None


class ReferPortfolioReviewRequest(BaseModel):
    """Request payload to refer portfolio findings to Phase 72 Management Review."""
    model_config = ConfigDict(extra="forbid")

    management_review_reference: str = Field(..., min_length=3)
    referral_notes: str = Field(..., min_length=5)
