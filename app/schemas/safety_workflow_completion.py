"""Phase 65: Clinical Safety Workflow Completion Schemas.

Defines schemas for governed completion coordination, cross-phase outcome verification,
and controlled workflow closure.

Critical Architectural Distinctions & Invariants:
- HANDOFF COMPLETED != WORKFLOW COMPLETED
- DESTINATION WORKFLOW COMPLETED != RISK ELIMINATED
- ALL HANDOFFS RECONCILED != SAFETY ASSURED
- REQUIRED TASKS COMPLETED != CLINICAL OUTCOME VERIFIED
- COMPLETION ELIGIBILITY != COMPLETION AUTHORIZATION
- COMPLETION AUTHORIZED != CLINICAL SAFETY GUARANTEE
- NO OUTSTANDING HANDOFFS != NO OUTSTANDING RISK
- NO FOLLOW-UP REQUIRED != NO RISK EXISTS
- WORKFLOW CLOSURE != RISK ACCEPTANCE
- WORKFLOW CLOSURE != EFFECTIVENESS CONFIRMATION
- WORKFLOW CLOSURE != INCIDENT CLOSURE
- WORKFLOW CLOSURE != SAFETY ASSURANCE
- AI COMPLETION RECOMMENDATION != AUTHORIZED CLOSURE
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class CompletionLifecycleState(str, Enum):
    """Lifecycle states for Phase 65 governed completion coordination workflows."""

    # Standard progression
    CREATED = "CREATED"
    VALIDATING = "VALIDATING"
    READINESS_EVALUATION_PENDING = "READINESS_EVALUATION_PENDING"
    READINESS_EVALUATING = "READINESS_EVALUATING"
    NOT_READY = "NOT_READY"
    READY = "READY"
    READY_WITH_LIMITATIONS = "READY_WITH_LIMITATIONS"
    REVIEW_PENDING = "REVIEW_PENDING"
    REVIEW_IN_PROGRESS = "REVIEW_IN_PROGRESS"
    COMPLETION_AUTHORIZATION_PENDING = "COMPLETION_AUTHORIZATION_PENDING"
    CLOSURE_PENDING = "CLOSURE_PENDING"
    CLOSED = "CLOSED"
    POST_CLOSURE_MONITORING = "POST_CLOSURE_MONITORING"

    # Post-closure & Reassessment transitions
    REASSESSMENT_REQUIRED = "REASSESSMENT_REQUIRED"
    REOPEN_REQUIRED = "REOPEN_REQUIRED"
    REOPENED = "REOPENED"
    SUPERSEDED = "SUPERSEDED"
    CANCELLED = "CANCELLED"

    # Exceptional and fault states
    BLOCKED = "BLOCKED"
    STALE = "STALE"
    CONFLICTED = "CONFLICTED"
    DEPENDENCY_UNAVAILABLE = "DEPENDENCY_UNAVAILABLE"
    COMPLETION_FAILED = "COMPLETION_FAILED"
    MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"


class CreateSafetyWorkflowCompletionRequest(BaseModel):
    """Request payload to initialize a completion coordination workflow."""

    model_config = ConfigDict(extra="ignore")

    review_id: str
    disposition_id: str
    coordination_id: Optional[str] = None
    risk_context_id: Optional[str] = None
    contract_version: Optional[str] = "v1.0.0"
    applicable_policy_version: Optional[str] = "v1.0.0"
    correlation_id: Optional[str] = None
    idempotency_key: Optional[str] = None
    authorized_scope: Optional[Dict[str, Any]] = None
    initial_evidence_refs: Optional[List[str]] = Field(default_factory=list)


class SafetyWorkflowCompletionRecord(BaseModel):
    """Primary domain model representing a governed safety workflow completion."""

    model_config = ConfigDict(extra="ignore")

    completion_id: str = Field(default_factory=lambda: f"comp-{uuid.uuid4().hex[:12]}")
    coordination_id: str = Field(default_factory=lambda: f"coord-{uuid.uuid4().hex[:12]}")
    source_review_id: str
    source_disposition_id: str
    source_risk_context_id: str
    source_revision: str = "v1.0.0"
    organization_id: str
    facility_id: str
    state: CompletionLifecycleState = CompletionLifecycleState.CREATED
    readiness_state: str = "NOT_EVALUATED"

    # Scope and Provenance
    authorized_scope: Dict[str, Any] = Field(default_factory=dict)
    provenance_reference: str = "PHASE_64_HANDOFF_ORCHESTRATION"
    contract_version: str = "v1.0.0"
    applicable_policy_version: str = "v1.0.0"
    correlation_id: str = Field(default_factory=lambda: f"corr-{uuid.uuid4().hex[:12]}")
    idempotency_key: Optional[str] = None
    created_by: str = "system"

    # Detailed collections
    requirements: List[Dict[str, Any]] = Field(default_factory=list)
    outcomes: List[Dict[str, Any]] = Field(default_factory=list)
    follow_ups: List[Dict[str, Any]] = Field(default_factory=list)
    completion_package: Optional[Dict[str, Any]] = None

    # Review, Authorization & Closure
    review: Optional[Dict[str, Any]] = None
    authorization: Optional[Dict[str, Any]] = None
    closure: Optional[Dict[str, Any]] = None

    # Limitations & Blockers
    limitations: List[str] = Field(default_factory=list)
    blockers: List[str] = Field(default_factory=list)
    blocking_reason: Optional[str] = None

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    evaluated_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None
    authorized_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    reopened_at: Optional[datetime] = None

    # History & Version
    history: List[Dict[str, Any]] = Field(default_factory=list)
    reopen_history: List[Dict[str, Any]] = Field(default_factory=list)
    version: int = 1
