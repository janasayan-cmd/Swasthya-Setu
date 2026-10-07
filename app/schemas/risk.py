"""Phase 51: Clinical Safety Risk Registration, History & Lifecycle Schemas.

Defines schemas for registering safety findings as governed risks,
tracking risk provenance, history, residual risk metrics, closure, and reopening.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.safety_governance import (
    AITraceabilityMetadata,
    RiskCategory,
    RiskImpact,
    RiskLikelihood,
    RiskSeverity,
    RiskSourceType,
    RiskState,
)


class RiskSourceReference(BaseModel):
    """Provenance pointer to the authoritative origin of this risk."""

    model_config = ConfigDict(extra="ignore")

    source_type: RiskSourceType
    source_id: str = Field(description="Foreign ID (e.g. inc-123, sig-456, rec-789)")
    external_reference: Optional[str] = None
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RiskCreateRequest(BaseModel):
    """Client request to register a potential safety risk."""

    model_config = ConfigDict(extra="ignore")

    title: str = Field(min_length=3, max_length=255)
    description: str = Field(min_length=10)
    category: RiskCategory
    initial_severity: RiskSeverity = Field(default=RiskSeverity.MEDIUM)
    initial_likelihood: RiskLikelihood = Field(default=RiskLikelihood.UNKNOWN)
    initial_impact: RiskImpact = Field(default=RiskImpact.UNKNOWN)
    sources: List[RiskSourceReference] = Field(default_factory=list)
    affected_subsystem: Optional[str] = None
    affected_workflow: Optional[str] = None
    affected_provider: Optional[str] = None
    organization_id: Optional[str] = None
    facility_id: Optional[str] = None
    idempotency_key: Optional[str] = None
    ai_metadata: Optional[AITraceabilityMetadata] = None


class RiskHistoryEntry(BaseModel):
    """Immutable audit trail entry for risk state and version transitions."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: f"rhist-{uuid.uuid4().hex[:12]}")
    risk_id: str
    version: int
    previous_state: Optional[RiskState] = None
    new_state: RiskState
    action: str
    actor_id: str
    actor_role: str
    reason: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RiskRecord(BaseModel):
    """Authoritative clinical safety risk domain entity."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: f"risk-{uuid.uuid4().hex[:12]}")
    version: int = Field(default=1, description="Monotonically increasing version for concurrency control")
    title: str
    description: str
    category: RiskCategory
    state: RiskState = Field(default=RiskState.IDENTIFIED)

    # Initial risk evaluation
    initial_severity: RiskSeverity
    initial_likelihood: RiskLikelihood
    initial_impact: RiskImpact

    # Residual risk evaluation (updated upon structured assessment/mitigation)
    residual_severity: Optional[RiskSeverity] = None
    residual_likelihood: Optional[RiskLikelihood] = None
    residual_impact: Optional[RiskImpact] = None

    sources: List[RiskSourceReference] = Field(default_factory=list)
    affected_subsystem: Optional[str] = None
    affected_workflow: Optional[str] = None
    affected_provider: Optional[str] = None

    organization_id: Optional[str] = None
    facility_id: Optional[str] = None

    created_by_id: str
    created_by_role: str

    latest_assessment_id: Optional[str] = None
    latest_acceptance_id: Optional[str] = None
    linked_mitigation_ids: List[str] = Field(default_factory=list)
    linked_change_request_ids: List[str] = Field(default_factory=list)
    evidence_references: List[Dict[str, Any]] = Field(default_factory=list)

    # Closure metadata
    is_closed: bool = Field(default=False)
    closed_at: Optional[datetime] = None
    closed_by_id: Optional[str] = None
    closed_reason: Optional[str] = None

    # Reopening metadata
    reopened_at: Optional[datetime] = None
    reopened_by_id: Optional[str] = None
    reopened_reason: Optional[str] = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ai_metadata: Optional[AITraceabilityMetadata] = None


class RiskCloseRequest(BaseModel):
    """Request to close a risk after satisfying all governance criteria."""

    model_config = ConfigDict(extra="ignore")

    reason: str = Field(min_length=5)
    verification_notes: str = Field(min_length=5)
    expected_version: Optional[int] = None


class RiskReopenRequest(BaseModel):
    """Request to reopen a closed risk due to recurrence or new findings."""

    model_config = ConfigDict(extra="ignore")

    reason: str = Field(min_length=5)
    new_evidence: List[Dict[str, Any]] = Field(default_factory=list)
    expected_version: Optional[int] = None


class RiskReassessRequest(BaseModel):
    """Request to trigger formal reassessment of an active risk."""

    model_config = ConfigDict(extra="ignore")

    trigger_reason: str = Field(min_length=5)
    new_evidence: List[Dict[str, Any]] = Field(default_factory=list)
    expected_version: Optional[int] = None
