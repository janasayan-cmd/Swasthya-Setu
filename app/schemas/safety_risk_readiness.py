"""Phase 63: Clinical Safety Risk Decision-Readiness Schemas.

Defines decision-readiness states, evaluation records, and blocking rules.
Non-Negotiable Invariants:
- NOT_READY != SAFE
- BLOCKED != NO_RISK
- CONFLICTED / STALE / UNKNOWN != SAFE
- INSUFFICIENT_EVIDENCE != ACCEPTED
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class DecisionReadinessState(str, Enum):
    """Decision-readiness conceptual states for Phase 63 governed risk reviews."""

    NOT_READY = "NOT_READY"
    READY = "READY"
    READY_WITH_LIMITATIONS = "READY_WITH_LIMITATIONS"
    BLOCKED = "BLOCKED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    REASSESSMENT_REQUIRED = "REASSESSMENT_REQUIRED"
    EVIDENCE_REQUIRED = "EVIDENCE_REQUIRED"
    CONFLICTED = "CONFLICTED"
    STALE = "STALE"


class DecisionReadinessEvaluation(BaseModel):
    """Evaluation record capturing readiness of a review context for governed human decision."""

    model_config = ConfigDict(extra="ignore")

    evaluation_id: str = Field(default_factory=lambda: f"eval-{uuid.uuid4().hex[:12]}")
    state: DecisionReadinessState = DecisionReadinessState.NOT_READY
    is_ready_for_review: bool = False
    reasons: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    blocking_issues: List[str] = Field(default_factory=list)
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)
