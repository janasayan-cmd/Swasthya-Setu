"""Phase 79: Strategic Change Signals Schemas.

Defines schemas and models for:
- Detecting strategic change signals from existing governance evidence
- Classifying severity and disposition (advisory only; clinical risks routed to Phase 63)
"""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.governance_strategy_execution_monitoring import (
    CLINICAL_SAFETY_MONITORING_DISCLAIMER,
)


class SignalCategory(str, Enum):
    """Classification of strategic execution change signals."""
    REPEATED_MILESTONE_DELAYS = "REPEATED_MILESTONE_DELAYS"
    PERSISTENT_DEPENDENCY_FAILURES = "PERSISTENT_DEPENDENCY_FAILURES"
    UNRESOLVED_APPROVAL_REQUESTS = "UNRESOLVED_APPROVAL_REQUESTS"
    RECURRING_RESOURCE_CONSTRAINTS = "RECURRING_RESOURCE_CONSTRAINTS"
    DECLINING_CAPABILITY_INDICATORS = "DECLINING_CAPABILITY_INDICATORS"
    OPERATIONAL_ADOPTION_FAILURES = "OPERATIONAL_ADOPTION_FAILURES"
    BENEFIT_REALIZATION_GAPS = "BENEFIT_REALIZATION_GAPS"
    MATERIAL_MATURITY_CHANGES = "MATERIAL_MATURITY_CHANGES"
    INCREASING_EXCEPTIONS = "INCREASING_EXCEPTIONS"


class SignalSeverity(str, Enum):
    """Priority / severity ranking of detected strategic signal."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class SignalDisposition(str, Enum):
    """Review and disposition status of a detected signal."""
    ACTIVE = "ACTIVE"
    INVESTIGATING = "INVESTIGATING"
    ESCALATED_PHASE_63 = "ESCALATED_PHASE_63"
    ESCALATED_PHASE_49 = "ESCALATED_PHASE_49"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class StrategicChangeSignalRecord(BaseModel):
    """Authoritative record for an identified strategic change signal."""
    model_config = ConfigDict(extra="forbid")

    signal_id: str
    tenant_id: str
    category: SignalCategory
    affected_roadmap_ids: List[str] = Field(default_factory=list)
    source_references: List[str] = Field(default_factory=list)
    detection_rule: str
    observation_period: str
    severity: SignalSeverity
    evidence_limitations: str = ""
    strategic_implication: str
    recommended_destination: str
    disposition: SignalDisposition
    reviewed_by: Optional[str] = None
    review_notes: Optional[str] = None
    disclaimer: str = CLINICAL_SAFETY_MONITORING_DISCLAIMER
    detected_at: str


class CreateSignalRequest(BaseModel):
    """Request to log a detected strategic change signal."""
    model_config = ConfigDict(extra="forbid")

    category: SignalCategory
    affected_roadmap_ids: List[str]
    source_references: Optional[List[str]] = None
    detection_rule: str
    observation_period: str
    severity: SignalSeverity = SignalSeverity.HIGH
    evidence_limitations: Optional[str] = ""
    strategic_implication: str
    recommended_destination: str = "PHASE_78_ROADMAP_REVISION"


class ReviewSignalRequest(BaseModel):
    """Request to review and disposition a strategic change signal."""
    model_config = ConfigDict(extra="forbid")

    disposition: SignalDisposition
    review_notes: str
