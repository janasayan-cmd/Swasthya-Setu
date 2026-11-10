"""Phase 66: Safety Integrity Finding Schemas.

Defines schemas for integrity findings, finding lifecycle states, severity classifications,
and review/resolution contracts.

Mandatory Invariant:
A finding is an observation, not automatically a confirmed incident or a clinical conclusion.
Finding severity, materiality, escalation, and required actions must be governed by policy
and existing domain contracts.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class FindingCategory(str, Enum):
    """Controlled categories for Phase 66 post-closure integrity findings."""

    SOURCE_DISPOSITION_CHANGED = "SOURCE_DISPOSITION_CHANGED"
    HANDOFF_STATE_CHANGED = "HANDOFF_STATE_CHANGED"
    DESTINATION_WORKFLOW_REOPENED = "DESTINATION_WORKFLOW_REOPENED"
    DESTINATION_OUTCOME_INVALIDATED = "DESTINATION_OUTCOME_INVALIDATED"
    OUTCOME_VERSION_CHANGED = "OUTCOME_VERSION_CHANGED"
    REQUIRED_EVIDENCE_INVALIDATED = "REQUIRED_EVIDENCE_INVALIDATED"
    REQUIRED_EVIDENCE_UNAVAILABLE = "REQUIRED_EVIDENCE_UNAVAILABLE"
    FOLLOW_UP_FAILED = "FOLLOW_UP_FAILED"
    FOLLOW_UP_OVERDUE = "FOLLOW_UP_OVERDUE"
    REQUIRED_REASSESSMENT_CHANGED = "REQUIRED_REASSESSMENT_CHANGED"
    MATERIAL_SAFETY_SIGNAL_DETECTED = "MATERIAL_SAFETY_SIGNAL_DETECTED"
    POLICY_VERSION_CHANGED = "POLICY_VERSION_CHANGED"
    COMPLETION_PACKAGE_INCONSISTENCY = "COMPLETION_PACKAGE_INCONSISTENCY"
    AUTHORIZATION_EVIDENCE_MISSING = "AUTHORIZATION_EVIDENCE_MISSING"
    DEPENDENCY_STATE_UNKNOWN = "DEPENDENCY_STATE_UNKNOWN"
    AUTHORITATIVE_STATE_CONFLICT = "AUTHORITATIVE_STATE_CONFLICT"


class FindingSeverity(str, Enum):
    """Severity ratings for integrity findings."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFORMATIONAL = "INFORMATIONAL"


class FindingLifecycleState(str, Enum):
    """Lifecycle states for integrity findings."""

    DETECTED = "DETECTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    REVIEWED = "REVIEWED"
    REASSESSMENT_REQUESTED = "REASSESSMENT_REQUESTED"
    REOPEN_REQUESTED = "REOPEN_REQUESTED"
    RESOLVED = "RESOLVED"
    DISMISSED_WITH_RATIONALE = "DISMISSED_WITH_RATIONALE"
    SUPERSEDED = "SUPERSEDED"


class IntegrityFindingRecord(BaseModel):
    """Primary domain model representing a specific discrepancy or observation."""

    model_config = ConfigDict(extra="ignore")

    finding_id: str = Field(default_factory=lambda: f"fnd-{uuid.uuid4().hex[:12]}")
    completion_id: str
    verification_id: str
    organization_id: str
    facility_id: str

    category: FindingCategory
    severity: FindingSeverity = FindingSeverity.MEDIUM
    source_system: str
    authoritative_record_ref: str

    expected_state: str
    observed_state: str
    relevant_version_refs: Dict[str, Any] = Field(default_factory=dict)
    detected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    provenance: str = "PHASE_66_INTEGRITY_CHECKER"

    is_material: bool = True
    policy_reference: str = "v1.0.0"
    recommended_next_action: str = "REVIEW_REQUIRED"
    required_authorization: Optional[str] = None
    lifecycle_state: FindingLifecycleState = FindingLifecycleState.DETECTED

    # Review information
    review_notes: Optional[str] = None
    reviewed_by: Optional[str] = None
    reviewed_by_role: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    dismissal_rationale: Optional[str] = None

    # Resolution information
    resolution_evidence: Optional[str] = None
    resolved_by: Optional[str] = None
    resolved_by_role: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None

    audit_reference: str = Field(default_factory=lambda: f"aud-{uuid.uuid4().hex[:12]}")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ReviewFindingRequest(BaseModel):
    """Request payload to review an integrity finding."""

    model_config = ConfigDict(extra="ignore")

    action: str = "CONFIRM"  # CONFIRM, DISMISS, REQUEST_REASSESSMENT, REQUEST_REOPEN
    notes: str
    dismissal_rationale: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ResolveFindingRequest(BaseModel):
    """Request payload to resolve an integrity finding."""

    model_config = ConfigDict(extra="ignore")

    resolution_evidence: str
    resolution_notes: str
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
