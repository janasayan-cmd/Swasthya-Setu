"""Phase 88: Response Strategy and Recovery Option Reporting Schemas.

Defines executive reports for recovery options, feasibility summaries,
capability priorities, option comparisons, execution tracking, and deviations.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

from app.schemas.governance_response_common import (
    MANDATORY_RESPONSE_STRATEGY_DISCLAIMER,
)


class RecoveryOptionsSummaryReport(BaseModel):
    tenant_id: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    total_strategies_registered: int
    approved_strategies_count: int
    total_candidate_options_generated: int
    feasible_verified_options_count: int
    conditionally_feasible_options_count: int
    infeasible_options_count: int
    disclaimer: str = Field(default=MANDATORY_RESPONSE_STRATEGY_DISCLAIMER)


class StrategyFeasibilityReport(BaseModel):
    tenant_id: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    total_feasibility_assessments: int
    verified_feasible_pct: float
    top_failed_conditions: List[str] = Field(default_factory=list)
    options_with_expired_evidence: int
    disclaimer: str = Field(default=MANDATORY_RESPONSE_STRATEGY_DISCLAIMER)


class RecoveryPrioritiesReport(BaseModel):
    tenant_id: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    total_prioritized_capabilities: int
    tier_1_essential_capabilities_count: int
    tier_2_critical_capabilities_count: int
    unresolved_priority_conflicts_count: int
    disclaimer: str = Field(default=MANDATORY_RESPONSE_STRATEGY_DISCLAIMER)


class RecoveryComparisonsReport(BaseModel):
    tenant_id: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    total_comparisons_conducted: int
    total_trade_offs_analyzed: int
    options_recommended_for_decision: int
    disclaimer: str = Field(default=MANDATORY_RESPONSE_STRATEGY_DISCLAIMER)


class RecoveryExecutionTrackingReport(BaseModel):
    tenant_id: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    total_active_executions: int
    in_progress_count: int
    verified_restored_count: int
    average_progress_pct: float
    disclaimer: str = Field(default=MANDATORY_RESPONSE_STRATEGY_DISCLAIMER)


class StrategyDeviationsReport(BaseModel):
    tenant_id: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    total_executions_with_deviations: int
    total_deviations_reported: int
    active_blocked_activities_count: int
    disclaimer: str = Field(default=MANDATORY_RESPONSE_STRATEGY_DISCLAIMER)
