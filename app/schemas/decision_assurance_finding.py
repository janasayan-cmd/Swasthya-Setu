"""Phase 68: Decision Assurance Integrity Finding Schemas.

Defines schemas for traceable integrity findings detected during governance decision assurance.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class AssuranceFindingCategory(str, Enum):
    """Categorization of decision assurance integrity findings."""

    PROVENANCE_FAILURE = "PROVENANCE_FAILURE"
    AUTHORIZATION_INVALID = "AUTHORIZATION_INVALID"
    AUTHORIZATION_UNVERIFIABLE = "AUTHORIZATION_UNVERIFIABLE"
    SEPARATION_OF_DUTIES_VIOLATION = "SEPARATION_OF_DUTIES_VIOLATION"
    POLICY_MISMATCH = "POLICY_MISMATCH"
    EVIDENCE_INCOMPLETE = "EVIDENCE_INCOMPLETE"
    EVIDENCE_INVALIDATED = "EVIDENCE_INVALIDATED"
    CROSS_WORKFLOW_CONFLICT = "CROSS_WORKFLOW_CONFLICT"
    SUPERSEDED_SOURCE = "SUPERSEDED_SOURCE"


class FindingSeverity(str, Enum):
    """Governance severity classification for an assurance finding."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFORMATIONAL = "INFORMATIONAL"


class FindingReviewOutcome(str, Enum):
    """Controlled outcomes of a review on an assurance finding."""

    NO_ACTION_REQUIRED = "NO_ACTION_REQUIRED"
    CONFIRMED_BREACH = "CONFIRMED_BREACH"
    ADDITIONAL_EVIDENCE_REQUIRED = "ADDITIONAL_EVIDENCE_REQUIRED"
    AUTHORIZATION_REVIEW_REQUIRED = "AUTHORIZATION_REVIEW_REQUIRED"
    POLICY_REVIEW_REQUIRED = "POLICY_REVIEW_REQUIRED"
    SEPARATION_OF_DUTIES_REVIEW_REQUIRED = "SEPARATION_OF_DUTIES_REVIEW_REQUIRED"
    SOURCE_WORKFLOW_REASSESSMENT_REQUIRED = "SOURCE_WORKFLOW_REASSESSMENT_REQUIRED"
    DECISION_CORRECTION_REQUESTED = "DECISION_CORRECTION_REQUESTED"
    DECISION_REVOCATION_REVIEW_REQUIRED = "DECISION_REVOCATION_REVIEW_REQUIRED"
    ESCALATION_REQUIRED = "ESCALATION_REQUIRED"
    UNABLE_TO_VERIFY = "UNABLE_TO_VERIFY"


class AssuranceFindingRecord(BaseModel):
    """Domain record representing an assurance deficiency or discrepancy."""

    model_config = ConfigDict(extra="ignore")

    finding_id: str = Field(default_factory=lambda: f"gfind-{uuid.uuid4().hex[:12]}")
    decision_id: str
    assurance_id: str
    category: AssuranceFindingCategory
    severity: FindingSeverity = FindingSeverity.HIGH
    title: str
    description: str
    is_material: bool = True

    # Provenance and source context
    source_phase: str
    source_record_id: str
    source_version: str = "v1.0.0"

    # Evidence & rules
    authorization_evidence_ref: Optional[str] = None
    policy_reference: Optional[str] = None
    policy_version: Optional[str] = None
    evidence_refs: List[str] = Field(default_factory=list)

    # Resolution & review
    recommended_action: str
    review_outcome: Optional[FindingReviewOutcome] = None
    review_rationale: Optional[str] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None

    is_resolved: bool = False
    resolution_rationale: Optional[str] = None
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ReviewAssuranceFindingRequest(BaseModel):
    """Request payload to conduct review on an assurance finding."""

    model_config = ConfigDict(extra="ignore")

    review_outcome: FindingReviewOutcome
    review_rationale: str
    recommended_action: Optional[str] = None
    evidence_refs: Optional[List[str]] = Field(default_factory=list)


class ResolveAssuranceFindingRequest(BaseModel):
    """Request payload to mark an assurance finding resolved."""

    model_config = ConfigDict(extra="ignore")

    resolution_rationale: str
    supporting_evidence_refs: Optional[List[str]] = Field(default_factory=list)
