"""Phase 71: Cross-Audit Pattern & Systemic Issue Candidate Schemas.

Defines schemas for:
- Cross-audit analytical pattern identification
- Systemic issue candidate generation with deterministic scoring
- Insight review, disposition, and cross-phase governance referral
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.audit_analytics_source import DataQualityStatus


class PatternCategory(str, Enum):
    """Classification of cross-audit patterns."""

    CONTROL_WEAKNESS_CONCENTRATION = "CONTROL_WEAKNESS_CONCENTRATION"
    CROSS_FACILITY_DEVIATION = "CROSS_FACILITY_DEVIATION"
    RECURRING_DOCUMENTATION_GAP = "RECURRING_DOCUMENTATION_GAP"
    EVIDENCE_QUALITY_DEFICIT = "EVIDENCE_QUALITY_DEFICIT"
    AUTHORIZATION_FAILURE_PATTERN = "AUTHORIZATION_FAILURE_PATTERN"
    POST_CAPA_RECURRENCE = "POST_CAPA_RECURRENCE"
    TRACEABILITY_BREAKDOWN = "TRACEABILITY_BREAKDOWN"
    GENERAL_GOVERNANCE_PATTERN = "GENERAL_GOVERNANCE_PATTERN"


class PatternReviewStatus(str, Enum):
    """Review state of an identified cross-audit pattern."""

    DETECTED = "DETECTED"
    PENDING_REVIEW = "PENDING_REVIEW"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"
    REFERRED = "REFERRED"


class SystemicCandidateStatus(str, Enum):
    """Lifecycle state of a systemic issue candidate."""

    DETECTED = "DETECTED"
    PENDING_REVIEW = "PENDING_REVIEW"
    CONFIRMED_PATTERN = "CONFIRMED_PATTERN"
    SYSTEMIC_ISSUE_CANDIDATE = "SYSTEMIC_ISSUE_CANDIDATE"
    REJECTED = "REJECTED"
    ESCALATED = "ESCALATED"
    REFERRED_FOR_RISK_REVIEW = "REFERRED_FOR_RISK_REVIEW"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class AuditPatternRecord(BaseModel):
    """Domain model tracking an identified cross-audit analytical pattern."""

    model_config = ConfigDict(extra="ignore")

    pattern_id: str = Field(default_factory=lambda: f"gpat-{uuid.uuid4().hex[:12]}")
    pattern_name: str
    pattern_category: PatternCategory = PatternCategory.CONTROL_WEAKNESS_CONCENTRATION
    related_audit_ids: List[str] = Field(default_factory=list)
    related_finding_ids: List[str] = Field(default_factory=list)
    affected_controls: List[str] = Field(default_factory=list)
    affected_processes: List[str] = Field(default_factory=list)
    affected_facilities: List[str] = Field(default_factory=list)

    matching_criteria: Dict[str, Any] = Field(default_factory=dict)
    time_period: str = "LAST_12_MONTHS"
    potential_impact: str
    analytical_explanation: str

    review_status: PatternReviewStatus = PatternReviewStatus.DETECTED
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    review_rationale: Optional[str] = None

    referral_refs: List[Dict[str, Any]] = Field(default_factory=list)
    organization_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SystemicIssueCandidateRecord(BaseModel):
    """Domain model tracking a systemic issue candidate requiring human review."""

    model_config = ConfigDict(extra="ignore")

    candidate_id: str = Field(default_factory=lambda: f"gsys-{uuid.uuid4().hex[:12]}")
    title: str
    description: str
    status: SystemicCandidateStatus = SystemicCandidateStatus.DETECTED

    priority_score: float = 0.0
    score_factors: Dict[str, float] = Field(default_factory=dict)

    supporting_finding_ids: List[str] = Field(default_factory=list)
    supporting_audit_ids: List[str] = Field(default_factory=list)
    supporting_pattern_ids: List[str] = Field(default_factory=list)

    matching_rationale: str
    scoring_methodology: str = "DETERMINISTIC_WEIGHTED_SCORE_V1"
    configuration_version: str = "v1.0.0"

    affected_controls: List[str] = Field(default_factory=list)
    affected_processes: List[str] = Field(default_factory=list)
    affected_facilities: List[str] = Field(default_factory=list)

    data_quality_status: DataQualityStatus = DataQualityStatus.COMPLETE
    known_limitations: List[str] = Field(default_factory=list)

    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    review_rationale: Optional[str] = None

    referral_refs: List[Dict[str, Any]] = Field(default_factory=list)
    organization_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)


# Request Models
class ReviewPatternRequest(BaseModel):
    """Request payload to review an identified pattern."""

    model_config = ConfigDict(extra="ignore")

    review_status: PatternReviewStatus
    review_rationale: str


class ReferPatternRequest(BaseModel):
    """Request payload to refer a pattern to an authoritative governance workflow."""

    model_config = ConfigDict(extra="ignore")

    destination_workflow: str  # PHASE_54_CAPA, PHASE_63_RISK_REVIEW, PHASE_67_ESCALATION, PHASE_69_COMPLIANCE, PHASE_70_FOLLOW_UP
    referral_reason: str
    notes: Optional[str] = None


class ReviewSystemicCandidateRequest(BaseModel):
    """Request payload to record a human review decision on a systemic issue candidate."""

    model_config = ConfigDict(extra="ignore")

    status: SystemicCandidateStatus
    review_rationale: str


class ConfirmSystemicCandidateRequest(BaseModel):
    """Request payload to confirm a systemic issue candidate."""

    model_config = ConfigDict(extra="ignore")

    review_rationale: str


class RejectSystemicCandidateRequest(BaseModel):
    """Request payload to reject a systemic issue candidate."""

    model_config = ConfigDict(extra="ignore")

    rejection_rationale: str


class ReferSystemicCandidateRequest(BaseModel):
    """Request payload to refer a systemic issue to authoritative governance workflows."""

    model_config = ConfigDict(extra="ignore")

    destination_workflow: str  # PHASE_54_CAPA, PHASE_55_EFFECTIVENESS, PHASE_63_RISK_REVIEW, PHASE_67_ESCALATION, PHASE_69_COMPLIANCE, PHASE_49_INCIDENT
    referral_reason: str
    notes: Optional[str] = None
