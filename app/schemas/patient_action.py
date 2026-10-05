"""HealthSetu Phase 42 - Patient Action Schemas.

Patient Engagement, Consented Self-Service & Care Journey Action Management.
Defines Action Definitions, Action Instances, Action Lifecycles, and History.

NON-NEGOTIABLE CLINICAL SAFETY PRINCIPLES:
- PATIENT ACTION != CLINICAL DECISION
- PATIENT RESPONSE != CLINICAL VERIFICATION
- PATIENT ACKNOWLEDGEMENT != CLINICAL UNDERSTANDING OR ADHERENCE
- PATIENT CONFIRMATION != CLINICAL CONSENT UNLESS EXPLICITLY DEFINED
- PATIENT SUBMISSION != VERIFIED MEDICAL DATA
- SUBMITTED != VERIFIED; COMPLETED != CLINICAL OUTCOME; EXPIRED != PATIENT FAILURE
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class ActionType(str, Enum):
    """Categorization of patient self-service actions."""

    ACKNOWLEDGEMENT = "ACKNOWLEDGEMENT"
    CONFIRMATION = "CONFIRMATION"
    QUESTIONNAIRE = "QUESTIONNAIRE"
    DOCUMENT_SUBMISSION = "DOCUMENT_SUBMISSION"
    APPOINTMENT_CONFIRMATION = "APPOINTMENT_CONFIRMATION"
    FOLLOW_UP_RESPONSE = "FOLLOW_UP_RESPONSE"
    CARE_PLAN_ACKNOWLEDGEMENT = "CARE_PLAN_ACKNOWLEDGEMENT"
    COMMUNICATION_PREFERENCE = "COMMUNICATION_PREFERENCE"
    INFORMATION_REQUEST = "INFORMATION_REQUEST"
    PATIENT_FEEDBACK = "PATIENT_FEEDBACK"
    ADMINISTRATIVE_CONFIRMATION = "ADMINISTRATIVE_CONFIRMATION"


class ActionStatus(str, Enum):
    """Lifecycle states of a patient action instance."""

    CREATED = "CREATED"
    AVAILABLE = "AVAILABLE"
    STARTED = "STARTED"
    SUBMITTED = "SUBMITTED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class ActionPriority(str, Enum):
    """Operational priority for action ordering (NOT clinical triage severity)."""

    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    URGENT = "URGENT"


class ActionDefinitionRecord(BaseModel):
    """Reusable catalog definition of a patient-facing operational action."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    id: str = Field(default_factory=lambda: f"actdef_{uuid4().hex[:12]}")
    code: str = Field(..., description="Unique machine-readable action definition code")
    title: str = Field(..., description="Human-readable title")
    description: Optional[str] = None
    action_type: ActionType
    default_expiration_hours: int = 72
    requires_consent: bool = False
    required_consent_type: Optional[str] = None
    questionnaire_id: Optional[str] = None
    is_active: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PatientActionRecord(BaseModel):
    """Authoritative representation of a patient action instance."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(default_factory=lambda: f"pact_{uuid4().hex[:16]}")
    definition_id: Optional[str] = None
    patient_id: str = Field(..., description="Subject patient identifier")
    organization_id: Optional[str] = None
    facility_id: Optional[str] = None
    care_team_id: Optional[str] = None
    encounter_id: Optional[str] = None
    title: str = Field(..., description="Patient-facing action title")
    description: Optional[str] = None
    action_type: ActionType
    status: ActionStatus = ActionStatus.AVAILABLE
    priority: ActionPriority = ActionPriority.NORMAL
    target_resource_type: Optional[str] = None
    target_resource_id: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    available_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    submitted_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    cancellation_reason: Optional[str] = None
    created_by: Optional[str] = None
    is_refusal: bool = False
    refusal_reason: Optional[str] = None
    reminder_count: int = 0
    last_reminder_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    clinical_safety_notice: str = (
        "PATIENT SELF-SERVICE IS AN OPERATIONAL INTERACTION LAYER, NOT CLINICAL AUTHORITY. "
        "PATIENT ACTION != CLINICAL DECISION, AND SUBMISSION != VERIFIED MEDICAL DATA."
    )


class PatientActionHistoryRecord(BaseModel):
    """Audit and state transition history for a patient action."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    id: str = Field(default_factory=lambda: f"pah_{uuid4().hex[:12]}")
    action_id: str
    from_status: Optional[ActionStatus] = None
    to_status: ActionStatus
    actor_id: Optional[str] = None
    actor_role: Optional[str] = None
    reason: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    details: Dict[str, Any] = Field(default_factory=dict)


# API Request Models
class PatientActionCreateRequest(BaseModel):
    """Request payload to create a new patient action instance."""

    definition_id: Optional[str] = None
    patient_id: str
    organization_id: Optional[str] = None
    facility_id: Optional[str] = None
    care_team_id: Optional[str] = None
    encounter_id: Optional[str] = None
    title: str
    description: Optional[str] = None
    action_type: ActionType
    priority: ActionPriority = ActionPriority.NORMAL
    target_resource_type: Optional[str] = None
    target_resource_id: Optional[str] = None
    expires_in_hours: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PatientActionStartRequest(BaseModel):
    """Request payload for starting a patient action."""

    notes: Optional[str] = None


class PatientActionSubmitRequest(BaseModel):
    """Request payload for submitting a patient self-service response."""

    responses: Dict[str, Any] = Field(default_factory=dict, description="Structured answer or response data")
    document_ids: List[str] = Field(default_factory=list, description="IDs of documents attached to submission")
    notes: Optional[str] = None
    idempotency_key: Optional[str] = None


class PatientActionCompleteRequest(BaseModel):
    """Request payload for marking an operational action completed."""

    notes: Optional[str] = None


class PatientActionCancelRequest(BaseModel):
    """Request payload for cancelling an action."""

    reason: str = Field(..., min_length=2, description="Reason for cancellation")


class PatientActionAcknowledgeRequest(BaseModel):
    """Request payload for acknowledging receipt of notices or care plans."""

    notes: Optional[str] = None


class PatientActionRefuseRequest(BaseModel):
    """Request payload for patient explicit refusal/opt-out."""

    reason: str = Field(..., min_length=2, description="Patient's stated reason for declining action")


class PatientActionCorrectionRequest(BaseModel):
    """Request payload for submitting a correction without overwriting history."""

    reason: str = Field(..., min_length=2, description="Reason for correction")
    corrected_responses: Dict[str, Any] = Field(..., description="Updated answer or response data")
    document_ids: List[str] = Field(default_factory=list)
    notes: Optional[str] = None


class PatientActionReviewRequest(BaseModel):
    """Clinician / admin review of submitted patient action."""

    review_outcome: str = Field(..., description="ACCEPT, REJECT, or REQUEST_CORRECTION")
    reviewer_notes: Optional[str] = None


# API Response Models
class PatientActionResponse(BaseModel):
    """Response containing an authoritative patient action instance."""

    success: bool = True
    action: PatientActionRecord


class PatientActionListResponse(BaseModel):
    """Paginated response for patient action listings."""

    success: bool = True
    items: List[PatientActionRecord]
    total: int
    page: int
    page_size: int
    has_more: bool


class PatientActionHistoryResponse(BaseModel):
    """Response containing state transition history for an action."""

    success: bool = True
    action_id: str
    history: List[PatientActionHistoryRecord]
