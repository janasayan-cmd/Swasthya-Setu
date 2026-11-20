"""Phase 74: Governance Change Adoption Registration Schemas.

Defines schemas and models for:
- Operational adoption registration intake from Phase 73 implementation records
- Operational scope and adoption milestone targets
- Governance change adoption lifecycle and lineage tracking
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class AdoptionRegistrationStatus(str, Enum):
    """Lifecycle status for a registered governance change adoption monitoring initiative."""
    PENDING_BASELINE = "PENDING_BASELINE"
    ACTIVE_MONITORING = "ACTIVE_MONITORING"
    SUSPENDED = "SUSPENDED"
    CONCLUDED = "CONCLUDED"
    DISCONTINUED = "DISCONTINUED"


class OperationalScope(BaseModel):
    """Target operational scope across organizational boundaries."""
    model_config = ConfigDict(extra="forbid")

    facilities: List[str] = Field(default_factory=list, description="Target healthcare facilities or hospital sites")
    departments: List[str] = Field(default_factory=list, description="Target clinical or administrative departments")
    teams: List[str] = Field(default_factory=list, description="Operational units or clinical teams")
    roles: List[str] = Field(default_factory=list, description="Accountable professional roles")
    workflows: List[str] = Field(default_factory=list, description="Specific clinical or governance workflows")


class AdoptionMilestoneTarget(BaseModel):
    """Specific operational milestone to measure routine integration over time."""
    model_config = ConfigDict(extra="forbid")

    milestone_key: str = Field(..., description="Unique key for the milestone")
    title: str = Field(..., description="Descriptive milestone title")
    description: Optional[str] = Field(None, description="Detailed milestone criteria")
    target_date: str = Field(..., description="Expected milestone completion ISO timestamp")
    completed: bool = Field(default=False, description="Whether milestone has been achieved")
    completed_date: Optional[str] = Field(None, description="Achieved ISO timestamp")


class GovernanceChangeAdoptionRecord(BaseModel):
    """Authoritative record for an operational governance change adoption monitoring initiative."""
    model_config = ConfigDict(extra="forbid")

    registration_id: str
    tenant_id: str
    management_review_id: str = Field(..., description="Phase 72 management review reference")
    decision_id: str = Field(..., description="Phase 72 approved decision reference")
    implementation_id: str = Field(..., description="Phase 73 implementation record reference")
    title: str
    change_description: str
    operational_scope: OperationalScope
    accountable_operational_owner_id: str
    adoption_monitoring_owner_id: str
    status: AdoptionRegistrationStatus = AdoptionRegistrationStatus.PENDING_BASELINE
    monitoring_start_date: str
    expected_monitoring_duration_days: int = 90
    current_baseline_version: Optional[str] = None
    active_baseline_id: Optional[str] = None
    adoption_milestones: List[AdoptionMilestoneTarget] = Field(default_factory=list)
    required_evidence_categories: List[str] = Field(default_factory=list)
    limitations_disclosed: List[str] = Field(default_factory=list)
    created_by: str
    created_at: str
    updated_at: str
    version: int = 1


class CreateAdoptionRegistrationRequest(BaseModel):
    """Request payload to register an implemented change for operational adoption monitoring."""
    model_config = ConfigDict(extra="forbid")

    management_review_id: str
    decision_id: str
    implementation_id: str
    title: str = Field(..., min_length=3, max_length=255)
    change_description: str = Field(..., min_length=5)
    operational_scope: OperationalScope = Field(default_factory=OperationalScope)
    accountable_operational_owner_id: str
    adoption_monitoring_owner_id: str
    monitoring_start_date: str
    expected_monitoring_duration_days: int = Field(default=90, ge=7, le=730)
    adoption_milestones: List[AdoptionMilestoneTarget] = Field(default_factory=list)
    required_evidence_categories: List[str] = Field(default_factory=list)
    limitations_disclosed: List[str] = Field(default_factory=list)


class UpdateAdoptionRegistrationRequest(BaseModel):
    """Request payload to update an adoption monitoring initiative."""
    model_config = ConfigDict(extra="forbid")

    title: Optional[str] = Field(None, min_length=3, max_length=255)
    change_description: Optional[str] = Field(None, min_length=5)
    operational_scope: Optional[OperationalScope] = None
    accountable_operational_owner_id: Optional[str] = None
    adoption_monitoring_owner_id: Optional[str] = None
    expected_monitoring_duration_days: Optional[int] = Field(None, ge=7, le=730)
    status: Optional[AdoptionRegistrationStatus] = None
    limitations_disclosed: Optional[List[str]] = None


class AdoptionLineageResponse(BaseModel):
    """Traceability response reconstructing the full governance decision-to-adoption chain."""
    model_config = ConfigDict(extra="forbid")

    registration_id: str
    tenant_id: str
    management_review_id: str
    decision_id: str
    implementation_id: str
    active_baseline_version: Optional[str] = None
    baselines_count: int = 0
    monitoring_plans_count: int = 0
    evidence_count: int = 0
    indicators_count: int = 0
    drift_signals_count: int = 0
    sustainability_assessments_count: int = 0
    exceptions_count: int = 0
    consequences_count: int = 0
    escalations_count: int = 0
    lineage_nodes: List[Dict[str, Any]] = Field(default_factory=list)
