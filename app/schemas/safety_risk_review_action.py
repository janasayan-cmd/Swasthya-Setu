"""Phase 63: Clinical Safety Review Action Schemas.

Defines governed human reviewer actions and outcome records.
Non-Negotiable Invariants:
- AI RECOMMENDATION != GOVERNED DECISION
- Governed risk review requires authorized human action.
- AI agents cannot autonomously authorize reviews or declare safety.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class ReviewerActionType(str, Enum):
    """Supported human reviewer actions for governed risk review."""

    ACKNOWLEDGE = "ACKNOWLEDGE"
    REQUEST_MORE_EVIDENCE = "REQUEST_MORE_EVIDENCE"
    REQUEST_REASSESSMENT = "REQUEST_REASSESSMENT"
    CONTINUE_MONITORING = "CONTINUE_MONITORING"
    ESCALATE = "ESCALATE"
    ROUTE_TO_INCIDENT = "ROUTE_TO_INCIDENT"
    ROUTE_TO_ASSURANCE = "ROUTE_TO_ASSURANCE"
    ROUTE_TO_EFFECTIVENESS = "ROUTE_TO_EFFECTIVENESS"
    ROUTE_TO_GOVERNANCE = "ROUTE_TO_GOVERNANCE"
    ROUTE_TO_CONTROLLED_ACTION = "ROUTE_TO_CONTROLLED_ACTION"
    ROUTE_TO_LEARNING = "ROUTE_TO_LEARNING"
    ROUTE_TO_IMPROVEMENT = "ROUTE_TO_IMPROVEMENT"
    REJECT_RISK_CHARACTERIZATION = "REJECT_RISK_CHARACTERIZATION"
    CLOSE_REVIEW = "CLOSE_REVIEW"


class ReviewActionRecord(BaseModel):
    """Immutable audit record of a performed review action."""

    model_config = ConfigDict(extra="ignore")

    action_id: str = Field(default_factory=lambda: f"act-{uuid.uuid4().hex[:12]}")
    review_id: str
    action_type: ReviewerActionType
    reviewer_id: str
    reviewer_role: str
    rationale: str
    is_ai_assisted: bool = False
    ai_metadata: Optional[Dict[str, Any]] = None
    performed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PerformReviewActionRequest(BaseModel):
    """Request payload to record an authorized human reviewer action."""

    model_config = ConfigDict(extra="ignore")

    action_type: ReviewerActionType
    rationale: str
    is_ai: bool = False
    ai_metadata: Optional[Dict[str, Any]] = None
    idempotency_key: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
