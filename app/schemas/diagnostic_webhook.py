"""Pydantic schemas for Diagnostic Webhooks (Phase 34).

SAFETY & SECURITY INVARIANTS:
- WEBHOOK PAYLOAD != CLINICAL TRUTH UNTIL VALIDATED
- SIGNATURE VERIFICATION MANDATORY BEFORE ANY PROCESSING
- REPLAY & DUPLICATE PROTECTION REQUIRED VIA EVENT ID & NONCE
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field


class WebhookEventType(str, Enum):
    """Supported diagnostic provider webhook events."""

    ORDER_ACCEPTED = "ORDER_ACCEPTED"
    ORDER_REJECTED = "ORDER_REJECTED"
    ORDER_STATUS_CHANGED = "ORDER_STATUS_CHANGED"
    SPECIMEN_COLLECTED = "SPECIMEN_COLLECTED"
    SPECIMEN_RECEIVED = "SPECIMEN_RECEIVED"
    SPECIMEN_REJECTED = "SPECIMEN_REJECTED"
    RESULT_AVAILABLE = "RESULT_AVAILABLE"
    RESULT_AMENDED = "RESULT_AMENDED"
    REPORT_PUBLISHED = "REPORT_PUBLISHED"


class DiagnosticWebhookPayload(BaseModel):
    """External laboratory webhook body."""

    model_config = ConfigDict(extra="ignore")

    event_id: str = Field(description="Unique provider-assigned event ID for replay prevention")
    event_type: WebhookEventType
    provider_id: str
    timestamp: datetime
    order_id: Optional[str] = None
    provider_order_id: Optional[str] = None
    provider_result_id: Optional[str] = None
    status: Optional[str] = None
    data: Dict[str, Any] = Field(default_factory=dict)


class WebhookIngestResponse(BaseModel):
    """Acknowledgement response to webhook caller."""

    status: str = Field(default="RECEIVED")
    event_id: str
    message: str
    processed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
