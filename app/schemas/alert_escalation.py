"""Pydantic schemas for Alert Escalation Engine (Phase 35).

CORE SAFETY PRINCIPLES:
- ESCALATION != DIAGNOSIS
- ESCALATION != EMERGENCY DISPATCH
- Never escalate an alert that has already been acknowledged, resolved, or dismissed.
- Escalation chains follow authorized organizational tiers, not arbitrary broadcast.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field


class EscalationLevel(int, Enum):
    """Tiered escalation hierarchy."""

    LEVEL_0_CLINICIAN = 0       # Responsible clinician
    LEVEL_1_CARE_TEAM = 1       # Designated clinical care team
    LEVEL_2_FACILITY = 2        # Authorized facility escalation contact
    LEVEL_3_ORGANIZATION = 3    # Authorized organization escalation contact


class EscalationStatus(str, Enum):
    """Lifecycle of an escalation attempt."""

    SCHEDULED = "SCHEDULED"
    TRIGGERED = "TRIGGERED"
    COMPLETED = "COMPLETED"
    STOPPED = "STOPPED"
    FAILED = "FAILED"


class EscalationRecord(BaseModel):
    """Audit and tracking record for an alert escalation event."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(description="Unique escalation event ID (e.g. ESC-20261003-0001)")
    alert_id: str = Field(description="Target alert ID")
    from_level: int = Field(description="Escalation level prior to event")
    to_level: int = Field(description="New escalation level reached")
    escalated_to_recipient_id: str = Field(description="Recipient ID of newly designated tier")
    escalated_to_role: str = Field(description="Role or group title of designated tier")
    escalated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Timestamp escalation was executed")
    status: EscalationStatus = Field(default=EscalationStatus.COMPLETED, description="Status of escalation attempt")
    stop_reason: Optional[str] = Field(default=None, description="Reason if escalation was halted (e.g. ACKNOWLEDGED, RESOLVED)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadata associated with escalation")
