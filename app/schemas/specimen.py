"""Pydantic schemas for Specimen Information (Phase 34).

SAFETY & ARCHITECTURAL INVARIANTS:
- SPECIMEN INFORMATION MUST NOT BE INFERRED OR ASSUMED
- IF COLLECTION INFORMATION IS MISSING -> UNKNOWN / NOT_RECORDED
- SPECIMEN REJECTION MUST REMAIN DISTINGUISHABLE FROM TEST FAILURE
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field


class SpecimenStatus(str, Enum):
    """Controlled lifecycle statuses for biological and diagnostic specimens."""

    ORDERED = "ORDERED"
    COLLECTION_PENDING = "COLLECTION_PENDING"
    COLLECTED = "COLLECTED"
    RECEIVED = "RECEIVED"
    REJECTED = "REJECTED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    UNKNOWN = "UNKNOWN"


class SpecimenType(str, Enum):
    """Standard biological specimen matrices."""

    BLOOD = "BLOOD"
    SERUM = "SERUM"
    PLASMA = "PLASMA"
    URINE = "URINE"
    CSF = "CSF"
    STOOL = "STOOL"
    SALIVA = "SALIVA"
    SWAB = "SWAB"
    TISSUE = "TISSUE"
    SPUTUM = "SPUTUM"
    OTHER = "OTHER"


class SpecimenCreate(BaseModel):
    """Payload to create or record a specimen."""

    specimen_type: SpecimenType = Field(description="Biological specimen category")
    collection_site: Optional[str] = Field(default=None, description="Anatomical site or method of collection")
    notes: Optional[str] = Field(default=None, description="Collection instructions or observations")
    collected_at: Optional[datetime] = Field(default=None, description="Time of collection if completed")


class SpecimenRecord(BaseModel):
    """Authoritative specimen entity."""

    model_config = ConfigDict(populate_by_name=True)

    specimen_id: str = Field(description="Internal unique identifier for specimen")
    order_id: str = Field(description="Associated diagnostic order ID")
    patient_id: str = Field(description="Associated patient ID")
    specimen_type: SpecimenType
    status: SpecimenStatus = Field(default=SpecimenStatus.COLLECTION_PENDING)
    collection_site: Optional[str] = None
    collected_at: Optional[datetime] = None
    received_at: Optional[datetime] = None
    rejected_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    provider_reference: Optional[str] = None
    notes: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
