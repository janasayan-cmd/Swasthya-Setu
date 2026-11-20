"""Phase 72: Management Review Scheduling & Participant Management Schemas.

Defines schemas for:
- Review meeting lifecycle states (DRAFT to COMPLETED/CANCELLED)
- Meeting scheduling, rescheduling, and postponement
- Participant roles, decision authority validation, and conflict declarations
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class ManagementReviewStatus(str, Enum):
    """Lifecycle states for a management review meeting."""

    DRAFT = "DRAFT"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    SCHEDULED = "SCHEDULED"
    PREPARATION = "PREPARATION"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    IN_PROGRESS = "IN_PROGRESS"
    PENDING_DECISION_FINALIZATION = "PENDING_DECISION_FINALIZATION"
    FOLLOW_UP = "FOLLOW_UP"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class ParticipantRole(str, Enum):
    """Functional role of a participant in a management review."""

    CHAIRPERSON = "CHAIRPERSON"
    EXECUTIVE_REVIEWER = "EXECUTIVE_REVIEWER"
    CLINICAL_SAFETY_REPRESENTATIVE = "CLINICAL_SAFETY_REPRESENTATIVE"
    COMPLIANCE_REPRESENTATIVE = "COMPLIANCE_REPRESENTATIVE"
    RISK_REPRESENTATIVE = "RISK_REPRESENTATIVE"
    AUDIT_REPRESENTATIVE = "AUDIT_REPRESENTATIVE"
    CORRECTIVE_ACTION_OWNER = "CORRECTIVE_ACTION_OWNER"
    SUBJECT_MATTER_EXPERT = "SUBJECT_MATTER_EXPERT"
    SECRETARY = "SECRETARY"
    OBSERVER = "OBSERVER"


class AttendanceStatus(str, Enum):
    """Attendance status for an invited participant."""

    INVITED = "INVITED"
    CONFIRMED = "CONFIRMED"
    ATTENDED = "ATTENDED"
    EXCUSED = "EXCUSED"
    ABSENT = "ABSENT"


class ManagementReviewRecord(BaseModel):
    """Domain model tracking a management review meeting and its lifecycle."""

    model_config = ConfigDict(extra="ignore")

    review_id: str = Field(default_factory=lambda: f"gmrv-{uuid.uuid4().hex[:12]}")
    programme_id: str
    title: str
    objectives: List[str] = Field(default_factory=list)
    status: ManagementReviewStatus = ManagementReviewStatus.DRAFT

    planned_date: datetime
    time_zone: str = "UTC"
    duration_minutes: int = 60
    actual_start_time: Optional[datetime] = None
    actual_end_time: Optional[datetime] = None

    chairperson_id: Optional[str] = None
    meeting_owner_id: str

    agenda_preparation_deadline: Optional[datetime] = None
    evidence_preparation_deadline: Optional[datetime] = None
    decision_recording_deadline: Optional[datetime] = None
    follow_up_deadline: Optional[datetime] = None

    organization_id: str
    facility_id: Optional[str] = None

    cancellation_reason: Optional[str] = None
    rescheduled_reason: Optional[str] = None

    created_by: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ReviewParticipantRecord(BaseModel):
    """Domain model tracking an invited participant and their decision authority."""

    model_config = ConfigDict(extra="ignore")

    participant_id: str = Field(default_factory=lambda: f"gmpt-{uuid.uuid4().hex[:12]}")
    review_id: str
    user_id: str
    user_name: Optional[str] = None
    role: ParticipantRole = ParticipantRole.EXECUTIVE_REVIEWER
    attendance_status: AttendanceStatus = AttendanceStatus.INVITED
    has_decision_authority: bool = False

    delegated_from_id: Optional[str] = None
    conflict_declared: bool = False
    conflict_details: Optional[str] = None
    attendance_confirmed_at: Optional[datetime] = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)


# Request Models
class CreateManagementReviewRequest(BaseModel):
    """Request payload to initiate a new review meeting under a programme."""

    model_config = ConfigDict(extra="ignore")

    programme_id: str
    title: str
    objectives: Optional[List[str]] = Field(default_factory=list)
    planned_date: datetime
    time_zone: Optional[str] = "UTC"
    duration_minutes: Optional[int] = 60
    chairperson_id: Optional[str] = None
    facility_id: Optional[str] = None
    agenda_preparation_deadline: Optional[datetime] = None
    evidence_preparation_deadline: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class UpdateManagementReviewRequest(BaseModel):
    """Request payload to update review meeting properties."""

    model_config = ConfigDict(extra="ignore")

    title: Optional[str] = None
    objectives: Optional[List[str]] = None
    planned_date: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    chairperson_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ScheduleReviewRequest(BaseModel):
    """Request payload to schedule or progress review to SCHEDULED."""

    model_config = ConfigDict(extra="ignore")

    planned_date: datetime
    chairperson_id: str
    notes: Optional[str] = None


class RescheduleReviewRequest(BaseModel):
    """Request payload to reschedule an existing review."""

    model_config = ConfigDict(extra="ignore")

    new_planned_date: datetime
    rescheduled_reason: str


class CancelReviewRequest(BaseModel):
    """Request payload to cancel a review."""

    model_config = ConfigDict(extra="ignore")

    cancellation_reason: str


class AddParticipantRequest(BaseModel):
    """Request payload to add a participant to a review meeting."""

    model_config = ConfigDict(extra="ignore")

    user_id: str
    user_name: Optional[str] = None
    role: ParticipantRole
    has_decision_authority: Optional[bool] = False
    delegated_from_id: Optional[str] = None
    conflict_declared: Optional[bool] = False
    conflict_details: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class UpdateParticipantRequest(BaseModel):
    """Request payload to update participant role, authority, or conflict."""

    model_config = ConfigDict(extra="ignore")

    role: Optional[ParticipantRole] = None
    has_decision_authority: Optional[bool] = None
    conflict_declared: Optional[bool] = None
    conflict_details: Optional[str] = None


class ConfirmAttendanceRequest(BaseModel):
    """Request payload to confirm or update attendance status."""

    model_config = ConfigDict(extra="ignore")

    attendance_status: AttendanceStatus
    conflict_declared: Optional[bool] = False
    conflict_details: Optional[str] = None
