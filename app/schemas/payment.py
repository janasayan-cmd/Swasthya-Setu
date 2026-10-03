"""Payment schemas for Phase 32 — Billing, Payments & Financial Transaction Management.

CRITICAL PAYMENT INVARIANTS:
- PAYMENT ≠ CLINICAL VERIFICATION
- PAYMENT STATUS ≠ APPOINTMENT STATUS
- PAYMENT SUCCESS ≠ CLINICAL SERVICE COMPLETION
- PAYMENT FAILURE ≠ CLINICAL FAILURE
- UNKNOWN PAYMENT ≠ FAILED PAYMENT
- UNKNOWN PAYMENT ≠ SUCCESSFUL PAYMENT
- CLIENT PAYMENT STATUS ≠ AUTHORITATIVE PAYMENT STATUS
- All amounts must be in integer minor units (paise/cents).
- NO sensitive card details / CVVs / bank credentials are ever accepted or stored!
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PaymentStatus(str, Enum):
    """Database-aligned payment transaction states."""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    REFUNDED = "REFUNDED"
    UNKNOWN = "UNKNOWN"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"


class PaymentMethodType(str, Enum):
    """Standard payment instrument categories."""
    CARD = "CARD"
    UPI = "UPI"
    NET_BANKING = "NET_BANKING"
    WALLET = "WALLET"
    CASH = "CASH"
    BANK_TRANSFER = "BANK_TRANSFER"
    OTHER = "OTHER"


class PaymentCreateRequest(BaseModel):
    """Payload to initiate a payment transaction."""
    model_config = ConfigDict(extra="forbid")

    invoice_id: str = Field(..., min_length=1, max_length=128, description="Target invoice ID")
    amount_in_minor_units: int = Field(..., gt=0, description="Payment amount in integer minor units (e.g. paise)")
    currency: str = Field(default="INR", min_length=3, max_length=3, description="ISO 4217 currency code")
    payment_method: PaymentMethodType = Field(default=PaymentMethodType.UPI)
    idempotency_key: Optional[str] = Field(None, max_length=255, description="Client-provided idempotency key")
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        return v.strip().upper()


class PaymentVerificationRequest(BaseModel):
    """Payload to verify an externally initiated payment with provider references."""
    model_config = ConfigDict(extra="forbid")

    provider_transaction_id: str = Field(..., min_length=1, max_length=255)
    provider_order_id: Optional[str] = Field(None, max_length=255)
    provider_signature: Optional[str] = Field(None, max_length=1000)


class PaymentRecord(BaseModel):
    """Authoritative internal payment transaction record."""
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(default_factory=lambda: f"pay_{uuid.uuid4().hex[:12]}")
    payment_number: str = Field(..., description="Unique human-readable transaction identifier")
    invoice_id: str
    patient_id: str
    organization_id: Optional[str] = None
    facility_id: Optional[str] = None
    amount_in_minor_units: int = Field(..., gt=0)
    amount_refunded_in_minor_units: int = Field(default=0, ge=0)
    currency: str = Field(default="INR")
    status: PaymentStatus = Field(default=PaymentStatus.PENDING)
    payment_method: PaymentMethodType = Field(default=PaymentMethodType.UPI)
    provider_name: str = Field(default="MOCK")
    provider_transaction_id: Optional[str] = None
    provider_order_id: Optional[str] = None
    provider_status: Optional[str] = None
    idempotency_key: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None


class PaymentResponse(BaseModel):
    """Public API response for a payment transaction."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    payment_number: str
    invoice_id: str
    patient_id: str
    organization_id: Optional[str] = None
    facility_id: Optional[str] = None
    amount_in_minor_units: int
    amount_refunded_in_minor_units: int
    currency: str
    status: PaymentStatus
    payment_method: PaymentMethodType
    provider_name: str
    provider_transaction_id: Optional[str] = None
    provider_order_id: Optional[str] = None
    provider_status: Optional[str] = None
    idempotency_key: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None


class PaymentListResponse(BaseModel):
    """Paginated payments list response."""
    items: List[PaymentResponse]
    total: int
    limit: int
    offset: int
