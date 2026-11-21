"""Phase 79: Strategic Execution Exception Schemas.

Defines schemas and models for:
- Logging strategic execution exceptions (cross-roadmap conflicts, dependency failures, invalidated assumptions)
- Routing exceptions to authoritative workflows (Phase 67, Phase 63, Phase 49, Phase 54, Phase 72)
"""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.governance_strategy_execution_monitoring import (
    CLINICAL_SAFETY_MONITORING_DISCLAIMER,
)


class ExecutionExceptionCategory(str, Enum):
    """Classification of strategic execution exceptions."""
    CROSS_ROADMAP_CONFLICT = "CROSS_ROADMAP_CONFLICT"
    DEPENDENCY_FAILURE = "DEPENDENCY_FAILURE"
    OBJECTIVE_MISALIGNMENT = "OBJECTIVE_MISALIGNMENT"
    DELAYED_APPROVAL = "DELAYED_APPROVAL"
    INVALIDATED_ASSUMPTION = "INVALIDATED_ASSUMPTION"
    RESOURCE_CONSTRAINT = "RESOURCE_CONSTRAINT"
    STALE_EXECUTION_EVIDENCE = "STALE_EXECUTION_EVIDENCE"
    UNOWNED_COMMITMENT = "UNOWNED_COMMITMENT"
    REPEATED_MILESTONE_SLIPPAGE = "REPEATED_MILESTONE_SLIPPAGE"


class ExecutionExceptionStatus(str, Enum):
    """Lifecycle status of a strategic execution exception."""
    OPEN = "OPEN"
    UNDER_REVIEW = "UNDER_REVIEW"
    ESCALATED_PHASE_67 = "ESCALATED_PHASE_67"
    ESCALATED_PHASE_63 = "ESCALATED_PHASE_63"
    ESCALATED_PHASE_49 = "ESCALATED_PHASE_49"
    ESCALATED_PHASE_54 = "ESCALATED_PHASE_54"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class StrategicExecutionExceptionRecord(BaseModel):
    """Authoritative record for an identified strategic execution exception."""
    model_config = ConfigDict(extra="forbid")

    exception_id: str
    tenant_id: str
    category: ExecutionExceptionCategory
    affected_roadmap_ids: List[str] = Field(default_factory=list)
    affected_objective_ids: List[str] = Field(default_factory=list)
    evidence_references: List[str] = Field(default_factory=list)
    detection_source: str
    impact_description: str
    responsible_owner_id: str
    escalation_destination: Optional[str] = None
    escalation_reference: Optional[str] = None
    status: ExecutionExceptionStatus
    resolution_evidence: Optional[str] = None
    disclaimer: str = CLINICAL_SAFETY_MONITORING_DISCLAIMER
    created_at: str
    updated_at: str


class CreateExecutionExceptionRequest(BaseModel):
    """Request to log a strategic execution exception."""
    model_config = ConfigDict(extra="forbid")

    category: ExecutionExceptionCategory
    affected_roadmap_ids: List[str]
    affected_objective_ids: Optional[List[str]] = None
    evidence_references: Optional[List[str]] = None
    detection_source: str
    impact_description: str
    responsible_owner_id: str


class EscalateExecutionExceptionRequest(BaseModel):
    """Request to escalate exception to an authoritative workflow."""
    model_config = ConfigDict(extra="forbid")

    escalation_destination: str = Field(..., description="Target phase e.g. PHASE_67_ESCALATION, PHASE_63_RISK, PHASE_49_INCIDENT, PHASE_54_CAPA")
    escalation_reference: Optional[str] = None
    notes: Optional[str] = None


class ResolveExecutionExceptionRequest(BaseModel):
    """Request to resolve a strategic execution exception."""
    model_config = ConfigDict(extra="forbid")

    resolution_evidence: str
