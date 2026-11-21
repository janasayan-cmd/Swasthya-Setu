"""Phase 76: Benefit Sustainability & Independent Verification Schemas.

Defines schemas and models for:
- Longitudinal benefit sustainability tracking across subsequent observation periods
- Independent verification coordination with strict conflict of interest and separation of duties checks
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class SustainabilityTrend(str, Enum):
    """Longitudinal trajectory of a previously realized benefit."""
    SUSTAINED = "SUSTAINED"
    DECLINING = "DECLINING"
    REVERSED = "REVERSED"
    INCONSISTENT = "INCONSISTENT"
    MEASUREMENT_DISCONTINUITY = "MEASUREMENT_DISCONTINUITY"
    STALE_DATA = "STALE_DATA"
    UNABLE_TO_DETERMINE = "UNABLE_TO_DETERMINE"


class BenefitSustainabilityRecord(BaseModel):
    """Authoritative record evaluating longitudinal sustainability of a benefit."""
    model_config = ConfigDict(extra="forbid")

    sustainability_id: str
    benefit_id: str
    tenant_id: str
    assessment_period: str
    trend: SustainabilityTrend
    consecutive_positive_periods: int = 1
    performance_stability_score: float = 1.0
    stale_evidence_flagged: bool = False
    referral_target: Optional[str] = None
    notes: str
    clinical_safety_notice: str = (
        "Sustainability monitoring evaluates ongoing operational adoption and metric continuity. Declining trends are operational review signals, not automatic proof of clinical failure."
    )
    assessed_by: str
    created_at: str


class CreateSustainabilityAssessmentRequest(BaseModel):
    """Request payload to record a sustainability evaluation."""
    model_config = ConfigDict(extra="forbid")

    assessment_period: str = Field(..., min_length=2)
    notes: str = Field(..., min_length=5)


# -----------------------------------------------------------------------------
# Independent Verification
# -----------------------------------------------------------------------------


class VerificationStatus(str, Enum):
    """Status of an independent benefit verification."""
    REQUESTED = "REQUESTED"
    ASSIGNED = "ASSIGNED"
    IN_REVIEW = "IN_REVIEW"
    VERIFIED = "VERIFIED"
    VERIFIED_WITH_LIMITATIONS = "VERIFIED_WITH_LIMITATIONS"
    NOT_VERIFIED = "NOT_VERIFIED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    CONFLICT_OF_INTEREST_IDENTIFIED = "CONFLICT_OF_INTEREST_IDENTIFIED"
    REASSESSMENT_REQUIRED = "REASSESSMENT_REQUIRED"


class BenefitVerificationRecord(BaseModel):
    """Authoritative record for independent benefit verification."""
    model_config = ConfigDict(extra="forbid")

    verification_id: str
    benefit_id: str
    tenant_id: str
    verification_scope: str
    requester_id: str
    assigned_verifier_id: Optional[str] = None
    conflict_of_interest_checked: bool = False
    evidence_reviewed: List[str] = Field(default_factory=list)
    recalculated_values: Dict[str, Any] = Field(default_factory=dict)
    status: VerificationStatus = VerificationStatus.REQUESTED
    findings: Optional[str] = None
    verifier_comments: Optional[str] = None
    completed_at: Optional[str] = None
    created_at: str
    updated_at: str


class CreateVerificationRequest(BaseModel):
    """Request payload to initiate independent verification."""
    model_config = ConfigDict(extra="forbid")

    verification_scope: str = Field(..., min_length=5)
    evidence_reviewed: List[str] = Field(default_factory=list)


class AssignVerifierRequest(BaseModel):
    """Request payload to assign an independent verifier."""
    model_config = ConfigDict(extra="forbid")

    verifier_id: str = Field(..., min_length=2)
    conflict_of_interest_cleared: bool = Field(..., description="Must affirm verifier did not produce the source measurement")


class CompleteVerificationRequest(BaseModel):
    """Request payload to finalize independent verification findings."""
    model_config = ConfigDict(extra="forbid")

    status: VerificationStatus
    findings: str = Field(..., min_length=5)
    verifier_comments: str = Field(..., min_length=5)
    recalculated_values: Dict[str, Any] = Field(default_factory=dict)
