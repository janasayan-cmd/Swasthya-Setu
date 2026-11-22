"""Phase 80: Governance Continuity Plan Management Schemas.

Defines schemas and models for:
- Version-controlled continuity plans covering critical governance capabilities
- Activation conditions, alternative operating procedures, restoration criteria
- Material revision audit history
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.governance_continuity_capability import (
    CLINICAL_SAFETY_CONTINUITY_DISCLAIMER,
)


class ContinuityPlanStatus(str, Enum):
    """Lifecycle states of a governance continuity plan."""
    DRAFT = "DRAFT"
    UNDER_REVIEW = "UNDER_REVIEW"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    ACTIVE = "ACTIVE"
    UNDER_REVISION = "UNDER_REVISION"
    SUPERSEDED = "SUPERSEDED"
    RETIRED = "RETIRED"


class GovernanceContinuityPlanRecord(BaseModel):
    """Authoritative record for a clinical safety governance continuity plan."""
    model_config = ConfigDict(extra="forbid")

    plan_id: str
    tenant_id: str
    title: str
    organizational_scope: Dict[str, Any] = Field(default_factory=dict)
    covered_capability_ids: List[str] = Field(default_factory=list)
    plan_owner_id: str
    authorized_approver_id: Optional[str] = None
    activation_conditions: str
    disruption_categories: List[str] = Field(default_factory=list)
    escalation_procedures: str
    communication_arrangements: str
    alternative_operating_procedures: str
    delegation_arrangements: str
    required_resources: str
    recovery_priorities: str
    restoration_criteria: str
    verification_requirements: str
    testing_schedule: str
    review_schedule: str
    status: ContinuityPlanStatus
    version: int = 1
    approval_reference: Optional[str] = None
    approval_history: List[Dict[str, Any]] = Field(default_factory=list)
    version_history: List[Dict[str, Any]] = Field(default_factory=list)
    disclaimer: str = CLINICAL_SAFETY_CONTINUITY_DISCLAIMER
    created_at: str
    updated_at: str


class CreateContinuityPlanRequest(BaseModel):
    """Request to create a new governance continuity plan draft."""
    model_config = ConfigDict(extra="forbid")

    title: str
    organizational_scope: Optional[Dict[str, Any]] = None
    covered_capability_ids: List[str]
    plan_owner_id: str
    activation_conditions: str
    disruption_categories: List[str]
    escalation_procedures: str
    communication_arrangements: str
    alternative_operating_procedures: str
    delegation_arrangements: str
    required_resources: str = "Emergency mobile devices, paper forms, secondary communication bridge."
    recovery_priorities: str = "Priority 1: Incident Reporting; Priority 2: Risk Disposition."
    restoration_criteria: str = "Primary electronic workflow confirmed operational with dual-factor verification."
    verification_requirements: str = "Clinical safety officer independent sign-off and reconciliation audit."
    testing_schedule: str = "Bi-annual tabletop simulation and communication drill."
    review_schedule: str = "Annual review or following any major disruption."


class UpdateContinuityPlanRequest(BaseModel):
    """Request to update draft continuity plan."""
    model_config = ConfigDict(extra="forbid")

    title: Optional[str] = None
    covered_capability_ids: Optional[List[str]] = None
    activation_conditions: Optional[str] = None
    disruption_categories: Optional[List[str]] = None
    escalation_procedures: Optional[str] = None
    communication_arrangements: Optional[str] = None
    alternative_operating_procedures: Optional[str] = None
    delegation_arrangements: Optional[str] = None
    required_resources: Optional[str] = None
    restoration_criteria: Optional[str] = None


class SubmitContinuityPlanRequest(BaseModel):
    """Request to submit continuity plan for formal governance approval."""
    model_config = ConfigDict(extra="forbid")

    submission_notes: Optional[str] = None


class ApproveContinuityPlanRequest(BaseModel):
    """Request to formally approve a continuity plan (enforces separation of duties)."""
    model_config = ConfigDict(extra="forbid")

    approval_reference: str
    approval_notes: Optional[str] = None


class ReviseContinuityPlanRequest(BaseModel):
    """Request to revise an approved continuity plan preserving baseline in version history."""
    model_config = ConfigDict(extra="forbid")

    revision_reason: str
    updated_alternative_procedures: Optional[str] = None
    updated_activation_conditions: Optional[str] = None
    updated_restoration_criteria: Optional[str] = None
