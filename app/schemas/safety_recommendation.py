"""Phase 50: Safety Learning Recommendation & Governance Schemas.

Defines candidate preventive improvements, human-review lifecycles,
and structured rationales without exposing raw chain-of-thought.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


class RecommendationType(str, Enum):
    """Controlled taxonomy of preventive risk improvements."""

    STRENGTHEN_SAFETY_GATE = "STRENGTHEN_SAFETY_GATE"
    ADD_VALIDATION_RULE = "ADD_VALIDATION_RULE"
    REQUIRE_HUMAN_REVIEW = "REQUIRE_HUMAN_REVIEW"
    IMPROVE_PROVIDER_FALLBACK = "IMPROVE_PROVIDER_FALLBACK"
    ADD_OPERATIONAL_MONITORING = "ADD_OPERATIONAL_MONITORING"
    IMPROVE_TIMEOUT_HANDLING = "IMPROVE_TIMEOUT_HANDLING"
    ADD_RECONCILIATION_STEP = "ADD_RECONCILIATION_STEP"
    CONSTRAIN_CONFIGURATION = "CONSTRAIN_CONFIGURATION"
    UPDATE_SAFETY_POLICY = "UPDATE_SAFETY_POLICY"
    UPDATE_DOCUMENTATION = "UPDATE_DOCUMENTATION"
    CREATE_ENGINEERING_TASK = "CREATE_ENGINEERING_TASK"


class RecommendationStatus(str, Enum):
    """Lifecycle progression of a candidate preventive recommendation."""

    GENERATED = "GENERATED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    UNDER_REVIEW = "UNDER_REVIEW"
    ACCEPTED = "ACCEPTED"
    IMPLEMENTATION_REQUIRED = "IMPLEMENTATION_REQUIRED"
    IMPLEMENTATION_IN_PROGRESS = "IMPLEMENTATION_IN_PROGRESS"
    VALIDATION_REQUIRED = "VALIDATION_REQUIRED"
    VALIDATED = "VALIDATED"
    CLOSED = "CLOSED"
    REJECTED = "REJECTED"
    DEFERRED = "DEFERRED"
    CANCELLED = "CANCELLED"
    SUPERSEDED = "SUPERSEDED"
    STALE = "STALE"


class SafetyRecommendation(BaseModel):
    """Authoritative candidate preventive improvement awaiting human review."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: f"rec-{uuid.uuid4().hex[:12]}")
    analysis_id: Optional[str] = None
    pattern_id: Optional[str] = None
    recommendation_type: RecommendationType
    title: str
    description: str
    rationale_summary: str = Field(description="Structured evidence rationale. Chain-of-thought is excluded.")
    affected_subsystem: str
    status: RecommendationStatus = Field(default=RecommendationStatus.REVIEW_REQUIRED)
    evidence_references: List[Dict[str, Any]] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    reviewed_by_id: Optional[str] = None
    reviewed_by_role: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    review_notes: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    version: str = Field(default="1.0")


class RecommendationReviewRequest(BaseModel):
    """Payload for human safety officer to review, accept, or reject recommendation."""

    model_config = ConfigDict(extra="forbid")

    decision: str = Field(description="'ACCEPT', 'REJECT', 'DEFER'")
    notes: str
    evidence_reviewed: List[str] = Field(default_factory=list)
