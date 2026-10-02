"""Pydantic schemas for Notification Provider Monitoring & Admin Diagnostics (Phase 29).

Enforces:
- Provider credentials NEVER appear in responses or telemetry.
- Comprehensive connectivity diagnostics for SREs and admins.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.notification import NotificationChannel


class ProviderStatusEnum(str, Enum):
    """Normalized provider operational status."""

    AVAILABLE = "AVAILABLE"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"
    DISABLED = "DISABLED"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    UNKNOWN = "UNKNOWN"


class NotificationProviderStatus(BaseModel):
    """Operational status and health metrics for an active notification provider."""

    model_config = ConfigDict(from_attributes=True)

    provider_name: str = Field(..., description="Provider adapter identifier")
    channel: NotificationChannel = Field(..., description="Primary delivery channel")
    status: ProviderStatusEnum = Field(..., description="Current operational status")
    connectivity_ok: bool = Field(..., description="Active connectivity verification status")
    total_requests: int = Field(default=0, ge=0, description="Total delivery attempts")
    success_count: int = Field(default=0, ge=0, description="Successful delivery count")
    failure_count: int = Field(default=0, ge=0, description="Failed delivery count")
    timeout_count: int = Field(default=0, ge=0, description="Provider timeout events")
    rate_limit_count: int = Field(default=0, ge=0, description="Provider HTTP 429 throttle events")
    last_success_at: Optional[datetime] = Field(None, description="Timestamp of most recent successful dispatch")
    last_failure_at: Optional[datetime] = Field(None, description="Timestamp of most recent failure")
    last_error: Optional[str] = Field(None, description="Sanitized description of last error")


class ProviderTestRequest(BaseModel):
    """Payload to test external provider connectivity."""

    model_config = ConfigDict(extra="forbid")

    channel: NotificationChannel = Field(..., description="Channel to test")
    test_target: str = Field(..., min_length=3, max_length=128, description="Target address (masked phone/email)")


class ProviderTestResponse(BaseModel):
    """Diagnostic response for external provider connectivity test."""

    model_config = ConfigDict(from_attributes=True)

    provider_name: str = Field(..., description="Tested provider identifier")
    channel: NotificationChannel = Field(..., description="Delivery channel tested")
    success: bool = Field(..., description="Whether test ping succeeded")
    latency_ms: float = Field(..., ge=0.0, description="Roundtrip latency in milliseconds")
    message: str = Field(..., description="Diagnostic summary message")
    details: Dict[str, Any] = Field(default_factory=dict, description="Sanitized diagnostic metadata")
