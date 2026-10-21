"""Phase 65: Safety Completion Follow-up Obligation Schemas.

Defines schemas for aggregating and reconciling downstream follow-up obligations.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class FollowUpStatus(str, Enum):
    """Lifecycle status of a follow-up obligation."""

    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    SATISFIED = "SATISFIED"
    WAIVED_BY_AUTHORIZED_POLICY = "WAIVED_BY_AUTHORIZED_POLICY"
    BLOCKED = "BLOCKED"
    CONFLICTED = "CONFLICTED"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"


class FollowUpObligationRecord(BaseModel):
    """Record representing a follow-up obligation attached to completion coordination."""

    model_config = ConfigDict(extra="ignore")

    follow_up_id: str = Field(default_factory=lambda: f"fup-{uuid.uuid4().hex[:12]}")
    completion_id: str
    originating_phase: str
    originating_ref: str
    destination_phase: Optional[str] = None
    description: str
    status: FollowUpStatus = FollowUpStatus.PENDING

    is_mandatory: bool = True
    assigned_role: Optional[str] = None
    due_date: Optional[datetime] = None

    waiver_reason: Optional[str] = None
    waived_by: Optional[str] = None
    waived_at: Optional[datetime] = None
    waiver_policy_reference: Optional[str] = None

    satisfaction_evidence_refs: List[str] = Field(default_factory=list)
    satisfied_at: Optional[datetime] = None
    satisfied_by: Optional[str] = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)
