"""Phase 43 Consent & Sharing Authorization Schemas.

CRITICAL INVARIANTS:
- CONSENT IS AN ACCESS-CONTROL INPUT, NOT CLINICAL AUTHORITY.
- CONSENT ≠ DIAGNOSIS, TRIAGE, TREATMENT, PRESCRIPTION, MEDICATION CHANGE, EMERGENCY DISPATCH.
- CONSENT GRANTED ≠ INFORMATION VERIFIED.
- CONSENT REQUESTED ≠ CONSENT GRANTED.
- CONSENT WITHDRAWN ≠ DATA AUTOMATICALLY ERASED.
- CONSENT ≠ UNLIMITED ACCESS.
- READ ≠ UPDATE ≠ SHARE ≠ EXPORT ≠ COMMUNICATE.
- AI ≠ CONSENT AUTHORITY.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.authorization import (
    ConsentCreateRequest,
    ConsentListResponse,
    ConsentResponse,
    ConsentRevokeRequest,
    ConsentStatus,
)


class ConsentResourceCategory(str, Enum):
    """Supported resource categories for scoped consent."""
    PATIENT_PROFILE = "PATIENT_PROFILE"
    CLINICAL_RECORD = "CLINICAL_RECORD"
    ENCOUNTERS = "ENCOUNTERS"
    MEDICATIONS = "MEDICATIONS"
    ALLERGIES = "ALLERGIES"
    VITALS = "VITALS"
    PRESCRIPTIONS = "PRESCRIPTIONS"
    DOCUMENTS = "DOCUMENTS"
    LAB_RESULTS = "LAB_RESULTS"
    DIAGNOSTIC_RESULTS = "DIAGNOSTIC_RESULTS"
    CARE_PLANS = "CARE_PLANS"
    DISCHARGE_INFORMATION = "DISCHARGE_INFORMATION"
    APPOINTMENTS = "APPOINTMENTS"
    COMMUNICATIONS = "COMMUNICATIONS"
    TASKS = "TASKS"
    CLINICAL_SUMMARIES = "CLINICAL_SUMMARIES"
    ALL_RECORDS = "ALL_RECORDS"


class ConsentActionScope(str, Enum):
    """Supported action scopes for access control."""
    READ = "READ"
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    SHARE = "SHARE"
    EXPORT = "EXPORT"
    DOWNLOAD = "DOWNLOAD"
    COMMUNICATE = "COMMUNICATE"


class ConsentPurposeScope(str, Enum):
    """Supported purpose definitions under policy."""
    CARE = "CARE"
    CARE_COORDINATION = "CARE_COORDINATION"
    FOLLOW_UP = "FOLLOW_UP"
    SECOND_OPINION = "SECOND_OPINION"
    REFERRAL = "REFERRAL"
    TRANSFER = "TRANSFER"
    DIAGNOSTIC_REVIEW = "DIAGNOSTIC_REVIEW"
    MEDICATION_REVIEW = "MEDICATION_REVIEW"
    PATIENT_REQUEST = "PATIENT_REQUEST"
    INTEROPERABILITY = "INTEROPERABILITY"
    ADMINISTRATIVE_SUPPORT = "ADMINISTRATIVE_SUPPORT"
    OTHER_APPROVED_PURPOSE = "OTHER_APPROVED_PURPOSE"
    # Legacy compatibility
    CARE_DELIVERY = "care_delivery"
    RESEARCH = "research"
    ADMINISTRATIVE = "administrative"
    EMERGENCY_ACCESS = "emergency_access"


class ConsentRecipientType(str, Enum):
    """Recipient classification for sharing authorization."""
    CLINICIAN = "CLINICIAN"
    CARE_TEAM = "CARE_TEAM"
    FACILITY = "FACILITY"
    ORGANIZATION = "ORGANIZATION"
    EXTERNAL_PROVIDER = "EXTERNAL_PROVIDER"
    INTEROPERABILITY_PARTNER = "INTEROPERABILITY_PARTNER"
    REPRESENTATIVE = "REPRESENTATIVE"


class ConsentRequestStatus(str, Enum):
    """Consent request lifecycle states."""
    PENDING = "PENDING"
    REQUESTED = "REQUESTED"
    APPROVED = "APPROVED"
    DENIED = "DENIED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


# ---------------------------------------------------------------------------
# Consent Request Schemas
# ---------------------------------------------------------------------------

class ConsentRequestCreate(BaseModel):
    """Request payload to initiate a consent request to a patient."""
    model_config = ConfigDict(extra="forbid")

    patient_id: str = Field(..., description="Target patient subject reference")
    grantee_id: str = Field(..., description="Recipient user or entity ID requesting access")
    recipient_type: ConsentRecipientType = Field(
        default=ConsentRecipientType.CLINICIAN,
        description="Type of recipient seeking consent",
    )
    purpose: str = Field(
        ...,
        description="Purpose from approved policy set (e.g. CARE, REFERRAL, SECOND_OPINION)",
    )
    resource_scopes: List[str] = Field(
        ...,
        min_length=1,
        description="List of resource categories requested (e.g. ['DOCUMENTS', 'PRESCRIPTIONS'])",
    )
    action_scopes: List[str] = Field(
        default_factory=lambda: ["READ"],
        description="List of action scopes requested (e.g. ['READ'])",
    )
    requested_duration_days: int = Field(
        default=90,
        ge=1,
        le=365,
        description="Requested validity period in days",
    )
    notes: Optional[str] = Field(None, max_length=1000, description="Context note from requester")


class ConsentRequestResponse(BaseModel):
    """Public representation of a consent request."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    patient_id: str
    requester_id: str
    requester_role: str
    grantee_id: str
    recipient_type: str
    purpose: str
    resource_scopes: List[str]
    action_scopes: List[str]
    requested_duration_days: int
    status: ConsentRequestStatus
    notes: Optional[str] = None
    created_at: datetime
    decided_at: Optional[datetime] = None
    decided_by: Optional[str] = None
    decision_reason: Optional[str] = None


class ConsentRequestListResponse(BaseModel):
    """Paginated or listed consent requests."""
    items: List[ConsentRequestResponse]
    total: int


# ---------------------------------------------------------------------------
# Action Schemas (Grant, Deny, Withdraw, Renew)
# ---------------------------------------------------------------------------

class ConsentGrantAction(BaseModel):
    """Explicit grant action from patient."""
    model_config = ConfigDict(extra="forbid")

    duration_days: Optional[int] = Field(None, ge=1, le=365)
    expires_at: Optional[datetime] = None
    notes: Optional[str] = Field(None, max_length=1000)
    evidence: Optional[dict[str, Any]] = Field(default_factory=dict)


class ConsentDenyAction(BaseModel):
    """Explicit denial of consent."""
    model_config = ConfigDict(extra="forbid")

    reason: Optional[str] = Field(None, max_length=500)
    notes: Optional[str] = Field(None, max_length=1000)


class ConsentWithdrawAction(BaseModel):
    """Patient withdrawal of previously granted consent."""
    model_config = ConfigDict(extra="forbid")

    reason: Optional[str] = Field(None, max_length=500)
    notes: Optional[str] = Field(None, max_length=1000)


class ConsentRenewAction(BaseModel):
    """Patient renewal of expired or expiring consent."""
    model_config = ConfigDict(extra="forbid")

    duration_days: Optional[int] = Field(default=90, ge=1, le=365)
    expires_at: Optional[datetime] = None
    reason: Optional[str] = Field(None, max_length=500)
    notes: Optional[str] = Field(None, max_length=1000)


# ---------------------------------------------------------------------------
# History Schemas
# ---------------------------------------------------------------------------

class ConsentHistoryItem(BaseModel):
    """Historical audit snapshot of a consent state transition."""
    model_config = ConfigDict(from_attributes=True)

    version: int
    status: str
    changed_at: datetime
    actor_id: str
    reason: Optional[str] = None
    purpose: str
    resource_scopes: List[str]
    action_scopes: List[str]


class ConsentHistoryResponse(BaseModel):
    """Complete audit provenance for a consent record."""
    consent_id: str
    patient_id: str
    current_version: int
    current_status: str
    history: List[ConsentHistoryItem]


# ---------------------------------------------------------------------------
# Break-Glass Emergency Model
# ---------------------------------------------------------------------------

class BreakGlassRequest(BaseModel):
    """Request payload for emergency break-glass data access under strict policy."""
    model_config = ConfigDict(extra="forbid")

    patient_id: str = Field(..., description="Target patient reference")
    resource_type: str = Field(..., description="Resource type needed (e.g. CLINICAL_RECORD, DOCUMENTS)")
    resource_id: Optional[str] = Field(None, description="Optional specific resource identifier")
    reason: str = Field(..., min_length=10, max_length=1000, description="Mandatory detailed clinical emergency justification")


class BreakGlassResponse(BaseModel):
    """Response returned upon granting exceptional break-glass access."""
    token: str
    actor_id: str
    patient_id: str
    resource_type: str
    expires_at: datetime
    enhanced_audit_id: str
    reason: str
