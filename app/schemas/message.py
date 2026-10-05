"""Clinical Message, Attachment, and Delivery Schemas (Phase 41).

CRITICAL NON-NEGOTIABLE SAFETY BOUNDARIES:
- MESSAGING IS A COMMUNICATION MECHANISM, NOT CLINICAL AUTHORITY
- MESSAGE != CLINICAL ORDER
- MESSAGE != DIAGNOSIS
- MESSAGE != TRIAGE
- MESSAGE != PRESCRIPTION
- MESSAGE != MEDICATION CHANGE
- MESSAGE != EMERGENCY DISPATCH
- SENT != DELIVERED
- DELIVERED != READ
- READ != ACKNOWLEDGED
- ACKNOWLEDGED != CLINICAL ACTION COMPLETED
- AI DRAFT != APPROVED CLINICAL COMMUNICATION
- AI CANNOT AUTONOMOUSLY SEND CLINICAL MESSAGES TO PATIENTS
- TRANSLATION != CLINICAL INTERPRETATION
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class MessageType(str, Enum):
    """Supported message classifications."""

    TEXT = "TEXT"
    SYSTEM = "SYSTEM"
    DOCUMENT_REFERENCE = "DOCUMENT_REFERENCE"
    APPOINTMENT_REFERENCE = "APPOINTMENT_REFERENCE"
    CARE_PLAN_REFERENCE = "CARE_PLAN_REFERENCE"
    DISCHARGE_REFERENCE = "DISCHARGE_REFERENCE"
    TASK_REFERENCE = "TASK_REFERENCE"
    ALERT_REFERENCE = "ALERT_REFERENCE"
    WORKFLOW_REFERENCE = "WORKFLOW_REFERENCE"


class MessageStatus(str, Enum):
    """Authoritative delivery and interaction lifecycle states."""

    CREATED = "CREATED"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    READ = "READ"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    FAILED = "FAILED"
    RETRY_PENDING = "RETRY_PENDING"
    EXPIRED = "EXPIRED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class AttachmentReference(BaseModel):
    """Reference to an existing secure document in storage."""

    model_config = ConfigDict(populate_by_name=True)

    attachment_id: str = Field(description="Unique attachment reference identifier")
    document_id: str = Field(description="Authorized document ID in Phase 5 storage")
    file_name: str = Field(description="Original sanitized file name")
    content_type: str = Field(description="MIME type of the attachment")
    size_bytes: int = Field(description="File size in bytes")
    storage_path: Optional[str] = Field(default=None, description="Internal storage identifier (not public URL)")


class MessageSendRequest(BaseModel):
    """Payload to submit a new message into a conversation."""

    content: str = Field(..., description="Untrusted text content of message")
    message_type: MessageType = Field(default=MessageType.TEXT)
    reply_to_message_id: Optional[str] = Field(default=None, description="Optional parent message ID in same conversation")
    reference_resource_type: Optional[str] = Field(default=None, max_length=100)
    reference_resource_id: Optional[str] = Field(default=None, max_length=100)
    attachments: Optional[List[AttachmentReference]] = Field(default=None)
    idempotency_key: Optional[str] = Field(default=None, max_length=128)
    metadata: Optional[Dict[str, Any]] = Field(default=None)


class MessageAcknowledgeRequest(BaseModel):
    """Payload to record explicit acknowledgment of a message."""

    note: Optional[str] = Field(default=None, max_length=500)
    acknowledgment_basis: Optional[str] = Field(default="Clinician reviewed", max_length=200)


class MessageRecord(BaseModel):
    """Full domain model for a secure clinical message."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(description="Unique message identifier")
    conversation_id: str = Field(description="Parent conversation identifier")
    sender_id: str = Field(description="User ID of sender")
    sender_role: str = Field(description="Role of sender at transmission time")
    sender_organization_id: Optional[str] = None
    sender_facility_id: Optional[str] = None
    message_type: MessageType = Field(default=MessageType.TEXT)
    content: str
    reply_to_message_id: Optional[str] = None
    reference_resource_type: Optional[str] = None
    reference_resource_id: Optional[str] = None
    attachments: List[AttachmentReference] = Field(default_factory=list)
    status: MessageStatus = Field(default=MessageStatus.CREATED)
    idempotency_key: Optional[str] = None
    provider: Optional[str] = None
    provider_message_id: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    read_by: List[str] = Field(default_factory=list, description="User IDs who have marked this message as read")
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    acknowledgment_note: Optional[str] = None
    retry_count: int = Field(default=0)
    failure_reason: Optional[str] = None
    is_ai_draft: bool = Field(default=False)
    ai_approved: bool = Field(default=False)
    translations: Dict[str, str] = Field(default_factory=dict, description="target_lang -> translated_text")
    metadata: Optional[Dict[str, Any]] = None


class MessageDeliveryHistoryRecord(BaseModel):
    """Audit record of a delivery state transition."""

    id: str
    message_id: str
    provider: Optional[str] = None
    previous_status: Optional[MessageStatus] = None
    new_status: MessageStatus
    reason: Optional[str] = None
    event_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MessageListResponse(BaseModel):
    """Bounded, cursor-supported message listing."""

    messages: List[MessageRecord]
    total: int
    limit: int
    cursor: Optional[str] = None
    next_cursor: Optional[str] = None
    has_more: bool


class AIDraftRequest(BaseModel):
    """Payload to request an AI-assisted draft response for clinician review."""

    prompt_context: str = Field(..., min_length=1, max_length=2000)
    target_tone: Optional[str] = Field(default="Empathetic and professional", max_length=100)


class AIDraftResponse(BaseModel):
    """AI-suggested draft with mandatory human clinician approval boundaries."""

    draft_id: str
    conversation_id: str
    suggested_content: str
    requires_human_approval: bool = True
    disclaimer: str = (
        "AI DRAFT ONLY: Not an approved clinical communication. "
        "Must be reviewed, edited, and explicitly approved by an authorized clinician before transmission."
    )
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MessageTranslationRequest(BaseModel):
    """Request translation of a message to an authorized target language."""

    target_language: str = Field(..., min_length=2, max_length=10, description="ISO-639-1 language code (e.g. 'hi', 'bn', 'es')")


class MessageTranslationResponse(BaseModel):
    """Derived translated representation preserving original authoritative content."""

    message_id: str
    target_language: str
    translated_content: str
    provider: str
    disclaimer: str = (
        "TRANSLATION IS A DERIVED REPRESENTATION: The original message remains the sole clinical and legal authority. "
        "Translation does not constitute clinical interpretation."
    )
    translated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ConversationSummaryResponse(BaseModel):
    """Non-authoritative communication summary for operational overview."""

    conversation_id: str
    summary: str
    message_count: int
    disclaimer: str = (
        "COMMUNICATION SUMMARY ONLY: Does not constitute a clinical encounter summary or medical record entry."
    )
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
