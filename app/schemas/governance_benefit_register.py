"""Phase 76: Governance Benefit Register & Lineage Schemas.

Defines schemas and models for:
- Registering expected benefits associated with approved governance changes
- Benefit categorization across operational and authorized clinical domains
- Maintaining lineage from Phase 72 decisions, Phase 73 implementations, Phase 74 adoptions, and Phase 75 portfolios
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class BenefitCategory(str, Enum):
    """Classification of governance change benefits."""
    OPERATIONAL_EFFICIENCY = "OPERATIONAL_EFFICIENCY"
    WORKFLOW_CONSISTENCY = "WORKFLOW_CONSISTENCY"
    PROCESS_RELIABILITY = "PROCESS_RELIABILITY"
    TRAINING_READINESS = "TRAINING_READINESS"
    DOCUMENTATION_QUALITY = "DOCUMENTATION_QUALITY"
    EVIDENCE_COMPLETENESS = "EVIDENCE_COMPLETENESS"
    OPERATIONAL_COORDINATION = "OPERATIONAL_COORDINATION"
    COMPLIANCE_PROCESS_IMPROVEMENT = "COMPLIANCE_PROCESS_IMPROVEMENT"
    PATIENT_EXPERIENCE_AUTHORIZED = "PATIENT_EXPERIENCE_AUTHORIZED"
    CLINICAL_OUTCOME_INDICATOR = "CLINICAL_OUTCOME_INDICATOR"


class BenefitStatus(str, Enum):
    """Lifecycle status of a registered governance benefit."""
    DRAFT = "DRAFT"
    REGISTERED = "REGISTERED"
    ACTIVE_MONITORING = "ACTIVE_MONITORING"
    UNDER_REVIEW = "UNDER_REVIEW"
    REALIZED = "REALIZED"
    PARTIALLY_REALIZED = "PARTIALLY_REALIZED"
    DELAYED = "DELAYED"
    NOT_REALIZED = "NOT_REALIZED"
    RETIRED = "RETIRED"
    SUSPENDED = "SUSPENDED"


class GovernanceBenefitRecord(BaseModel):
    """Authoritative record for an expected governance change benefit."""
    model_config = ConfigDict(extra="forbid")

    benefit_id: str
    tenant_id: str
    title: str
    description: str
    category: BenefitCategory
    expected_outcome: str
    decision_id: str = Field(..., description="Phase 72 approved governance decision reference")
    implementation_id: str = Field(..., description="Phase 73 implementation record reference")
    portfolio_id: Optional[str] = Field(None, description="Phase 75 portfolio reference, where applicable")
    adoption_registration_id: Optional[str] = Field(None, description="Phase 74 adoption tracking reference, where applicable")
    responsible_benefit_owner_id: str
    organizational_scope: Dict[str, Any] = Field(default_factory=dict)
    expected_realization_date: str
    measurement_period: str
    active_baseline_id: Optional[str] = None
    active_target_id: Optional[str] = None
    measurement_methodology: str
    evidence_requirements: List[str] = Field(default_factory=list)
    verification_requirements: List[str] = Field(default_factory=list)
    status: BenefitStatus = BenefitStatus.DRAFT
    created_by: str
    created_at: str
    updated_at: str
    version: int = 1


class RegisterBenefitRequest(BaseModel):
    """Request payload to register an expected governance change benefit."""
    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=3, max_length=255)
    description: str = Field(..., min_length=5)
    category: BenefitCategory
    expected_outcome: str = Field(..., min_length=5)
    decision_id: str = Field(..., min_length=2)
    implementation_id: str = Field(..., min_length=2)
    portfolio_id: Optional[str] = None
    adoption_registration_id: Optional[str] = None
    responsible_benefit_owner_id: str = Field(..., min_length=2)
    organizational_scope: Dict[str, Any] = Field(default_factory=dict)
    expected_realization_date: str
    measurement_period: str = Field(..., min_length=2)
    measurement_methodology: str = Field(..., min_length=5)
    evidence_requirements: List[str] = Field(default_factory=list)
    verification_requirements: List[str] = Field(default_factory=list)


class BenefitLineageResponse(BaseModel):
    """Full decision-to-benefit governance lineage response."""
    model_config = ConfigDict(extra="forbid")

    benefit_id: str
    decision_id: str
    implementation_id: str
    portfolio_id: Optional[str] = None
    adoption_registration_id: Optional[str] = None
    title: str
    status: BenefitStatus
    category: BenefitCategory
    active_baseline_id: Optional[str] = None
    active_target_id: Optional[str] = None
    lineage_nodes: List[Dict[str, Any]] = Field(default_factory=list)
