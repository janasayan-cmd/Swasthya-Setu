"""Phase 87: Multi-Resource and Compound Disruption Analysis Schemas.

Defines schemas for scenarios involving multiple simultaneous failures,
such as primary and fallback concurrent outages, or infrastructure and personnel constraints.
"""

from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from app.schemas.governance_disruption_common import (
    MANDATORY_DISRUPTION_IMPACT_DISCLAIMER,
    ImpactSeverity,
)


class CompoundDisruptionScenarioRecord(BaseModel):
    compound_scenario_id: str
    tenant_id: str
    scenario_name: str
    description: str
    component_scenario_ids: List[str] = Field(default_factory=list)
    simultaneous_resource_ids: List[str] = Field(default_factory=list)
    shared_dependencies_identified: List[str] = Field(default_factory=list)
    combined_affected_capabilities: List[str] = Field(default_factory=list)
    combined_affected_responsibilities: List[str] = Field(default_factory=list)
    available_fallback_arrangements: List[str] = Field(default_factory=list)
    non_independent_fallbacks: List[str] = Field(default_factory=list)
    capacity_limitations: List[str] = Field(default_factory=list)
    unresolved_assumptions: List[str] = Field(default_factory=list)
    compound_severity: ImpactSeverity = ImpactSeverity.CRITICAL
    evaluated_at: Optional[datetime] = None
    evaluated_by: Optional[str] = None
    created_by: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    disclaimer: str = Field(default=MANDATORY_DISRUPTION_IMPACT_DISCLAIMER)


class CreateCompoundScenarioRequest(BaseModel):
    scenario_name: str
    description: str
    component_scenario_ids: List[str] = Field(default_factory=list)
    simultaneous_resource_ids: List[str] = Field(default_factory=list)


class EvaluateCompoundScenarioRequest(BaseModel):
    include_personnel_constraints: bool = True
    assumed_overlap_hours: float = Field(default=4.0, ge=0.5)
