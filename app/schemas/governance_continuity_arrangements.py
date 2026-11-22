"""Phase 80: Alternative Governance Operating Arrangements Schemas.

Defines schemas and models for:
- Tracking authorized temporary operating arrangements during disruptions
- Preserving clinical authorization boundaries and preventing temporary drift
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.governance_continuity_capability import (
    CLINICAL_SAFETY_CONTINUITY_DISCLAIMER,
)


class ArrangementVerificationStatus(str, Enum):
    """Operational status of a temporary operating arrangement."""
    ACTIVE = "ACTIVE"
    REVIEW_DUE = "REVIEW_DUE"
    RECONCILIATION_PENDING = "RECONCILIATION_PENDING"
    DEACTIVATED = "DEACTIVATED"
    VERIFIED_CLOSED = "VERIFIED_CLOSED"


class AlternativeOperatingArrangementRecord(BaseModel):
    """Authoritative record for an authorized temporary alternative operating arrangement."""
    model_config = ConfigDict(extra="forbid")

    arrangement_id: str
    tenant_id: str
    activation_id: str
    affected_capability_id: str
    description: str
    authorized_procedure_reference: str
    responsible_owner_id: str
    activation_time: str
    expiry_or_review_time: str
    evidence_capture_requirements: str
    data_reconciliation_requirements: str
    security_restrictions: str
    deactivation_conditions: str
    verification_status: ArrangementVerificationStatus
    disclaimer: str = CLINICAL_SAFETY_CONTINUITY_DISCLAIMER
    created_at: str
    updated_at: str


class CreateAlternativeArrangementRequest(BaseModel):
    """Request to establish an authorized temporary alternative operating arrangement."""
    model_config = ConfigDict(extra="forbid")

    activation_id: str
    affected_capability_id: str
    description: str
    authorized_procedure_reference: str
    responsible_owner_id: str
    expiry_or_review_time: str
    evidence_capture_requirements: str = "Log all manual triage assessments on Form-SAF-701 with clinician signature."
    data_reconciliation_requirements: str = "Transcribe offline assessments into primary safety system within 24h of restoration."
    security_restrictions: str = "Physical storage in locked clinical governance office; no unencrypted transfers."
    deactivation_conditions: str = "Primary electronic safety reporting system verified online."


class UpdateAlternativeArrangementRequest(BaseModel):
    """Request to update temporary arrangement status or extension."""
    model_config = ConfigDict(extra="forbid")

    verification_status: Optional[ArrangementVerificationStatus] = None
    extended_expiry_time: Optional[str] = None
    review_notes: Optional[str] = None


class DeactivateAlternativeArrangementRequest(BaseModel):
    """Request to deactivate alternative arrangement upon restoration."""
    model_config = ConfigDict(extra="forbid")

    deactivation_reason: str
    reconciliation_reference: str
