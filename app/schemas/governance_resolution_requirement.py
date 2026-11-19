"""Phase 67: Governance Resolution Requirement Schemas.

Defines schemas for resolution requirements, reconciliation against authoritative
upstream/downstream workflows, governed closure, and reopening.

Mandatory Governance Invariants:
1. An escalation may only become RESOLVED when all mandatory resolution conditions are satisfied.
2. Resolving one finding does not automatically resolve related findings.
3. An escalation closed administratively does not establish clinical safety.
4. Historical closure records are preserved across stales, conflicts, and reopenings.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class RequirementStatus(str, Enum):
    """Lifecycle status for an individual resolution requirement."""

    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    SATISFIED = "SATISFIED"
    WAIVED_WITH_AUTHORIZATION = "WAIVED_WITH_AUTHORIZATION"
    BLOCKED = "BLOCKED"
    REOPENED = "REOPENED"


class RequirementCategory(str, Enum):
    """Categories of resolution requirements coordinating across safety phases."""

    SOURCE_WORKFLOW_REASSESSMENT = "SOURCE_WORKFLOW_REASSESSMENT"
    INCIDENT_REVIEW = "INCIDENT_REVIEW"
    ADDITIONAL_EVIDENCE_SUBMISSION = "ADDITIONAL_EVIDENCE_SUBMISSION"
    HANDOFF_RECONCILIATION = "HANDOFF_RECONCILIATION"
    COMPLETION_COORDINATION_REASSESSMENT = "COMPLETION_COORDINATION_REASSESSMENT"
    POST_CLOSURE_VERIFICATION = "POST_CLOSURE_VERIFICATION"
    GOVERNANCE_APPROVAL = "GOVERNANCE_APPROVAL"
    CONTROLLED_ACTION_COMPLETION = "CONTROLLED_ACTION_COMPLETION"
    ASSURANCE_REVIEW = "ASSURANCE_REVIEW"
    EFFECTIVENESS_EVALUATION = "EFFECTIVENESS_EVALUATION"
    POLICY_REVIEW = "POLICY_REVIEW"
    SPECIALIST_REVIEW = "SPECIALIST_REVIEW"


class ResolutionRequirementRecord(BaseModel):
    """Domain model representing a mandatory or optional condition for escalation resolution."""

    model_config = ConfigDict(extra="ignore")

    requirement_id: str = Field(default_factory=lambda: f"greq-{uuid.uuid4().hex[:12]}")
    escalation_id: str
    title: str
    category: RequirementCategory
    is_mandatory: bool = True
    status: RequirementStatus = RequirementStatus.PENDING

    # Responsible authority
    responsible_phase: str
    responsible_owner: Optional[str] = None
    target_record_id: Optional[str] = None
    target_version: Optional[str] = "v1.0.0"

    # Evidence & reconciliation
    completion_evidence_refs: List[str] = Field(default_factory=list)
    blocking_reason: Optional[str] = None
    waiver_rationale: Optional[str] = None
    waived_by: Optional[str] = None
    due_date: Optional[datetime] = None
    reconciled_at: Optional[datetime] = None
    reconciled_by: Optional[str] = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ReconcileResolutionRequirementRequest(BaseModel):
    """Request payload to reconcile a resolution requirement."""

    model_config = ConfigDict(extra="ignore")

    status: RequirementStatus
    reconciliation_evidence: Optional[List[str]] = Field(default_factory=list)
    notes: str
    waiver_rationale: Optional[str] = None


class ResolveEscalationRequest(BaseModel):
    """Request payload to mark an escalation RESOLVED after satisfying all conditions."""

    model_config = ConfigDict(extra="ignore")

    resolution_rationale: str
    resolution_evidence: Optional[List[str]] = Field(default_factory=list)


class CloseEscalationRequest(BaseModel):
    """Request payload to perform controlled administrative closure of an escalation."""

    model_config = ConfigDict(extra="ignore")

    closure_rationale: str
    administrative_notes: Optional[str] = None


class ReopenEscalationRequest(BaseModel):
    """Request payload to reopen a resolved or closed escalation upon material new findings."""

    model_config = ConfigDict(extra="ignore")

    reopen_reason: str
    triggering_source_phase: str
    triggering_source_record_id: str
    new_evidence_refs: Optional[List[str]] = Field(default_factory=list)


class ExtendDeadlineRequest(BaseModel):
    """Request payload to request or authorize a deadline extension."""

    model_config = ConfigDict(extra="ignore")

    deadline_type: str  # acknowledgement, review, decision, resolution
    extended_until: datetime
    extension_rationale: str
