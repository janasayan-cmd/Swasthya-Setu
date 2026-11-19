"""Phase 68: Decision Correction Coordination and Reporting Schemas.

Defines schemas for correction and revocation review requests directed to
authoritative workflow owners, cross-workflow consistency evaluations, and assurance reporting.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.decision_assurance import (
    AssuranceLifecycleState,
    AuthorizationVerificationStatus,
    DecisionSourcePhase,
    EvidenceAssuranceStatus,
    SeparationOfDutiesStatus,
)


class CorrectionRequestStatus(str, Enum):
    """Lifecycle status of a decision correction or revocation request."""

    SUBMITTED = "SUBMITTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    IN_REVIEW = "IN_REVIEW"
    ACCEPTED = "ACCEPTED"
    ACCEPTED_AND_AMENDED = "ACCEPTED_AND_AMENDED"
    AMENDED = "AMENDED"
    REJECTED = "REJECTED"
    REVERIFIED = "REVERIFIED"


class CorrectionRequestRecord(BaseModel):
    """Domain model tracking a correction or revocation review request sent to an authoritative owner."""

    model_config = ConfigDict(extra="ignore")

    request_id: str = Field(default_factory=lambda: f"gcorr-{uuid.uuid4().hex[:12]}")
    decision_id: str
    target_phase: DecisionSourcePhase
    target_record_id: str
    request_type: str  # CORRECTION or REVOCATION_REVIEW
    status: CorrectionRequestStatus = CorrectionRequestStatus.SUBMITTED

    reason: str
    finding_refs: List[str] = Field(default_factory=list)
    requested_by: str
    requested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Authoritative owner response
    response_notes: Optional[str] = None
    responded_by: Optional[str] = None
    responded_at: Optional[datetime] = None
    authoritative_action_taken: Optional[str] = None
    updated_record_version: Optional[str] = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SubmitDecisionCorrectionRequest(BaseModel):
    """Request payload to submit a correction request to an authoritative decision owner."""

    model_config = ConfigDict(extra="ignore")

    reason: str
    finding_refs: Optional[List[str]] = Field(default_factory=list)
    suggested_correction: Optional[str] = None


class SubmitRevocationReviewRequest(BaseModel):
    """Request payload to request revocation review from an authoritative decision owner."""

    model_config = ConfigDict(extra="ignore")

    reason: str
    finding_refs: Optional[List[str]] = Field(default_factory=list)
    revocation_grounds: str


class RespondCorrectionRequest(BaseModel):
    """Authoritative owner response payload accepting or rejecting a correction request."""

    model_config = ConfigDict(extra="ignore")

    status: CorrectionRequestStatus  # ACCEPTED or REJECTED
    response_notes: str
    authoritative_action_taken: Optional[str] = None
    updated_record_version: Optional[str] = None


class CrossWorkflowConsistencyCheckResult(BaseModel):
    """Domain model capturing consistency evaluation between two related decisions."""

    model_config = ConfigDict(extra="ignore")

    check_id: str = Field(default_factory=lambda: f"gcons-{uuid.uuid4().hex[:12]}")
    decision_id: str
    related_decision_id: str
    is_consistent: bool
    conflict_type: Optional[str] = None
    conflict_description: Optional[str] = None
    discrepancy_type: Optional[str] = None
    discrepancy_details: Optional[str] = None
    checked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DecisionAssuranceReportResponse(BaseModel):
    """Aggregated governance assurance summary report."""

    model_config = ConfigDict(extra="ignore")

    organization_id: str
    facility_id: Optional[str] = None
    total_decisions_registered: int
    verified_count: int
    verified_with_limitations_count: int
    review_required_count: int
    authorization_unverifiable_count: int
    separation_violation_count: int
    conflicted_count: int
    active_findings_count: int
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
