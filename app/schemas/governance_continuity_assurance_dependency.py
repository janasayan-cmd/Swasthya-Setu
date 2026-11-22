"""Phase 81: Critical Dependency Resilience Assurance Schemas.

Evaluates dependencies from Phase 80 (personnel, system, information, external),
identifies single points of failure (SPOFs), and verifies tested alternative availability.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.schemas.governance_continuity_assurance_framework import (
    MANDATORY_GOVERNANCE_CONTINUITY_ASSURANCE_DISCLAIMER,
)


class DependencyResilienceEvaluation(str, Enum):
    RESILIENT_TESTED = "RESILIENT_TESTED"
    DOCUMENTED_UNTESTED = "DOCUMENTED_UNTESTED"
    SINGLE_POINT_OF_FAILURE = "SINGLE_POINT_OF_FAILURE"
    ALTERNATIVE_UNAVAILABLE = "ALTERNATIVE_UNAVAILABLE"
    EVIDENCE_STALE = "EVIDENCE_STALE"
    UNABLE_TO_DETERMINE = "UNABLE_TO_DETERMINE"


class AssessDependencyResilienceRequest(BaseModel):
    dependency_id: str  # References Phase 80 GovernanceContinuityDependencyRecord
    source_capability_id: str
    dependency_type: str  # PERSONNEL, SYSTEM, INFORMATION, EXTERNAL_PARTNER
    criticality: str  # CRITICAL, HIGH, MEDIUM, LOW
    has_alternative: bool
    alternative_arrangement_ref: Optional[str] = None
    testing_evidence_ref: Optional[str] = None
    evidence_timestamp: Optional[datetime] = None
    external_provider_sla_ref: Optional[str] = None
    notes: Optional[str] = None


class DependencyResilienceAssuranceRecord(BaseModel):
    assessment_id: str
    dependency_id: str
    source_capability_id: str
    dependency_type: str
    criticality: str
    has_alternative: bool
    alternative_arrangement_ref: Optional[str] = None
    testing_evidence_ref: Optional[str] = None
    evidence_timestamp: Optional[datetime] = None
    is_spof: bool = False
    resilience_evaluation: DependencyResilienceEvaluation = DependencyResilienceEvaluation.UNABLE_TO_DETERMINE
    unresolved_limitations: Optional[str] = None
    recommended_follow_up: List[str] = Field(default_factory=list)
    evaluated_by: str
    evaluated_at: datetime
    tenant_id: str = "default"
    disclaimer: str = MANDATORY_GOVERNANCE_CONTINUITY_ASSURANCE_DISCLAIMER
