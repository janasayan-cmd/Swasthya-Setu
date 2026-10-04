"""Pydantic schemas for Workflow Provenance and Execution History (Phase 37).

Enforces reproducible audit trails for every workflow state transition.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field


class WorkflowHistoryAction(str, Enum):
    """Lifecycle actions recorded in workflow audit history."""

    CREATED = "CREATED"
    STARTED = "STARTED"
    STEP_STARTED = "STEP_STARTED"
    STEP_COMPLETED = "STEP_COMPLETED"
    STEP_FAILED = "STEP_FAILED"
    STEP_RETRIED = "STEP_RETRIED"
    APPROVAL_REQUESTED = "APPROVAL_REQUESTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    PAUSED = "PAUSED"
    RESUMED = "RESUMED"
    BLOCKED = "BLOCKED"
    UNBLOCKED = "UNBLOCKED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class WorkflowHistoryEntry(BaseModel):
    """Immutable audit record entry for workflow execution."""

    model_config = ConfigDict(extra="ignore")

    history_id: str = Field(description="Unique history event identifier")
    workflow_id: str = Field(description="Workflow instance identifier")
    step_id: Optional[str] = Field(default=None, description="Step identifier if step-related")
    action: WorkflowHistoryAction = Field(description="Lifecycle action performed")
    from_status: Optional[str] = Field(default=None, description="Previous status")
    to_status: str = Field(description="Resulting status")
    actor_id: Optional[str] = Field(default=None, description="Actor or system initiating transition")
    actor_role: Optional[str] = Field(default=None, description="Role of the actor")
    reason: Optional[str] = Field(default=None, description="Reason or explanation for action")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Structured contextual metadata (sanitized, no PHI)")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Event recorded timestamp",
    )
