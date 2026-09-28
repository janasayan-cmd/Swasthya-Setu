"""Provenance schemas and lifecycle verification structures (Phase 26)."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field


class ProvenanceCategory(str, Enum):
    """Origin classification for healthcare data (TRD Sec 7)."""
    PATIENT_REPORTED = "PATIENT_REPORTED"
    CLINICIAN_ENTERED = "CLINICIAN_ENTERED"
    CLINIC_ENTERED = "CLINIC_ENTERED"
    DOCUMENT_EXTRACTED = "DOCUMENT_EXTRACTED"
    OCR_EXTRACTED = "OCR_EXTRACTED"
    IMPORTED = "IMPORTED"
    AI_EXTRACTED = "AI_EXTRACTED"
    SYSTEM_GENERATED = "SYSTEM_GENERATED"


class ProvenanceVerificationState(str, Enum):
    """Clinical verification status attached to provenance metadata."""
    UNVERIFIED = "UNVERIFIED"
    PATIENT_CONFIRMED = "PATIENT_CONFIRMED"
    CLINICIAN_VERIFIED = "CLINICIAN_VERIFIED"
    SYSTEM_VALIDATED = "SYSTEM_VALIDATED"


class ProvenanceRecord(BaseModel):
    """Complete provenance trace attached to clinical resources and findings."""
    model_config = ConfigDict(extra="ignore")

    resource_type: str
    resource_id: str
    category: ProvenanceCategory
    source_system: str
    source_organization_id: Optional[str] = None
    source_facility_id: Optional[str] = None
    created_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_timestamp: Optional[datetime] = None
    imported_timestamp: Optional[datetime] = None
    verification_state: ProvenanceVerificationState = ProvenanceVerificationState.UNVERIFIED
    verified_by_actor_id: Optional[str] = None
    verified_at: Optional[datetime] = None
    is_external: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)
