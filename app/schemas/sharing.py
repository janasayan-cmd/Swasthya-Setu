"""Pydantic Schemas for Clinical Data Sharing, External Access & Controlled Data Exchange (Phase 44).

CRITICAL ARCHITECTURAL BOUNDARIES:
- DATA SHARING != DATA CREATION
- DATA SHARING != CLINICAL DECISION
- DATA SHARING != DIAGNOSIS / TREATMENT / PRESCRIPTION / MEDICATION CHANGE / TRIAGE
- READ != DOWNLOAD != SHARE != EXPORT != MODIFY
- AI != SHARING AUTHORITY
- QUEUED AUTHORIZATION != CURRENT AUTHORIZATION
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class SharingType(str, Enum):
    """Categorization of sharing workflows and directionality."""

    PATIENT_TO_CLINICIAN = "PATIENT_TO_CLINICIAN"
    PATIENT_TO_CARE_TEAM = "PATIENT_TO_CARE_TEAM"
    CLINICIAN_TO_PATIENT = "CLINICIAN_TO_PATIENT"
    CLINICIAN_TO_CLINICIAN = "CLINICIAN_TO_CLINICIAN"
    CLINICIAN_TO_CARE_TEAM = "CLINICIAN_TO_CARE_TEAM"
    ORGANIZATION_TO_ORGANIZATION = "ORGANIZATION_TO_ORGANIZATION"
    FACILITY_TO_FACILITY = "FACILITY_TO_FACILITY"
    PATIENT_TO_EXTERNAL_SYSTEM = "PATIENT_TO_EXTERNAL_SYSTEM"
    HEALTHSETU_TO_EXTERNAL_SYSTEM = "HEALTHSETU_TO_EXTERNAL_SYSTEM"
    EXTERNAL_SYSTEM_TO_HEALTHSETU = "EXTERNAL_SYSTEM_TO_HEALTHSETU"
    TRANSFER_RELATED_SHARING = "TRANSFER_RELATED_SHARING"
    REFERRAL_RELATED_SHARING = "REFERRAL_RELATED_SHARING"
    DISCHARGE_RELATED_SHARING = "DISCHARGE_RELATED_SHARING"
    INTEROPERABILITY_EXCHANGE = "INTEROPERABILITY_EXCHANGE"
    AUTHORIZED_EXPORT = "AUTHORIZED_EXPORT"


class SharingStatus(str, Enum):
    """Lifecycle states of a sharing request."""

    DRAFT = "DRAFT"
    REQUESTED = "REQUESTED"
    PENDING_AUTHORIZATION = "PENDING_AUTHORIZATION"
    APPROVED = "APPROVED"
    PROCESSING = "PROCESSING"
    SHARED = "SHARED"
    DELIVERED = "DELIVERED"
    DENIED = "DENIED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"
    FAILED = "FAILED"
    REJECTED = "REJECTED"
    PARTIALLY_SHARED = "PARTIALLY_SHARED"
    PARTIALLY_FAILED = "PARTIALLY_FAILED"
    SUPERSEDED = "SUPERSEDED"


class SharingAction(str, Enum):
    """Explicit requested action scope."""

    READ = "READ"
    VIEW = "VIEW"
    DOWNLOAD = "DOWNLOAD"
    EXPORT = "EXPORT"
    SHARE = "SHARE"
    TRANSMIT = "TRANSMIT"
    IMPORT = "IMPORT"
    RECEIVE = "RECEIVE"
    FORWARD = "FORWARD"


class DestinationType(str, Enum):
    """Validated destination targets."""

    INTERNAL_CLINICIAN = "INTERNAL_CLINICIAN"
    INTERNAL_CARE_TEAM = "INTERNAL_CARE_TEAM"
    INTERNAL_ORGANIZATION = "INTERNAL_ORGANIZATION"
    INTERNAL_FACILITY = "INTERNAL_FACILITY"
    REGISTERED_EXTERNAL_ORGANIZATION = "REGISTERED_EXTERNAL_ORGANIZATION"
    REGISTERED_INTEROPERABILITY_ENDPOINT = "REGISTERED_INTEROPERABILITY_ENDPOINT"
    AUTHORIZED_EXTERNAL_SYSTEM = "AUTHORIZED_EXTERNAL_SYSTEM"


class DeliveryMethod(str, Enum):
    """Controlled transport mechanism for data transmission."""

    DIRECT_API = "DIRECT_API"
    FHIR_REST = "FHIR_REST"
    SECURE_DOWNLOAD_LINK = "SECURE_DOWNLOAD_LINK"
    ENCRYPTED_MESSAGE = "ENCRYPTED_MESSAGE"
    IN_APP = "IN_APP"


class SharingRequestCreate(BaseModel):
    """Request payload to initiate a controlled clinical data sharing request."""

    model_config = ConfigDict(extra="ignore")

    patient_id: str = Field(..., description="Target patient whose data is to be shared")
    sharing_type: SharingType = Field(..., description="Directionality / category of sharing")
    recipient_id: str = Field(..., description="Target recipient identifier (clinician, org, facility, system)")
    recipient_type: DestinationType = Field(..., description="Target recipient category")
    destination_url: Optional[str] = Field(
        None,
        description="External destination endpoint URL (must pass strict SSRF and allowlist validation)",
    )
    resource_scopes: List[str] = Field(
        ...,
        min_length=1,
        description="Explicit resource categories to share (e.g. ['MEDICATIONS', 'ALLERGIES'])",
    )
    action: SharingAction = Field(default=SharingAction.SHARE, description="Requested action scope")
    purpose: str = Field(default="CARE_DELIVERY", description="Explicit clinical or business purpose")
    delivery_method: DeliveryMethod = Field(
        default=DeliveryMethod.DIRECT_API,
        description="Transport delivery method",
    )
    requested_format: str = Field(
        default="JSON",
        description="Payload format: 'JSON', 'FHIR_R4', 'SUMMARY_PDF'",
    )
    consent_id: Optional[str] = Field(
        None,
        description="Optional pre-existing Phase 43 consent record reference",
    )
    expiration_hours: Optional[int] = Field(
        None,
        ge=1,
        le=720,
        description="Optional request expiration override in hours (defaults to system setting)",
    )
    reason: Optional[str] = Field(None, max_length=500, description="Justification or clinical note")
    idempotency_key: Optional[str] = Field(
        None,
        description="Idempotency key for mutation operations to prevent duplicate sharing requests",
    )


class SharingApproveAction(BaseModel):
    """Payload for approving a pending sharing request."""

    model_config = ConfigDict(extra="ignore")

    reason: Optional[str] = Field(None, max_length=500, description="Approval notes")
    consent_id: Optional[str] = Field(None, description="Explicit Phase 43 consent grant reference")


class SharingDenyAction(BaseModel):
    """Payload for denying a sharing request."""

    model_config = ConfigDict(extra="ignore")

    reason: str = Field(..., min_length=3, max_length=500, description="Denial reason code or explanation")


class SharingCancelAction(BaseModel):
    """Payload for cancelling a sharing request."""

    model_config = ConfigDict(extra="ignore")

    reason: str = Field(..., min_length=3, max_length=500, description="Cancellation reason")


class SharingExecuteAction(BaseModel):
    """Payload for executing an approved sharing request."""

    model_config = ConfigDict(extra="ignore")

    force_sync: bool = Field(
        default=False,
        description="Force synchronous execution if allowed (otherwise dispatches async job)",
    )


class SharingRequestResponse(BaseModel):
    """Representation of a controlled clinical data sharing request."""

    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: str
    patient_id: str
    requester_id: str
    requester_role: str
    sharing_type: SharingType
    recipient_id: str
    recipient_type: DestinationType
    destination_url: Optional[str] = None
    resource_scopes: List[str]
    action: SharingAction
    purpose: str
    delivery_method: DeliveryMethod
    requested_format: str
    status: SharingStatus
    consent_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    expires_at: datetime
    approved_at: Optional[datetime] = None
    executed_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    denial_reason: Optional[str] = None
    delivery_status: Optional[str] = None
    provider_reference: Optional[str] = None
    retry_count: int = 0
    provenance_id: Optional[str] = None


class SharingRequestListResponse(BaseModel):
    """List response envelope for sharing requests."""

    model_config = ConfigDict(extra="ignore")

    items: List[SharingRequestResponse]
    total: int
    page: int
    size: int


class SharedDataSummaryResponse(BaseModel):
    """Summary of data shared for a patient."""

    model_config = ConfigDict(extra="ignore")

    patient_id: str
    active_shares_count: int
    last_shared_at: Optional[datetime] = None
    authorized_recipients: List[str]
    authorized_resource_scopes: List[str]
    shared_requests: List[SharingRequestResponse]


class SharingEvaluationRequest(BaseModel):
    """Internal evaluation request for sharing eligibility."""

    model_config = ConfigDict(extra="ignore")

    actor_id: str
    actor_role: str
    patient_id: str
    recipient_id: str
    recipient_type: DestinationType
    destination_url: Optional[str] = None
    resource_scopes: List[str]
    action: SharingAction
    purpose: str


class SharingEvaluationResponse(BaseModel):
    """Result of internal sharing policy evaluation."""

    model_config = ConfigDict(extra="ignore")

    allowed: bool
    decision: str  # ALLOW, DENY, REQUIRES_AUTHORIZATION, etc.
    reason_code: str
    reason_detail: str
    filtered_resource_scopes: List[str] = Field(default_factory=list)
    consent_id: Optional[str] = None
