"""Phase 88: Recovery Priority and Capability Sequencing Schemas.

Defines schemas for evaluating governance capability restoration priorities
and sequencing restoration activities based on dependency constraints and continuity requirements.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

from app.schemas.governance_response_common import (
    MANDATORY_RESPONSE_STRATEGY_DISCLAIMER,
)


class CapabilityRestorationPriorityItem(BaseModel):
    capability_ref: str
    priority_tier: str  # TIER_1_ESSENTIAL, TIER_2_CRITICAL, TIER_3_IMPORTANT, TIER_4_SUPPORTING
    priority_rank: int
    rationale: str
    prerequisite_capability_refs: List[str] = Field(default_factory=list)
    required_resource_refs: List[str] = Field(default_factory=list)
    required_role_refs: List[str] = Field(default_factory=list)
    max_acceptable_outage_hours: float = 4.0
    estimated_restoration_hours: float = 2.0
    outstanding_constraints: List[str] = Field(default_factory=list)


class RecoveryPriorityEvaluationRecord(BaseModel):
    priority_evaluation_id: str
    tenant_id: str
    scenario_id: Optional[str] = None
    impact_assessment_id: Optional[str] = None
    prioritized_capabilities: List[CapabilityRestorationPriorityItem] = Field(default_factory=list)
    unresolved_priority_conflicts: List[str] = Field(default_factory=list)
    evaluated_by: str
    evaluated_at: datetime = Field(default_factory=datetime.utcnow)
    disclaimer: str = Field(default=MANDATORY_RESPONSE_STRATEGY_DISCLAIMER)


class EvaluateRecoveryPrioritiesRequest(BaseModel):
    scenario_id: Optional[str] = None
    impact_assessment_id: Optional[str] = None
    capability_refs: List[str] = Field(default_factory=list)


class RecoverySequenceRecord(BaseModel):
    sequence_id: str
    tenant_id: str
    sequence_name: str
    ordered_capability_refs: List[str] = Field(default_factory=list)
    milestone_targets: List[str] = Field(default_factory=list)
    blocked_activities: List[str] = Field(default_factory=list)
    critical_dependency_bottlenecks: List[str] = Field(default_factory=list)
    estimated_total_duration_hours: float = Field(default=4.0)
    created_by: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    disclaimer: str = Field(default=MANDATORY_RESPONSE_STRATEGY_DISCLAIMER)


class CreateRecoverySequenceRequest(BaseModel):
    sequence_name: str
    priority_evaluation_id: str
    milestone_targets: List[str] = Field(default_factory=list)
