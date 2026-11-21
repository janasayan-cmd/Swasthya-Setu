"""Phase 79: Strategic Alignment Analysis Schemas.

Defines schemas and models for:
- Explainable strategic alignment evaluation
- Detecting orphan objectives, disconnected portfolios, and contradictory timelines
- Maintaining human review records (no autonomous modification of strategic commitments)
"""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.governance_strategy_execution_monitoring import (
    CLINICAL_SAFETY_MONITORING_DISCLAIMER,
)


class AlignmentFindingCategory(str, Enum):
    """Classification of strategic alignment deficits or disconnects."""
    ORPHAN_OBJECTIVE = "ORPHAN_OBJECTIVE"
    ORPHAN_MILESTONE = "ORPHAN_MILESTONE"
    DISCONNECTED_PORTFOLIO = "DISCONNECTED_PORTFOLIO"
    DUPLICATE_INITIATIVE = "DUPLICATE_INITIATIVE"
    CONFLICTING_TARGET_STATE = "CONFLICTING_TARGET_STATE"
    COMPETING_RESOURCES = "COMPETING_RESOURCES"
    CONTRADICTORY_TIMELINE = "CONTRADICTORY_TIMELINE"
    UNOWNED_COMMITMENT = "UNOWNED_COMMITMENT"
    CHANGED_ASSUMPTION = "CHANGED_ASSUMPTION"


class AlignmentFindingStatus(str, Enum):
    """Review status of an alignment finding."""
    DETECTED = "DETECTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    ACCEPTED_FOR_ADAPTATION = "ACCEPTED_FOR_ADAPTATION"
    DISMISSED = "DISMISSED"


class StrategicAlignmentFindingRecord(BaseModel):
    """Authoritative record for an identified strategic misalignment condition."""
    model_config = ConfigDict(extra="forbid")

    finding_id: str
    tenant_id: str
    category: AlignmentFindingCategory
    affected_roadmap_ids: List[str] = Field(default_factory=list)
    affected_record_references: List[str] = Field(default_factory=list)
    detection_method: str
    rule_version: str
    explanation: str
    confidence_score: float = Field(1.0, ge=0.0, le=1.0)
    evidence_limitations: str = ""
    status: AlignmentFindingStatus
    reviewed_by: Optional[str] = None
    review_notes: Optional[str] = None
    suggested_review_destination: str
    disclaimer: str = CLINICAL_SAFETY_MONITORING_DISCLAIMER
    detected_at: str


class CreateAlignmentFindingRequest(BaseModel):
    """Request to record a strategic alignment finding."""
    model_config = ConfigDict(extra="forbid")

    category: AlignmentFindingCategory
    affected_roadmap_ids: List[str]
    affected_record_references: Optional[List[str]] = None
    detection_method: str
    rule_version: str = "1.0"
    explanation: str
    confidence_score: float = 1.0
    evidence_limitations: Optional[str] = ""
    suggested_review_destination: str = "PHASE_72_MANAGEMENT_REVIEW"


class ReviewAlignmentFindingRequest(BaseModel):
    """Request to review and disposition an alignment finding."""
    model_config = ConfigDict(extra="forbid")

    status: AlignmentFindingStatus
    review_notes: str
