"""Phase 73: Milestones, Evidence & Verification Schemas.

Defines schemas for:
- Granular implementation milestones
- Structured evidence references and classification
- Independent implementation verification enforcing separation of duties
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class MilestoneStatus(str, Enum):
    """Lifecycle status of an individual milestone."""

    NOT_STARTED = "NOT_STARTED"
    READY = "READY"
    IN_PROGRESS = "IN_PROGRESS"
    BLOCKED = "BLOCKED"
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class VerificationOutcome(str, Enum):
    """Outcome of an independent verification review."""

    VERIFIED = "VERIFIED"
    PARTIALLY_VERIFIED = "PARTIALLY_VERIFIED"
    REJECTED = "REJECTED"
    INCONCLUSIVE = "INCONCLUSIVE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ImplementationMilestoneRecord(BaseModel):
    """Domain model tracking an individual implementation milestone."""

    model_config = ConfigDict(extra="ignore")

    milestone_id: str = Field(default_factory=lambda: f"gdms-{uuid.uuid4().hex[:12]}")
    implementation_id: str
    title: str
    description: str
    responsible_owner_id: str

    start_date: Optional[datetime] = None
    target_date: datetime
    completion_date: Optional[datetime] = None

    status: MilestoneStatus = MilestoneStatus.NOT_STARTED
    expected_output: str
    required_evidence_types: List[str] = Field(default_factory=list)
    dependency_ids: List[str] = Field(default_factory=list)

    submission_notes: Optional[str] = None
    submitted_at: Optional[datetime] = None
    verification_status: str = "UNVERIFIED"

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ImplementationEvidenceRecord(BaseModel):
    """Domain record representing referenced proof of milestone or action completion."""

    model_config = ConfigDict(extra="ignore")

    evidence_id: str = Field(default_factory=lambda: f"gdev-{uuid.uuid4().hex[:12]}")
    implementation_id: str
    milestone_id: Optional[str] = None
    source_record_ref: str
    evidence_type: str
    version: str = "1.0"
    owner_id: str

    submitted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    access_classification: str = "STANDARD"  # STANDARD, RESTRICTED, CONFIDENTIAL
    review_status: str = "PENDING_REVIEW"  # PENDING_REVIEW, ACCEPTED, REJECTED, CONTRADICTORY

    reviewed_by: Optional[str] = None
    review_comments: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ImplementationVerificationRecord(BaseModel):
    """Domain record of an independent verification check."""

    model_config = ConfigDict(extra="ignore")

    verification_id: str = Field(default_factory=lambda: f"gdvr-{uuid.uuid4().hex[:12]}")
    implementation_id: str
    milestone_id: Optional[str] = None
    verification_criteria: List[str] = Field(default_factory=list)
    evidence_reviewed: List[str] = Field(default_factory=list)

    outcome: VerificationOutcome
    verifier_id: str
    verifier_role: str
    verified_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    rationale: str
    outstanding_deficiencies: List[str] = Field(default_factory=list)
    required_remediation: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


# Request Models
class CreateMilestoneRequest(BaseModel):
    """Request payload to add a milestone to an implementation plan."""

    model_config = ConfigDict(extra="ignore")

    title: str
    description: str
    responsible_owner_id: str
    target_date: datetime
    start_date: Optional[datetime] = None
    expected_output: str
    required_evidence_types: Optional[List[str]] = Field(default_factory=list)
    dependency_ids: Optional[List[str]] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class UpdateMilestoneRequest(BaseModel):
    """Request payload to update milestone properties."""

    model_config = ConfigDict(extra="ignore")

    title: Optional[str] = None
    description: Optional[str] = None
    target_date: Optional[datetime] = None
    status: Optional[MilestoneStatus] = None
    expected_output: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class SubmitMilestoneRequest(BaseModel):
    """Request payload when owner submits completed milestone."""

    model_config = ConfigDict(extra="ignore")

    submission_notes: str
    evidence_refs: Optional[List[str]] = Field(default_factory=list)


class SubmitEvidenceRequest(BaseModel):
    """Request payload to attach an evidence reference."""

    model_config = ConfigDict(extra="ignore")

    milestone_id: Optional[str] = None
    source_record_ref: str
    evidence_type: str
    version: Optional[str] = "1.0"
    access_classification: Optional[str] = "STANDARD"
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ReviewEvidenceRequest(BaseModel):
    """Request payload to accept, reject, or flag contradictory evidence."""

    model_config = ConfigDict(extra="ignore")

    review_status: str  # ACCEPTED, REJECTED, CONTRADICTORY
    review_comments: str


class VerifyMilestoneRequest(BaseModel):
    """Request payload for independent verification of milestone implementation."""

    model_config = ConfigDict(extra="ignore")

    milestone_id: Optional[str] = None
    outcome: VerificationOutcome
    verification_criteria: Optional[List[str]] = Field(default_factory=list)
    evidence_reviewed: Optional[List[str]] = Field(default_factory=list)
    rationale: str
    outstanding_deficiencies: Optional[List[str]] = Field(default_factory=list)
    required_remediation: Optional[str] = None
