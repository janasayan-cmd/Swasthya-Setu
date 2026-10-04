"""Pydantic schemas for Clinical Task Assignment (Phase 36).

CORE SAFETY PRINCIPLES:
- TASK != CLINICAL DECISION
- TASK ASSIGNED != TASK ACCEPTED
- TASK ACCEPTED != TASK PERFORMED
- TEAM ASSIGNMENT != INDIVIDUAL CLINICIAN ACCEPTANCE
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class AssigneeType(str, Enum):
    """Class of assignee target for clinical/operational task."""

    USER = "USER"
    CARE_TEAM = "CARE_TEAM"
    FACILITY_TEAM = "FACILITY_TEAM"
    ORGANIZATION_TEAM = "ORGANIZATION_TEAM"


class TaskAssignRequest(BaseModel):
    """Payload to assign a task to an authorized user or team."""

    model_config = ConfigDict(extra="ignore")

    assignee_id: str = Field(description="Unique identifier of target user or designated team")
    assignee_type: AssigneeType = Field(default=AssigneeType.USER, description="Classification of target assignee")
    team_id: Optional[str] = Field(default=None, description="Optional team grouping identifier")
    notes: Optional[str] = Field(default=None, max_length=500, description="Contextual instructions for assignment")


class TaskReassignRequest(BaseModel):
    """Payload to reassign an existing task with mandatory justification."""

    model_config = ConfigDict(extra="ignore")

    new_assignee_id: str = Field(description="Unique identifier of replacement assignee")
    new_assignee_type: AssigneeType = Field(default=AssigneeType.USER, description="Classification of replacement assignee")
    new_team_id: Optional[str] = Field(default=None, description="Optional team grouping identifier")
    reason: str = Field(min_length=3, max_length=500, description="Mandatory reason for reassignment")


class TaskAssignmentRecord(BaseModel):
    """Audit-grade record of an assignment event."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(description="Unique assignment event UUID")
    task_id: str = Field(description="Target task identifier")
    assignee_id: str = Field(description="Assigned user or team ID")
    assignee_type: AssigneeType = Field(description="Assigned entity type")
    team_id: Optional[str] = Field(default=None, description="Team ID if applicable")
    assigned_by: str = Field(description="User who initiated assignment")
    assigned_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Timestamp of assignment")
    reason: Optional[str] = Field(default=None, description="Assignment or reassignment reason")
