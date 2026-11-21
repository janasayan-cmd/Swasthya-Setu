"""Phase 75: Portfolio Scheduling, Cumulative Impact & Resource Coordination Schemas.

Defines schemas and models for:
- Portfolio-level scheduling assessments and sequencing recommendations (advisory only)
- Cumulative operational impact assessments across facilities, departments, and workflows
- Resource dependency visibility without unsupported capacity assumptions
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ScheduleAssessmentRecord(BaseModel):
    """Authoritative evaluation of cross-initiative scheduling coordination."""
    model_config = ConfigDict(extra="forbid")

    assessment_id: str
    portfolio_id: str
    tenant_id: str
    assessment_date: str
    overlapping_initiatives: List[Dict[str, Any]] = Field(default_factory=list)
    sequencing_recommendations: List[str] = Field(
        default_factory=list,
        description="Advisory sequencing suggestions. Does not independently modify Phase 73 implementation dates."
    )
    assessed_by: str
    created_at: str


class CreateScheduleAssessmentRequest(BaseModel):
    """Request payload to perform a portfolio schedule assessment."""
    model_config = ConfigDict(extra="forbid")

    assessment_date: Optional[str] = None
    target_facilities: List[str] = Field(default_factory=list)
    target_departments: List[str] = Field(default_factory=list)


class CumulativeImpactAssessmentRecord(BaseModel):
    """Evaluation of cumulative operational disruption and burden across concurrent changes."""
    model_config = ConfigDict(extra="forbid")

    assessment_id: str
    portfolio_id: str
    tenant_id: str
    assessment_period: str
    included_initiative_ids: List[str] = Field(default_factory=list)
    affected_facilities: List[str] = Field(default_factory=list)
    affected_departments: List[str] = Field(default_factory=list)
    shared_workflows: List[str] = Field(default_factory=list)
    concurrent_changes_count: int = 0
    estimated_training_workload_hours: float = 0.0
    procedure_update_count: int = 0
    disruption_risk_level: str = "MEDIUM"  # LOW, MEDIUM, HIGH, ELEVATED
    data_coverage_percentage: float = 100.0
    limitations_disclosed: List[str] = Field(default_factory=list)
    assumptions_noted: List[str] = Field(default_factory=list)
    clinical_safety_notice: str = (
        "Operational burden assessment only. Does not predict or evaluate clinical safety outcomes."
    )
    assessor_id: str
    created_at: str


class CreateImpactAssessmentRequest(BaseModel):
    """Request payload to calculate cumulative operational impact."""
    model_config = ConfigDict(extra="forbid")

    assessment_period: str = Field(..., min_length=3)
    included_initiative_ids: List[str] = Field(default_factory=list)
    limitations_disclosed: List[str] = Field(default_factory=list)
    assumptions_noted: List[str] = Field(default_factory=list)


class ResourceDependencyRecord(BaseModel):
    """Visibility into shared subject-matter experts, training, and technical resources."""
    model_config = ConfigDict(extra="forbid")

    resource_dependency_id: str
    portfolio_id: str
    tenant_id: str
    initiative_ids: List[str] = Field(default_factory=list)
    resource_name: str
    resource_category: str  # SME, CLINICAL_TRAINER, INTEGRATION_ENGINEER, SYSTEM_AVAILABILITY_WINDOW, FACILITY_SIMULATION
    capacity_status: str = "UNKNOWN"  # AVAILABLE, CONSTRAINED, BOTTLENECK, UNKNOWN
    notes: Optional[str] = None
    created_by: str
    created_at: str


class CreateResourceDependencyRequest(BaseModel):
    """Request payload to register a resource dependency."""
    model_config = ConfigDict(extra="forbid")

    initiative_ids: List[str] = Field(default_factory=list)
    resource_name: str = Field(..., min_length=2, max_length=255)
    resource_category: str = Field(..., min_length=2)
    capacity_status: str = Field(default="UNKNOWN")
    notes: Optional[str] = None
