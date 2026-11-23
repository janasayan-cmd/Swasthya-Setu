"""Phase 85: Coverage Scenarios and Stress-Testing Schemas.

Enables advisory stress testing of role coverage under simulated absences,
mass unavailability, or prolonged operational disruptions.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

from app.schemas.governance_role_coverage_common import (
    ScenarioType,
    MANDATORY_ROLE_COVERAGE_DISCLAIMER,
)


class CoverageScenarioEvaluationRecord(BaseModel):
    evaluation_id: str
    tenant_id: str
    scenario_type: ScenarioType
    scenario_name: str
    simulated_unavailable_user_ids: List[str] = Field(default_factory=list)
    total_critical_responsibilities_evaluated: int
    fully_covered_count: int
    partially_covered_count: int
    uncovered_count: int
    overall_coverage_resilience_percentage: float
    uncovered_responsibility_ids: List[str] = Field(default_factory=list)
    single_points_of_failure_revealed: List[str] = Field(default_factory=list)
    evaluated_by: str
    evaluated_at: datetime = Field(default_factory=datetime.utcnow)
    advisory_recommendations: List[str] = Field(default_factory=list)
    disclaimer: str = Field(default=MANDATORY_ROLE_COVERAGE_DISCLAIMER)


class EvaluateCoverageScenarioRequest(BaseModel):
    scenario_type: ScenarioType
    scenario_name: str
    simulated_unavailable_user_ids: List[str] = Field(default_factory=list)
    description: Optional[str] = None
