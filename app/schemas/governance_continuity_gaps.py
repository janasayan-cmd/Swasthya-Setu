"""Phase 80: Continuity Gap and Resilience Weakness Schemas.

Defines schemas and models for:
- Detecting gaps across capabilities, plans, owners, and recovery evidence
- Severity classification and corrective action routing to Phase 54 / Phase 63
"""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.governance_continuity_capability import (
    CLINICAL_SAFETY_CONTINUITY_DISCLAIMER,
)


class ContinuityGapCategory(str, Enum):
    """Classification of continuity gaps and resilience weaknesses."""
    CAPABILITY_WITHOUT_PLAN = "CAPABILITY_WITHOUT_PLAN"
    MISSING_ACCOUNTABLE_OWNER = "MISSING_ACCOUNTABLE_OWNER"
    MISSING_DELEGATED_AUTHORITY = "MISSING_DELEGATED_AUTHORITY"
    UNVALIDATED_RECOVERY_REQUIREMENT = "UNVALIDATED_RECOVERY_REQUIREMENT"
    SPOF_WITHOUT_ALTERNATIVE = "SPOF_WITHOUT_ALTERNATIVE"
    EXPIRED_CONTINUITY_PLAN = "EXPIRED_CONTINUITY_PLAN"
    OVERDUE_EXERCISE = "OVERDUE_EXERCISE"
    FAILED_EXERCISE = "FAILED_EXERCISE"
    UNRESOLVED_RECOVERY_ISSUE = "UNRESOLVED_RECOVERY_ISSUE"
    INCOMPLETE_RECONCILIATION = "INCOMPLETE_RECONCILIATION"
    MISSING_RESTORATION_EVIDENCE = "MISSING_RESTORATION_EVIDENCE"
    STAFFING_COVERAGE_GAP = "STAFFING_COVERAGE_GAP"


class ContinuityGapSeverity(str, Enum):
    """Priority ranking of identified continuity gap."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ContinuityGapStatus(str, Enum):
    """Disposition status of continuity gap finding."""
    DETECTED = "DETECTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    ACTION_REFERRED = "ACTION_REFERRED"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"


class ContinuityGapRecord(BaseModel):
    """Authoritative record for an identified governance resilience gap."""
    model_config = ConfigDict(extra="forbid")

    gap_id: str
    tenant_id: str
    category: ContinuityGapCategory
    affected_capability_ids: List[str] = Field(default_factory=list)
    detection_method: str
    explanation: str
    severity: ContinuityGapSeverity
    recommended_action: str
    status: ContinuityGapStatus
    escalation_destination: str = "PHASE_54_CAPA"
    reviewed_by: Optional[str] = None
    review_notes: Optional[str] = None
    corrective_action_reference: Optional[str] = None
    disclaimer: str = CLINICAL_SAFETY_CONTINUITY_DISCLAIMER
    detected_at: str


class CreateContinuityGapRequest(BaseModel):
    """Request to log an identified continuity gap."""
    model_config = ConfigDict(extra="forbid")

    category: ContinuityGapCategory
    affected_capability_ids: List[str]
    detection_method: str
    explanation: str
    severity: ContinuityGapSeverity = ContinuityGapSeverity.HIGH
    recommended_action: str
    escalation_destination: str = "PHASE_54_CAPA"


class ReviewContinuityGapRequest(BaseModel):
    """Request to review and disposition a continuity gap."""
    model_config = ConfigDict(extra="forbid")

    status: ContinuityGapStatus
    review_notes: str


class ReferGapToCorrectiveActionRequest(BaseModel):
    """Request to formally route gap finding to Phase 54 CAPA or Phase 63 Risk."""
    model_config = ConfigDict(extra="forbid")

    escalation_destination: str = Field(..., description="Target phase e.g. PHASE_54_CAPA, PHASE_63_RISK, PHASE_67_ESCALATION")
    corrective_action_reference: Optional[str] = None
    routing_notes: Optional[str] = None
