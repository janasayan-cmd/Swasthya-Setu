"""Pydantic schemas for Phase 31 — Scheduling, Appointment & Clinical Access Management.

CRITICAL CLINICAL SAFETY PRINCIPLES:
- SCHEDULING ≠ CLINICAL DECISION
- SCHEDULING ≠ DIAGNOSIS
- SCHEDULING ≠ TRIAGE
- SCHEDULING ≠ TREATMENT RECOMMENDATION
- AVAILABLE SLOT ≠ CLINICAL RECOMMENDATION
- APPOINTMENT ≠ CLINICAL ENCOUNTER
- APPOINTMENT BOOKED ≠ PATIENT SEEN
- APPOINTMENT CANCELLED ≠ CLINICAL CANCELLATION
- APPOINTMENT REASON ≠ DIAGNOSIS
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, ConfigDict, Field


class AppointmentType(str, Enum):
    """Configured reference appointment types."""

    CONSULTATION = "CONSULTATION"
    FOLLOW_UP = "FOLLOW_UP"
    GENERAL_VISIT = "GENERAL_VISIT"
    SPECIALIST_VISIT = "SPECIALIST_VISIT"
    DIAGNOSTIC_VISIT = "DIAGNOSTIC_VISIT"
    PROCEDURE = "PROCEDURE"
    VACCINATION = "VACCINATION"
    TELECONSULTATION = "TELECONSULTATION"
    OTHER = "OTHER"


class AppointmentStatus(str, Enum):
    """Database-approved lifecycle states for HealthSetu appointments."""

    REQUESTED = "REQUESTED"
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    RESCHEDULE_REQUESTED = "RESCHEDULE_REQUESTED"
    RESCHEDULED = "RESCHEDULED"
    CHECKED_IN = "CHECKED_IN"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    NO_SHOW = "NO_SHOW"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    FAILED = "FAILED"


# Valid state transitions according to TRD Section 8 & Section 25
VALID_APPOINTMENT_TRANSITIONS: Dict[AppointmentStatus, Set[AppointmentStatus]] = {
    AppointmentStatus.REQUESTED: {
        AppointmentStatus.CONFIRMED,
        AppointmentStatus.PENDING,
        AppointmentStatus.REJECTED,
        AppointmentStatus.CANCELLED,
        AppointmentStatus.EXPIRED,
    },
    AppointmentStatus.PENDING: {
        AppointmentStatus.CONFIRMED,
        AppointmentStatus.REJECTED,
        AppointmentStatus.CANCELLED,
        AppointmentStatus.EXPIRED,
    },
    AppointmentStatus.CONFIRMED: {
        AppointmentStatus.RESCHEDULE_REQUESTED,
        AppointmentStatus.RESCHEDULED,
        AppointmentStatus.CHECKED_IN,
        AppointmentStatus.CANCELLED,
        AppointmentStatus.NO_SHOW,
    },
    AppointmentStatus.RESCHEDULE_REQUESTED: {
        AppointmentStatus.RESCHEDULED,
        AppointmentStatus.CONFIRMED,
        AppointmentStatus.CANCELLED,
    },
    AppointmentStatus.RESCHEDULED: {
        AppointmentStatus.CONFIRMED,
        AppointmentStatus.CHECKED_IN,
        AppointmentStatus.CANCELLED,
        AppointmentStatus.NO_SHOW,
    },
    AppointmentStatus.CHECKED_IN: {
        AppointmentStatus.IN_PROGRESS,
        AppointmentStatus.CANCELLED,
        AppointmentStatus.NO_SHOW,
    },
    AppointmentStatus.IN_PROGRESS: {
        AppointmentStatus.COMPLETED,
        AppointmentStatus.FAILED,
    },
    AppointmentStatus.COMPLETED: set(),  # Terminal state
    AppointmentStatus.CANCELLED: set(),  # Terminal state
    AppointmentStatus.NO_SHOW: set(),    # Terminal state
    AppointmentStatus.REJECTED: set(),   # Terminal state
    AppointmentStatus.EXPIRED: set(),    # Terminal state
    AppointmentStatus.FAILED: set(),     # Terminal state
}


class AppointmentCreateRequest(BaseModel):
    """Payload for creating or booking an appointment."""

    patient_id: str = Field(..., description="ID of the patient requesting the appointment")
    facility_id: str = Field(..., description="ID of the healthcare facility")
    clinician_id: Optional[str] = Field(None, description="Optional ID of the clinician")
    appointment_type: AppointmentType = Field(AppointmentType.CONSULTATION, description="Clinical service type")
    slot_id: Optional[str] = Field(None, description="Authoritative slot identifier if booking against an existing slot")
    start_time: datetime = Field(..., description="Requested start timestamp with timezone offset")
    end_time: datetime = Field(..., description="Requested end timestamp with timezone offset")
    reason: Optional[str] = Field(None, max_length=500, description="Patient-submitted reason for appointment (NOT a diagnosis)")
    organization_id: Optional[str] = Field(None, description="Parent healthcare organization ID")
    encounter_id: Optional[str] = Field(None, description="Associated clinical encounter if already established")

    model_config = ConfigDict(extra="forbid")


class AppointmentRescheduleRequest(BaseModel):
    """Payload for rescheduling an existing appointment."""

    slot_id: Optional[str] = Field(None, description="New target slot identifier")
    start_time: Optional[datetime] = Field(None, description="New requested start time if not using slot_id")
    end_time: Optional[datetime] = Field(None, description="New requested end time if not using slot_id")
    reason: Optional[str] = Field(None, max_length=500, description="Reason for rescheduling")

    model_config = ConfigDict(extra="forbid")


class AppointmentCancelRequest(BaseModel):
    """Payload for cancelling an appointment."""

    reason: Optional[str] = Field("Patient requested cancellation", max_length=500, description="Reason for cancellation")

    model_config = ConfigDict(extra="forbid")


class AppointmentStatusUpdateRequest(BaseModel):
    """Payload for administrative / clinician status update."""

    status: AppointmentStatus = Field(..., description="Target appointment status")
    reason: Optional[str] = Field(None, max_length=500, description="Reason or notes for transition")

    model_config = ConfigDict(extra="forbid")


class AppointmentRecord(BaseModel):
    """Authoritative appointment entity record matching the database contract."""

    id: str = Field(..., description="Unique appointment ID")
    patient_id: str = Field(..., description="Patient ID")
    facility_id: str = Field(..., description="Healthcare facility ID")
    clinician_id: Optional[str] = Field(None, description="Clinician ID")
    organization_id: Optional[str] = Field(None, description="Organization ID")
    appointment_type: AppointmentType = Field(..., description="Appointment service type")
    slot_id: Optional[str] = Field(None, description="Authoritative slot ID")
    start_time: datetime = Field(..., description="Start datetime with timezone")
    end_time: datetime = Field(..., description="End datetime with timezone")
    status: AppointmentStatus = Field(..., description="Current appointment status")
    reason: Optional[str] = Field(None, description="Appointment reason (non-diagnostic)")
    encounter_id: Optional[str] = Field(None, description="Reference to encounter if created")
    idempotency_key: Optional[str] = Field(None, description="Idempotency key associated with creation")
    created_by: str = Field(..., description="User ID or actor who created the appointment")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    cancelled_at: Optional[datetime] = Field(None, description="Cancellation timestamp")
    cancellation_reason: Optional[str] = Field(None, description="Cancellation reason")
    checked_in_at: Optional[datetime] = Field(None, description="Patient arrival timestamp")
    completed_at: Optional[datetime] = Field(None, description="Appointment completion timestamp")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Operational metadata")

    model_config = ConfigDict(extra="ignore")


class AppointmentResponseData(BaseModel):
    """Standard payload envelope containing single appointment."""

    appointment: AppointmentRecord


class AppointmentResponse(BaseModel):
    """Unified API response envelope."""

    success: bool = True
    data: AppointmentResponseData


class AppointmentListResponseData(BaseModel):
    """Standard payload envelope containing appointment list."""

    items: List[AppointmentRecord] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 50


class AppointmentListResponse(BaseModel):
    """Unified API response envelope for appointment lists."""

    success: bool = True
    data: AppointmentListResponseData
