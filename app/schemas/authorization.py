"""Combined Authorization Schemas.

Covers both:
1. Phase 3: Access Control, Consent, and Policy Decision Models.
2. Phase 33: Pre-Authorization (Prior Auth) Workflow Schemas.

CRITICAL INVARIANTS:
- PRE-AUTHORIZATION ≠ CLINICAL AUTHORITY.
- APPROVED AUTHORIZATION DOES NOT MEAN TREATMENT WAS PERFORMED OR CLAIM WILL BE PAID.
- SYSTEM DOES NOT AUTONOMOUSLY DETERMINE MEDICAL NECESSITY.
- AMOUNTS REPRESENTED AS INTEGER MINOR UNITS.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Phase 3: Authorization Decision & Context
# ---------------------------------------------------------------------------

class AuthorizationOutcome(str, Enum):
    """Possible outcomes from an authorization evaluation."""

    ALLOW = "ALLOW"
    DENY = "DENY"


class DenialReason(str, Enum):
    """Internal denial reasons — NOT exposed verbatim to clients.

    These are used internally for audit logging and service-layer branching.
    Client-facing responses always use generic messages to avoid leaking
    policy details or resource existence.
    """

    NO_PERMISSION = "NO_PERMISSION"
    NOT_RESOURCE_OWNER = "NOT_RESOURCE_OWNER"
    NO_RELATIONSHIP = "NO_RELATIONSHIP"
    CONSENT_REQUIRED = "CONSENT_REQUIRED"
    CONSENT_NOT_FOUND = "CONSENT_NOT_FOUND"
    CONSENT_REVOKED = "CONSENT_REVOKED"
    CONSENT_EXPIRED = "CONSENT_EXPIRED"
    CONSENT_PURPOSE_MISMATCH = "CONSENT_PURPOSE_MISMATCH"
    CONSENT_SCOPE_MISMATCH = "CONSENT_SCOPE_MISMATCH"
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    ACCOUNT_NOT_ALLOWED = "ACCOUNT_NOT_ALLOWED"
    UNKNOWN_POLICY = "UNKNOWN_POLICY"


class AuthorizationDecision(BaseModel):
    """Result of an authorization evaluation.

    The 'reason' field is INTERNAL and must not be forwarded to API clients.
    Use it for audit logging and service-layer branching only.
    """

    model_config = ConfigDict(frozen=True)

    outcome: AuthorizationOutcome
    reason: DenialReason | None = Field(
        default=None,
        description="Internal denial reason code — do not expose to clients",
    )
    permission_checked: str | None = Field(
        default=None,
        description="The permission identifier that was evaluated",
    )

    @property
    def allowed(self) -> bool:
        """True if the outcome is ALLOW."""
        return self.outcome == AuthorizationOutcome.ALLOW

    @classmethod
    def allow(cls, permission_checked: str | None = None) -> "AuthorizationDecision":
        """Convenience constructor for an ALLOW decision."""
        return cls(outcome=AuthorizationOutcome.ALLOW, permission_checked=permission_checked)

    @classmethod
    def deny(
        cls,
        reason: DenialReason,
        permission_checked: str | None = None,
    ) -> "AuthorizationDecision":
        """Convenience constructor for a DENY decision."""
        return cls(
            outcome=AuthorizationOutcome.DENY,
            reason=reason,
            permission_checked=permission_checked,
        )


class AuthorizationContext(BaseModel):
    """Full authorization context assembled for a single request evaluation.

    Carries only the minimum fields needed to evaluate the authorization
    decision. Never carries clinical record content or raw token values.
    """

    model_config = ConfigDict(frozen=True)

    # Authenticated caller
    user_id: str
    role: str

    # Optional resource context (populated by routes that know the target)
    resource_type: str | None = None
    resource_id: str | None = None
    resource_owner_id: str | None = None     # patient who owns the resource

    # Relationship context (populated when a doctor–patient check is needed)
    relationship_context: dict[str, Any] | None = None

    # Consent evaluation context
    consent_purpose: str | None = None
    consent_scope: str | None = None


# ---------------------------------------------------------------------------
# Phase 3: Consent Schemas
# ---------------------------------------------------------------------------

class ConsentStatus(str, Enum):
    """Consent lifecycle states.

    DATABASE TEAM DEPENDENCY:
    If the database team defines a different enum name or values, update
    this mapping to stay in sync. The backend policy layer must treat
    anything other than ACTIVE as non-consenting.
    """

    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"
    PENDING = "PENDING"
    DENIED = "DENIED"


class ConsentCreateRequest(BaseModel):
    """Request body for creating a new consent grant.

    The server validates and enforces the actual scope/purpose — clients
    cannot elevate their own permissions by submitting arbitrary values.
    """

    model_config = ConfigDict(extra="forbid")

    grantee_id: str = Field(
        ...,
        description="User ID of the consent recipient (e.g., a doctor's user ID)",
        examples=["usr-doctor-001"],
    )
    purpose: str = Field(
        ...,
        description="Consent purpose from the supported set (e.g., care_delivery)",
        examples=["care_delivery"],
    )
    scope: str = Field(
        ...,
        description="Resource scope covered by this consent (e.g., clinical_records)",
        examples=["clinical_records"],
    )
    expires_at: datetime | None = Field(
        default=None,
        description="Optional explicit expiry timestamp. Must be in the future.",
    )
    notes: str | None = Field(
        default=None,
        max_length=1000,
        description="Optional free-text notes from the patient. Not a clinical note.",
    )


class ConsentRevokeRequest(BaseModel):
    """Request body for revoking an existing consent."""

    model_config = ConfigDict(extra="forbid")

    reason: str | None = Field(
        default=None,
        max_length=500,
        description="Optional plain-text reason for revocation",
    )


class ConsentResponse(BaseModel):
    """Public consent representation — never exposes internal IDs or PHI."""

    id: str = Field(description="Consent unique identifier")
    patient_id: str = Field(description="Patient (subject) user ID")
    grantee_id: str = Field(description="Recipient (grantee) user ID")
    purpose: str = Field(description="Consent purpose")
    scope: str = Field(description="Consent resource scope")
    status: ConsentStatus = Field(description="Current consent lifecycle status")
    granted_at: datetime = Field(description="When consent was created")
    effective_from: datetime = Field(description="When consent becomes effective")
    expires_at: datetime | None = Field(default=None, description="Consent expiry timestamp")
    revoked_at: datetime | None = Field(default=None, description="Revocation timestamp if applicable")
    version: int = Field(default=1, description="Consent version")


class ConsentListResponse(BaseModel):
    """Paginated consent list."""

    items: list[ConsentResponse]
    total: int


class ConsentCheckResult(BaseModel):
    """Result of a consent check operation.

    INTERNAL — never serialize this directly into an HTTP response.
    Use AuthorizationDecision for API responses.
    """

    model_config = ConfigDict(frozen=True)

    allowed: bool
    consent_id: str | None = None
    reason: DenialReason | None = None

    @classmethod
    def permitted(cls, consent_id: str) -> "ConsentCheckResult":
        return cls(allowed=True, consent_id=consent_id)

    @classmethod
    def denied(cls, reason: DenialReason) -> "ConsentCheckResult":
        return cls(allowed=False, reason=reason)


# ---------------------------------------------------------------------------
# Phase 33: Pre-Authorization (Prior Auth) Workflow Schemas
# ---------------------------------------------------------------------------

class PreAuthorizationStatus(str, Enum):
    """Lifecycle states for prior authorization."""
    DRAFT = "DRAFT"
    REQUESTED = "REQUESTED"
    SUBMITTED = "SUBMITTED"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    PARTIALLY_APPROVED = "PARTIALLY_APPROVED"
    DENIED = "DENIED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    UNKNOWN = "UNKNOWN"
    FAILED = "FAILED"


class PreAuthorizationCreate(BaseModel):
    """Payload to initiate a pre-authorization request."""
    model_config = ConfigDict(extra="forbid")

    patient_id: str = Field(..., description="Target patient reference")
    coverage_id: str = Field(..., description="Insurance policy coverage ID")
    appointment_id: Optional[str] = Field(None, description="Linked Phase 31 appointment ID if any")
    facility_id: Optional[str] = Field(None, description="Performing facility ID")
    clinician_id: Optional[str] = Field(None, description="Requesting clinician ID")
    service_code: str = Field(..., description="Medical procedure or service code")
    service_description: str = Field(..., max_length=255, description="Clinical service description")
    estimated_amount_in_minor_units: int = Field(..., gt=0, description="Estimated total cost in integer minor units")
    currency: str = Field("INR", max_length=3, description="ISO 4217 Currency Code")
    requested_date: Optional[str] = Field(None, description="Proposed date of service (YYYY-MM-DD)")
    clinical_documentation_reference_ids: List[str] = Field(default_factory=list, description="Phase 5 document references supporting authorization")
    diagnosis_codes: List[str] = Field(default_factory=list, description="Clinician-approved ICD/clinical diagnosis codes")
    procedure_codes: List[str] = Field(default_factory=list, description="CPT/Procedure codes")
    notes: Optional[str] = Field(None, description="Administrative or clinical notes")


class PreAuthorizationSubmitRequest(BaseModel):
    """Request payload to submit authorization to payer."""
    model_config = ConfigDict(extra="forbid")

    notes: Optional[str] = Field(None, description="Submission notes")
    idempotency_key: Optional[str] = Field(None, description="Optional submission idempotency key")


class PreAuthorizationResponse(BaseModel):
    """Pre-authorization status representation."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    authorization_number: str
    patient_id: str
    coverage_id: str
    payer_id: str
    facility_id: Optional[str] = None
    clinician_id: Optional[str] = None
    appointment_id: Optional[str] = None
    status: PreAuthorizationStatus
    service_code: str
    service_description: str
    estimated_amount_in_minor_units: int
    approved_amount_in_minor_units: Optional[int] = None
    currency: str
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None
    payer_reference: Optional[str] = None
    denial_reason: Optional[str] = None
    denial_code: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class PreAuthorizationRecord(BaseModel):
    """Internal database model for pre-authorization."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    authorization_number: str
    patient_id: str
    coverage_id: str
    payer_id: str
    facility_id: Optional[str] = None
    clinician_id: Optional[str] = None
    appointment_id: Optional[str] = None
    status: PreAuthorizationStatus = PreAuthorizationStatus.DRAFT
    service_code: str
    service_description: str
    estimated_amount_in_minor_units: int
    approved_amount_in_minor_units: Optional[int] = None
    currency: str = "INR"
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None
    payer_reference: Optional[str] = None
    denial_reason: Optional[str] = None
    denial_code: Optional[str] = None
    clinical_doc_refs: List[str] = Field(default_factory=list)
    diagnosis_codes: List[str] = Field(default_factory=list)
    procedure_codes: List[str] = Field(default_factory=list)
    notes: Optional[str] = None
    idempotency_key: Optional[str] = None
    raw_response: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def to_response(self) -> PreAuthorizationResponse:
        return PreAuthorizationResponse(
            id=self.id,
            authorization_number=self.authorization_number,
            patient_id=self.patient_id,
            coverage_id=self.coverage_id,
            payer_id=self.payer_id,
            facility_id=self.facility_id,
            clinician_id=self.clinician_id,
            appointment_id=self.appointment_id,
            status=self.status,
            service_code=self.service_code,
            service_description=self.service_description,
            estimated_amount_in_minor_units=self.estimated_amount_in_minor_units,
            approved_amount_in_minor_units=self.approved_amount_in_minor_units,
            currency=self.currency,
            valid_from=self.valid_from,
            valid_to=self.valid_to,
            payer_reference=self.payer_reference,
            denial_reason=self.denial_reason,
            denial_code=self.denial_code,
            notes=self.notes,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )
