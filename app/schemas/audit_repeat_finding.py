"""Phase 71: Repeat-Finding Detection Schemas.

Defines schemas for:
- Deterministic repeat finding candidate detection
- Matching dimensions and confidence tiers
- Human review and confirmation/rejection workflow
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class RepeatConfidence(str, Enum):
    """Confidence classification of a detected repeat-finding relationship."""

    POSSIBLE_REPEAT = "POSSIBLE_REPEAT"
    LIKELY_REPEAT = "LIKELY_REPEAT"
    CONFIRMED_REPEAT = "CONFIRMED_REPEAT"
    NOT_A_REPEAT = "NOT_A_REPEAT"
    REQUIRES_REVIEW = "REQUIRES_REVIEW"


class MatchingDimension(str, Enum):
    """Evaluation dimensions used for repeat finding correlation."""

    CATEGORY = "CATEGORY"
    CONTROL = "CONTROL"
    REQUIREMENT = "REQUIREMENT"
    PROCESS = "PROCESS"
    ORGANIZATIONAL_UNIT = "ORGANIZATIONAL_UNIT"
    ROOT_CAUSE = "ROOT_CAUSE"
    SEMANTIC_SIMILARITY = "SEMANTIC_SIMILARITY"
    CORRECTIVE_ACTION_REF = "CORRECTIVE_ACTION_REF"


class CandidateReviewStatus(str, Enum):
    """Human review state for a repeat finding candidate."""

    PENDING_REVIEW = "PENDING_REVIEW"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"
    REQUIRES_REVIEW = "REQUIRES_REVIEW"


class RepeatFindingCandidateRecord(BaseModel):
    """Domain model tracking a detected repeat finding candidate."""

    model_config = ConfigDict(extra="ignore")

    candidate_id: str = Field(default_factory=lambda: f"grfc-{uuid.uuid4().hex[:12]}")
    current_finding_id: str
    current_finding_statement: str
    current_audit_id: str
    category: str
    severity: str

    historical_finding_ids: List[str] = Field(default_factory=list)
    matching_dimensions: List[str] = Field(default_factory=list)
    matching_rationale: str

    confidence: RepeatConfidence = RepeatConfidence.POSSIBLE_REPEAT
    confidence_score: float = 0.5
    detection_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    detection_method: str = "DETERMINISTIC_RULES"
    reporting_period: str = "LAST_12_MONTHS"

    review_status: CandidateReviewStatus = CandidateReviewStatus.PENDING_REVIEW
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    review_rationale: Optional[str] = None

    organization_id: str
    facility_id: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ReviewRepeatFindingRequest(BaseModel):
    """Request payload to record a human review decision on a repeat finding candidate."""

    model_config = ConfigDict(extra="ignore")

    review_status: CandidateReviewStatus
    review_rationale: str


class ConfirmRepeatFindingRequest(BaseModel):
    """Request payload to confirm a repeat finding candidate."""

    model_config = ConfigDict(extra="ignore")

    review_rationale: str


class RejectRepeatFindingRequest(BaseModel):
    """Request payload to reject a repeat finding candidate."""

    model_config = ConfigDict(extra="ignore")

    rejection_rationale: str
