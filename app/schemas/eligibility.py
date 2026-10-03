"""Phase 33 — Insurance Eligibility Verification Schemas.

CRITICAL INVARIANTS:
- ELIGIBILITY VERIFICATION IS A POINT-IN-TIME CHECK.
- ACTIVE COVERAGE TODAY DOES NOT GUARANTEE FUTURE COVERAGE, CLAIM PAYMENT, OR REIMBURSEMENT.
- UNKNOWN ≠ INELIGIBLE; UNKNOWN ≠ ELIGIBLE.
- PROVIDER FAILURE ≠ ELIGIBLE.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class EligibilityStatus(str, Enum):
    """Normalized eligibility verification statuses."""
    ELIGIBLE = "ELIGIBLE"
    INELIGIBLE = "INELIGIBLE"
    PENDING = "PENDING"
    UNKNOWN = "UNKNOWN"
    ERROR = "ERROR"
    NOT_SUPPORTED = "NOT_SUPPORTED"


class EligibilityCheckRequest(BaseModel):
    """Payload to request insurance eligibility check."""
    model_config = ConfigDict(extra="forbid")

    coverage_id: str = Field(..., description="Insurance coverage reference ID")
    service_type: Optional[str] = Field("GENERAL", description="Service category code (e.g. OPD, IPD, DIAGNOSTIC)")
    date_of_service: Optional[str] = Field(None, description="Date of proposed medical service (YYYY-MM-DD)")
    facility_id: Optional[str] = Field(None, description="Target hospital / facility identifier")
    clinician_id: Optional[str] = Field(None, description="Requesting clinician identifier")


class EligibilityCheckResponse(BaseModel):
    """Point-in-time eligibility verification response."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    patient_id: str
    coverage_id: str
    payer_id: str
    payer_name: str
    status: EligibilityStatus
    verification_timestamp: datetime
    effective_date: Optional[str] = None
    termination_date: Optional[str] = None
    plan_name: Optional[str] = None
    limitations: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    raw_provider_reference: Optional[str] = None
    provider_name: str = "MOCK"
    provider_version: str = "1.0"
    created_at: datetime


class EligibilityCheckRecord(BaseModel):
    """Internal database and cache representation of eligibility check."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    patient_id: str
    coverage_id: str
    payer_id: str
    payer_name: str
    status: EligibilityStatus = EligibilityStatus.UNKNOWN
    verification_timestamp: datetime = Field(default_factory=datetime.utcnow)
    effective_date: Optional[str] = None
    termination_date: Optional[str] = None
    plan_name: Optional[str] = None
    limitations: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    raw_provider_reference: Optional[str] = None
    provider_name: str = "MOCK"
    provider_version: str = "1.0"
    raw_response: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    def to_response(self) -> EligibilityCheckResponse:
        return EligibilityCheckResponse(
            id=self.id,
            patient_id=self.patient_id,
            coverage_id=self.coverage_id,
            payer_id=self.payer_id,
            payer_name=self.payer_name,
            status=self.status,
            verification_timestamp=self.verification_timestamp,
            effective_date=self.effective_date,
            termination_date=self.termination_date,
            plan_name=self.plan_name,
            limitations=self.limitations,
            warnings=self.warnings,
            raw_provider_reference=self.raw_provider_reference,
            provider_name=self.provider_name,
            provider_version=self.provider_version,
            created_at=self.created_at,
        )
