"""Phase 64: Clinical Safety Risk Handoff Outcome Reconciliation Schemas.

Defines reconciliation states and immutable reconciliation records.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class OutcomeReconciliationState(str, Enum):
    """Possible outcome reconciliation states for a handoff."""

    PENDING = "PENDING"
    MATCHED = "MATCHED"
    MATCHED_WITH_LIMITATIONS = "MATCHED_WITH_LIMITATIONS"
    DUPLICATE = "DUPLICATE"
    STALE = "STALE"
    CONFLICTED = "CONFLICTED"
    INVALID_PROVENANCE = "INVALID_PROVENANCE"
    UNKNOWN_DESTINATION = "UNKNOWN_DESTINATION"
    MISSING_REQUIRED_FIELDS = "MISSING_REQUIRED_FIELDS"
    RECONCILIATION_FAILED = "RECONCILIATION_FAILED"
    MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"


class HandoffReconciliationRecord(BaseModel):
    """Immutable record capturing the result of outcome reconciliation."""

    model_config = ConfigDict(extra="ignore")

    reconciliation_id: str = Field(default_factory=lambda: f"rec-{uuid.uuid4().hex[:12]}")
    handoff_id: str
    state: OutcomeReconciliationState
    reconciled_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    reconciled_by: str
    summary: str
    limitations: List[str] = Field(default_factory=list)
    conflict_details: Optional[str] = None
