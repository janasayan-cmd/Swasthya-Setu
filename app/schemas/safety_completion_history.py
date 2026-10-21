"""Phase 65: Safety Completion History and Status Schemas.

Defines schemas for audit trails, history entries, and lifecycle status responses.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.safety_workflow_completion import CompletionLifecycleState


class CompletionHistoryEntry(BaseModel):
    """Immutable audit trail entry of state transitions."""

    model_config = ConfigDict(extra="ignore")

    entry_id: str = Field(default_factory=lambda: f"hist-{uuid.uuid4().hex[:12]}")
    completion_id: str
    from_state: str
    to_state: str
    actor_id: str
    actor_role: str
    action: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    details: Dict[str, Any] = Field(default_factory=dict)


class CompletionStatusResponse(BaseModel):
    """Enriched lifecycle and readiness status response."""

    model_config = ConfigDict(extra="ignore")

    completion_id: str
    coordination_id: str
    state: CompletionLifecycleState
    readiness_state: str
    is_ready_for_review: bool
    is_ready_for_closure: bool
    total_requirements: int
    satisfied_requirements: int
    pending_requirements: int
    blocked_requirements: int
    total_handoffs: int
    completed_handoffs: int
    total_follow_ups: int
    satisfied_follow_ups: int
    blockers: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    updated_at: datetime
