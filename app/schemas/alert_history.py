"""Pydantic schemas for Alert Audit History (Phase 35)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.alert import AlertStatus


class AlertHistoryEntry(BaseModel):
    """Immutable transition entry in the lifecycle history of an alert."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(description="History record identifier")
    alert_id: str = Field(description="Target alert ID")
    from_status: AlertStatus = Field(description="Previous alert status")
    to_status: AlertStatus = Field(description="New alert status")
    actor_id: Optional[str] = Field(default=None, description="User or system actor initiating transition")
    action: str = Field(description="Action name (e.g. CREATED, ACKNOWLEDGED, RESOLVED, ESCALATED)")
    note: Optional[str] = Field(default=None, description="Action or transition notes")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadata associated with transition")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Transition timestamp")
