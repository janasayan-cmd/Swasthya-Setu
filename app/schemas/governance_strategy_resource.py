"""Phase 78: Governance Resource Proposal Schemas.

Defines schemas and models for:
- Recording proposed strategic investment and resource requirements
- Distinguishing PROPOSED, REVIEWED, APPROVED, FUNDED, and COMMITTED
- Strict boundary: NOT a financial accounting system, no autonomous fund allocation
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.governance_strategy_objective import CLINICAL_SAFETY_STRATEGY_DISCLAIMER


class InvestmentReviewStatus(str, Enum):
    """Review and commitment status of a strategic resource proposal."""
    PROPOSED = "PROPOSED"
    REVIEWED = "REVIEWED"
    APPROVED = "APPROVED"
    FUNDED = "FUNDED"
    COMMITTED = "COMMITTED"


class GovernanceResourceProposalRecord(BaseModel):
    """Authoritative record for an estimated strategic resource requirement."""
    model_config = ConfigDict(extra="forbid")

    proposal_id: str
    tenant_id: str
    roadmap_id: str
    related_objective_id: Optional[str] = None
    title: str
    rationale: str
    proposed_financial_investment: float = 0.0
    currency: str = "INR"
    staffing_requirements: str = ""
    technology_requirements: str = ""
    training_requirements: str = ""
    external_service_dependencies: str = ""
    funding_assumptions: str = ""
    expected_strategic_contribution: str = ""
    status: InvestmentReviewStatus
    proposed_by: str
    reviewed_by: Optional[str] = None
    approval_reference: Optional[str] = Field(None, description="External authorized financial or management governance reference")
    disclaimer: str = CLINICAL_SAFETY_STRATEGY_DISCLAIMER
    created_at: str
    updated_at: str


class CreateResourceProposalRequest(BaseModel):
    """Request to create a new strategic resource proposal."""
    model_config = ConfigDict(extra="forbid")

    roadmap_id: str
    related_objective_id: Optional[str] = None
    title: str
    rationale: str
    proposed_financial_investment: float = 0.0
    currency: str = "INR"
    staffing_requirements: Optional[str] = ""
    technology_requirements: Optional[str] = ""
    training_requirements: Optional[str] = ""
    external_service_dependencies: Optional[str] = ""
    funding_assumptions: Optional[str] = ""
    expected_strategic_contribution: Optional[str] = ""


class ReviewResourceProposalRequest(BaseModel):
    """Request to record governance review of a resource proposal."""
    model_config = ConfigDict(extra="forbid")

    status: InvestmentReviewStatus
    review_notes: Optional[str] = None


class RecordApprovalReferenceRequest(BaseModel):
    """Request to associate an authorized external financial/management governance approval reference."""
    model_config = ConfigDict(extra="forbid")

    approval_reference: str = Field(..., description="External organizational financial/executive decision ID")
    status: InvestmentReviewStatus = InvestmentReviewStatus.APPROVED
