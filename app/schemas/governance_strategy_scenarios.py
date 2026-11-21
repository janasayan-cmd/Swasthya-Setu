"""Phase 79: Strategic Scenario Analysis Schemas.

Defines schemas and models for:
- Advisory what-if strategic execution scenario modeling
- Clearly labelling projected impacts vs. actual outcomes
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.governance_strategy_execution_monitoring import (
    CLINICAL_SAFETY_MONITORING_DISCLAIMER,
)


class ScenarioType(str, Enum):
    """Classification of simulated strategic execution scenario."""
    DELAYED_EXECUTION = "DELAYED_EXECUTION"
    REDUCED_RESOURCES = "REDUCED_RESOURCES"
    INCREASED_CAPACITY = "INCREASED_CAPACITY"
    CHANGED_TECHNOLOGY = "CHANGED_TECHNOLOGY"
    DEPENDENCY_RESOLUTION = "DEPENDENCY_RESOLUTION"
    CHANGED_SEQUENCE = "CHANGED_SEQUENCE"
    REVISED_HORIZON = "REVISED_HORIZON"


class StrategicScenarioRecord(BaseModel):
    """Authoritative record for an advisory strategic scenario analysis."""
    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    tenant_id: str
    title: str
    scenario_type: ScenarioType
    description: str
    input_roadmap_id: str
    assumptions: List[str] = Field(default_factory=list)
    variables: Dict[str, Any] = Field(default_factory=dict)
    calculation_method: str
    projected_milestone_impacts: List[Dict[str, Any]] = Field(default_factory=list)
    projected_dependency_impacts: List[Dict[str, Any]] = Field(default_factory=list)
    projected_resource_implications: str = ""
    expected_strategic_consequences: str = ""
    uncertainty_range: str = ""
    limitations: str = ""
    created_by: str
    disclaimer: str = CLINICAL_SAFETY_MONITORING_DISCLAIMER
    created_at: str


class CreateScenarioRequest(BaseModel):
    """Request to define a strategic scenario definition."""
    model_config = ConfigDict(extra="forbid")

    title: str
    scenario_type: ScenarioType
    description: str
    input_roadmap_id: str
    assumptions: Optional[List[str]] = None
    variables: Optional[Dict[str, Any]] = None
    calculation_method: str = "Deterministic dependency and milestone impact modeling"
    projected_resource_implications: Optional[str] = ""
    expected_strategic_consequences: Optional[str] = ""
    uncertainty_range: Optional[str] = ""
    limitations: Optional[str] = ""


class ExecuteScenarioRequest(BaseModel):
    """Request to compute simulated impacts for a scenario."""
    model_config = ConfigDict(extra="forbid")

    milestone_delays_days: Optional[int] = 0
    budget_variance_pct: Optional[float] = 0.0


class ScenarioComparisonResponse(BaseModel):
    """Comparative evaluation across multiple strategic scenarios."""
    model_config = ConfigDict(extra="forbid")

    tenant_id: str
    compared_scenarios: List[StrategicScenarioRecord]
    baseline_roadmap_id: str
    comparative_summary: str
    disclaimer: str = CLINICAL_SAFETY_MONITORING_DISCLAIMER
