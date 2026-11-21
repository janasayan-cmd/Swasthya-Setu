"""Phase 78: Governance Strategic Priority Schemas.

Defines schemas and models for:
- Traceable strategic priority identification from Phase 77, Phase 70, Phase 71, Phase 63, Phase 49, etc.
- Evidence references, confidence, and limitation tracking
- Human review and acceptance outcomes (no automatic conversion)
"""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.governance_strategy_objective import CLINICAL_SAFETY_STRATEGY_DISCLAIMER


class PriorityLevel(str, Enum):
    """Priority level ranking."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class PriorityReviewOutcome(str, Enum):
    """Lifecycle review status of a proposed strategic priority."""
    PROPOSED = "PROPOSED"
    REVIEWED = "REVIEWED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


class SourceEvidenceReference(BaseModel):
    """Traceable reference to upstream authoritative governance evidence."""
    model_config = ConfigDict(extra="forbid")

    source_workflow: str = Field(..., description="e.g. PHASE_77_MATURITY, PHASE_77_SYSTEMIC_GAP, PHASE_70_AUDIT, PHASE_71_AUDIT_INTEL, PHASE_63_RISK, PHASE_72_DECISION")
    source_record_id: str
    ownership: str
    timestamp: str
    confidence_score: float = Field(1.0, ge=0.0, le=1.0)
    limitations: str = ""


class GovernanceStrategyPriorityRecord(BaseModel):
    """Authoritative record for an identified clinical safety governance strategic priority."""
    model_config = ConfigDict(extra="forbid")

    priority_id: str
    tenant_id: str
    title: str
    strategic_rationale: str
    potential_impact: str
    urgency: str
    evidence_references: List[SourceEvidenceReference]
    proposed_priority_level: PriorityLevel
    status: PriorityReviewOutcome
    proposed_by: str
    reviewed_by: Optional[str] = None
    review_outcome: Optional[PriorityReviewOutcome] = None
    review_notes: Optional[str] = None
    linked_objective_id: Optional[str] = None
    disclaimer: str = CLINICAL_SAFETY_STRATEGY_DISCLAIMER
    created_at: str
    updated_at: str


class ProposePriorityRequest(BaseModel):
    """Request to propose a new strategic priority based on verified governance evidence."""
    model_config = ConfigDict(extra="forbid")

    title: str
    strategic_rationale: str
    potential_impact: str
    urgency: str
    evidence_references: List[SourceEvidenceReference]
    proposed_priority_level: PriorityLevel = PriorityLevel.HIGH
    linked_objective_id: Optional[str] = None


class ReviewPriorityRequest(BaseModel):
    """Request to review and accept/reject a proposed strategic priority."""
    model_config = ConfigDict(extra="forbid")

    outcome: PriorityReviewOutcome
    review_notes: str
