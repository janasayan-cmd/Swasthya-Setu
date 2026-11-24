"""Phase 88: Recovery Option Comparison and Trade-Off Analysis Schemas.

Defines schemas for side-by-side comparison of candidate recovery options,
transparent trade-off analysis, and satisfied vs unsatisfied requirements.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

from app.schemas.governance_response_common import (
    MANDATORY_RESPONSE_STRATEGY_DISCLAIMER,
    RecoveryFeasibilityOutcome,
)


class TradeOffAnalysisItem(BaseModel):
    trade_off_type: str  # SPEED_VS_CAPACITY, CENTRALIZED_VS_DISTRIBUTED, SUBSTITUTION_VS_CONCENTRATION, MANUAL_VS_CONSISTENCY
    competing_objectives: str
    affected_capabilities: List[str] = Field(default_factory=list)
    advantages: List[str] = Field(default_factory=list)
    disadvantages: List[str] = Field(default_factory=list)
    decision_authority_required: str
    evidence_refs: List[str] = Field(default_factory=list)


class OptionComparisonItem(BaseModel):
    option_id: str
    option_name: str
    feasibility_outcome: RecoveryFeasibilityOutcome
    estimated_recovery_hours: float
    satisfied_requirements: List[str] = Field(default_factory=list)
    unsatisfied_requirements: List[str] = Field(default_factory=list)
    resource_concentration_risk: str  # HIGH, MEDIUM, LOW
    security_limitations: List[str] = Field(default_factory=list)
    personnel_coverage_status: str  # VERIFIED, UNVERIFIED, CONSTRAINED


class RecoveryComparisonRecord(BaseModel):
    comparison_id: str
    tenant_id: str
    comparison_name: str
    candidate_option_ids: List[str] = Field(default_factory=list)
    compared_options: List[OptionComparisonItem] = Field(default_factory=list)
    trade_offs_identified: List[TradeOffAnalysisItem] = Field(default_factory=list)
    unresolved_risks: List[str] = Field(default_factory=list)
    top_recommended_option_id: Optional[str] = None
    comparison_methodology_version: str = "1.0"
    compared_by: str
    compared_at: datetime = Field(default_factory=datetime.utcnow)
    disclaimer: str = Field(default=MANDATORY_RESPONSE_STRATEGY_DISCLAIMER)


class RunRecoveryComparisonRequest(BaseModel):
    comparison_name: str
    candidate_option_ids: List[str]
    methodology_version: str = "1.0"
