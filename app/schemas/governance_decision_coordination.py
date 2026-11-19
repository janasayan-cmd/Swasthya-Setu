"""Phase 67: Governance Decision and Conflict Coordination Schemas.

Defines schemas for governance reviews, decision recording, cross-workflow conflict
detection, and decision provenance tracking.

Mandatory Governance Invariants:
1. A recommendation does not constitute approval.
2. A conflict between workflows must not be silently resolved by choosing the newest record.
3. A governance escalation cannot override an authoritative decision owned by another phase.
4. Historical decisions remain immutable and traceable.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class GovernanceReviewOutcome(str, Enum):
    """Controlled outcomes of a governance escalation review."""

    ACCEPT_FOR_REVIEW = "ACCEPT_FOR_REVIEW"
    ACTION_REQUIRED = "ACTION_REQUIRED"
    ADDITIONAL_EVIDENCE_REQUIRED = "ADDITIONAL_EVIDENCE_REQUIRED"
    REASSESSMENT_REQUIRED = "REASSESSMENT_REQUIRED"
    SPECIALIST_REVIEW_REQUIRED = "SPECIALIST_REVIEW_REQUIRED"
    GOVERNANCE_COMMITTEE_REVIEW_REQUIRED = "GOVERNANCE_COMMITTEE_REVIEW_REQUIRED"
    REFER_TO_AUTHORITATIVE_WORKFLOW = "REFER_TO_AUTHORITATIVE_WORKFLOW"
    RESOLUTION_RECOMMENDED = "RESOLUTION_RECOMMENDED"
    ESCALATION_CONTINUED = "ESCALATION_CONTINUED"
    INSUFFICIENT_INFORMATION = "INSUFFICIENT_INFORMATION"


class ConflictSeverity(str, Enum):
    """Severity classification for cross-workflow decision conflicts."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MODERATE = "MODERATE"
    INFORMATIONAL = "INFORMATIONAL"


class CrossWorkflowConflictRecord(BaseModel):
    """Domain model capturing conflicting authoritative decisions across workflows."""

    model_config = ConfigDict(extra="ignore")

    conflict_id: str = Field(default_factory=lambda: f"gconf-{uuid.uuid4().hex[:12]}")
    escalation_id: str
    conflict_type: str
    severity: ConflictSeverity = ConflictSeverity.HIGH
    is_material: bool = True

    # Source Workflow A
    source_phase_a: str
    source_record_id_a: str
    source_state_a: str
    source_version_a: str

    # Source Workflow B
    source_phase_b: str
    source_record_id_b: str
    source_state_b: str
    source_version_b: str

    description: str
    is_resolved: bool = False
    resolution_rationale: Optional[str] = None
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None

    detected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)


class GovernanceReviewRecord(BaseModel):
    """Domain model representing a formal governance review execution."""

    model_config = ConfigDict(extra="ignore")

    review_id: str = Field(default_factory=lambda: f"grev-{uuid.uuid4().hex[:12]}")
    escalation_id: str
    reviewer_id: str
    reviewer_role: str
    outcome: GovernanceReviewOutcome
    rationale: str

    policy_version: str = "v1.0.0"
    reviewed_exception_ids: List[str] = Field(default_factory=list)
    evidence_refs: List[str] = Field(default_factory=list)
    required_follow_up_actions: List[str] = Field(default_factory=list)
    required_downstream_workflows: List[str] = Field(default_factory=list)

    reviewed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RecordGovernanceReviewRequest(BaseModel):
    """Request payload to submit a formal governance review on an escalation."""

    model_config = ConfigDict(extra="ignore")

    outcome: GovernanceReviewOutcome
    rationale: str
    policy_version: Optional[str] = "v1.0.0"
    reviewed_exception_ids: Optional[List[str]] = Field(default_factory=list)
    evidence_refs: Optional[List[str]] = Field(default_factory=list)
    required_follow_up_actions: Optional[List[str]] = Field(default_factory=list)
    required_downstream_workflows: Optional[List[str]] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class GovernanceDecisionRecord(BaseModel):
    """Domain model for an authorized governance decision recorded for an escalation."""

    model_config = ConfigDict(extra="ignore")

    decision_id: str = Field(default_factory=lambda: f"gdec-{uuid.uuid4().hex[:12]}")
    escalation_id: str
    decided_by: str
    decided_by_role: str
    decision_type: str
    decision_title: str
    rationale: str

    policy_reference: str = "gov-decision-policy-v1"
    policy_version: str = "v1.0.0"
    approved_actions: List[str] = Field(default_factory=list)
    required_resolution_requirements: List[str] = Field(default_factory=list)
    target_workflow_instructions: Dict[str, Any] = Field(default_factory=dict)

    decided_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RecordGovernanceDecisionRequest(BaseModel):
    """Request payload to record an authorized governance decision."""

    model_config = ConfigDict(extra="ignore")

    decision_type: str
    decision_title: str
    rationale: str
    policy_reference: Optional[str] = "gov-decision-policy-v1"
    policy_version: Optional[str] = "v1.0.0"
    approved_actions: Optional[List[str]] = Field(default_factory=list)
    required_resolution_requirements: Optional[List[str]] = Field(default_factory=list)
    target_workflow_instructions: Optional[Dict[str, Any]] = Field(default_factory=dict)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
