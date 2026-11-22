"""Phase 80: Governance Continuity Activation Coordination Schemas.

Defines schemas and models for:
- Human-authorized continuity plan activation requests and decisions
- Tracking coordinator acknowledgement and timeline
- Deactivation of continuity arrangements
"""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.governance_continuity_capability import (
    CLINICAL_SAFETY_CONTINUITY_DISCLAIMER,
)


class ContinuityActivationStatus(str, Enum):
    """Lifecycle states of a continuity plan activation."""
    PROPOSED = "PROPOSED"
    UNDER_ASSESSMENT = "UNDER_ASSESSMENT"
    APPROVED = "APPROVED"
    ACTIVATED = "ACTIVATED"
    PARTIALLY_ACTIVATED = "PARTIALLY_ACTIVATED"
    REJECTED = "REJECTED"
    DEACTIVATED = "DEACTIVATED"
    CLOSED = "CLOSED"


class GovernanceContinuityActivationRecord(BaseModel):
    """Authoritative record for continuity plan activation."""
    model_config = ConfigDict(extra="forbid")

    activation_id: str
    tenant_id: str
    triggering_disruption_id: str
    affected_capability_ids: List[str] = Field(default_factory=list)
    applicable_plan_id: str
    plan_version: int
    activation_requestor_id: str
    authorized_decision_maker_id: Optional[str] = None
    decision_timestamp: Optional[str] = None
    status: ContinuityActivationStatus
    decision_rationale: Optional[str] = None
    alternative_operating_arrangements: List[str] = Field(default_factory=list)
    responsible_coordinator_id: str
    acknowledgement_timestamp: Optional[str] = None
    communication_references: List[str] = Field(default_factory=list)
    disclaimer: str = CLINICAL_SAFETY_CONTINUITY_DISCLAIMER
    created_at: str
    updated_at: str


class CreateActivationRequest(BaseModel):
    """Request to propose activating a continuity plan for an active disruption."""
    model_config = ConfigDict(extra="forbid")

    triggering_disruption_id: str
    affected_capability_ids: List[str]
    applicable_plan_id: str
    plan_version: int = 1
    responsible_coordinator_id: str
    activation_rationale: str


class AssessActivationRequest(BaseModel):
    """Request to record impact assessment for continuity activation."""
    model_config = ConfigDict(extra="forbid")

    assessment_notes: str
    recommended_status: ContinuityActivationStatus = ContinuityActivationStatus.UNDER_ASSESSMENT


class AuthorizeActivationDecisionRequest(BaseModel):
    """Request to record authorized decision to activate or reject continuity plan (separation of duties)."""
    model_config = ConfigDict(extra="forbid")

    status: ContinuityActivationStatus
    decision_rationale: str
    alternative_arrangements_approved: Optional[List[str]] = None


class AcknowledgeActivationRequest(BaseModel):
    """Request for designated coordinator to formally acknowledge activation."""
    model_config = ConfigDict(extra="forbid")

    acknowledgement_notes: Optional[str] = None


class DeactivateActivationRequest(BaseModel):
    """Request to deactivate continuity plan upon verified recovery."""
    model_config = ConfigDict(extra="forbid")

    deactivation_rationale: str
    recovery_verification_reference: str
