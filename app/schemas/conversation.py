"""Clinical Conversation and Participant Schemas (Phase 41).

CRITICAL NON-NEGOTIABLE SAFETY BOUNDARIES:
- CONVERSATION != CLINICAL ENCOUNTER
- CONVERSATION != MEDICAL RECORD BY DEFAULT
- MESSAGING IS A COMMUNICATION MECHANISM, NOT CLINICAL AUTHORITY
- CONVERSATION CLOSURE DOES NOT MEAN CLINICAL RESOLUTION
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ConversationCategory(str, Enum):
    """Controlled categories for clinical and operational conversations."""

    PATIENT_CLINICIAN = "PATIENT_CLINICIAN"
    PATIENT_CARE_TEAM = "PATIENT_CARE_TEAM"
    CLINICIAN_CARE_TEAM = "CLINICIAN_CARE_TEAM"
    CLINICAL_FOLLOW_UP = "CLINICAL_FOLLOW_UP"
    APPOINTMENT_COMMUNICATION = "APPOINTMENT_COMMUNICATION"
    DISCHARGE_COMMUNICATION = "DISCHARGE_COMMUNICATION"
    TRANSFER_COMMUNICATION = "TRANSFER_COMMUNICATION"
    ADMINISTRATIVE_COMMUNICATION = "ADMINISTRATIVE_COMMUNICATION"
    SUPPORT_COMMUNICATION = "SUPPORT_COMMUNICATION"
    ORGANIZATION_COMMUNICATION = "ORGANIZATION_COMMUNICATION"
    SYSTEM_GENERATED = "SYSTEM_GENERATED"


class ConversationStatus(str, Enum):
    """Lifecycle states for a conversation."""

    CREATED = "CREATED"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    CLOSED = "CLOSED"
    ARCHIVED = "ARCHIVED"
    CANCELLED = "CANCELLED"
    LOCKED = "LOCKED"


class ParticipantRole(str, Enum):
    """Authorized role of a participant in a conversation."""

    PATIENT = "PATIENT"
    CLINICIAN = "CLINICIAN"
    CARE_TEAM_MEMBER = "CARE_TEAM_MEMBER"
    ORGANIZATION_ADMIN = "ORGANIZATION_ADMIN"
    SUPPORT_AGENT = "SUPPORT_AGENT"
    SYSTEM = "SYSTEM"


class ParticipantRecord(BaseModel):
    """Membership record of an actor in a conversation."""

    model_config = ConfigDict(populate_by_name=True)

    participant_id: str = Field(description="Unique participant identifier")
    conversation_id: str = Field(description="Associated conversation identifier")
    user_id: str = Field(description="User identifier of the actor")
    role: ParticipantRole = Field(description="Participant's role in this conversation")
    organization_id: Optional[str] = Field(default=None, description="Organization tenancy boundary")
    facility_id: Optional[str] = Field(default=None, description="Facility operational boundary")
    display_name: Optional[str] = Field(default=None, description="Safe display name for communication UI")
    joined_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    left_at: Optional[datetime] = Field(default=None)
    is_active: bool = Field(default=True)
    notification_preferences: Optional[Dict[str, Any]] = Field(default=None)


class ParticipantAddRequest(BaseModel):
    """Payload to add a new participant to an existing conversation."""

    user_id: str = Field(..., min_length=1, max_length=100)
    role: ParticipantRole
    display_name: Optional[str] = Field(default=None, max_length=200)
    organization_id: Optional[str] = Field(default=None, max_length=100)
    facility_id: Optional[str] = Field(default=None, max_length=100)


class ConversationCreateRequest(BaseModel):
    """Payload to initiate a new conversation."""

    patient_id: str = Field(..., min_length=1, max_length=100, description="Target patient subject identifier")
    category: ConversationCategory = Field(default=ConversationCategory.PATIENT_CLINICIAN)
    subject: str = Field(..., min_length=1, max_length=250, description="Brief subject of conversation")
    organization_id: Optional[str] = Field(default=None, max_length=100)
    facility_id: Optional[str] = Field(default=None, max_length=100)
    encounter_id: Optional[str] = Field(default=None, max_length=100)
    initial_participant_ids: Optional[List[str]] = Field(default=None, description="Optional extra user IDs to add as participants")
    initial_message_content: Optional[str] = Field(default=None, max_length=10000)
    metadata: Optional[Dict[str, Any]] = Field(default=None)


class ConversationCloseRequest(BaseModel):
    """Payload to close a conversation."""

    reason: Optional[str] = Field(default="Completed", max_length=500)


class ConversationReopenRequest(BaseModel):
    """Payload to reopen a closed conversation."""

    reason: Optional[str] = Field(default="Follow-up needed", max_length=500)


class ConversationRecord(BaseModel):
    """Full domain model for a conversation."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(description="Unique conversation identifier")
    patient_id: str = Field(description="Associated patient identifier")
    category: ConversationCategory
    subject: str
    status: ConversationStatus = Field(default=ConversationStatus.ACTIVE)
    organization_id: Optional[str] = None
    facility_id: Optional[str] = None
    encounter_id: Optional[str] = None
    created_by: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    closed_at: Optional[datetime] = None
    closed_by: Optional[str] = None
    close_reason: Optional[str] = None
    participants: List[ParticipantRecord] = Field(default_factory=list)
    last_message_at: Optional[datetime] = None
    last_message_preview: Optional[str] = None
    total_messages: int = Field(default=0)
    metadata: Optional[Dict[str, Any]] = None


class ConversationHistoryRecord(BaseModel):
    """Audit transition record for a conversation lifecycle event."""

    id: str
    conversation_id: str
    actor_id: str
    action: str
    previous_status: Optional[ConversationStatus] = None
    new_status: Optional[ConversationStatus] = None
    reason: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ConversationListResponse(BaseModel):
    """Paginated list of conversations."""

    conversations: List[ConversationRecord]
    total: int
    limit: int
    offset: int
    has_more: bool
