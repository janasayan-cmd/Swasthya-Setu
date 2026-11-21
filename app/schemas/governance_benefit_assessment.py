"""Phase 76: Benefit Realization & Portfolio Benefit Assessment Schemas.

Defines schemas and models for:
- Benefit realization evaluation comparing baseline, target, and validated observations
- Explicit distinction between operational benefit realization and clinical effectiveness
- Portfolio-level cumulative benefit aggregation without double-counting
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class RealizationDisposition(str, Enum):
    """Disposition of an assessed benefit."""
    NOT_YET_DUE = "NOT_YET_DUE"
    ON_TRACK = "ON_TRACK"
    PARTIALLY_REALIZED = "PARTIALLY_REALIZED"
    REALIZED = "REALIZED"
    EXCEEDED_TARGET = "EXCEEDED_TARGET"
    DELAYED = "DELAYED"
    NOT_REALIZED = "NOT_REALIZED"
    DETERIORATING = "DETERIORATING"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    UNABLE_TO_DETERMINE = "UNABLE_TO_DETERMINE"
    REQUIRES_MANAGEMENT_REVIEW = "REQUIRES_MANAGEMENT_REVIEW"


class BenefitRealizationAssessmentRecord(BaseModel):
    """Authoritative evaluation of a benefit against baseline and target."""
    model_config = ConfigDict(extra="forbid")

    assessment_id: str
    benefit_id: str
    tenant_id: str
    measurement_period: str
    baseline_version: int
    target_version: int
    disposition: RealizationDisposition
    indicator_results: List[Dict[str, Any]] = Field(default_factory=list)
    evidence_references: List[str] = Field(default_factory=list)
    assessment_methodology_version: str = "v1.0"
    calculation_details: Dict[str, Any] = Field(default_factory=dict)
    limitations: List[str] = Field(default_factory=list)
    clinical_safety_notice: str = (
        "Operational benefit realization only. Does not establish or verify clinical effectiveness without Phase 55 authorization. Does not claim patient safety improvement or treatment outcome guarantee."
    )
    status: str = "DRAFT"  # DRAFT, SUBMITTED, APPROVED
    assessor_id: str
    approved_by: Optional[str] = None
    approval_timestamp: Optional[str] = None
    created_at: str
    updated_at: str


class CreateRealizationAssessmentRequest(BaseModel):
    """Request payload to perform a benefit realization assessment."""
    model_config = ConfigDict(extra="forbid")

    measurement_period: str = Field(..., min_length=2)
    evidence_references: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    calculation_notes: Optional[str] = None


class SubmitRealizationAssessmentRequest(BaseModel):
    """Request payload to submit a realization assessment for sign-off."""
    model_config = ConfigDict(extra="forbid")

    submission_notes: Optional[str] = None


class ApproveRealizationAssessmentRequest(BaseModel):
    """Request payload to approve a realization assessment."""
    model_config = ConfigDict(extra="forbid")

    approval_notes: str = Field(..., min_length=3)


# -----------------------------------------------------------------------------
# Portfolio-level Benefit Schemas
# -----------------------------------------------------------------------------


class PortfolioBenefitSummaryResponse(BaseModel):
    """Consolidated benefit realization overview for a Phase 75 portfolio."""
    model_config = ConfigDict(extra="forbid")

    portfolio_id: str
    tenant_id: str
    total_benefits: int = 0
    realized_benefits: int = 0
    partially_realized_benefits: int = 0
    delayed_benefits: int = 0
    unrealized_benefits: int = 0
    insufficient_evidence_benefits: int = 0
    shared_indicator_count: int = 0
    cross_initiative_conflicts_count: int = 0
    benefit_breakdown: List[Dict[str, Any]] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    methodology_disclosure: str = (
        "Aggregates operational benefit realization only. Unrelated metrics are not combined into a single score. Does not evaluate clinical efficacy."
    )


class PortfolioBenefitAssessmentRecord(BaseModel):
    """Formal portfolio-level cumulative benefit assessment."""
    model_config = ConfigDict(extra="forbid")

    assessment_id: str
    portfolio_id: str
    tenant_id: str
    assessment_period: str
    portfolio_disposition: str
    metrics_summary: Dict[str, Any] = Field(default_factory=dict)
    double_counting_checks_passed: bool = True
    shared_sources_disclosed: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    clinical_safety_notice: str = (
        "Operational benefit realization only. Does not replace Phase 55 clinical effectiveness."
    )
    assessor_id: str
    created_at: str


class CreatePortfolioBenefitAssessmentRequest(BaseModel):
    """Request payload to evaluate portfolio-level cumulative benefit realization."""
    model_config = ConfigDict(extra="forbid")

    assessment_period: str = Field(..., min_length=2)
    limitations: List[str] = Field(default_factory=list)
