"""Refund schemas for Phase 32 — Billing, Payments & Financial Transaction Management.

CRITICAL REFUND INVARIANTS:
- REFUND ≠ CLINICAL REVERSAL
- A refund does NOT cancel an appointment or reverse a clinical diagnosis/treatment!
- Refund amount must NEVER exceed refundable amount.
- Duplicate refunds are strictly prohibited.
- Refunds against failed, pending, or unknown payments are rejected.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class RefundStatus(str, Enum):
    """Database-aligned refund transaction states."""
    REQUESTED = "REQUESTED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    REJECTED = "REJECTED"


class RefundCreateRequest(BaseModel):
    """Payload to initiate a refund against a successful payment."""
    model_config = ConfigDict(extra="forbid")

    payment_id: str = Field(..., min_length=1, max_length=128, description="Target payment transaction ID")
    amount_in_minor_units: int = Field(..., gt=0, description="Refund amount in integer minor units")
    reason: str = Field(..., min_length=3, max_length=500, description="Audit reason for refund")
    idempotency_key: Optional[str] = Field(None, max_length=255, description="Idempotency key for safe retry")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RefundRecord(BaseModel):
    """Authoritative internal refund record."""
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(default_factory=lambda: f"ref_{uuid.uuid4().hex[:12]}")
    refund_number: str = Field(..., description="Unique human-readable refund reference")
    payment_id: str
    invoice_id: str
    patient_id: str
    organization_id: Optional[str] = None
    facility_id: Optional[str] = None
    amount_in_minor_units: int = Field(..., gt=0)
    currency: str = Field(default="INR")
    status: RefundStatus = Field(default=RefundStatus.REQUESTED)
    reason: str
    provider_name: str = Field(default="MOCK")
    provider_refund_id: Optional[str] = None
    provider_status: Optional[str] = None
    idempotency_key: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None


class RefundResponse(BaseModel):
    """Public API response for a refund."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    refund_number: str
    payment_id: str
    invoice_id: str
    patient_id: str
    amount_in_minor_units: int
    currency: str
    status: RefundStatus
    reason: str
    provider_name: str
    provider_refund_id: Optional[str] = None
    provider_status: Optional[str] = None
    idempotency_key: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None


class RefundListResponse(BaseModel):
    """Paginated refunds list response."""
    items: List[RefundResponse]
    total: int
    limit: int
    offset: int
