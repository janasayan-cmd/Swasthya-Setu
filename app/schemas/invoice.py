"""Invoice schemas for Phase 32 — Billing, Payments & Financial Transaction Management.

CRITICAL INVARIANTS:
- INVOICE ≠ MEDICAL RECORD
- BILLING ≠ CLINICAL DECISION
- Totals must be deterministic integer minor units. Never use LLMs or floating point for financial calculations!
- Strict state machine:
  DRAFT -> ISSUED -> PARTIALLY_PAID -> PAID
  ISSUED -> CANCELLED / VOID / OVERDUE
  PAID -> PARTIALLY_REFUNDED -> REFUNDED
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.billing_item import BillingItemCreate, BillingItemRecord


class InvoiceStatus(str, Enum):
    """Database-aligned invoice lifecycle states."""
    DRAFT = "DRAFT"
    ISSUED = "ISSUED"
    PARTIALLY_PAID = "PARTIALLY_PAID"
    PAID = "PAID"
    OVERDUE = "OVERDUE"
    CANCELLED = "CANCELLED"
    VOID = "VOID"
    REFUNDED = "REFUNDED"
    PARTIALLY_REFUNDED = "PARTIALLY_REFUNDED"
    FAILED = "FAILED"


class InvoiceCreateRequest(BaseModel):
    """Payload to create a new draft invoice."""
    model_config = ConfigDict(extra="forbid")

    patient_id: str = Field(..., min_length=1, max_length=128, description="Target patient ID")
    organization_id: Optional[str] = Field(None, max_length=128, description="Issuing organization ID")
    facility_id: Optional[str] = Field(None, max_length=128, description="Issuing facility ID")
    currency: str = Field(default="INR", min_length=3, max_length=3, description="ISO 4217 currency code")
    due_at: Optional[datetime] = Field(None, description="Payment due date")
    notes: Optional[str] = Field(None, max_length=1000, description="Administrative invoice notes")
    items: List[BillingItemCreate] = Field(..., min_length=1, description="Billable line items")
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        return v.strip().upper()


class InvoiceUpdateRequest(BaseModel):
    """Payload to update a draft invoice before issuance."""
    model_config = ConfigDict(extra="forbid")

    notes: Optional[str] = Field(None, max_length=1000)
    due_at: Optional[datetime] = None
    items: Optional[List[BillingItemCreate]] = None
    metadata: Optional[Dict[str, Any]] = None


class InvoiceCancelRequest(BaseModel):
    """Payload to cancel an issued invoice."""
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(..., min_length=3, max_length=500, description="Mandatory reason for audit")


class InvoiceRecord(BaseModel):
    """Authoritative internal invoice record."""
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(default_factory=lambda: f"inv_{uuid.uuid4().hex[:12]}")
    invoice_number: str = Field(..., description="Unique human-readable invoice reference")
    patient_id: str
    organization_id: Optional[str] = None
    facility_id: Optional[str] = None
    status: InvoiceStatus = Field(default=InvoiceStatus.DRAFT)
    currency: str = Field(default="INR")
    subtotal_in_minor_units: int = Field(default=0, ge=0)
    tax_in_minor_units: int = Field(default=0, ge=0)
    discount_in_minor_units: int = Field(default=0, ge=0)
    total_in_minor_units: int = Field(default=0, ge=0)
    amount_paid_in_minor_units: int = Field(default=0, ge=0)
    amount_refunded_in_minor_units: int = Field(default=0, ge=0)
    outstanding_amount_in_minor_units: int = Field(default=0, ge=0)
    items: List[BillingItemRecord] = Field(default_factory=list)
    notes: Optional[str] = None
    issued_at: Optional[datetime] = None
    due_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    cancellation_reason: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class InvoiceResponse(BaseModel):
    """Public API response for an invoice."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    invoice_number: str
    patient_id: str
    organization_id: Optional[str] = None
    facility_id: Optional[str] = None
    status: InvoiceStatus
    currency: str
    subtotal_in_minor_units: int
    tax_in_minor_units: int
    discount_in_minor_units: int
    total_in_minor_units: int
    amount_paid_in_minor_units: int
    amount_refunded_in_minor_units: int
    outstanding_amount_in_minor_units: int
    items: List[BillingItemRecord]
    notes: Optional[str] = None
    issued_at: Optional[datetime] = None
    due_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    cancellation_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class InvoiceListResponse(BaseModel):
    """Paginated invoices list response."""
    items: List[InvoiceResponse]
    total: int
    limit: int
    offset: int
