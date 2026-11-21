"""Phase 78: Governance Strategy Coordination and Issue Routing Schemas.

Defines schemas and models for:
- Coordinating roadmaps with Phase 75 portfolios and Phase 73 implementation records
- Tracking strategic delivery issues, delays, and conflicts
- Routing governance issues to authoritative workflows (Phase 63, Phase 67, Phase 49, Phase 54)
"""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.governance_strategy_objective import CLINICAL_SAFETY_STRATEGY_DISCLAIMER


class StrategyIssueClassification(str, Enum):
    """Classification of strategic delivery issue or risk."""
    ROADMAP_DELAY = "ROADMAP_DELAY"
    DEPENDENCY_FAILURE = "DEPENDENCY_FAILURE"
    UNFUNDED_COMMITMENT = "UNFUNDED_COMMITMENT"
    RESOURCE_CONFLICT = "RESOURCE_CONFLICT"
    READINESS_GAP = "READINESS_GAP"
    STALE_EVIDENCE = "STALE_EVIDENCE"
    GOVERNANCE_EXCEPTION = "GOVERNANCE_EXCEPTION"
    CLINICAL_SAFETY_RISK = "CLINICAL_SAFETY_RISK"


class StrategyIssueStatus(str, Enum):
    """Lifecycle status of an identified strategic issue."""
    OPEN = "OPEN"
    INVESTIGATING = "INVESTIGATING"
    ESCALATED = "ESCALATED"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class PortfolioLinkRecord(BaseModel):
    """Linkage between an approved strategic objective and an existing Phase 75 portfolio."""
    model_config = ConfigDict(extra="forbid")

    link_id: str
    tenant_id: str
    roadmap_id: str
    objective_id: str
    portfolio_id: str
    status: str = "ACTIVE"
    linked_at: str


class ImplementationLinkRecord(BaseModel):
    """Linkage between a roadmap milestone and a Phase 73 implementation record."""
    model_config = ConfigDict(extra="forbid")

    link_id: str
    tenant_id: str
    roadmap_id: str
    milestone_id: str
    implementation_id: str
    status: str = "ACTIVE"
    linked_at: str


class GovernanceStrategyIssueRecord(BaseModel):
    """Authoritative record for an identified strategic conflict, delay, or risk."""
    model_config = ConfigDict(extra="forbid")

    issue_id: str
    tenant_id: str
    roadmap_id: str
    affected_objective_ids: List[str] = Field(default_factory=list)
    affected_milestone_ids: List[str] = Field(default_factory=list)
    classification: StrategyIssueClassification
    title: str
    description: str
    impact_description: str
    status: StrategyIssueStatus
    detected_by: str
    detection_timestamp: str
    escalation_target: Optional[str] = Field(None, description="e.g. PHASE_63_RISK, PHASE_67_ESCALATION, PHASE_49_INCIDENT, PHASE_54_CAPA")
    escalation_reference: Optional[str] = None
    resolution_notes: Optional[str] = None
    disclaimer: str = CLINICAL_SAFETY_STRATEGY_DISCLAIMER


class LinkPortfolioRequest(BaseModel):
    """Request to link a strategic objective to an existing Phase 75 portfolio."""
    model_config = ConfigDict(extra="forbid")

    objective_id: str
    portfolio_id: str


class LinkImplementationRequest(BaseModel):
    """Request to link a milestone to a Phase 73 implementation record."""
    model_config = ConfigDict(extra="forbid")

    milestone_id: str
    implementation_id: str


class CreateStrategyIssueRequest(BaseModel):
    """Request to record an identified strategic issue or delivery conflict."""
    model_config = ConfigDict(extra="forbid")

    roadmap_id: str
    affected_objective_ids: Optional[List[str]] = None
    affected_milestone_ids: Optional[List[str]] = None
    classification: StrategyIssueClassification
    title: str
    description: str
    impact_description: str


class EscalateStrategyIssueRequest(BaseModel):
    """Request to escalate a strategic issue to an authoritative workflow."""
    model_config = ConfigDict(extra="forbid")

    escalation_target: str = Field(..., description="Target phase e.g. PHASE_63_RISK, PHASE_67_ESCALATION, PHASE_49_INCIDENT, PHASE_54_CAPA")
    escalation_reference: Optional[str] = None
    notes: Optional[str] = None


class ResolveStrategyIssueRequest(BaseModel):
    """Request to resolve a strategic issue."""
    model_config = ConfigDict(extra="forbid")

    resolution_notes: str
