"""Communication Provider, Webhook, and Preferences Schemas (Phase 41).

CRITICAL NON-NEGOTIABLE SAFETY BOUNDARIES:
- PROVIDER ACCEPTANCE != READ BY PATIENT
- UNKNOWN STATUS != SUCCESS
- PROVIDER FAILURE != SUCCESS
- WEBHOOK PAYLOADS ARE UNTRUSTED INPUTS
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ProviderState(str, Enum):
    """Operational health state of a communication provider."""

    AVAILABLE = "AVAILABLE"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"
    DISABLED = "DISABLED"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    UNKNOWN = "UNKNOWN"


class ProviderSendResult(BaseModel):
    """Result returned by a communication provider after send attempt."""

    success: bool
    provider_name: str
    provider_message_id: Optional[str] = None
    provider_status: str
    error_message: Optional[str] = None
    latency_ms: float = 0.0


class WebhookPayload(BaseModel):
    """Normalized webhook callback from an external communication provider."""

    event_id: str = Field(description="Unique event ID from provider for replay protection")
    event_type: str = Field(description="Provider event type e.g. message.delivered, message.failed")
    provider: str = Field(description="Provider identifier e.g. mock, twilio, sendgrid")
    message_id: str = Field(description="HealthSetu internal message ID")
    provider_message_id: Optional[str] = None
    delivery_status: str = Field(description="Normalized status e.g. DELIVERED, FAILED, BOUNCED")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    reason: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class CommunicationPreference(BaseModel):
    """User-controlled communication and notification settings."""

    user_id: str
    in_app_enabled: bool = True
    email_enabled: bool = True
    sms_enabled: bool = False
    push_enabled: bool = True
    quiet_hours_start: Optional[str] = None  # e.g. "22:00"
    quiet_hours_end: Optional[str] = None    # e.g. "07:00"


class CommunicationMetricsResponse(BaseModel):
    """PHI-safe operational metrics summary for communication service."""

    total_conversations: int
    active_conversations: int
    closed_conversations: int
    total_messages: int
    sent_messages: int
    delivered_messages: int
    read_messages: int
    acknowledged_messages: int
    failed_messages: int
    provider_state: ProviderState
    active_provider: str
