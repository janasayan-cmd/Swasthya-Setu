"""Phase 65: Safety Completion Requirement Register Schemas.

Defines requirement types, statuses, and records for the cross-phase completion register.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class RequirementType(str, Enum):
    """Permitted requirement types for completion coordination."""

    REQUIRED_HANDOFF = "REQUIRED_HANDOFF"
    REQUIRED_DESTINATION_OUTCOME = "REQUIRED_DESTINATION_OUTCOME"
    REQUIRED_EVIDENCE = "REQUIRED_EVIDENCE"
    REQUIRED_REVIEW = "REQUIRED_REVIEW"
    REQUIRED_APPROVAL = "REQUIRED_APPROVAL"
    REQUIRED_FOLLOW_UP = "REQUIRED_FOLLOW_UP"
    REQUIRED_REASSESSMENT = "REQUIRED_REASSESSMENT"
    REQUIRED_MONITORING_REGISTRATION = "REQUIRED_MONITORING_REGISTRATION"
    REQUIRED_INCIDENT_WORKFLOW = "REQUIRED_INCIDENT_WORKFLOW"
    REQUIRED_ASSURANCE_WORKFLOW = "REQUIRED_ASSURANCE_WORKFLOW"
    REQUIRED_EFFECTIVENESS_WORKFLOW = "REQUIRED_EFFECTIVENESS_WORKFLOW"
    REQUIRED_GOVERNANCE_WORKFLOW = "REQUIRED_GOVERNANCE_WORKFLOW"
    REQUIRED_CONTROLLED_ACTION_WORKFLOW = "REQUIRED_CONTROLLED_ACTION_WORKFLOW"


class RequirementStatus(str, Enum):
    """Lifecycle status of an individual requirement in the register."""

    UNRESOLVED = "UNRESOLVED"
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    SATISFIED = "SATISFIED"
    BLOCKED = "BLOCKED"
    WAIVED = "WAIVED"
    CONFLICTED = "CONFLICTED"
    STALE = "STALE"


class CompletionRequirementRecord(BaseModel):
    """Logical record for a completion requirement in the register."""

    model_config = ConfigDict(extra="ignore")

    requirement_id: str = Field(default_factory=lambda: f"req-{uuid.uuid4().hex[:12]}")
    completion_id: str
    requirement_type: RequirementType
    description: str
    originating_phase: str = "PHASE_64"
    originating_record_ref: str
    destination_phase: Optional[str] = None
    destination_workflow_ref: Optional[str] = None

    is_mandatory: bool = True
    status: RequirementStatus = RequirementStatus.UNRESOLVED

    evidence_references: List[str] = Field(default_factory=list)
    provenance: str = "GOVERNED_DISPOSITION"
    source_revision: str = "v1.0.0"
    applicable_policy_version: str = "v1.0.0"

    blocker_reason: Optional[str] = None
    waiver_reason: Optional[str] = None
    waived_by: Optional[str] = None

    last_evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)
