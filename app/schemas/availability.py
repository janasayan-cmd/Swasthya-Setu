"""Pydantic schemas for Phase 31 — Slot Availability Retrieval & Management.

CRITICAL CLINICAL SAFETY PRINCIPLES:
- AVAILABLE SLOT ≠ CLINICAL RECOMMENDATION
- NO VERIFIED AVAILABILITY → DO NOT SHOW SLOT AS AVAILABLE
- FACILITY DISCOVERY ≠ APPOINTMENT AVAILABILITY
- CLINICIAN PROFILE ≠ CLINICIAN AVAILABILITY
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.appointment import AppointmentType


class SlotStatus(str, Enum):
    """Authoritative availability slot status."""

    AVAILABLE = "AVAILABLE"
    RESERVED = "RESERVED"
    BOOKED = "BOOKED"
    BLOCKED = "BLOCKED"


class AvailabilitySlotRecord(BaseModel):
    """Authoritative schedulable slot item."""

    slot_id: str = Field(..., description="Unique slot identifier")
    facility_id: str = Field(..., description="Healthcare facility ID")
    clinician_id: Optional[str] = Field(None, description="Clinician ID if slot is doctor-specific")
    appointment_type: AppointmentType = Field(AppointmentType.CONSULTATION, description="Schedulable service type")
    start_time: datetime = Field(..., description="Slot start time with timezone")
    end_time: datetime = Field(..., description="Slot end time with timezone")
    status: SlotStatus = Field(SlotStatus.AVAILABLE, description="Current slot status")
    capacity: int = Field(1, ge=1, description="Maximum simultaneous bookings allowed")
    booked_count: int = Field(0, ge=0, description="Current confirmed bookings count")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Operational slot metadata")

    model_config = ConfigDict(extra="ignore")


class AvailabilityQuery(BaseModel):
    """Query parameters for slot availability retrieval."""

    facility_id: Optional[str] = Field(None, description="Target facility ID")
    clinician_id: Optional[str] = Field(None, description="Target clinician ID")
    appointment_type: Optional[AppointmentType] = Field(None, description="Appointment type filter")
    date: Optional[str] = Field(None, description="Target date (YYYY-MM-DD)")
    start_date: Optional[str] = Field(None, description="Start date of window (YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, description="End date of window (YYYY-MM-DD)")
    duration: Optional[int] = Field(None, ge=5, le=480, description="Duration filter in minutes")
    timezone: Optional[str] = Field("UTC", description="Requested timezone for output")

    model_config = ConfigDict(extra="forbid")


class AvailabilityResponseData(BaseModel):
    """Payload envelope for slot availability list."""

    slots: List[AvailabilitySlotRecord] = Field(default_factory=list)
    total: int = 0


class AvailabilityResponse(BaseModel):
    """Standard unified response envelope for slot availability queries."""

    success: bool = True
    data: AvailabilityResponseData
