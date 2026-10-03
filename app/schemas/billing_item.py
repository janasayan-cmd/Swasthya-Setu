"""Billing item and billable event schemas for Phase 32 — Billing, Payments & Financial Transaction Management.

CRITICAL FINANCIAL & CLINICAL SAFETY INVARIANTS:
- BILLING ≠ CLINICAL DECISION
- INVOICE ITEM ≠ MEDICAL RECORD
- APPOINTMENT ≠ BILLABLE CHARGE (an appointment is only billable if explicitly configured)
- All monetary amounts MUST be integer minor units (paise for INR, cents for USD). Never use floating point!
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BillingItemCategory(str, Enum):
    """Categorization for billable line items."""
    CONSULTATION = "CONSULTATION"
    DIAGNOSTIC = "DIAGNOSTIC"
    PROCEDURE = "PROCEDURE"
    ROOM = "ROOM"
    PHARMACY = "PHARMACY"
    SERVICE = "SERVICE"
    ADMINISTRATIVE = "ADMINISTRATIVE"
    OTHER = "OTHER"


class BillableEventRecord(BaseModel):
    """Authoritative representation of a billable operational event."""
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(default_factory=lambda: f"ble_{uuid.uuid4().hex[:12]}")
    source_type: str = Field(..., description="Originating workflow e.g. appointment, diagnostic_order, transfer")
    source_id: str = Field(..., description="ID in the originating domain e.g. appointment_id")
    patient_id: str = Field(..., description="Authorized patient ID")
    organization_id: Optional[str] = Field(None, description="Issuing organization ID")
    facility_id: Optional[str] = Field(None, description="Issuing facility ID")
    clinician_id: Optional[str] = Field(None, description="Associated clinician ID")
    description: str = Field(..., min_length=1, max_length=255)
    category: BillingItemCategory = Field(default=BillingItemCategory.SERVICE)
    amount_in_minor_units: int = Field(..., gt=0, description="Amount in integer minor units (e.g. paise)")
    currency: str = Field(default="INR", min_length=3, max_length=3, description="ISO 4217 currency code")
    is_billed: bool = Field(default=False, description="Whether this event has been attached to an invoice")
    invoice_id: Optional[str] = Field(None, description="Linked invoice ID if billed")
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BillingItemCreate(BaseModel):
    """Request payload to create an invoice line item."""
    model_config = ConfigDict(extra="forbid")

    description: str = Field(..., min_length=1, max_length=255)
    category: BillingItemCategory = Field(default=BillingItemCategory.SERVICE)
    unit_price_in_minor_units: int = Field(..., gt=0, description="Unit price in integer minor units")
    quantity: int = Field(default=1, gt=0, description="Quantity")
    tax_in_minor_units: int = Field(default=0, ge=0, description="Tax in integer minor units")
    discount_in_minor_units: int = Field(default=0, ge=0, description="Discount in integer minor units")
    currency: str = Field(default="INR", min_length=3, max_length=3)
    billable_event_id: Optional[str] = Field(None, description="Optional linked billable event ID")
    appointment_id: Optional[str] = Field(None, description="Optional linked appointment ID")
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("currency")
    @classmethod
    def validate_currency_uppercase(cls, v: str) -> str:
        return v.strip().upper()


class BillingItemRecord(BaseModel):
    """Authoritative representation of an invoice line item."""
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(default_factory=lambda: f"item_{uuid.uuid4().hex[:12]}")
    invoice_id: str = Field(..., description="Parent invoice ID")
    description: str = Field(..., min_length=1, max_length=255)
    category: BillingItemCategory = Field(default=BillingItemCategory.SERVICE)
    unit_price_in_minor_units: int = Field(..., gt=0)
    quantity: int = Field(default=1, gt=0)
    tax_in_minor_units: int = Field(default=0, ge=0)
    discount_in_minor_units: int = Field(default=0, ge=0)
    total_in_minor_units: int = Field(..., description="Calculated: (unit_price * quantity) + tax - discount")
    currency: str = Field(default="INR", min_length=3, max_length=3)
    billable_event_id: Optional[str] = None
    appointment_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
