"""Phase 76: Benefit Attribution & Unintended Consequences Schemas.

Defines schemas and models for:
- Transparent benefit attribution distinguishing correlation from direct causation
- Capturing unintended operational consequences and benefit trade-offs
- Routing safety, risk, CAPA, and adoption concerns to authoritative modules
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class AttributionType(str, Enum):
    """Classification of attribution confidence and relationship."""
    DIRECTLY_ATTRIBUTABLE = "DIRECTLY_ATTRIBUTABLE"
    SHARED_CONTRIBUTION = "SHARED_CONTRIBUTION"
    ASSOCIATED_IMPROVEMENT = "ASSOCIATED_IMPROVEMENT"
    CORRELATED_CHANGE = "CORRELATED_CHANGE"
    ATTRIBUTION_UNCERTAIN = "ATTRIBUTION_UNCERTAIN"
    ATTRIBUTION_NOT_ESTABLISHED = "ATTRIBUTION_NOT_ESTABLISHED"


class BenefitAttributionRecord(BaseModel):
    """Authoritative record analyzing attribution of observed improvements."""
    model_config = ConfigDict(extra="forbid")

    attribution_id: str
    benefit_id: str
    tenant_id: str
    attribution_type: AttributionType
    related_initiative_ids: List[str] = Field(default_factory=list)
    relevant_implementation_periods: List[str] = Field(default_factory=list)
    external_influencing_factors: List[str] = Field(default_factory=list)
    measurement_limitations: List[str] = Field(default_factory=list)
    attribution_methodology: str
    supporting_evidence: List[str] = Field(default_factory=list)
    reviewer_id: str
    clinical_safety_notice: str = (
        "Attribution analysis evaluates operational associations only. Correlation does not imply causation."
    )
    created_at: str


class CreateAttributionAssessmentRequest(BaseModel):
    """Request payload to record an attribution analysis."""
    model_config = ConfigDict(extra="forbid")

    attribution_type: AttributionType
    related_initiative_ids: List[str] = Field(default_factory=list)
    relevant_implementation_periods: List[str] = Field(default_factory=list)
    external_influencing_factors: List[str] = Field(default_factory=list)
    measurement_limitations: List[str] = Field(default_factory=list)
    attribution_methodology: str = Field(..., min_length=5)
    supporting_evidence: List[str] = Field(default_factory=list)


# -----------------------------------------------------------------------------
# Unintended Consequences & Trade-offs
# -----------------------------------------------------------------------------


class ConsequenceClassification(str, Enum):
    """Lifecycle status of an identified unintended consequence or trade-off."""
    POTENTIAL_CONSEQUENCE = "POTENTIAL_CONSEQUENCE"
    CONFIRMED_OPERATIONAL_CONSEQUENCE = "CONFIRMED_OPERATIONAL_CONSEQUENCE"
    ACCEPTED_TRADE_OFF = "ACCEPTED_TRADE_OFF"
    UNRESOLVED_CONCERN = "UNRESOLVED_CONCERN"
    RESOLVED_CONSEQUENCE = "RESOLVED_CONSEQUENCE"
    UNABLE_TO_DETERMINE = "UNABLE_TO_DETERMINE"


class UnintendedConsequenceRecord(BaseModel):
    """Authoritative record for an unintended consequence or operational trade-off."""
    model_config = ConfigDict(extra="forbid")

    consequence_id: str
    benefit_id: str
    tenant_id: str
    related_initiative_ids: List[str] = Field(default_factory=list)
    description: str
    affected_organizational_scope: Dict[str, Any] = Field(default_factory=dict)
    evidence_references: List[str] = Field(default_factory=list)
    source_measurements: List[str] = Field(default_factory=list)
    detection_date: str
    potential_impact: str
    status: ConsequenceClassification = ConsequenceClassification.POTENTIAL_CONSEQUENCE
    reviewer_id: Optional[str] = None
    review_notes: Optional[str] = None
    routed_destination: Optional[str] = None
    destination_reference: Optional[str] = None
    routing_notes: Optional[str] = None
    created_by: str
    created_at: str
    updated_at: str


class CreateConsequenceRequest(BaseModel):
    """Request payload to record an unintended consequence or trade-off."""
    model_config = ConfigDict(extra="forbid")

    description: str = Field(..., min_length=5)
    related_initiative_ids: List[str] = Field(default_factory=list)
    affected_organizational_scope: Dict[str, Any] = Field(default_factory=dict)
    evidence_references: List[str] = Field(default_factory=list)
    source_measurements: List[str] = Field(default_factory=list)
    potential_impact: str = Field(..., min_length=3)


class ReviewConsequenceRequest(BaseModel):
    """Request payload to record human review of a consequence."""
    model_config = ConfigDict(extra="forbid")

    status: ConsequenceClassification
    review_notes: str = Field(..., min_length=5)


class RouteConsequenceRequest(BaseModel):
    """Request payload to route a consequence to an authoritative workflow."""
    model_config = ConfigDict(extra="forbid")

    routed_destination: str = Field(
        ...,
        description="Target module (e.g. PHASE_49_INCIDENTS, PHASE_54_CAPA, PHASE_63_RISK_REVIEW, PHASE_74_ADOPTION)",
        min_length=3,
    )
    destination_reference: str = Field(..., min_length=2)
    routing_notes: str = Field(..., min_length=5)
