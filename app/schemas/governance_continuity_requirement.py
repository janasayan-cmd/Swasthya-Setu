"""Phase 80: Governance Continuity Requirements Schemas.

Defines schemas and models for:
- Required operating hours, recovery targets (RTO, RPO, MTPD, MBCO)
- Staffing, communication, and manual alternative criteria
"""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.governance_continuity_capability import (
    CLINICAL_SAFETY_CONTINUITY_DISCLAIMER,
)


class ContinuityRequirementStatus(str, Enum):
    """Lifecycle status of continuity requirements."""
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    SUPERSEDED = "SUPERSEDED"


class GovernanceContinuityRequirementRecord(BaseModel):
    """Authoritative record defining continuity targets and operational requirements."""
    model_config = ConfigDict(extra="forbid")

    requirement_id: str
    tenant_id: str
    capability_id: str
    required_operating_hours: str
    max_acceptable_interruption_hours: float
    recovery_time_objective_hours: float = Field(..., description="Approved RTO")
    recovery_point_objective_hours: float = Field(..., description="Approved RPO")
    maximum_tolerable_period_disruption_hours: float = Field(..., description="Approved MTPD")
    minimum_continuity_objective: str = Field(..., description="Approved MBCO")
    required_staffing_coverage: str
    required_role_availability: List[str] = Field(default_factory=list)
    required_communication_channels: List[str] = Field(default_factory=list)
    required_supporting_systems: List[str] = Field(default_factory=list)
    required_escalation_arrangements: str
    required_manual_alternatives: str
    evidence_required_to_verify: str
    status: ContinuityRequirementStatus
    approved_by: Optional[str] = None
    approval_reference: Optional[str] = None
    version: int = 1
    disclaimer: str = CLINICAL_SAFETY_CONTINUITY_DISCLAIMER
    created_at: str
    updated_at: str


class CreateContinuityRequirementRequest(BaseModel):
    """Request to define continuity requirements for a governance capability."""
    model_config = ConfigDict(extra="forbid")

    capability_id: str
    required_operating_hours: str = "24x7 Emergency / 08:00-18:00 Routine"
    max_acceptable_interruption_hours: float = 4.0
    recovery_time_objective_hours: float = 2.0
    recovery_point_objective_hours: float = 1.0
    maximum_tolerable_period_disruption_hours: float = 8.0
    minimum_continuity_objective: str = "Maintain immediate clinical risk triage and serious incident notification."
    required_staffing_coverage: str = "At least 1 qualified clinical safety lead and 1 backup delegate on duty."
    required_role_availability: Optional[List[str]] = None
    required_communication_channels: Optional[List[str]] = None
    required_supporting_systems: Optional[List[str]] = None
    required_escalation_arrangements: str = "Escalate to Chief Medical Officer if disruption exceeds 2 hours."
    required_manual_alternatives: str = "Paper-based incident escalation log and cellular phone chain."
    evidence_required_to_verify: str = "Signed offline incident logs and decision continuity records."


class SubmitContinuityRequirementRequest(BaseModel):
    """Request to submit continuity requirements for formal approval."""
    model_config = ConfigDict(extra="forbid")

    submission_notes: Optional[str] = None


class ApproveContinuityRequirementRequest(BaseModel):
    """Request to approve continuity requirements (separation of duties)."""
    model_config = ConfigDict(extra="forbid")

    approval_reference: str
    approval_notes: Optional[str] = None
