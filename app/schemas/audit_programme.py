"""Phase 70: Audit Programme Management Schemas.

Defines schemas for:
- Clinical safety governance audit programmes
- Objectives, priorities, categories, and organizational scope
- Approval and version governance
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class AuditProgrammeCategory(str, Enum):
    """Classification of governance audit programme."""

    SCHEDULED_GOVERNANCE = "SCHEDULED_GOVERNANCE"
    RISK_BASED = "RISK_BASED"
    THEMATIC = "THEMATIC"
    PROCESS = "PROCESS"
    CONTROL_IMPLEMENTATION = "CONTROL_IMPLEMENTATION"
    FOLLOW_UP = "FOLLOW_UP"
    SPECIAL_TRIGGERED = "SPECIAL_TRIGGERED"


class AuditPriority(str, Enum):
    """Priority level for audit planning and execution."""

    ROUTINE = "ROUTINE"
    ELEVATED = "ELEVATED"
    HIGH = "HIGH"
    URGENT = "URGENT"
    CRITICAL = "CRITICAL"


class AuditProgrammeStatus(str, Enum):
    """Lifecycle status of an audit programme."""

    DRAFT = "DRAFT"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    ARCHIVED = "ARCHIVED"


class AuditProgrammeRecord(BaseModel):
    """Domain model tracking a multi-audit governance programme."""

    model_config = ConfigDict(extra="ignore")

    programme_id: str = Field(default_factory=lambda: f"gprg-{uuid.uuid4().hex[:12]}")
    name: str
    description: str
    objectives: List[str] = Field(default_factory=list)
    category: AuditProgrammeCategory = AuditProgrammeCategory.SCHEDULED_GOVERNANCE
    priority: AuditPriority = AuditPriority.ROUTINE
    status: AuditProgrammeStatus = AuditProgrammeStatus.DRAFT

    organization_id: str
    facility_id: Optional[str] = None
    responsible_owner_id: str
    responsible_owner_role: str

    planned_start_date: Optional[datetime] = None
    planned_end_date: Optional[datetime] = None
    related_framework_ids: List[str] = Field(default_factory=list)  # Phase 69 frameworks

    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    approval_rationale: Optional[str] = None

    created_by: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CreateAuditProgrammeRequest(BaseModel):
    """Request payload to establish an audit programme."""

    model_config = ConfigDict(extra="ignore")

    name: str
    description: str
    objectives: List[str]
    category: Optional[AuditProgrammeCategory] = AuditProgrammeCategory.SCHEDULED_GOVERNANCE
    priority: Optional[AuditPriority] = AuditPriority.ROUTINE
    facility_id: Optional[str] = None
    planned_start_date: Optional[datetime] = None
    planned_end_date: Optional[datetime] = None
    related_framework_ids: Optional[List[str]] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class UpdateAuditProgrammeRequest(BaseModel):
    """Request payload to modify draft or active audit programme parameters."""

    model_config = ConfigDict(extra="ignore")

    name: Optional[str] = None
    description: Optional[str] = None
    objectives: Optional[List[str]] = None
    priority: Optional[AuditPriority] = None
    planned_start_date: Optional[datetime] = None
    planned_end_date: Optional[datetime] = None
    related_framework_ids: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None


class ApproveAuditProgrammeRequest(BaseModel):
    """Request payload to formally approve an audit programme."""

    model_config = ConfigDict(extra="ignore")

    approval_rationale: str
