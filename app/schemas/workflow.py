"""Multi-step workflow schemas and state tracking (Phase 22).

Workflows orchestrate multiple asynchronous jobs in sequence while preserving
intermediate results on partial failure.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
import uuid


class WorkflowStatus(str, Enum):
    """Lifecycle state of an orchestrated multi-step workflow."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    PARTIALLY_FAILED = "PARTIALLY_FAILED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class StepStatus(str, Enum):
    """Lifecycle state of an individual workflow stage."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class WorkflowStep(BaseModel):
    """Definition and execution state of a single stage in a workflow."""

    step_name: str
    order: int
    status: StepStatus = Field(default=StepStatus.PENDING)
    job_id: Optional[str] = None
    required: bool = True
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    result: Optional[Dict[str, Any]] = None


class WorkflowRecord(BaseModel):
    """Database representation of an orchestrated multi-step workflow."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    workflow_type: str
    patient_id: Optional[str] = None
    initiating_user_id: Optional[str] = None
    status: WorkflowStatus = Field(default=WorkflowStatus.PENDING)
    current_step_index: int = 0
    steps: List[WorkflowStep] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class WorkflowResponse(BaseModel):
    """API response model for workflow status tracking."""

    id: str
    workflow_type: str
    patient_id: Optional[str] = None
    status: WorkflowStatus
    current_step_index: int
    steps: List[WorkflowStep]
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
