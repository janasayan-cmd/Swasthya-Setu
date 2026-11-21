"""Phase 78: Governance Capability Target Schemas.

Defines schemas and models for:
- Desired future governance capability operating states
- Linking Phase 77 current maturity assessment baselines (without replacing Phase 77)
- Establishing measurable progress evidence requirements
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.governance_strategy_objective import CLINICAL_SAFETY_STRATEGY_DISCLAIMER


class CapabilityDomainEnum(str, Enum):
    """Configurable capability domains for clinical safety governance."""
    GOVERNANCE_ACCOUNTABILITY = "GOVERNANCE_ACCOUNTABILITY"
    CLINICAL_SAFETY_LEADERSHIP = "CLINICAL_SAFETY_LEADERSHIP"
    RISK_MANAGEMENT = "RISK_MANAGEMENT"
    INCIDENT_LEARNING = "INCIDENT_LEARNING"
    AUDIT_ASSURANCE = "AUDIT_ASSURANCE"
    CORRECTIVE_ACTION_GOVERNANCE = "CORRECTIVE_ACTION_GOVERNANCE"
    EVIDENCE_MANAGEMENT = "EVIDENCE_MANAGEMENT"
    POLICY_GOVERNANCE = "POLICY_GOVERNANCE"
    SAFETY_COMMUNICATION = "SAFETY_COMMUNICATION"
    WORKFORCE_COMPETENCY = "WORKFORCE_COMPETENCY"
    ORGANIZATIONAL_OVERSIGHT = "ORGANIZATIONAL_OVERSIGHT"
    CONTINUOUS_IMPROVEMENT = "CONTINUOUS_IMPROVEMENT"
    INFORMATION_QUALITY = "INFORMATION_QUALITY"
    STRATEGIC_PERFORMANCE = "STRATEGIC_PERFORMANCE"


class CapabilityTargetStatus(str, Enum):
    """Status of a proposed capability development target."""
    PROPOSED = "PROPOSED"
    ACCEPTED = "ACCEPTED"
    IN_PROGRESS = "IN_PROGRESS"
    MET = "MET"
    DEFERRED = "DEFERRED"


class GovernanceCapabilityTargetRecord(BaseModel):
    """Authoritative record for a desired future capability development target."""
    model_config = ConfigDict(extra="forbid")

    target_id: str
    tenant_id: str
    capability_domain: CapabilityDomainEnum
    title: str
    current_state_description: str
    current_maturity_reference: Optional[str] = Field(None, description="Phase 77 assessment ID or level")
    desired_future_state_description: str
    target_maturity_level: Optional[str] = Field(None, description="Proposed target level in Phase 77 framework")
    organizational_scope: Dict[str, Any] = Field(default_factory=dict)
    planned_milestone_id: Optional[str] = None
    responsible_owner_id: str
    evidence_required: List[str] = Field(default_factory=list)
    review_criteria: str
    status: CapabilityTargetStatus
    disclaimer: str = CLINICAL_SAFETY_STRATEGY_DISCLAIMER
    created_at: str
    updated_at: str


class CreateCapabilityTargetRequest(BaseModel):
    """Request to create a new capability development target proposal."""
    model_config = ConfigDict(extra="forbid")

    capability_domain: CapabilityDomainEnum
    title: str
    current_state_description: str
    current_maturity_reference: Optional[str] = None
    desired_future_state_description: str
    target_maturity_level: Optional[str] = None
    organizational_scope: Optional[Dict[str, Any]] = None
    planned_milestone_id: Optional[str] = None
    responsible_owner_id: str
    evidence_required: Optional[List[str]] = None
    review_criteria: str


class UpdateCapabilityTargetRequest(BaseModel):
    """Request to update a capability target proposal."""
    model_config = ConfigDict(extra="forbid")

    desired_future_state_description: Optional[str] = None
    target_maturity_level: Optional[str] = None
    status: Optional[CapabilityTargetStatus] = None
    planned_milestone_id: Optional[str] = None
