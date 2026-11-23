"""Phase 87: Disruption Scenario Registry Schemas.

Defines schemas for registering, updating, and approving configurable disruption scenarios.
Scenarios represent hypothetical stress conditions and must never be treated as live incidents.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

from app.schemas.governance_disruption_common import (
    MANDATORY_DISRUPTION_IMPACT_DISCLAIMER,
    DisruptionDurationType,
    DisruptionScenarioCategory,
    ImpactSeverity,
    ScenarioReviewStatus,
)


class DisruptionScenarioRecord(BaseModel):
    scenario_id: str
    tenant_id: str
    scenario_name: str
    description: str
    category: DisruptionScenarioCategory
    organizational_scope: str = "ORGANIZATION"
    affected_resource_refs: List[str] = Field(default_factory=list)
    affected_capability_refs: List[str] = Field(default_factory=list)
    affected_responsibility_refs: List[str] = Field(default_factory=list)
    initial_disruption_conditions: str
    duration_type: DisruptionDurationType = DisruptionDurationType.EXTENDED_INTERRUPTION
    assumed_duration_hours: float = Field(default=4.0, ge=0.1)
    severity_assumption: ImpactSeverity = ImpactSeverity.HIGH
    expected_operating_constraints: List[str] = Field(default_factory=list)
    potential_recovery_conditions: Optional[str] = None
    evidence_refs: List[str] = Field(default_factory=list)
    live_incident_ref: Optional[str] = None
    scenario_version: str = "1.0"
    scenario_owner: str
    review_status: ScenarioReviewStatus = ScenarioReviewStatus.DRAFT
    approval_ref: Optional[str] = None
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    created_by: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    disclaimer: str = Field(default=MANDATORY_DISRUPTION_IMPACT_DISCLAIMER)


class CreateDisruptionScenarioRequest(BaseModel):
    scenario_name: str
    description: str
    category: DisruptionScenarioCategory
    organizational_scope: str = "ORGANIZATION"
    affected_resource_refs: List[str] = Field(default_factory=list)
    affected_capability_refs: List[str] = Field(default_factory=list)
    affected_responsibility_refs: List[str] = Field(default_factory=list)
    initial_disruption_conditions: str
    duration_type: DisruptionDurationType = DisruptionDurationType.EXTENDED_INTERRUPTION
    assumed_duration_hours: float = Field(default=4.0, ge=0.1)
    severity_assumption: ImpactSeverity = ImpactSeverity.HIGH
    expected_operating_constraints: List[str] = Field(default_factory=list)
    potential_recovery_conditions: Optional[str] = None
    evidence_refs: List[str] = Field(default_factory=list)
    live_incident_ref: Optional[str] = None


class UpdateDisruptionScenarioRequest(BaseModel):
    scenario_name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[DisruptionScenarioCategory] = None
    organizational_scope: Optional[str] = None
    affected_resource_refs: Optional[List[str]] = None
    affected_capability_refs: Optional[List[str]] = None
    affected_responsibility_refs: Optional[List[str]] = None
    initial_disruption_conditions: Optional[str] = None
    duration_type: Optional[DisruptionDurationType] = None
    assumed_duration_hours: Optional[float] = None
    severity_assumption: Optional[ImpactSeverity] = None
    expected_operating_constraints: Optional[List[str]] = None
    potential_recovery_conditions: Optional[str] = None
    evidence_refs: Optional[List[str]] = None
    live_incident_ref: Optional[str] = None


class SubmitDisruptionScenarioRequest(BaseModel):
    submission_notes: Optional[str] = None


class ApproveDisruptionScenarioRequest(BaseModel):
    approval_ref: str
    approval_notes: Optional[str] = None
