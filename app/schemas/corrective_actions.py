"""Phase 49: Corrective & Preventive Action Schemas.

Defines remediation actions linked to clinical safety incidents, integrating with
Phase 36 task tracking and Phase 46 clinical record versioning.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


class ActionType(str, Enum):
    """Classification of remedial and preventive measures."""

    CODE_FIX = "CODE_FIX"
    CONFIGURATION_CORRECTION = "CONFIGURATION_CORRECTION"
    PROVIDER_CORRECTION = "PROVIDER_CORRECTION"
    VALIDATION_IMPROVEMENT = "VALIDATION_IMPROVEMENT"
    WORKFLOW_CORRECTION = "WORKFLOW_CORRECTION"
    SECURITY_PATCH = "SECURITY_PATCH"
    DATA_RECONCILIATION = "DATA_RECONCILIATION"
    CLINICAL_RECORD_CORRECTION = "CLINICAL_RECORD_CORRECTION"
    TEST_ADDITION = "TEST_ADDITION"
    POLICY_UPDATE = "POLICY_UPDATE"
    PREVENTIVE_RULE = "PREVENTIVE_RULE"


class ActionStatus(str, Enum):
    """Lifecycle status of a corrective or preventive action."""

    CREATED = "CREATED"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    BLOCKED = "BLOCKED"
    COMPLETED = "COMPLETED"
    VALIDATION_REQUIRED = "VALIDATION_REQUIRED"
    VERIFIED = "VERIFIED"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"
    REOPENED = "REOPENED"


class CorrectiveActionRecord(BaseModel):
    """Authoritative record of a corrective or preventive action."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: f"act-{uuid.uuid4().hex[:12]}")
    incident_id: str
    action_type: ActionType
    is_preventive: bool = False
    title: str
    description: str
    status: ActionStatus = Field(default=ActionStatus.CREATED)
    assigned_to_id: Optional[str] = None
    assigned_to_role: Optional[str] = None
    linked_task_id: Optional[str] = Field(default=None, description="Linked Phase 36 task ID")
    linked_version_id: Optional[str] = Field(default=None, description="Linked Phase 46 version correction reference")
    resolution_details: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    verified_at: Optional[datetime] = None
    verified_by_id: Optional[str] = None


class CorrectiveActionCreateRequest(BaseModel):
    """Payload to initiate a corrective or preventive action."""

    model_config = ConfigDict(extra="forbid")

    action_type: ActionType
    title: str
    description: str
    is_preventive: bool = False
    assigned_to_id: Optional[str] = None
    assigned_to_role: Optional[str] = None


class CorrectiveActionStatusUpdateRequest(BaseModel):
    """Payload to advance status of an action."""

    model_config = ConfigDict(extra="forbid")

    status: ActionStatus
    resolution_details: Optional[str] = None
    linked_task_id: Optional[str] = None
