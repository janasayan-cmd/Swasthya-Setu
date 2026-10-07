"""Phase 51: Controlled Safety Change Request & Impact Assessment Schemas.

Defines schemas for governed safety changes, multi-dimensional clinical impact assessment,
version preservation (current, proposed, implemented, validated), and rollback planning.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.safety_governance import (
    AITraceabilityMetadata,
    ChangeRequestState,
    RolloutScopeType,
    SafetyChangeTargetType,
)


class ImpactAreaEvaluation(BaseModel):
    """Evaluation of potential impact across a specific safety dimension."""

    model_config = ConfigDict(extra="ignore")

    area: str  # e.g., clinical_workflow, medication_safety, triage, safety_gates, privacy, data_integrity
    potential_risk: str  # e.g., NONE, LOW, MEDIUM, HIGH
    assessment_summary: str
    compensating_controls: List[str] = Field(default_factory=list)


class ImpactAssessment(BaseModel):
    """Multi-dimensional impact assessment required prior to change approval."""

    model_config = ConfigDict(extra="ignore")

    evaluations: List[ImpactAreaEvaluation] = Field(default_factory=list)
    overall_impact_summary: str
    assessed_by_id: str
    assessed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SafetyChangeCreateRequest(BaseModel):
    """Request to initiate a controlled safety change request."""

    model_config = ConfigDict(extra="ignore")

    risk_id: str
    title: str = Field(min_length=3, max_length=255)
    description: str = Field(min_length=10)
    target_type: SafetyChangeTargetType
    affected_subsystem: str
    current_version: str
    proposed_version: str
    proposed_change_details: Dict[str, Any]
    reason: str
    expected_benefit: str
    possible_adverse_effects: List[str] = Field(default_factory=list)
    dependencies: List[str] = Field(default_factory=list)
    implementation_scope: RolloutScopeType = Field(default=RolloutScopeType.INTERNAL)
    scope_details: Dict[str, Any] = Field(default_factory=dict)
    rollback_plan: Dict[str, Any] = Field(description="Must define concrete reversion strategy")
    validation_plan: Dict[str, Any] = Field(description="Must define acceptance tests and safety checks")
    monitoring_plan: Dict[str, Any] = Field(description="Must define observation window and safety signal triggers")
    impact_assessment: Optional[ImpactAssessment] = None
    is_emergency: bool = Field(default=False)
    emergency_justification: Optional[str] = None
    expected_risk_version: Optional[int] = None
    idempotency_key: Optional[str] = None
    ai_metadata: Optional[AITraceabilityMetadata] = None


class SafetyChangeRecord(BaseModel):
    """Authoritative controlled safety change request record."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: f"chg-{uuid.uuid4().hex[:12]}")
    risk_id: str
    risk_version_at_creation: int
    version: int = Field(default=1, description="Version of the change request itself")

    title: str
    description: str
    target_type: SafetyChangeTargetType
    affected_subsystem: str
    state: ChangeRequestState = Field(default=ChangeRequestState.DRAFT)

    # Version tracking across lifecycle
    current_version: str
    proposed_version: str
    implemented_version: Optional[str] = None
    validated_version: Optional[str] = None

    proposed_change_details: Dict[str, Any]
    reason: str
    expected_benefit: str
    possible_adverse_effects: List[str] = Field(default_factory=list)
    dependencies: List[str] = Field(default_factory=list)

    implementation_scope: RolloutScopeType
    scope_details: Dict[str, Any] = Field(default_factory=dict)

    rollback_plan: Dict[str, Any]
    validation_plan: Dict[str, Any]
    monitoring_plan: Dict[str, Any]
    impact_assessment: Optional[ImpactAssessment] = None

    latest_approval_id: Optional[str] = None
    latest_implementation_id: Optional[str] = None
    latest_validation_id: Optional[str] = None
    latest_rollback_id: Optional[str] = None

    created_by_id: str
    created_by_role: str
    organization_id: Optional[str] = None
    facility_id: Optional[str] = None

    is_emergency: bool = Field(default=False)
    emergency_justification: Optional[str] = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ai_metadata: Optional[AITraceabilityMetadata] = None
