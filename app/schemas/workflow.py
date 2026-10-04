"""Pydantic schemas for Clinical Workflow Orchestration & Order Management (Phase 37).

CORE SAFETY PRINCIPLES:
- WORKFLOW != CLINICAL DECISION
- WORKFLOW != DIAGNOSIS
- WORKFLOW != TREATMENT
- WORKFLOW != PRESCRIPTION
- WORKFLOW != MEDICATION CHANGE
- WORKFLOW != TRIAGE
- WORKFLOW != EMERGENCY DISPATCH
- WORKFLOW DEFINITION != WORKFLOW INSTANCE
- WORKFLOW STEP != CLINICAL ACTION
- TASK COMPLETION != CLINICAL OUTCOME
- AUTOMATED TRANSITION != CLINICAL AUTHORITY
- APPROVAL REQUEST != APPROVAL
- APPROVAL != CLINICAL TRUTH
- AI SUGGESTION != WORKFLOW AUTHORIZATION
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.workflow_step import (
    WorkflowStepDefinition,
    WorkflowStepRecord,
    WorkflowStepStatus,
)


class WorkflowCategory(str, Enum):
    """Broad category governing workflow policies and routing."""

    DIAGNOSTIC = "DIAGNOSTIC"
    MEDICATION = "MEDICATION"
    DISCHARGE = "DISCHARGE"
    APPOINTMENT = "APPOINTMENT"
    TRANSFER = "TRANSFER"
    DOCUMENT_PROCESSING = "DOCUMENT_PROCESSING"
    DATA_QUALITY = "DATA_QUALITY"
    INTEROPERABILITY = "INTEROPERABILITY"
    OPERATIONAL = "OPERATIONAL"
    GENERAL = "GENERAL"


class WorkflowStatus(str, Enum):
    """Authoritative lifecycle status for a workflow instance."""

    CREATED = "CREATED"
    READY = "READY"
    RUNNING = "RUNNING"
    WAITING = "WAITING"
    PAUSED = "PAUSED"
    BLOCKED = "BLOCKED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class WorkflowTriggerType(str, Enum):
    """Explicit trigger source authorizing workflow instantiation."""

    DOMAIN_EVENT = "DOMAIN_EVENT"
    USER_ACTION = "USER_ACTION"
    TASK_COMPLETION = "TASK_COMPLETION"
    DIAGNOSTIC_RESULT = "DIAGNOSTIC_RESULT"
    MEDICATION_SAFETY = "MEDICATION_SAFETY"
    TRIAGE_EVENT = "TRIAGE_EVENT"
    DISCHARGE_EVENT = "DISCHARGE_EVENT"
    APPOINTMENT_EVENT = "APPOINTMENT_EVENT"
    TRANSFER_EVENT = "TRANSFER_EVENT"
    INTEROPERABILITY_EVENT = "INTEROPERABILITY_EVENT"


class WorkflowProvenance(BaseModel):
    """Immutable audit metadata tracing origin event and definition version."""

    model_config = ConfigDict(extra="ignore")

    source_event_id: Optional[str] = Field(default=None, description="Triggering event identifier")
    source_event_type: Optional[str] = Field(default=None, description="Triggering event type")
    initiated_by: Optional[str] = Field(default=None, description="User ID or system that triggered instance")
    definition_id: str = Field(description="Workflow definition identifier")
    definition_version: str = Field(description="Workflow definition version locked at creation")
    correlation_id: str = Field(description="Tracing correlation identifier")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp of workflow initiation",
    )


class WorkflowDefinition(BaseModel):
    """Versioned specification of an approved clinical or operational workflow."""

    model_config = ConfigDict(extra="ignore")

    definition_id: str = Field(description="Unique definition slug e.g. diagnostic_review")
    version: str = Field(default="1.0", description="Semantic or numeric definition version")
    name: str = Field(description="Human-readable title of workflow definition")
    description: Optional[str] = Field(default=None, description="Purpose and clinical boundaries")
    category: WorkflowCategory = Field(description="Domain category")
    enabled: bool = Field(default=True, description="Whether definition is active for new instances")
    trigger_type: WorkflowTriggerType = Field(description="Authorized trigger type")
    steps: List[WorkflowStepDefinition] = Field(default_factory=list, description="Ordered step configurations")
    timeout_minutes: int = Field(default=1440, description="Workflow instance timeout window in minutes")
    escalation_enabled: bool = Field(default=True, description="Whether escalation policies apply")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Definition creation timestamp",
    )


class WorkflowCreate(BaseModel):
    """Request payload for starting or requesting a new workflow instance."""

    model_config = ConfigDict(extra="forbid")

    workflow_definition: str = Field(description="Definition identifier e.g. diagnostic_review")
    workflow_version: Optional[str] = Field(default=None, description="Optional pinned version (defaults to latest)")
    source_type: str = Field(description="Source entity type e.g. diagnostic_result, prescription, transfer")
    source_id: str = Field(description="Source entity identifier e.g. RESULT-123")
    patient_id: Optional[str] = Field(default=None, description="Referenced Patient ID")
    encounter_id: Optional[str] = Field(default=None, description="Referenced Encounter ID")
    resource_id: Optional[str] = Field(default=None, description="Target Resource ID")
    facility_id: Optional[str] = Field(default=None, description="Referenced Facility ID")
    correlation_id: Optional[str] = Field(default=None, description="Tracing correlation identifier")
    idempotency_key: Optional[str] = Field(default=None, description="Client idempotency key")
    initial_context: Dict[str, Any] = Field(
        default_factory=dict,
        description="Initial context references (must NOT contain raw clinical text or PHI)",
    )


class WorkflowPauseRequest(BaseModel):
    """Request payload for pausing a running workflow."""

    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=3, max_length=500, description="Mandatory reason for pause")


class WorkflowResumeRequest(BaseModel):
    """Request payload for resuming a paused workflow."""

    model_config = ConfigDict(extra="forbid")

    reason: Optional[str] = Field(default=None, max_length=500, description="Optional reason for resuming")


class WorkflowCancelRequest(BaseModel):
    """Request payload for cancelling an active workflow."""

    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=3, max_length=500, description="Mandatory cancellation reason")
    cancel_pending_tasks: bool = Field(
        default=False,
        description="Whether to also cancel related pending tasks (if permitted by policy)",
    )


class WorkflowRecord(BaseModel):
    """Authoritative state record of a workflow instance."""

    model_config = ConfigDict(extra="ignore")

    workflow_id: str = Field(description="Unique workflow instance identifier e.g. WF-12345")
    definition_id: str = Field(description="Workflow definition identifier")
    definition_version: str = Field(description="Pinned definition version")
    name: str = Field(description="Workflow title")
    category: WorkflowCategory = Field(description="Workflow category")
    status: WorkflowStatus = Field(default=WorkflowStatus.CREATED, description="Current workflow state")
    current_step_id: Optional[str] = Field(default=None, description="Currently active step ID")
    patient_id: Optional[str] = Field(default=None, description="Referenced Patient ID")
    encounter_id: Optional[str] = Field(default=None, description="Referenced Encounter ID")
    resource_id: Optional[str] = Field(default=None, description="Referenced Resource ID")
    facility_id: Optional[str] = Field(default=None, description="Referenced Facility ID")
    correlation_id: str = Field(description="Tracing correlation ID")
    source_event_id: Optional[str] = Field(default=None, description="Source trigger ID")
    source_event_type: Optional[str] = Field(default=None, description="Source trigger type")
    idempotency_key: Optional[str] = Field(default=None, description="Computed idempotency key")
    provenance: WorkflowProvenance = Field(description="Provenance audit trail")
    steps: List[WorkflowStepRecord] = Field(default_factory=list, description="Ordered step instances")
    context: Dict[str, Any] = Field(default_factory=dict, description="Workflow context references")
    failure_reason: Optional[str] = Field(default=None, description="Sanitized failure description")
    error_code: Optional[str] = Field(default=None, description="Failure error code")
    retry_count: int = Field(default=0, description="Retry count")
    started_at: Optional[datetime] = Field(default=None, description="Execution start timestamp")
    completed_at: Optional[datetime] = Field(default=None, description="Execution finish timestamp")
    expires_at: Optional[datetime] = Field(default=None, description="Scheduled expiration timestamp")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Instance creation timestamp",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Instance last updated timestamp",
    )


class WorkflowFilter(BaseModel):
    """Filter criteria for searching and paginating workflow instances."""

    model_config = ConfigDict(extra="ignore")

    status: Optional[WorkflowStatus] = None
    category: Optional[WorkflowCategory] = None
    definition_id: Optional[str] = None
    patient_id: Optional[str] = None
    facility_id: Optional[str] = None
    correlation_id: Optional[str] = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class WorkflowListResponse(BaseModel):
    """Paginated list of workflow instances."""

    items: List[WorkflowRecord]
    total: int
    page: int
    page_size: int
    has_more: bool
