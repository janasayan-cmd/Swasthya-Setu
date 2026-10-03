"""Phase 33 — Medical Claims Management Schemas.

CRITICAL INVARIANTS:
- CLAIM STATUS ≠ PATIENT TREATMENT STATUS.
- CLAIM APPROVAL ≠ CLINICAL APPROVAL.
- CLAIM DENIAL ≠ CLINICAL DENIAL.
- PAYER CLAIM PAYMENT ≠ PATIENT PAYMENT (Distinct concepts and records).
- ALL MONETARY BALANCES ARE INTEGER MINOR UNITS (paise/cents).
- UNKNOWN CLAIM STATUS ≠ FAILED CLAIM.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ClaimStatus(str, Enum):
    """Lifecycle states of an insurance claim."""
    DRAFT = "DRAFT"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    READY = "READY"
    SUBMITTED = "SUBMITTED"
    RECEIVED = "RECEIVED"
    PENDING = "PENDING"
    ADJUDICATED = "ADJUDICATED"
    APPROVED = "APPROVED"
    PARTIALLY_APPROVED = "PARTIALLY_APPROVED"
    DENIED = "DENIED"
    REJECTED = "REJECTED"
    PAID = "PAID"
    PARTIALLY_PAID = "PARTIALLY_PAID"
    CANCELLED = "CANCELLED"
    RESUBMITTED = "RESUBMITTED"
    UNKNOWN = "UNKNOWN"
    FAILED = "FAILED"


class ClaimType(str, Enum):
    """Claim classification according to medical standards."""
    INSTITUTIONAL = "INSTITUTIONAL"
    PROFESSIONAL = "PROFESSIONAL"
    PHARMACY = "PHARMACY"
    DENTAL = "DENTAL"


class ClaimItemCreate(BaseModel):
    """Billable service line item in a claim."""
    model_config = ConfigDict(extra="forbid")

    description: str = Field(..., max_length=255, description="Item or service description")
    service_code: Optional[str] = Field(None, max_length=64, description="Procedure or diagnostic test code")
    category: str = Field("SERVICE", max_length=64, description="Service category")
    unit_price_in_minor_units: int = Field(..., gt=0, description="Unit price in minor currency units (paise/cents)")
    quantity: int = Field(default=1, gt=0, description="Item quantity")
    tax_in_minor_units: int = Field(default=0, ge=0, description="Tax in minor units")
    discount_in_minor_units: int = Field(default=0, ge=0, description="Discount in minor units")
    currency: str = Field("INR", max_length=3, description="ISO 4217 Currency Code")
    appointment_id: Optional[str] = Field(None, description="Linked appointment ID from Phase 31")
    invoice_item_id: Optional[str] = Field(None, description="Linked Phase 32 invoice line item ID")


class ClaimItemResponse(BaseModel):
    """Claim line item response representation."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    claim_id: str
    description: str
    service_code: Optional[str] = None
    category: str
    unit_price_in_minor_units: int
    quantity: int
    total_in_minor_units: int
    approved_amount_in_minor_units: Optional[int] = None
    patient_responsibility_in_minor_units: Optional[int] = None
    denial_reason: Optional[str] = None


class ClaimItemRecord(BaseModel):
    """Internal model for claim line items."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    claim_id: str
    description: str
    service_code: Optional[str] = None
    category: str = "SERVICE"
    unit_price_in_minor_units: int
    quantity: int = 1
    tax_in_minor_units: int = 0
    discount_in_minor_units: int = 0
    total_in_minor_units: int
    approved_amount_in_minor_units: Optional[int] = None
    patient_responsibility_in_minor_units: Optional[int] = None
    denial_reason: Optional[str] = None
    currency: str = "INR"
    appointment_id: Optional[str] = None
    invoice_item_id: Optional[str] = None

    def to_response(self) -> ClaimItemResponse:
        return ClaimItemResponse(
            id=self.id,
            claim_id=self.claim_id,
            description=self.description,
            service_code=self.service_code,
            category=self.category,
            unit_price_in_minor_units=self.unit_price_in_minor_units,
            quantity=self.quantity,
            total_in_minor_units=self.total_in_minor_units,
            approved_amount_in_minor_units=self.approved_amount_in_minor_units,
            patient_responsibility_in_minor_units=self.patient_responsibility_in_minor_units,
            denial_reason=self.denial_reason,
        )


class ClaimCreateRequest(BaseModel):
    """Payload to construct a new medical claim."""
    model_config = ConfigDict(extra="forbid")

    patient_id: str = Field(..., description="Target patient reference")
    coverage_id: str = Field(..., description="Active insurance coverage reference")
    organization_id: Optional[str] = Field(None, description="Billing provider organization")
    facility_id: Optional[str] = Field(None, description="Rendering facility ID")
    clinician_id: Optional[str] = Field(None, description="Rendering clinician ID")
    appointment_id: Optional[str] = Field(None, description="Phase 31 appointment ID")
    invoice_id: Optional[str] = Field(None, description="Phase 32 invoice reference")
    claim_type: ClaimType = Field(default=ClaimType.INSTITUTIONAL)
    currency: str = Field("INR", max_length=3)
    authorization_id: Optional[str] = Field(None, description="Pre-authorization reference ID")
    diagnosis_codes: List[str] = Field(default_factory=list, description="Validated clinician diagnosis codes")
    items: List[ClaimItemCreate] = Field(..., min_length=1, description="Billable line items")
    notes: Optional[str] = Field(None)


class ClaimSubmitRequest(BaseModel):
    """Request payload to submit claim to external payer."""
    model_config = ConfigDict(extra="forbid")

    idempotency_key: Optional[str] = Field(None, max_length=255, description="Client idempotency key")
    provider_name: Optional[str] = Field(None, description="Target payer provider adapter override")


class ClaimResponse(BaseModel):
    """Claim state representation for client applications."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    claim_number: str
    patient_id: str
    coverage_id: str
    payer_id: str
    organization_id: Optional[str] = None
    facility_id: Optional[str] = None
    clinician_id: Optional[str] = None
    invoice_id: Optional[str] = None
    authorization_id: Optional[str] = None
    claim_type: ClaimType
    status: ClaimStatus
    total_amount_in_minor_units: int
    approved_amount_in_minor_units: Optional[int] = None
    payer_paid_amount_in_minor_units: Optional[int] = None
    patient_responsibility_in_minor_units: Optional[int] = None
    currency: str
    items: List[ClaimItemResponse] = Field(default_factory=list)
    provider_claim_reference: Optional[str] = None
    idempotency_key: Optional[str] = None
    submission_timestamp: Optional[datetime] = None
    adjudication_timestamp: Optional[datetime] = None
    denial_reason: Optional[str] = None
    denial_code: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ClaimRecord(BaseModel):
    """Internal database and state representation of an insurance claim."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    claim_number: str
    patient_id: str
    coverage_id: str
    payer_id: str
    organization_id: Optional[str] = None
    facility_id: Optional[str] = None
    clinician_id: Optional[str] = None
    invoice_id: Optional[str] = None
    authorization_id: Optional[str] = None
    claim_type: ClaimType = ClaimType.INSTITUTIONAL
    status: ClaimStatus = ClaimStatus.DRAFT
    total_amount_in_minor_units: int
    approved_amount_in_minor_units: Optional[int] = None
    payer_paid_amount_in_minor_units: Optional[int] = None
    patient_responsibility_in_minor_units: Optional[int] = None
    currency: str = "INR"
    items: List[ClaimItemRecord] = Field(default_factory=list)
    diagnosis_codes: List[str] = Field(default_factory=list)
    provider_claim_reference: Optional[str] = None
    idempotency_key: Optional[str] = None
    submission_timestamp: Optional[datetime] = None
    adjudication_timestamp: Optional[datetime] = None
    denial_reason: Optional[str] = None
    denial_code: Optional[str] = None
    notes: Optional[str] = None
    raw_response: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def to_response(self) -> ClaimResponse:
        return ClaimResponse(
            id=self.id,
            claim_number=self.claim_number,
            patient_id=self.patient_id,
            coverage_id=self.coverage_id,
            payer_id=self.payer_id,
            organization_id=self.organization_id,
            facility_id=self.facility_id,
            clinician_id=self.clinician_id,
            invoice_id=self.invoice_id,
            authorization_id=self.authorization_id,
            claim_type=self.claim_type,
            status=self.status,
            total_amount_in_minor_units=self.total_amount_in_minor_units,
            approved_amount_in_minor_units=self.approved_amount_in_minor_units,
            payer_paid_amount_in_minor_units=self.payer_paid_amount_in_minor_units,
            patient_responsibility_in_minor_units=self.patient_responsibility_in_minor_units,
            currency=self.currency,
            items=[item.to_response() for item in self.items],
            provider_claim_reference=self.provider_claim_reference,
            idempotency_key=self.idempotency_key,
            submission_timestamp=self.submission_timestamp,
            adjudication_timestamp=self.adjudication_timestamp,
            denial_reason=self.denial_reason,
            denial_code=self.denial_code,
            notes=self.notes,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )
