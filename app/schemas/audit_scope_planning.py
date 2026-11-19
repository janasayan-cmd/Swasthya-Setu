"""Phase 70: Audit Scope and Planning Schemas.

Defines schemas for:
- Clinical safety audit lifecycle records
- Governed audit scope definition, freeze, and authorized change control
- Audit planning, scheduling, pausing, and cancellation
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.audit_programme import AuditPriority, AuditProgrammeCategory


class AuditLifecycleStatus(str, Enum):
    """Lifecycle states for independent clinical safety governance audits."""

    DRAFT = "DRAFT"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    SCHEDULED = "SCHEDULED"
    IN_PROGRESS = "IN_PROGRESS"
    PAUSED = "PAUSED"
    PENDING_REVIEW = "PENDING_REVIEW"
    REPORT_DRAFT = "REPORT_DRAFT"
    REPORT_APPROVED = "REPORT_APPROVED"
    FOLLOW_UP_REQUIRED = "FOLLOW_UP_REQUIRED"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


class AuditScopeStatus(str, Enum):
    """Governance status of an audit scope."""

    DRAFT = "DRAFT"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    FROZEN = "FROZEN"
    AMENDED = "AMENDED"


class AuditScopeRecord(BaseModel):
    """Domain model tracking approved scope and boundary exclusions."""

    model_config = ConfigDict(extra="ignore")

    scope_id: str = Field(default_factory=lambda: f"gscp-{uuid.uuid4().hex[:12]}")
    audit_id: str
    version: int = 1
    status: AuditScopeStatus = AuditScopeStatus.DRAFT

    included_governance_processes: List[str] = Field(default_factory=list)
    included_safety_controls: List[str] = Field(default_factory=list)
    included_compliance_requirements: List[str] = Field(default_factory=list)  # Phase 69 requirement refs
    included_workflow_phases: List[str] = Field(default_factory=list)  # PHASE_48..PHASE_69
    included_facilities: List[str] = Field(default_factory=list)

    evaluation_period_start: Optional[datetime] = None
    evaluation_period_end: Optional[datetime] = None

    scope_limitations: List[str] = Field(default_factory=list)
    scope_exclusions: List[Dict[str, str]] = Field(default_factory=list)  # [{"item": ..., "justification": ...}]

    is_frozen: bool = False
    frozen_at: Optional[datetime] = None
    frozen_by: Optional[str] = None

    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None

    change_history: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ClinicalSafetyAuditRecord(BaseModel):
    """Domain record representing an independent safety governance audit."""

    model_config = ConfigDict(extra="ignore")

    audit_id: str = Field(default_factory=lambda: f"gaud-{uuid.uuid4().hex[:12]}")
    programme_id: str
    title: str
    description: str
    category: AuditProgrammeCategory = AuditProgrammeCategory.SCHEDULED_GOVERNANCE
    priority: AuditPriority = AuditPriority.ROUTINE
    lifecycle_status: AuditLifecycleStatus = AuditLifecycleStatus.DRAFT

    organization_id: str
    facility_id: Optional[str] = None
    lead_auditor_id: Optional[str] = None
    scope_id: Optional[str] = None

    planned_start_date: Optional[datetime] = None
    planned_end_date: Optional[datetime] = None
    actual_start_date: Optional[datetime] = None
    actual_end_date: Optional[datetime] = None

    closure_rationale: Optional[str] = None
    cancellation_reason: Optional[str] = None
    paused_reason: Optional[str] = None

    created_by: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ===========================================================================
# Request Models
# ===========================================================================

class CreateAuditRequest(BaseModel):
    """Request payload to initiate a new audit under a programme."""

    model_config = ConfigDict(extra="ignore")

    programme_id: str
    title: str
    description: str
    category: Optional[AuditProgrammeCategory] = AuditProgrammeCategory.SCHEDULED_GOVERNANCE
    priority: Optional[AuditPriority] = AuditPriority.ROUTINE
    facility_id: Optional[str] = None
    planned_start_date: Optional[datetime] = None
    planned_end_date: Optional[datetime] = None
    lead_auditor_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class UpdateAuditRequest(BaseModel):
    """Request payload to update basic audit details."""

    model_config = ConfigDict(extra="ignore")

    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[AuditPriority] = None
    planned_start_date: Optional[datetime] = None
    planned_end_date: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None


class ScheduleAuditRequest(BaseModel):
    """Request payload to transition an approved audit into SCHEDULED or IN_PROGRESS."""

    model_config = ConfigDict(extra="ignore")

    scheduled_start_date: datetime
    scheduled_end_date: datetime
    start_immediately: Optional[bool] = False


class PauseAuditRequest(BaseModel):
    """Request payload to pause an in-progress audit."""

    model_config = ConfigDict(extra="ignore")

    paused_reason: str


class CancelAuditRequest(BaseModel):
    """Request payload to cancel an audit."""

    model_config = ConfigDict(extra="ignore")

    cancellation_reason: str


class DefineAuditScopeRequest(BaseModel):
    """Request payload to establish or update draft audit scope."""

    model_config = ConfigDict(extra="ignore")

    included_governance_processes: Optional[List[str]] = Field(default_factory=list)
    included_safety_controls: Optional[List[str]] = Field(default_factory=list)
    included_compliance_requirements: Optional[List[str]] = Field(default_factory=list)
    included_workflow_phases: Optional[List[str]] = Field(default_factory=list)
    included_facilities: Optional[List[str]] = Field(default_factory=list)
    evaluation_period_start: Optional[datetime] = None
    evaluation_period_end: Optional[datetime] = None
    scope_limitations: Optional[List[str]] = Field(default_factory=list)
    scope_exclusions: Optional[List[Dict[str, str]]] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ApproveAuditScopeRequest(BaseModel):
    """Request payload to approve an audit scope prior to execution."""

    model_config = ConfigDict(extra="ignore")

    approval_rationale: str


class AmendAuditScopeRequest(BaseModel):
    """Request payload to amend a frozen or approved scope with documented justification."""

    model_config = ConfigDict(extra="ignore")

    change_justification: str
    amended_processes: Optional[List[str]] = None
    amended_requirements: Optional[List[str]] = None
    amended_controls: Optional[List[str]] = None
    amended_exclusions: Optional[List[Dict[str, str]]] = None
