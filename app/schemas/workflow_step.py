"""Pydantic schemas for Clinical Workflow Steps (Phase 37).

CORE SAFETY PRINCIPLES:
- WORKFLOW STEP != CLINICAL ACTION
- WORKFLOW STEP != CLINICAL OUTCOME
- WORKFLOW STEP AUTOMATION != CLINICAL AUTHORITY
- TASK CREATION != WORKFLOW STEP COMPLETION
- AI SUGGESTION != STEP AUTHORIZATION
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class WorkflowStepStatus(str, Enum):
    """Lifecycle status for an individual workflow step instance."""

    PENDING = "PENDING"
    READY = "READY"
    RUNNING = "RUNNING"
    WAITING = "WAITING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    CANCELLED = "CANCELLED"
    BLOCKED = "BLOCKED"


class WorkflowStepActionType(str, Enum):
    """Type of deterministic orchestration action executed by the step."""

    CREATE_TASK = "CREATE_TASK"
    SEND_NOTIFICATION = "SEND_NOTIFICATION"
    CREATE_ALERT = "CREATE_ALERT"
    REQUEST_DOCUMENT_PROCESSING = "REQUEST_DOCUMENT_PROCESSING"
    REQUEST_NORMALIZATION = "REQUEST_NORMALIZATION"
    WAIT_FOR_EVENT = "WAIT_FOR_EVENT"
    HUMAN_APPROVAL = "HUMAN_APPROVAL"
    DOMAIN_ACTION = "DOMAIN_ACTION"


class WorkflowStepDependency(BaseModel):
    """Prerequisite step dependency configuration."""

    model_config = ConfigDict(extra="ignore")

    depends_on_step_id: str = Field(description="Step ID that must complete first")
    required_status: WorkflowStepStatus = Field(
        default=WorkflowStepStatus.COMPLETED,
        description="Required status of prerequisite step",
    )


class WorkflowStepDefinition(BaseModel):
    """Configured definition for a step within a workflow template."""

    model_config = ConfigDict(extra="ignore")

    step_id: str = Field(description="Unique identifier for step within workflow definition")
    name: str = Field(description="Human readable name of the step")
    description: Optional[str] = Field(default=None, description="Detailed description of step action")
    order: int = Field(default=1, description="Execution order sequence index")
    action_type: WorkflowStepActionType = Field(description="Action executed by this step")
    action_config: Dict[str, Any] = Field(default_factory=dict, description="Deterministic configuration for step action")
    dependencies: List[WorkflowStepDependency] = Field(default_factory=list, description="Step dependencies")
    approval_required: bool = Field(default=False, description="Whether this step requires human approval gate")
    required_approval_role: Optional[str] = Field(default=None, description="Role required to approve this step")
    timeout_minutes: Optional[int] = Field(default=None, description="Maximum execution/wait time for step")
    max_retries: int = Field(default=3, description="Maximum retries for transient failure")
    optional: bool = Field(default=False, description="Whether step is optional for workflow completion")


class WorkflowStepRecord(BaseModel):
    """Authoritative state record of a workflow step instance."""

    model_config = ConfigDict(extra="ignore")

    step_instance_id: str = Field(description="Unique runtime instance ID for step")
    workflow_id: str = Field(description="Parent workflow instance identifier")
    step_id: str = Field(description="Definition step ID")
    name: str = Field(description="Step name")
    order: int = Field(default=1, description="Step order index")
    action_type: WorkflowStepActionType = Field(description="Action type")
    action_config: Dict[str, Any] = Field(default_factory=dict, description="Action parameters")
    status: WorkflowStepStatus = Field(default=WorkflowStepStatus.PENDING, description="Current step status")
    dependencies: List[WorkflowStepDependency] = Field(default_factory=list, description="Step dependencies")
    approval_required: bool = Field(default=False, description="Approval gate required")
    required_approval_role: Optional[str] = Field(default=None, description="Required role for approval")
    related_task_id: Optional[str] = Field(default=None, description="Created Task ID if step creates a task")
    related_alert_id: Optional[str] = Field(default=None, description="Created Alert ID if step creates an alert")
    waiting_for_event: Optional[str] = Field(default=None, description="Event name if step is WAITING")
    retry_count: int = Field(default=0, description="Number of retry attempts executed")
    max_retries: int = Field(default=3, description="Maximum retries allowed")
    error_message: Optional[str] = Field(default=None, description="Sanitized failure description")
    error_code: Optional[str] = Field(default=None, description="Error code on failure")
    started_at: Optional[datetime] = Field(default=None, description="Step execution start timestamp")
    completed_at: Optional[datetime] = Field(default=None, description="Step execution completion timestamp")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Step instance creation timestamp",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Step instance update timestamp",
    )
