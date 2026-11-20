"""Phase 73: Handoffs, Outcomes, Exceptions & Change Impact Schemas.

Defines schemas for:
- Destination workflow coordination (Phase 54 CAPA, 55 effectiveness, 63 risk, 67 escalation, 69 compliance, 70 audit, 49 incident)
- Outcome and intended-result reconciliation
- Implementation exception tracking
- Decision supersession and change-impact coordination
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class DestinationWorkflow(str, Enum):
    """Authoritative destination workflows coordinated by Phase 73."""

    PHASE_54_CAPA = "PHASE_54_CAPA"
    PHASE_55_EFFECTIVENESS = "PHASE_55_EFFECTIVENESS"
    PHASE_63_RISK_REVIEW = "PHASE_63_RISK_REVIEW"
    PHASE_67_ESCALATION = "PHASE_67_ESCALATION"
    PHASE_69_COMPLIANCE = "PHASE_69_COMPLIANCE"
    PHASE_70_AUDIT = "PHASE_70_AUDIT"
    PHASE_49_INCIDENT = "PHASE_49_INCIDENT"


class HandoffStatus(str, Enum):
    """Lifecycle status of a delegation handoff to a destination workflow."""

    PENDING = "PENDING"
    DISPATCHED = "DISPATCHED"
    ACCEPTED = "ACCEPTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    RECONCILED = "RECONCILED"


class WorkflowHandoffRecord(BaseModel):
    """Domain model tracking delegation to an authoritative destination workflow."""

    model_config = ConfigDict(extra="ignore")

    handoff_id: str = Field(default_factory=lambda: f"gdho-{uuid.uuid4().hex[:12]}")
    implementation_id: str
    destination_workflow: DestinationWorkflow
    destination_record_id: Optional[str] = None
    requested_outcome: str
    responsible_owner_id: str

    status: HandoffStatus = HandoffStatus.PENDING
    latest_destination_status: Optional[str] = None
    dispatched_at: Optional[datetime] = None
    reconciled_at: Optional[datetime] = None
    retry_count: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class OutcomeState(str, Enum):
    """Evaluation status of delivered implementation against intended decision outcome."""

    NOT_ASSESSED = "NOT_ASSESSED"
    OUTCOME_ACHIEVED = "OUTCOME_ACHIEVED"
    PARTIALLY_ACHIEVED = "PARTIALLY_ACHIEVED"
    NOT_ACHIEVED = "NOT_ACHIEVED"
    INCONCLUSIVE = "INCONCLUSIVE"
    SUPERSEDED = "SUPERSEDED"
    CANCELLED_WITH_AUTHORIZATION = "CANCELLED_WITH_AUTHORIZATION"


class OutcomeAssessmentRecord(BaseModel):
    """Domain model evaluating whether the delivered implementation achieved the intended result."""

    model_config = ConfigDict(extra="ignore")

    assessment_id: str = Field(default_factory=lambda: f"gdoa-{uuid.uuid4().hex[:12]}")
    implementation_id: str
    decision_id: str
    state: OutcomeState = OutcomeState.NOT_ASSESSED
    rationale: str
    supporting_evidence_refs: List[str] = Field(default_factory=list)

    destination_workflow_outcome: Dict[str, Any] = Field(default_factory=dict)
    remaining_limitations: List[str] = Field(default_factory=list)
    unresolved_dependencies: List[str] = Field(default_factory=list)

    assessed_by: str
    assessed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ImplementationExceptionCategory(str, Enum):
    """Categories of operational and governance exceptions during implementation."""

    DELAYED_IMPLEMENTATION = "DELAYED_IMPLEMENTATION"
    UNASSIGNED_OWNERSHIP = "UNASSIGNED_OWNERSHIP"
    REJECTED_EVIDENCE = "REJECTED_EVIDENCE"
    FAILED_VERIFICATION = "FAILED_VERIFICATION"
    BLOCKED_DEPENDENCIES = "BLOCKED_DEPENDENCIES"
    CONFLICTING_DESTINATION_STATUS = "CONFLICTING_DESTINATION_STATUS"
    MISSING_DESTINATION_RECORDS = "MISSING_DESTINATION_RECORDS"
    PLAN_DEVIATION = "PLAN_DEVIATION"
    CONDITIONS_UNSATISFIED = "CONDITIONS_UNSATISFIED"
    OUTCOME_NOT_ACHIEVED = "OUTCOME_NOT_ACHIEVED"
    REPEATED_FAILURE = "REPEATED_FAILURE"


class ImplementationExceptionRecord(BaseModel):
    """Domain record representing an exception encountered during implementation."""

    model_config = ConfigDict(extra="ignore")

    exception_id: str = Field(default_factory=lambda: f"gdex-{uuid.uuid4().hex[:12]}")
    implementation_id: str
    decision_id: str
    category: ImplementationExceptionCategory
    description: str
    priority: str = "HIGH"
    owner_id: str
    detection_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    escalation_reference_id: Optional[str] = None  # Link to Phase 67
    resolution_reference: Optional[str] = None
    resolved_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DecisionChangeImpactRecord(BaseModel):
    """Domain record analyzing impact when a Phase 72 decision is amended or superseded."""

    model_config = ConfigDict(extra="ignore")

    impact_id: str = Field(default_factory=lambda: f"gdci-{uuid.uuid4().hex[:12]}")
    implementation_id: str
    decision_id: str
    previous_decision_status: str
    new_decision_status: str
    superseded_by_decision_id: Optional[str] = None

    impacted_milestones: List[str] = Field(default_factory=list)
    impacted_dependencies: List[str] = Field(default_factory=list)
    impacted_handoffs: List[str] = Field(default_factory=list)

    recommended_disposition: str = "MODIFY"  # CONTINUE, MODIFY, SUSPEND, CANCEL
    disposition_decision: Optional[str] = None
    disposition_authorized_by: Optional[str] = None
    reviewed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)


# Request Models
class CreateHandoffRequest(BaseModel):
    """Request payload to delegate work to a destination workflow."""

    model_config = ConfigDict(extra="ignore")

    destination_workflow: DestinationWorkflow
    destination_record_id: Optional[str] = None
    requested_outcome: str
    responsible_owner_id: str
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ReconcileHandoffRequest(BaseModel):
    """Request payload to update status from destination workflow."""

    model_config = ConfigDict(extra="ignore")

    latest_destination_status: str
    status: HandoffStatus
    notes: Optional[str] = None


class AssessOutcomeRequest(BaseModel):
    """Request payload to formally assess implementation outcome."""

    model_config = ConfigDict(extra="ignore")

    state: OutcomeState
    rationale: str
    supporting_evidence_refs: Optional[List[str]] = Field(default_factory=list)
    destination_workflow_outcome: Optional[Dict[str, Any]] = Field(default_factory=dict)
    remaining_limitations: Optional[List[str]] = Field(default_factory=list)
    unresolved_dependencies: Optional[List[str]] = Field(default_factory=list)


class ReferExceptionRequest(BaseModel):
    """Request payload to refer an implementation exception to Phase 67."""

    model_config = ConfigDict(extra="ignore")

    escalation_reference_id: str
    notes: Optional[str] = None


class ReviewChangeImpactRequest(BaseModel):
    """Request payload to record an authorized disposition on decision change."""

    model_config = ConfigDict(extra="ignore")

    disposition_decision: str  # CONTINUE, MODIFY, SUSPEND, CANCEL
    rationale: str
