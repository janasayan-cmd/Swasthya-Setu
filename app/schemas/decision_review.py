"""Decision Review & Human Oversight Schemas (Phase 47).

Defines:
- Review actions (APPROVED, REJECTED, MODIFIED, etc.)
- Review records capturing reviewer identity, role, justifications, and state transitions
- Invariants:
  - SYSTEM GENERATED != HUMAN REVIEWED != HUMAN APPROVED
  - AI confidence or rule matches NEVER automatically approve clinical outputs
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.decisions import DecisionStatus


class ReviewAction(str, Enum):
    """Explicit human oversight determinations."""

    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    MODIFIED = "MODIFIED"
    RETURNED_FOR_REVIEW = "RETURNED_FOR_REVIEW"
    NEEDS_MORE_INFORMATION = "NEEDS_MORE_INFORMATION"


class DecisionReviewRecord(BaseModel):
    """Immutable audit record of a clinician's human oversight decision."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: f"rev-{uuid.uuid4().hex[:12]}", description="Unique review record ID")
    decision_id: str = Field(description="Associated decision ID")
    reviewer_id: str = Field(description="Authorized clinician user ID")
    reviewer_role: str = Field(description="Role of clinician reviewer e.g. DOCTOR")
    action: ReviewAction = Field(description="Oversight determination")
    review_reason: str = Field(description="Clinical rationale for approval, rejection, or modification")
    previous_status: DecisionStatus = Field(description="Decision status prior to review")
    resulting_status: DecisionStatus = Field(description="Decision status after review")
    modifications: Optional[Dict[str, Any]] = Field(default=None, description="Modifications made if action=MODIFIED")
    reviewed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DecisionReviewRequest(BaseModel):
    """Request contract for clinician review submission."""

    model_config = ConfigDict(extra="forbid")

    action: ReviewAction = Field(description="Review action (APPROVED, REJECTED, MODIFIED)")
    reason: str = Field(min_length=3, max_length=500, description="Mandatory clinical justification for review decision")
    modifications: Optional[Dict[str, Any]] = Field(default=None, description="Updated parameters if MODIFIED")
    idempotency_key: Optional[str] = Field(default=None, max_length=128)
