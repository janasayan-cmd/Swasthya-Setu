"""Pydantic schemas for Clinical Task History & Audit Ledger (Phase 36).

Maintains an immutable record of all lifecycle state transitions, assignments,
and workflow actions on a task.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field


class TaskHistoryAction(str, Enum):
    """Lifecycle actions recorded in task audit history."""

    TASK_CREATED = "TASK_CREATED"
    TASK_ASSIGNED = "TASK_ASSIGNED"
    TASK_REASSIGNED = "TASK_REASSIGNED"
    TASK_ACCEPTED = "TASK_ACCEPTED"
    TASK_STARTED = "TASK_STARTED"
    TASK_BLOCKED = "TASK_BLOCKED"
    TASK_UNBLOCKED = "TASK_UNBLOCKED"
    TASK_COMPLETED = "TASK_COMPLETED"
    TASK_VERIFICATION_REQUESTED = "TASK_VERIFICATION_REQUESTED"
    TASK_VERIFIED = "TASK_VERIFIED"
    TASK_REJECTED = "TASK_REJECTED"
    TASK_CANCELLED = "TASK_CANCELLED"
    TASK_EXPIRED = "TASK_EXPIRED"
    TASK_FAILED = "TASK_FAILED"
    TASK_ESCALATED = "TASK_ESCALATED"


class TaskHistoryEntry(BaseModel):
    """Immutable transition entry in task lifecycle audit ledger."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(description="Unique history entry UUID")
    task_id: str = Field(description="Associated task identifier")
    action: TaskHistoryAction = Field(description="Action executed")
    from_status: Optional[str] = Field(default=None, description="Previous status state")
    to_status: str = Field(description="New status state")
    actor_id: str = Field(description="User or system worker executing the action")
    actor_role: str = Field(description="Role of the actor at execution time")
    reason: Optional[str] = Field(default=None, description="Optional or required justification note")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional structured provenance")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Timestamp of event")
