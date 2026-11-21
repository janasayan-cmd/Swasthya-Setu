"""Phase 79: Strategic Adaptation Proposal and Follow-Through Schemas.

Defines schemas and models for:
- Formulating evidence-backed strategic adaptation proposals
- Proposal lifecycle management and separation of duties
- Follow-through reconciliation across Phase 72, Phase 78, Phase 73, Phase 75, Phase 74, Phase 76, Phase 77
"""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.governance_strategy_execution_monitoring import (
    CLINICAL_SAFETY_MONITORING_DISCLAIMER,
)


class AdaptationProposalType(str, Enum):
    """Classification of recommended strategic adjustments."""
    REVISE_MILESTONE = "REVISE_MILESTONE"
    REORDER_MILESTONES = "REORDER_MILESTONES"
    REVISIT_CAPABILITY_PRIORITY = "REVISIT_CAPABILITY_PRIORITY"
    REVISE_OBJECTIVE = "REVISE_OBJECTIVE"
    REVIEW_TARGET_STATE = "REVIEW_TARGET_STATE"
    REVISIT_INVESTMENT_ASSUMPTION = "REVISIT_INVESTMENT_ASSUMPTION"
    RESOLVE_CROSS_DEPENDENCY = "RESOLVE_CROSS_DEPENDENCY"
    REVISE_PLANNING_HORIZON = "REVISE_PLANNING_HORIZON"
    PROPOSE_NEW_OBJECTIVE = "PROPOSE_NEW_OBJECTIVE"


class AdaptationProposalStatus(str, Enum):
    """Lifecycle status of a strategic adaptation proposal."""
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    ACCEPTED_FOR_CONSIDERATION = "ACCEPTED_FOR_CONSIDERATION"
    REJECTED = "REJECTED"
    APPROVED_AUTHORITATIVE = "APPROVED_AUTHORITATIVE"
    IMPLEMENTED_AUTHORITATIVE = "IMPLEMENTED_AUTHORITATIVE"
    SUPERSEDED = "SUPERSEDED"
    WITHDRAWN = "WITHDRAWN"


class StrategicAdaptationProposalRecord(BaseModel):
    """Authoritative record for an evidence-backed strategic adaptation proposal."""
    model_config = ConfigDict(extra="forbid")

    proposal_id: str
    tenant_id: str
    source_roadmap_id: str
    proposal_type: AdaptationProposalType
    affected_objective_ids: List[str] = Field(default_factory=list)
    affected_milestone_ids: List[str] = Field(default_factory=list)
    supporting_signal_ids: List[str] = Field(default_factory=list)
    proposed_change_description: str
    rationale: str
    expected_benefits: str
    potential_negative_consequences: str
    resource_implications: str
    uncertainty_limitations: str
    requesting_owner_id: str
    status: AdaptationProposalStatus
    review_notes: Optional[str] = None
    authoritative_decision_reference: Optional[str] = Field(None, description="Phase 72 decision reference")
    authoritative_roadmap_revision_id: Optional[str] = Field(None, description="Phase 78 revision reference")
    disclaimer: str = CLINICAL_SAFETY_MONITORING_DISCLAIMER
    created_at: str
    updated_at: str


class AdaptationFollowThroughRecord(BaseModel):
    """Record tracking downstream execution and realization of an approved strategic adaptation."""
    model_config = ConfigDict(extra="forbid")

    followthrough_id: str
    tenant_id: str
    proposal_id: str
    phase72_decision_reference: Optional[str] = None
    phase78_revision_reference: Optional[str] = None
    phase73_implementation_reference: Optional[str] = None
    phase75_portfolio_reference: Optional[str] = None
    phase74_adoption_reference: Optional[str] = None
    phase76_benefit_reference: Optional[str] = None
    phase77_maturity_reference: Optional[str] = None
    status: str = "IN_PROGRESS"
    verification_notes: Optional[str] = None
    disclaimer: str = CLINICAL_SAFETY_MONITORING_DISCLAIMER
    updated_at: str


class CreateAdaptationProposalRequest(BaseModel):
    """Request to create a new strategic adaptation proposal in DRAFT status."""
    model_config = ConfigDict(extra="forbid")

    source_roadmap_id: str
    proposal_type: AdaptationProposalType
    affected_objective_ids: Optional[List[str]] = None
    affected_milestone_ids: Optional[List[str]] = None
    supporting_signal_ids: Optional[List[str]] = None
    proposed_change_description: str
    rationale: str
    expected_benefits: str
    potential_negative_consequences: str
    resource_implications: str
    uncertainty_limitations: Optional[str] = ""


class SubmitAdaptationProposalRequest(BaseModel):
    """Request to submit an adaptation proposal for strategic review."""
    model_config = ConfigDict(extra="forbid")

    submission_notes: Optional[str] = None


class ReviewAdaptationProposalRequest(BaseModel):
    """Request to record governance review disposition on an adaptation proposal."""
    model_config = ConfigDict(extra="forbid")

    status: AdaptationProposalStatus
    review_notes: str


class LinkAuthoritativeDecisionRequest(BaseModel):
    """Request to link Phase 72 management decision or Phase 78 revision references."""
    model_config = ConfigDict(extra="forbid")

    phase72_decision_reference: Optional[str] = None
    phase78_revision_reference: Optional[str] = None
    phase73_implementation_reference: Optional[str] = None
    status: str = "AUTHORIZED"
