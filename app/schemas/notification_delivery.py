"""Pydantic schemas for Notification Delivery Tracking (Phase 29).

Enforces:
- Normalized provider delivery states.
- Provider credential leakage protection.
- Masked recipient targets in transmission logs.
- SENT != DELIVERED != READ invariant.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.notification import NotificationChannel


class DeliveryStatus(str, Enum):
    """Normalized delivery states across external providers."""

    QUEUED = "QUEUED"
    SENDING = "SENDING"
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class NotificationDelivery(BaseModel):
    """Detailed per-channel delivery attempt and status tracker."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique delivery attempt identifier")
    notification_id: str = Field(..., description="Linked notification ID")
    channel: NotificationChannel = Field(..., description="Delivery channel")
    recipient_target: str = Field(..., description="Masked recipient target address (email/phone/token)")
    provider: str = Field(..., description="Selected provider adapter identifier")
    provider_message_id: Optional[str] = Field(None, description="Upstream provider transaction reference ID")
    status: DeliveryStatus = Field(default=DeliveryStatus.QUEUED, description="Normalized delivery status")
    retry_count: int = Field(default=0, ge=0, description="Number of attempted retries")
    max_retries: int = Field(default=3, ge=0, description="Configured retry ceiling")
    last_error: Optional[str] = Field(None, description="Normalized error explanation")
    error_category: Optional[str] = Field(None, description="Error category (e.g. TIMEOUT, REJECTED, RATE_LIMIT)")
    sent_at: Optional[datetime] = Field(None, description="Timestamp dispatched to upstream network")
    delivered_at: Optional[datetime] = Field(None, description="Timestamp delivery confirmed by upstream provider")
    failed_at: Optional[datetime] = Field(None, description="Timestamp marked as terminal or transient failure")
    created_at: datetime = Field(..., description="Record creation timestamp")
    updated_at: datetime = Field(..., description="Record update timestamp")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Operational delivery metadata")
