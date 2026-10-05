"""Access Decision & Centralized Access Evaluation Schemas.

CRITICAL INVARIANTS:
- DENY-BY-DEFAULT.
- MISSING CONSENT DATA ≠ CONSENT GRANTED.
- UNKNOWN CONSENT STATE ≠ ACTIVE CONSENT.
- AI INTERPRETATION ≠ CONSENT AUTHORITY.
- READ ≠ UPDATE ≠ SHARE ≠ EXPORT ≠ COMMUNICATE.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class AccessDecisionCode(str, Enum):
    """Canonical decision codes for access control outcomes."""

    # Allowed codes
    ALLOWED_RELATIONSHIP = "ALLOWED_RELATIONSHIP"
    ALLOWED_CONSENT = "ALLOWED_CONSENT"
    ALLOWED_WORKFLOW = "ALLOWED_WORKFLOW"
    ALLOWED_POLICY = "ALLOWED_POLICY"
    ALLOWED_BREAK_GLASS = "ALLOWED_BREAK_GLASS"

    # Denied codes
    DENIED_NO_RELATIONSHIP = "DENIED_NO_RELATIONSHIP"
    DENIED_NO_CONSENT = "DENIED_NO_CONSENT"
    DENIED_SCOPE = "DENIED_SCOPE"
    DENIED_EXPIRED = "DENIED_EXPIRED"
    DENIED_WITHDRAWN = "DENIED_WITHDRAWN"
    DENIED_TIME_WINDOW = "DENIED_TIME_WINDOW"
    DENIED_PURPOSE = "DENIED_PURPOSE"
    DENIED_RESOURCE = "DENIED_RESOURCE"
    DENIED_ACTION = "DENIED_ACTION"
    DENIED_ORGANIZATION = "DENIED_ORGANIZATION"
    DENIED_FACILITY = "DENIED_FACILITY"
    DENIED_UNKNOWN_STATE = "DENIED_UNKNOWN_STATE"
    DENIED_AI_NOT_AUTHORIZED = "DENIED_AI_NOT_AUTHORIZED"


class AccessEvaluationRequest(BaseModel):
    """Internal contract for evaluating consent-aware resource access."""
    model_config = ConfigDict(extra="forbid")

    actor_id: str = Field(..., description="Identity of caller requesting resource access")
    patient_id: str = Field(..., description="Target patient subject reference")
    resource_type: str = Field(..., description="Category of resource (e.g. DOCUMENT, PRESCRIPTION, CLINICAL_RECORD)")
    resource_id: Optional[str] = Field(None, description="Target resource unique identifier")
    action: str = Field(default="READ", description="Target action attempted (READ, SHARE, EXPORT, UPDATE, etc.)")
    purpose: str = Field(default="CARE", description="Declared purpose for access (CARE, REFERRAL, etc.)")
    actor_role: Optional[str] = Field(None, description="Role of the actor if known (e.g. DOCTOR, PATIENT, ADMIN)")
    organization_id: Optional[str] = Field(None, description="Organization context of the actor")
    facility_id: Optional[str] = Field(None, description="Facility context of the actor")
    break_glass_token: Optional[str] = Field(None, description="Active emergency break-glass token if invoked")


class AccessEvaluationResponse(BaseModel):
    """Safe, minimal access evaluation decision."""
    model_config = ConfigDict(frozen=True)

    allowed: bool = Field(..., description="Whether the requested access is authorized")
    decision: str = Field(..., description="'ALLOWED' or 'DENIED'")
    reason_code: str = Field(..., description="Canonical reason code (e.g. ALLOWED_CONSENT, DENIED_SCOPE)")
    consent_id: Optional[str] = Field(None, description="ID of consent governing decision if applicable")
    consent_version: Optional[int] = Field(None, description="Version of consent record evaluated")
