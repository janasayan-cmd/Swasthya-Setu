"""Phase 86: Resource Capacity Requirements Schemas.

Defines minimum operating requirements, capacity evaluations, and shortfall tracking
for resources supporting critical clinical safety governance capabilities.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

from app.schemas.governance_resource_common import (
    MANDATORY_RESOURCE_DEPENDENCY_DISCLAIMER,
)


class CapacityRequirementRecord(BaseModel):
    requirement_id: str
    tenant_id: str
    governance_capability_ref: str
    resource_id: str
    minimum_availability_pct: float = Field(default=99.0)
    max_acceptable_interruption_minutes: float = Field(default=60.0)
    min_service_capacity_pct: Optional[float] = None
    min_information_accessibility_pct: Optional[float] = None
    required_communication_capacity: Optional[str] = None
    required_evidence_retrieval_capacity: Optional[str] = None
    max_acceptable_dependency_concentration: Optional[int] = None
    continuity_requirement_ref: Optional[str] = None
    required_capacity_note: Optional[str] = None
    reported_capacity_pct: Optional[float] = None
    verified_capacity_pct: Optional[float] = None
    capacity_shortfall_pct: Optional[float] = None
    evidence_freshness_hours: Optional[float] = None
    applicable_scenario: Optional[str] = None
    evaluation_status: str = "NOT_EVALUATED"
    last_evaluated_at: Optional[datetime] = None
    created_by: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    disclaimer: str = Field(default=MANDATORY_RESOURCE_DEPENDENCY_DISCLAIMER)


class CreateCapacityRequirementRequest(BaseModel):
    governance_capability_ref: str
    resource_id: str
    minimum_availability_pct: float = Field(default=99.0)
    max_acceptable_interruption_minutes: float = Field(default=60.0)
    min_service_capacity_pct: Optional[float] = None
    min_information_accessibility_pct: Optional[float] = None
    required_communication_capacity: Optional[str] = None
    max_acceptable_dependency_concentration: Optional[int] = None
    continuity_requirement_ref: Optional[str] = None
    required_capacity_note: Optional[str] = None


class EvaluateCapacityRequest(BaseModel):
    reported_capacity_pct: Optional[float] = None
    verified_capacity_pct: Optional[float] = None
    evidence_freshness_hours: Optional[float] = None
    applicable_scenario: Optional[str] = None
    evaluation_notes: Optional[str] = None
