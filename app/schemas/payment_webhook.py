"""Payment webhook schemas for Phase 32 — Billing, Payments & Financial Transaction Management.

CRITICAL WEBHOOK SAFETY INVARIANTS:
- WEBHOOK ≠ TRUSTED UNTIL VERIFIED
- Signature verification is mandatory before processing.
- Replay attacks and duplicate events must be idempotently handled.
- Never log card details, CVVs, passwords, or authentication secrets.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class WebhookProcessingStatus(str, Enum):
    """Lifecycle of an inbound webhook event."""
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    DUPLICATE = "DUPLICATE"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class WebhookEventRecord(BaseModel):
    """Audit and deduplication record for an inbound provider webhook event."""
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(default_factory=lambda: f"ev_{uuid.uuid4().hex[:12]}")
    provider: str = Field(..., description="Provider identifier e.g. MOCK, RAZORPAY, STRIPE")
    event_id: str = Field(..., description="Provider's unique event identifier for idempotency")
    event_type: str = Field(..., description="Event action e.g. payment.captured, payment.failed, refund.processed")
    signature: Optional[str] = None
    processed: bool = Field(default=False)
    processing_status: WebhookProcessingStatus = Field(default=WebhookProcessingStatus.PENDING)
    transaction_id: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    processed_at: Optional[datetime] = None


class WebhookProcessResult(BaseModel):
    """Response returned upon processing a webhook request."""
    status: WebhookProcessingStatus
    event_id: str
    provider: str
    transaction_id: Optional[str] = None
    message: str
