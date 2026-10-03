"""Phase 33 — Insurance Benefit Information Schemas.

CRITICAL INVARIANTS:
- BENEFIT INFORMATION ≠ GUARANTEED PAYMENT.
- DO NOT INFER BENEFIT COVERAGE WHERE THE PAYER DID NOT EXPLICITLY RETURN IT.
- ALL MONETARY BENEFIT LIMITS/COPAY/DEDUCTIBLE STORED IN INTEGER MINOR UNITS.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class BenefitCategory(str, Enum):
    """Standardized medical benefit categories."""
    CONSULTATION = "CONSULTATION"
    DIAGNOSTIC = "DIAGNOSTIC"
    INPATIENT = "INPATIENT"
    OUTPATIENT = "OUTPATIENT"
    PHARMACY = "PHARMACY"
    EMERGENCY = "EMERGENCY"
    SPECIALIST = "SPECIALIST"
    OTHER = "OTHER"


class BenefitItem(BaseModel):
    """Detailed benefit coverage terms for a specific category."""
    model_config = ConfigDict(from_attributes=True)

    category: BenefitCategory
    covered: Optional[bool] = Field(None, description="Explicit payer coverage indicator")
    copay_in_minor_units: Optional[int] = Field(None, ge=0, description="Fixed copay in minor currency units (paise/cents)")
    coinsurance_percentage: Optional[float] = Field(None, ge=0.0, le=100.0, description="Coinsurance percentage (e.g. 20.0 for 20%)")
    deductible_in_minor_units: Optional[int] = Field(None, ge=0, description="Annual category deductible in minor units")
    remaining_deductible_in_minor_units: Optional[int] = Field(None, ge=0, description="Remaining deductible balance")
    limitations: List[str] = Field(default_factory=list, description="Explicit policy limitations/cappings")
    exclusions: List[str] = Field(default_factory=list, description="Explicit exclusions")


class BenefitRequest(BaseModel):
    """Payload to retrieve benefit details for coverage."""
    model_config = ConfigDict(extra="forbid")

    coverage_id: str = Field(..., description="Insurance coverage reference ID")
    categories: Optional[List[BenefitCategory]] = Field(None, description="Filter to specific benefit categories")


class BenefitResponse(BaseModel):
    """Benefit breakdown returned to caller."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    patient_id: str
    coverage_id: str
    payer_id: str
    payer_name: str
    benefits: List[BenefitItem]
    response_timestamp: datetime
    raw_provider_reference: Optional[str] = None
    limitations: List[str] = Field(default_factory=list)
    uncertainty_notes: Optional[str] = None
    created_at: datetime


class BenefitRecord(BaseModel):
    """Internal database and cache representation of benefit inquiry."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    patient_id: str
    coverage_id: str
    payer_id: str
    payer_name: str
    benefits: List[BenefitItem] = Field(default_factory=list)
    response_timestamp: datetime = Field(default_factory=datetime.utcnow)
    raw_provider_reference: Optional[str] = None
    limitations: List[str] = Field(default_factory=list)
    uncertainty_notes: Optional[str] = None
    raw_response: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    def to_response(self) -> BenefitResponse:
        return BenefitResponse(
            id=self.id,
            patient_id=self.patient_id,
            coverage_id=self.coverage_id,
            payer_id=self.payer_id,
            payer_name=self.payer_name,
            benefits=self.benefits,
            response_timestamp=self.response_timestamp,
            raw_provider_reference=self.raw_provider_reference,
            limitations=self.limitations,
            uncertainty_notes=self.uncertainty_notes,
            created_at=self.created_at,
        )
