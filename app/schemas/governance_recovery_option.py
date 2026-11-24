"""Phase 88: Candidate Recovery Option and Feasibility Schemas.

Defines schemas for generating candidate recovery options from approved organizational evidence
(Phases 80, 85, 86, 87) and evaluating their operational feasibility transparently.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

from app.schemas.governance_response_common import (
    MANDATORY_RESPONSE_STRATEGY_DISCLAIMER,
    RecoveryFeasibilityOutcome,
    ResponseStrategyCategory,
)


class FeasibilityAssessmentRecord(BaseModel):
    assessment_id: str
    tenant_id: str
    option_id: str
    feasibility_outcome: RecoveryFeasibilityOutcome = RecoveryFeasibilityOutcome.NOT_ASSESSED
    resource_availability_verified: bool = False
    fallback_readiness_verified: bool = False
    personnel_coverage_verified: bool = False
    authorization_prerequisites_met: bool = False
    dependency_independence_confirmed: bool = False
    capacity_sufficient: bool = False
    failed_conditions: List[str] = Field(default_factory=list)
    unresolved_assumptions: List[str] = Field(default_factory=list)
    evidence_freshness_hours: Optional[float] = None
    evaluated_by: str
    evaluated_at: datetime = Field(default_factory=datetime.utcnow)
    disclaimer: str = Field(default=MANDATORY_RESPONSE_STRATEGY_DISCLAIMER)


class CandidateRecoveryOptionRecord(BaseModel):
    option_id: str
    tenant_id: str
    scenario_id: Optional[str] = None
    impact_assessment_id: Optional[str] = None
    strategy_id: Optional[str] = None
    option_name: str
    description: str
    category: ResponseStrategyCategory
    target_capability_refs: List[str] = Field(default_factory=list)
    required_resource_refs: List[str] = Field(default_factory=list)
    required_role_refs: List[str] = Field(default_factory=list)
    required_authorization_refs: List[str] = Field(default_factory=list)
    dependency_requirements: List[str] = Field(default_factory=list)
    estimated_recovery_hours: float = Field(default=2.0, ge=0.1)
    feasibility_outcome: RecoveryFeasibilityOutcome = RecoveryFeasibilityOutcome.NOT_ASSESSED
    feasibility_assessment_id: Optional[str] = None
    known_limitations: List[str] = Field(default_factory=list)
    evidence_refs: List[str] = Field(default_factory=list)
    is_recommended: bool = False
    generated_by: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    disclaimer: str = Field(default=MANDATORY_RESPONSE_STRATEGY_DISCLAIMER)


class GenerateRecoveryOptionsRequest(BaseModel):
    scenario_id: Optional[str] = None
    impact_assessment_id: Optional[str] = None
    target_capability_refs: List[str] = Field(default_factory=list)
    include_alternative_resources: bool = True
    include_manual_procedures: bool = True


class EvaluateOptionFeasibilityRequest(BaseModel):
    override_capacity_pct: Optional[float] = None
    notes: Optional[str] = None
