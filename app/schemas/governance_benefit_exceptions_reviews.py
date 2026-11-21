"""Phase 76: Benefit Exceptions & Management Review Packages Schemas.

Defines schemas and models for:
- Benefit measurement exception handling with explicit authorization
- Packaging benefit realization findings into management review packages for Phase 72 referral
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class BenefitExceptionStatus(str, Enum):
    """Lifecycle status of a benefit realization exception."""
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    RESOLVED = "RESOLVED"
    ESCALATED = "ESCALATED"


class BenefitExceptionRecord(BaseModel):
    """Authoritative record for an exception affecting benefit measurement or realization."""
    model_config = ConfigDict(extra="forbid")

    exception_id: str
    benefit_id: str
    portfolio_id: Optional[str] = None
    tenant_id: str
    exception_category: str
    description: str
    supporting_evidence: List[str] = Field(default_factory=list)
    impact_on_measurement: str
    requested_duration_days: int
    responsible_owner_id: str
    review_date: str
    authorization_reference: Optional[str] = None
    status: BenefitExceptionStatus = BenefitExceptionStatus.DRAFT
    review_notes: Optional[str] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[str] = None
    escalated_to: Optional[str] = None
    escalation_reason: Optional[str] = None
    created_by: str
    created_at: str
    updated_at: str


class CreateBenefitExceptionRequest(BaseModel):
    """Request payload to request a benefit measurement exception."""
    model_config = ConfigDict(extra="forbid")

    exception_category: str = Field(..., min_length=3)
    description: str = Field(..., min_length=5)
    supporting_evidence: List[str] = Field(default_factory=list)
    impact_on_measurement: str = Field(..., min_length=5)
    requested_duration_days: int = Field(default=30, ge=1, le=365)
    review_date: str


class SubmitBenefitExceptionRequest(BaseModel):
    """Request payload to submit an exception for review."""
    model_config = ConfigDict(extra="forbid")

    submission_notes: Optional[str] = None


class ReviewBenefitExceptionRequest(BaseModel):
    """Request payload to record formal review of an exception."""
    model_config = ConfigDict(extra="forbid")

    approved: bool
    authorization_reference: Optional[str] = None
    review_notes: str = Field(..., min_length=5)


class EscalateBenefitExceptionRequest(BaseModel):
    """Request payload to escalate an exception to Phase 67 governance escalation."""
    model_config = ConfigDict(extra="forbid")

    escalation_reason: str = Field(..., min_length=5)
    target_authority: str = Field(default="GOVERNANCE_BOARD")


# -----------------------------------------------------------------------------
# Management Review Packages
# -----------------------------------------------------------------------------


class BenefitReviewPackageRecord(BaseModel):
    """Structured benefit realization package prepared for Phase 72 Management Review."""
    model_config = ConfigDict(extra="forbid")

    review_id: str
    portfolio_id: str
    tenant_id: str
    review_period: str
    title: str
    participants: List[str] = Field(default_factory=list)
    benefits_snapshot: List[Dict[str, Any]] = Field(default_factory=list)
    delayed_benefits: List[str] = Field(default_factory=list)
    unrealized_benefits: List[str] = Field(default_factory=list)
    trade_offs_identified: List[str] = Field(default_factory=list)
    independent_verification_summaries: List[Dict[str, Any]] = Field(default_factory=list)
    recommendations: List[str] = Field(
        default_factory=list,
        description="Advisory recommendations only. Does not independently modify source governance decisions."
    )
    management_review_reference: Optional[str] = None
    referral_notes: Optional[str] = None
    status: str = "DRAFT"  # DRAFT, SUBMITTED, REFERRED_TO_MANAGEMENT
    created_by: str
    created_at: str
    updated_at: str


class CreateBenefitReviewRequest(BaseModel):
    """Request payload to initiate a benefit review package."""
    model_config = ConfigDict(extra="forbid")

    review_period: str = Field(..., min_length=2)
    title: str = Field(..., min_length=3, max_length=255)
    participants: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)


class SubmitBenefitReviewRequest(BaseModel):
    """Request payload to submit a review package."""
    model_config = ConfigDict(extra="forbid")

    submission_notes: Optional[str] = None


class ReferBenefitReviewRequest(BaseModel):
    """Request payload to formally refer findings to Phase 72 Management Review."""
    model_config = ConfigDict(extra="forbid")

    management_review_reference: str = Field(..., min_length=3)
    referral_notes: str = Field(..., min_length=5)
