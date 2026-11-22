"""Phase 81: Clinical Safety Governance Continuity Assurance Framework Schemas.

Defines the structure for configurable, version-controlled continuity assurance
frameworks, assessment dimensions, criteria, evidence requirements, and scoring methods.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

MANDATORY_GOVERNANCE_CONTINUITY_ASSURANCE_DISCLAIMER = (
    "Governance resilience validation and continuity assurance records are "
    "administrative evaluation instruments and do NOT constitute proof of "
    "clinical safety, regulatory compliance, or operational recovery. Phase 81 "
    "does not replace authoritative workflows of Phases 49, 54, 55, 63, 67, "
    "69, 70, 72, 73, 74, 75, 76, 77, 78, 79, or 80."
)


class FrameworkDimensionType(str, Enum):
    """15 Core Continuity Assurance Dimensions as defined in Section 4."""
    CAPABILITY_COVERAGE = "CAPABILITY_COVERAGE"
    PLAN_COMPLETENESS = "PLAN_COMPLETENESS"
    PLAN_APPROVAL_CURRENCY = "PLAN_APPROVAL_CURRENCY"
    CRITICAL_DEPENDENCY_COVERAGE = "CRITICAL_DEPENDENCY_COVERAGE"
    PERSONNEL_ROLE_COVERAGE = "PERSONNEL_ROLE_COVERAGE"
    DELEGATED_AUTHORITY_READINESS = "DELEGATED_AUTHORITY_READINESS"
    COMMUNICATION_READINESS = "COMMUNICATION_READINESS"
    ALTERNATIVE_OPERATING_ARRANGEMENTS = "ALTERNATIVE_OPERATING_ARRANGEMENTS"
    DECISION_CONTINUITY = "DECISION_CONTINUITY"
    EVIDENCE_PRESERVATION = "EVIDENCE_PRESERVATION"
    RECOVERY_READINESS = "RECOVERY_READINESS"
    RECOVERY_VERIFICATION = "RECOVERY_VERIFICATION"
    RECONCILIATION_INTEGRITY = "RECONCILIATION_INTEGRITY"
    EXERCISE_PERFORMANCE = "EXERCISE_PERFORMANCE"
    CORRECTIVE_ACTION_FOLLOW_THROUGH = "CORRECTIVE_ACTION_FOLLOW_THROUGH"


class EvaluationMethod(str, Enum):
    DOCUMENTARY_REVIEW = "DOCUMENTARY_REVIEW"
    EXERCISE_OBSERVATION = "EXERCISE_OBSERVATION"
    SIMULATION_ASSESSMENT = "SIMULATION_ASSESSMENT"
    INDEPENDENT_AUDIT_VERIFICATION = "INDEPENDENT_AUDIT_VERIFICATION"
    DATA_RECONCILIATION_ANALYSIS = "DATA_RECONCILIATION_ANALYSIS"


class ScoringMethod(str, Enum):
    QUALITATIVE_TIERED = "QUALITATIVE_TIERED"
    CRITERIA_PERCENTAGE = "CRITERIA_PERCENTAGE"
    WEIGHTED_CHECKLIST = "WEIGHTED_CHECKLIST"


class FrameworkStatus(str, Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    SUPERSEDED = "SUPERSEDED"


class DimensionCriterion(BaseModel):
    criterion_id: str
    name: str
    description: str
    required_evidence_type: str
    weight: float = 1.0
    mandatory: bool = True


class AssuranceDimension(BaseModel):
    dimension_id: str
    dimension_type: FrameworkDimensionType
    name: str
    description: str
    evaluation_method: EvaluationMethod
    scoring_method: ScoringMethod
    applicable_scopes: List[str] = Field(default_factory=lambda: ["ORGANIZATION", "FACILITY", "DEPARTMENT"])
    criteria: List[DimensionCriterion] = Field(default_factory=list)


class CreateContinuityAssuranceFrameworkRequest(BaseModel):
    framework_name: str
    description: str
    organizational_scope: str = "GLOBAL"
    dimensions: List[AssuranceDimension] = Field(default_factory=list)
    effective_date: Optional[datetime] = None
    review_date: Optional[datetime] = None
    scoring_method: ScoringMethod = ScoringMethod.QUALITATIVE_TIERED


class UpdateContinuityAssuranceFrameworkRequest(BaseModel):
    framework_name: Optional[str] = None
    description: Optional[str] = None
    dimensions: Optional[List[AssuranceDimension]] = None
    review_date: Optional[datetime] = None
    scoring_method: Optional[ScoringMethod] = None


class SubmitFrameworkRequest(BaseModel):
    submission_notes: Optional[str] = None


class ApproveFrameworkRequest(BaseModel):
    approval_notes: Optional[str] = None


class ContinuityAssuranceFrameworkRecord(BaseModel):
    framework_id: str
    framework_name: str
    description: str
    version: int = 1
    status: FrameworkStatus = FrameworkStatus.DRAFT
    organizational_scope: str = "GLOBAL"
    dimensions: List[AssuranceDimension] = Field(default_factory=list)
    effective_date: Optional[datetime] = None
    review_date: Optional[datetime] = None
    scoring_method: ScoringMethod = ScoringMethod.QUALITATIVE_TIERED
    created_by: str
    created_at: datetime
    submitted_by: Optional[str] = None
    submitted_at: Optional[datetime] = None
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    approval_notes: Optional[str] = None
    tenant_id: str = "default"
    disclaimer: str = MANDATORY_GOVERNANCE_CONTINUITY_ASSURANCE_DISCLAIMER
