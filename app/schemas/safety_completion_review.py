"""Phase 65: Safety Completion Review Schemas.

Defines schemas for authorized completion review and separation-of-duties enforcement.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class CompletionReviewDecision(str, Enum):
    """Decision outcomes for an authorized completion review."""

    APPROVED = "APPROVED"
    APPROVED_WITH_LIMITATIONS = "APPROVED_WITH_LIMITATIONS"
    REJECTED = "REJECTED"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"
    REASSESSMENT_REQUIRED = "REASSESSMENT_REQUIRED"


class SeparationOfDutiesRole(str, Enum):
    """Roles governed under separation-of-duties policy."""

    COMPLETION_PREPARER = "COMPLETION_PREPARER"
    COMPLETION_REVIEWER = "COMPLETION_REVIEWER"
    COMPLETION_AUTHORIZER = "COMPLETION_AUTHORIZER"
    GOVERNANCE_APPROVER = "GOVERNANCE_APPROVER"
    SAFETY_ACTION_AUTHORIZER = "SAFETY_ACTION_AUTHORIZER"


class SubmitCompletionReviewRequest(BaseModel):
    """Request payload to submit an authorized completion review outcome."""

    model_config = ConfigDict(extra="ignore")

    decision: CompletionReviewDecision
    reasoning: str
    limitations: Optional[List[str]] = Field(default_factory=list)
    action_items: Optional[List[str]] = Field(default_factory=list)
    acknowledged_prohibited_claims: bool = True
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class CompletionReviewRecord(BaseModel):
    """Record of an authorized completion review."""

    model_config = ConfigDict(extra="ignore")

    review_id: str = Field(default_factory=lambda: f"rev-{uuid.uuid4().hex[:12]}")
    completion_id: str
    reviewer_id: str
    reviewer_role: str
    decision: CompletionReviewDecision
    reasoning: str
    limitations: List[str] = Field(default_factory=list)
    action_items: List[str] = Field(default_factory=list)
    package_revision: str = "v1.0.0"
    reviewed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)
