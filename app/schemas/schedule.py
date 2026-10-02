"""Pydantic schemas for clinician and facility schedules (Phase 31).

Authoritative schedule templates consumed by availability and booking services.
"""

from __future__ import annotations

from datetime import date, time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class WorkingHoursRule(BaseModel):
    """Weekly recurring working period for a clinician or facility."""

    day_of_week: int = Field(..., ge=0, le=6, description="0=Monday, 6=Sunday")
    start_time: str = Field(..., pattern=r"^\d{2}:\d{2}$", description="Start time in HH:MM (24-hour)")
    end_time: str = Field(..., pattern=r"^\d{2}:\d{2}$", description="End time in HH:MM (24-hour)")
    slot_duration_minutes: int = Field(30, ge=5, le=240, description="Slot duration in minutes")

    model_config = ConfigDict(extra="ignore")


class ScheduleRecord(BaseModel):
    """Authoritative schedule configuration record."""

    id: str = Field(..., description="Unique schedule identifier")
    facility_id: str = Field(..., description="Healthcare facility ID")
    clinician_id: Optional[str] = Field(None, description="Clinician ID if clinician-specific")
    timezone: str = Field("UTC", description="Operating timezone identifier")
    working_hours: List[WorkingHoursRule] = Field(default_factory=list)
    blocked_dates: List[str] = Field(default_factory=list, description="Blocked YYYY-MM-DD dates or holidays")
    is_active: bool = Field(True, description="Whether this schedule rule is active")
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="ignore")


class ScheduleCreateRequest(BaseModel):
    """Payload to define or update a schedule."""

    facility_id: str = Field(...)
    clinician_id: Optional[str] = Field(None)
    timezone: str = Field("UTC")
    working_hours: List[WorkingHoursRule] = Field(default_factory=list)
    blocked_dates: List[str] = Field(default_factory=list)
    is_active: bool = Field(True)

    model_config = ConfigDict(extra="forbid")
