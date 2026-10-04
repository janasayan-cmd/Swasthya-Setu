"""Pydantic schemas for Clinical Tasks, Work Queues & Action Management (Phase 36).

CORE SAFETY PRINCIPLES:
- TASK != CLINICAL DECISION
- TASK != DIAGNOSIS
- TASK != PRESCRIPTION
- TASK != TREATMENT
- TASK != MEDICATION CHANGE
- TASK != TRIAGE
- TASK != EMERGENCY DISPATCH
- ALERT != TASK
- TASK CREATED != TASK STARTED
- TASK STARTED != TASK COMPLETED
- TASK COMPLETED != CLINICAL OUTCOME
- TASK ASSIGNED != TASK ACCEPTED
- TASK ACCEPTED != TASK PERFORMED
- TASK PERFORMED != TASK VERIFIED
- AI-GENERATED SUGGESTION != AUTHORIZED CLINICAL TASK
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.task_assignment import AssigneeType


class TaskCategory(str, Enum):
    """Categorization of clinical or operational task."""

    CLINICAL_TASK = "CLINICAL_TASK"
    FOLLOW_UP_TASK = "FOLLOW_UP_TASK"
    MEDICATION_REVIEW_TASK = "MEDICATION_REVIEW_TASK"
    DIAGNOSTIC_REVIEW_TASK = "DIAGNOSTIC_REVIEW_TASK"
    PATIENT_CONTACT_TASK = "PATIENT_CONTACT_TASK"
    DOCUMENT_REVIEW_TASK = "DOCUMENT_REVIEW_TASK"
    DISCHARGE_FOLLOW_UP_TASK = "DISCHARGE_FOLLOW_UP_TASK"
    APPOINTMENT_TASK = "APPOINTMENT_TASK"
    TRANSFER_TASK = "TRANSFER_TASK"
    DATA_QUALITY_TASK = "DATA_QUALITY_TASK"
    INTEROPERABILITY_TASK = "INTEROPERABILITY_TASK"
    ADMINISTRATIVE_TASK = "ADMINISTRATIVE_TASK"
    SECURITY_TASK = "SECURITY_TASK"
    SYSTEM_TASK = "SYSTEM_TASK"


class TaskStatus(str, Enum):
    """Authoritative lifecycle status for tasks."""

    CREATED = "CREATED"
    UNASSIGNED = "UNASSIGNED"
    ASSIGNED = "ASSIGNED"
    ACCEPTED = "ACCEPTED"
    IN_PROGRESS = "IN_PROGRESS"
    BLOCKED = "BLOCKED"
    COMPLETED = "COMPLETED"
    VERIFICATION_PENDING = "VERIFICATION_PENDING"
    VERIFIED = "VERIFIED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    FAILED = "FAILED"


class TaskPriority(str, Enum):
    """Explicit, non-inferred urgency priority for task execution."""

    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    URGENT = "URGENT"


class TaskDependencyStatus(str, Enum):
    """Prerequisite status for dependency resolution."""

    WAITING = "WAITING"
    READY = "READY"
    BLOCKED = "BLOCKED"
    COMPLETED = "COMPLETED"


class TaskDependency(BaseModel):
    """Prerequisite task dependency model."""

    model_config = ConfigDict(extra="ignore")

    depends_on_task_id: str = Field(description="Identifier of prerequisite task")
    dependency_type: str = Field(default="COMPLETION_REQUIRED", description="Type of prerequisite constraint")
    status: TaskDependencyStatus = Field(default=TaskDependencyStatus.WAITING, description="Current resolution state")


class TaskProvenance(BaseModel):
    """Immutable provenance metadata tracing origin event or source."""

    model_config = ConfigDict(extra="ignore")

    source_type: str = Field(description="Entity type generating task (e.g. diagnostic_result, alert, triage)")
    source_id: str = Field(description="Identifier of originating source resource")
    source_event_id: Optional[str] = Field(default=None, description="Authoritative event UUID if event-driven")
    source_system: str = Field(description="Subsystem name that requested/emitted task creation")
    policy_id: Optional[str] = Field(default=None, description="Applied task policy ID")
    policy_version: Optional[str] = Field(default=None, description="Applied task policy version")


class TaskRecord(BaseModel):
    """Database-aligned authoritative representation of a task."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(description="Unique task identifier (e.g. TSK-YYYYMMDD-XXXXX)")
    title: str = Field(description="Clear, non-diagnostic statement of required work")
    description: Optional[str] = Field(default=None, description="Contextual instructions without unmasked PHI")
    category: TaskCategory = Field(description="Domain category of work")
    priority: TaskPriority = Field(default=TaskPriority.NORMAL, description="Authoritative priority level")
    status: TaskStatus = Field(default=TaskStatus.CREATED, description="Lifecycle status")

    patient_id: Optional[str] = Field(default=None, description="Associated patient identifier")
    encounter_id: Optional[str] = Field(default=None, description="Associated encounter identifier")
    organization_id: Optional[str] = Field(default=None, description="Tenant organization scope")
    facility_id: Optional[str] = Field(default=None, description="Tenant facility scope")

    assignee_id: Optional[str] = Field(default=None, description="Designated user or team assignee")
    assignee_type: Optional[AssigneeType] = Field(default=None, description="Classification of assignee")
    team_id: Optional[str] = Field(default=None, description="Associated care team or group")

    created_by: str = Field(description="User or system entity that created the task")
    accepted_by: Optional[str] = Field(default=None, description="User who accepted task responsibility")
    accepted_at: Optional[datetime] = Field(default=None, description="Timestamp of acceptance")

    started_at: Optional[datetime] = Field(default=None, description="Timestamp task transitioned to IN_PROGRESS")
    completed_by: Optional[str] = Field(default=None, description="User who completed the task work")
    completed_at: Optional[datetime] = Field(default=None, description="Timestamp work reported completed")
    completion_notes: Optional[str] = Field(default=None, description="Notes recorded upon completion")

    verification_required: bool = Field(default=False, description="Flag indicating independent verification required")
    verified_by: Optional[str] = Field(default=None, description="Authorized verifier identifier")
    verified_at: Optional[datetime] = Field(default=None, description="Timestamp of verification")
    verification_notes: Optional[str] = Field(default=None, description="Verification review notes")

    cancelled_by: Optional[str] = Field(default=None, description="User who cancelled the task")
    cancelled_at: Optional[datetime] = Field(default=None, description="Timestamp of cancellation")
    cancellation_reason: Optional[str] = Field(default=None, description="Justification for cancellation")

    rejected_by: Optional[str] = Field(default=None, description="User who rejected the assignment")
    rejected_at: Optional[datetime] = Field(default=None, description="Timestamp of rejection")
    rejection_reason: Optional[str] = Field(default=None, description="Reason for assignment rejection")

    due_at: Optional[datetime] = Field(default=None, description="Target completion deadline")
    start_at: Optional[datetime] = Field(default=None, description="Earliest allowed start timestamp")
    expires_at: Optional[datetime] = Field(default=None, description="Timestamp after which task auto-expires")

    dependencies: List[TaskDependency] = Field(default_factory=list, description="Prerequisite task dependencies")
    provenance: TaskProvenance = Field(description="Origin source and policy provenance")
    idempotency_key: Optional[str] = Field(default=None, description="Key for duplicate suppression")

    escalation_level: int = Field(default=0, description="Current escalation tier (0=none)")
    escalation_deadline: Optional[datetime] = Field(default=None, description="Next escalation evaluation deadline")

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Creation timestamp")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Last update timestamp")


class TaskCreate(BaseModel):
    """Payload to create a new clinical or operational task."""

    model_config = ConfigDict(extra="ignore")

    title: str = Field(min_length=3, max_length=255, description="Clear, non-diagnostic statement of task")
    description: Optional[str] = Field(default=None, max_length=2000, description="Detailed instructions")
    category: TaskCategory = Field(description="Category of work")
    priority: TaskPriority = Field(default=TaskPriority.NORMAL, description="Urgency priority")

    patient_id: Optional[str] = Field(default=None, description="Patient context")
    encounter_id: Optional[str] = Field(default=None, description="Clinical encounter context")
    organization_id: Optional[str] = Field(default=None, description="Tenant organization ID")
    facility_id: Optional[str] = Field(default=None, description="Facility ID")

    assignee_id: Optional[str] = Field(default=None, description="Initial assignee user or team ID")
    assignee_type: Optional[AssigneeType] = Field(default=None, description="Assignee classification")
    team_id: Optional[str] = Field(default=None, description="Team ID")

    due_at: Optional[datetime] = Field(default=None, description="Completion deadline")
    start_at: Optional[datetime] = Field(default=None, description="Earliest start timestamp")
    verification_required: bool = Field(default=False, description="Require supervisor/peer verification")

    dependencies: List[TaskDependency] = Field(default_factory=list, description="Prerequisite dependencies")
    provenance: TaskProvenance = Field(description="Source provenance")
    idempotency_key: Optional[str] = Field(default=None, description="Unique client idempotency token")


class TaskAcceptRequest(BaseModel):
    """Payload for explicit task responsibility acceptance."""

    model_config = ConfigDict(extra="ignore")

    note: Optional[str] = Field(default=None, max_length=500, description="Optional acceptance acknowledgment note")


class TaskStartRequest(BaseModel):
    """Payload to transition task into IN_PROGRESS."""

    model_config = ConfigDict(extra="ignore")

    note: Optional[str] = Field(default=None, max_length=500, description="Optional note upon work commencement")


class TaskCompleteRequest(BaseModel):
    """Payload to report task completion."""

    model_config = ConfigDict(extra="ignore")

    completion_notes: Optional[str] = Field(default=None, max_length=1000, description="Factual notes on completion")


class TaskVerifyRequest(BaseModel):
    """Payload for formal verification review by authorized verifier."""

    model_config = ConfigDict(extra="ignore")

    approved: bool = Field(default=True, description="True to verify, False to reject verification back to assignee")
    verification_notes: Optional[str] = Field(default=None, max_length=1000, description="Review remarks")


class TaskRejectRequest(BaseModel):
    """Payload to reject an assignment."""

    model_config = ConfigDict(extra="ignore")

    reason: str = Field(min_length=3, max_length=500, description="Mandatory reason for rejection")


class TaskCancelRequest(BaseModel):
    """Payload to cancel a task."""

    model_config = ConfigDict(extra="ignore")

    reason: str = Field(min_length=3, max_length=500, description="Mandatory reason for cancellation")


class TaskStatusTransitionRequest(BaseModel):
    """Payload to request an explicit controlled status transition."""

    model_config = ConfigDict(extra="ignore")

    target_status: TaskStatus = Field(description="Desired target status")
    reason: Optional[str] = Field(default=None, max_length=500, description="Transition rationale")


class TaskFilter(BaseModel):
    """Query filters for task list and queue retrieval."""

    model_config = ConfigDict(extra="ignore")

    status: Optional[TaskStatus] = None
    category: Optional[TaskCategory] = None
    priority: Optional[TaskPriority] = None
    assignee_id: Optional[str] = None
    team_id: Optional[str] = None
    patient_id: Optional[str] = None
    facility_id: Optional[str] = None
    organization_id: Optional[str] = None
    source_type: Optional[str] = None
    source_id: Optional[str] = None
    overdue_only: Optional[bool] = None
    verification_required: Optional[bool] = None
    created_from: Optional[datetime] = None
    created_to: Optional[datetime] = None
    due_from: Optional[datetime] = None
    due_to: Optional[datetime] = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class TaskListResponse(BaseModel):
    """Paginated list response for tasks."""

    model_config = ConfigDict(extra="ignore")

    tasks: List[TaskRecord]
    total: int
    page: int
    page_size: int
    total_pages: int
