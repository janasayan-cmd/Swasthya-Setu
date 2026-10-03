"""Phase 33 — Payer Webhook Schemas.

CRITICAL INVARIANTS:
- CRYPTOGRAPHIC HMAC SIGNATURE VERIFICATION MANDATORY.
- IDEMPOTENT INGESTION — DUPLICATE WEBHOOK EVENTS MUST BE DEDUPLICATED.
- REPLAY ATTACK MITIGATION VIA EVENT ID AND NONCE TRACKING.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field


class PayerWebhookEventStatus(str, Enum):
    """Outcomes of webhook processing."""
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    DUPLICATE = "DUPLICATE"
    IGNORED = "IGNORED"


class PayerWebhookPayload(BaseModel):
    """Generic structured payload format for inbound payer webhooks."""
    model_config = ConfigDict(extra="ignore")

    event_id: str = Field(..., description="Unique event ID emitted by payer gateway")
    event_type: str = Field(..., description="Event type name (e.g. claim.adjudicated, preauth.approved)")
    provider: Optional[str] = Field("MOCK", description="Provider identifier")
    timestamp: Optional[str] = Field(None, description="Event generation timestamp")
    data: Dict[str, Any] = Field(default_factory=dict, description="Event payload payload data")


class PayerWebhookResult(BaseModel):
    """Response returned upon webhook receipt and dispatch."""
    model_config = ConfigDict(from_attributes=True)

    event_id: str
    status: PayerWebhookEventStatus
    message: str
    claim_id: Optional[str] = None
    authorization_id: Optional[str] = None
    processed_at: datetime = Field(default_factory=datetime.utcnow)


class PayerWebhookEventRecord(BaseModel):
    """Audit and deduplication record for inbound payer webhook events."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    event_id: str
    provider_name: str
    event_type: str
    status: PayerWebhookEventStatus
    payload_hash: str
    claim_id: Optional[str] = None
    authorization_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
