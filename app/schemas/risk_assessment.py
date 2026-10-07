"""Phase 51: Structured Clinical Risk Assessment & Residual Risk Schemas.

Defines schemas for explicit risk assessment, evaluation of existing controls,
residual-risk reduction metrics, and assessment versioning.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.safety_governance import (
    AITraceabilityMetadata,
    RiskCategory,
    RiskImpact,
    RiskLikelihood,
    RiskSeverity,
)


class ControlEffectiveness(str, Enum):
    """Evaluated effectiveness of an existing safety barrier or control."""

    INEFFECTIVE = "INEFFECTIVE"
    PARTIALLY_EFFECTIVE = "PARTIALLY_EFFECTIVE"
    EFFECTIVE = "EFFECTIVE"
    UNKNOWN = "UNKNOWN"


class ExistingControlEvaluation(BaseModel):
    """Detailed evaluation of an active safety control or barrier."""

    model_config = ConfigDict(extra="ignore")

    control_name: str
    control_type: str  # e.g., "AUTOMATED_SAFETY_GATE", "HUMAN_DOUBLE_CHECK", "VALIDATION_RULE"
    effectiveness: ControlEffectiveness
    notes: Optional[str] = None


class RiskAssessmentCreateRequest(BaseModel):
    """Request to record a structured risk assessment."""

    model_config = ConfigDict(extra="ignore")

    category: RiskCategory
    severity: RiskSeverity
    likelihood: RiskLikelihood
    impact: RiskImpact

    # Residual risk evaluation
    residual_severity: RiskSeverity
    residual_likelihood: RiskLikelihood
    residual_impact: RiskImpact

    affected_system: Optional[str] = None
    affected_workflow: Optional[str] = None
    affected_provider: Optional[str] = None
    affected_configuration: Optional[str] = None
    affected_scope: Optional[str] = None

    evidence: List[Dict[str, Any]] = Field(default_factory=list)
    existing_controls: List[ExistingControlEvaluation] = Field(default_factory=list)
    mitigation_recommendation: Optional[str] = None
    limitations: List[str] = Field(default_factory=list)
    assessment_notes: Optional[str] = None
    expected_version: Optional[int] = None
    idempotency_key: Optional[str] = None
    ai_metadata: Optional[AITraceabilityMetadata] = None


class RiskAssessmentRecord(BaseModel):
    """Immutable record of an authorized risk assessment."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: f"asm-{uuid.uuid4().hex[:12]}")
    risk_id: str
    assessment_version: int = Field(default=1)

    category: RiskCategory
    severity: RiskSeverity
    likelihood: RiskLikelihood
    impact: RiskImpact

    residual_severity: RiskSeverity
    residual_likelihood: RiskLikelihood
    residual_impact: RiskImpact

    affected_system: Optional[str] = None
    affected_workflow: Optional[str] = None
    affected_provider: Optional[str] = None
    affected_configuration: Optional[str] = None
    affected_scope: Optional[str] = None

    evidence: List[Dict[str, Any]] = Field(default_factory=list)
    existing_controls: List[ExistingControlEvaluation] = Field(default_factory=list)
    mitigation_recommendation: Optional[str] = None
    limitations: List[str] = Field(default_factory=list)

    assessor_id: str
    assessor_role: str
    assessed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    assessment_notes: Optional[str] = None
    ai_metadata: Optional[AITraceabilityMetadata] = None
