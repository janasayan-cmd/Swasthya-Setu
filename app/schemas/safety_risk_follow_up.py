"""Phase 63: Clinical Safety Follow-Up Schemas.

Defines schemas for governed follow-up tasks arising from risk review and disposition.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class FollowUpStatus(str, Enum):
    """Lifecycle status of a governed risk follow-up action."""

    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    OVERDUE = "OVERDUE"


class RiskFollowUpRecord(BaseModel):
    """Record of a required governed follow-up condition or monitoring task."""

    model_config = ConfigDict(extra="ignore")

    follow_up_id: str = Field(default_factory=lambda: f"fup-{uuid.uuid4().hex[:12]}")
    originating_review_id: str
    destination: str
    reason: str
    required_by: datetime
    owner_reference: Optional[str] = None
    status: FollowUpStatus = FollowUpStatus.PENDING
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    provenance: str = "PHASE_63_DISPOSITION"
    version_context: str = "v1.0.0"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CreateFollowUpRequest(BaseModel):
    """Request payload to create a new follow-up requirement."""

    model_config = ConfigDict(extra="ignore")

    destination: str
    reason: str
    required_by: datetime
    owner_reference: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
