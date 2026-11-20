"""Phase 74: Adoption Monitoring Plan Schemas.

Defines schemas and models for:
- Operational adoption monitoring plans
- Multi-level organizational monitoring scope
- Verification responsibilities, escalation thresholds, and end criteria
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.governance_change_adoption_registration import OperationalScope


class MonitoringPlanStatus(str, Enum):
    """Lifecycle status of an adoption monitoring plan."""
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    CONCLUDED = "CONCLUDED"


class EscalationThresholdConfig(BaseModel):
    """Configurable thresholds that trigger automatic escalation or alerts."""
    model_config = ConfigDict(extra="forbid")

    max_unverified_evidence_days: int = Field(default=14, description="Days an evidence item can stay unverified before alert")
    min_indicator_achievement_pct: float = Field(default=80.0, description="Minimum percentage of indicators achieved before flagging concern")
    max_unresolved_drift_signals: int = Field(default=3, description="Number of unresolved drift signals triggering escalation")
    max_days_without_monitoring_data: int = Field(default=30, description="Days without submitted evidence triggering stale alert")


class AdoptionMonitoringPlanRecord(BaseModel):
    """Authoritative operational adoption monitoring plan."""
    model_config = ConfigDict(extra="forbid")

    plan_id: str
    registration_id: str
    tenant_id: str
    title: str
    monitoring_objectives: List[str] = Field(default_factory=list)
    organizational_scope: OperationalScope = Field(default_factory=OperationalScope)
    baseline_id: str = Field(..., description="Approved baseline reference")
    baseline_version: str

    # Schedule & cadence
    monitoring_schedule_start: str
    monitoring_schedule_end: Optional[str] = None
    monitoring_frequency: str = "WEEKLY"  # DAILY, WEEKLY, BIWEEKLY, MONTHLY, QUARTERLY

    # Operational owners & verification
    responsible_operational_owner_id: str
    independent_verifier_role: Optional[str] = None
    escalation_thresholds: EscalationThresholdConfig = Field(default_factory=EscalationThresholdConfig)

    # Reporting and end criteria
    reporting_cadence: str = "MONTHLY"
    monitoring_end_criteria: List[str] = Field(default_factory=list)
    known_limitations: List[str] = Field(default_factory=list)

    # Lifecycle
    status: MonitoringPlanStatus = MonitoringPlanStatus.DRAFT
    created_by: str
    activated_by: Optional[str] = None
    activated_at: Optional[str] = None
    created_at: str
    updated_at: str


class CreateMonitoringPlanRequest(BaseModel):
    """Request payload to create an adoption monitoring plan."""
    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=3, max_length=255)
    monitoring_objectives: List[str] = Field(default_factory=list)
    organizational_scope: OperationalScope = Field(default_factory=OperationalScope)
    baseline_id: str
    monitoring_schedule_start: str
    monitoring_schedule_end: Optional[str] = None
    monitoring_frequency: str = Field(default="WEEKLY")
    responsible_operational_owner_id: str
    independent_verifier_role: Optional[str] = None
    escalation_thresholds: EscalationThresholdConfig = Field(default_factory=EscalationThresholdConfig)
    reporting_cadence: str = Field(default="MONTHLY")
    monitoring_end_criteria: List[str] = Field(default_factory=list)
    known_limitations: List[str] = Field(default_factory=list)


class UpdateMonitoringPlanRequest(BaseModel):
    """Request payload to update a monitoring plan."""
    model_config = ConfigDict(extra="forbid")

    title: Optional[str] = None
    monitoring_objectives: Optional[List[str]] = None
    organizational_scope: Optional[OperationalScope] = None
    monitoring_schedule_end: Optional[str] = None
    monitoring_frequency: Optional[str] = None
    responsible_operational_owner_id: Optional[str] = None
    independent_verifier_role: Optional[str] = None
    escalation_thresholds: Optional[EscalationThresholdConfig] = None
    reporting_cadence: Optional[str] = None
    monitoring_end_criteria: Optional[List[str]] = None
    known_limitations: Optional[List[str]] = None


class ActivateMonitoringPlanRequest(BaseModel):
    """Request payload to activate a monitoring plan."""
    model_config = ConfigDict(extra="forbid")

    activation_notes: Optional[str] = None
