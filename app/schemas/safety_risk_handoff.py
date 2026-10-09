"""Phase 64: Clinical Safety Risk Handoff Schemas.

Defines schemas for governed downstream action handoffs, destination routing,
and handoff records.
Non-Negotiable Invariants:
- DISPOSITION RECORDED != HANDOFF REQUESTED
- HANDOFF REQUESTED != HANDOFF ACCEPTED
- HANDOFF ACCEPTED != WORK STARTED
- WORK STARTED != WORK COMPLETED
- WORK COMPLETED != OUTCOME VERIFIED
- OUTCOME RECEIVED != OUTCOME RECONCILED
- OUTCOME RECONCILED != RISK ELIMINATED
- RETRY != DUPLICATE AUTHORIZATION
- ROUTING FAILURE != SAFE
- NO RESPONSE != SUCCESS
- DESTINATION ACKNOWLEDGEMENT != GOVERNANCE APPROVAL
- HANDOFF COMPLETION != CLINICAL ACTION AUTHORIZATION
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class HandoffLifecycleState(str, Enum):
    """Lifecycle states for Phase 64 governed action handoffs."""

    # Standard progression
    CREATED = "CREATED"
    VALIDATING = "VALIDATING"
    READY = "READY"
    SUBMISSION_PENDING = "SUBMISSION_PENDING"
    SUBMITTED = "SUBMITTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    IN_PROGRESS = "IN_PROGRESS"
    OUTCOME_PENDING = "OUTCOME_PENDING"
    OUTCOME_RECEIVED = "OUTCOME_RECEIVED"
    RECONCILIATION_PENDING = "RECONCILIATION_PENDING"
    RECONCILED = "RECONCILED"
    FOLLOW_UP_REQUIRED = "FOLLOW_UP_REQUIRED"
    COMPLETED = "COMPLETED"

    # Exceptional and fault states
    BLOCKED = "BLOCKED"
    REJECTED = "REJECTED"
    RETRY_PENDING = "RETRY_PENDING"
    RETRY_EXHAUSTED = "RETRY_EXHAUSTED"
    ACKNOWLEDGEMENT_TIMEOUT = "ACKNOWLEDGEMENT_TIMEOUT"
    OUTCOME_TIMEOUT = "OUTCOME_TIMEOUT"
    OUTCOME_CONFLICTED = "OUTCOME_CONFLICTED"
    OUTCOME_STALE = "OUTCOME_STALE"
    SOURCE_SUPERSEDED = "SOURCE_SUPERSEDED"
    DESTINATION_UNAVAILABLE = "DESTINATION_UNAVAILABLE"
    CANCELLED = "CANCELLED"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"
    MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"


class HandoffDestinationPhase(str, Enum):
    """Permitted authoritative downstream destination phases."""

    PHASE_49_INCIDENT = "PHASE_49_INCIDENT"
    PHASE_50_LEARNING = "PHASE_50_LEARNING"
    PHASE_51_GOVERNANCE = "PHASE_51_GOVERNANCE"
    PHASE_52_ASSURANCE = "PHASE_52_ASSURANCE"
    PHASE_54_SAFETY_ACTION = "PHASE_54_SAFETY_ACTION"
    PHASE_55_EFFECTIVENESS = "PHASE_55_EFFECTIVENESS"
    PHASE_56_IMPROVEMENT = "PHASE_56_IMPROVEMENT"
    PHASE_59_SURVEILLANCE = "PHASE_59_SURVEILLANCE"
    PHASE_62_REASSESSMENT = "PHASE_62_REASSESSMENT"


class DestinationAcknowledgement(BaseModel):
    """Authoritative acknowledgement received from downstream destination."""

    model_config = ConfigDict(extra="ignore")

    acknowledgement_id: str = Field(default_factory=lambda: f"ack-{uuid.uuid4().hex[:12]}")
    handoff_id: str
    destination_phase: HandoffDestinationPhase
    destination_workflow_ref: str
    status: str = "ACCEPTED"
    acknowledged_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)


class HandoffHistoryEntry(BaseModel):
    """Immutable audit trail of state transitions for a handoff."""

    model_config = ConfigDict(extra="ignore")

    entry_id: str = Field(default_factory=lambda: f"hist-{uuid.uuid4().hex[:12]}")
    from_state: HandoffLifecycleState
    to_state: HandoffLifecycleState
    actor_id: str
    actor_role: str
    action: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    details: Dict[str, Any] = Field(default_factory=dict)


class CreateSafetyRiskHandoffRequest(BaseModel):
    """Request payload to create a governed handoff from Phase 63 disposition."""

    model_config = ConfigDict(extra="ignore")

    review_id: str
    disposition_id: str
    destination_phase: Optional[HandoffDestinationPhase] = None
    destination_operation: Optional[str] = "GOVERNED_REVIEW_HANDOFF"
    authorized_scope: Optional[Dict[str, Any]] = None
    purpose: Optional[str] = "GOVERNED_ACTION_HANDOFF"
    contract_version: Optional[str] = "v1.0.0"
    correlation_id: Optional[str] = None
    idempotency_key: Optional[str] = None


class SafetyRiskHandoffRecord(BaseModel):
    """Primary domain model representing a governed downstream risk handoff."""

    model_config = ConfigDict(extra="ignore")

    handoff_id: str = Field(default_factory=lambda: f"hnd-{uuid.uuid4().hex[:12]}")
    source_review_id: str
    source_disposition_id: str
    source_risk_context_id: str
    source_revision: str = "v1.0.0"
    organization_id: str
    facility_id: str
    destination_phase: HandoffDestinationPhase
    destination_operation: str = "GOVERNED_REVIEW_HANDOFF"
    state: HandoffLifecycleState = HandoffLifecycleState.CREATED
    authorized_scope: Dict[str, Any] = Field(default_factory=dict)
    provenance_reference: str = "PHASE_63_GOVERNED_DISPOSITION"
    contract_version: str = "v1.0.0"
    correlation_id: str = Field(default_factory=lambda: f"corr-{uuid.uuid4().hex[:12]}")
    idempotency_key: Optional[str] = None
    created_by: str = "system"

    # Retry and Execution tracking
    retry_count: int = 0
    max_retries: int = 3
    blocking_reason: Optional[str] = None
    escalation_reason: Optional[str] = None
    follow_up_status: Optional[str] = "PENDING_HANDOFF"

    # Linked destination details
    acknowledgement: Optional[DestinationAcknowledgement] = None
    outcomes: List[Dict[str, Any]] = Field(default_factory=list)
    reconciliation: Optional[Dict[str, Any]] = None

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    submitted_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # History & Concurrency
    history: List[HandoffHistoryEntry] = Field(default_factory=list)
    version: int = 1
