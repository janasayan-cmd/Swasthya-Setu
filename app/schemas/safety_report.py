"""Phase 53: Safety Report Schemas.

Defines the authoritative domain types for governed safety oversight,
evidence consolidation, and reporting.

Core principle:
- REPORT GENERATED != CLINICAL OUTCOME
- Missing evidence != PASS
- Aggregate metric != Safety guarantee
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.safety_assurance import (
    ControlEffectivenessState,
    ControlCategory,
    EvidenceQualityState,
    DegradationState,
    AssuranceScopeRecord,
)

# ---------------------------------------------------------------------------
# Report Lifecycle States
# ---------------------------------------------------------------------------

class SafetyReportLifecycleState(str, Enum):
    """Lifecycle states for a safety report."""
    REQUESTED = "REQUESTED"
    AUTHORIZED = "AUTHORIZED"
    SCOPE_VALIDATED = "SCOPE_VALIDATED"
    EVIDENCE_COLLECTING = "EVIDENCE_COLLECTING"
    EVIDENCE_VALIDATED = "EVIDENCE_VALIDATED"
    AGGREGATING = "AGGREGATING"
    QUALITY_REVIEW = "QUALITY_REVIEW"
    GENERATED = "GENERATED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED_FOR_USE = "APPROVED_FOR_USE"
    PUBLISHED = "PUBLISHED"
    
    # Alternative states
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    STALE = "STALE"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"
    REOPENED = "REOPENED"


# ---------------------------------------------------------------------------
# Report Types
# ---------------------------------------------------------------------------

class SafetyReportType(str, Enum):
    """Supported types of safety oversight reports."""
    CONTROL_ASSURANCE_SUMMARY = "CONTROL_ASSURANCE_SUMMARY"
    CONTROL_EFFECTIVENESS_REPORT = "CONTROL_EFFECTIVENESS_REPORT"
    SAFETY_CONTROL_DEGRADATION_REPORT = "SAFETY_CONTROL_DEGRADATION_REPORT"
    SAFETY_REGRESSION_REPORT = "SAFETY_REGRESSION_REPORT"
    EVIDENCE_GAP_REPORT = "EVIDENCE_GAP_REPORT"
    SAFETY_CHANGE_EFFECTIVENESS_REPORT = "SAFETY_CHANGE_EFFECTIVENESS_REPORT"
    RISK_CONTROL_COVERAGE_REPORT = "RISK_CONTROL_COVERAGE_REPORT"
    PROVIDER_SAFETY_ASSURANCE_REPORT = "PROVIDER_SAFETY_ASSURANCE_REPORT"
    WORKFLOW_SAFETY_ASSURANCE_REPORT = "WORKFLOW_SAFETY_ASSURANCE_REPORT"
    AI_SAFETY_ASSURANCE_REPORT = "AI_SAFETY_ASSURANCE_REPORT"
    MEDICATION_SAFETY_ASSURANCE_REPORT = "MEDICATION_SAFETY_ASSURANCE_REPORT"
    TRIAGE_SAFETY_ASSURANCE_REPORT = "TRIAGE_SAFETY_ASSURANCE_REPORT"
    DATA_INTEGRITY_ASSURANCE_REPORT = "DATA_INTEGRITY_ASSURANCE_REPORT"
    ORGANIZATION_SAFETY_ASSURANCE_REPORT = "ORGANIZATION_SAFETY_ASSURANCE_REPORT"
    FACILITY_SAFETY_ASSURANCE_REPORT = "FACILITY_SAFETY_ASSURANCE_REPORT"
    PERIODIC_SAFETY_OVERSIGHT_REPORT = "PERIODIC_SAFETY_OVERSIGHT_REPORT"


# ---------------------------------------------------------------------------
# Report Quality States
# ---------------------------------------------------------------------------

class SafetyReportQualityState(str, Enum):
    """Overall evidence quality state of a safety report."""
    HIGH_CONFIDENCE_EVIDENCE = "HIGH_CONFIDENCE_EVIDENCE"
    SUFFICIENT_EVIDENCE = "SUFFICIENT_EVIDENCE"
    PARTIAL_EVIDENCE = "PARTIAL_EVIDENCE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    CONFLICTED_EVIDENCE = "CONFLICTED_EVIDENCE"
    STALE_EVIDENCE = "STALE_EVIDENCE"
    UNVERIFIED_EVIDENCE = "UNVERIFIED_EVIDENCE"


# ---------------------------------------------------------------------------
# Review Decisions
# ---------------------------------------------------------------------------

class SafetyReportReviewDecision(str, Enum):
    """Possible outcomes of human review of a safety report."""
    ACCEPT_REPORT = "ACCEPT_REPORT"
    ACCEPT_WITH_LIMITATIONS = "ACCEPT_WITH_LIMITATIONS"
    REQUEST_REVISION = "REQUEST_REVISION"
    REQUIRE_MORE_EVIDENCE = "REQUIRE_MORE_EVIDENCE"
    REJECT_REPORT = "REJECT_REPORT"
    ESCALATE_TO_GOVERNANCE = "ESCALATE_TO_GOVERNANCE"
    ESCALATE_TO_INCIDENT_REVIEW = "ESCALATE_TO_INCIDENT_REVIEW"
    ESCALATE_TO_SAFETY_CHANGE = "ESCALATE_TO_SAFETY_CHANGE"


# ---------------------------------------------------------------------------
# Evidence Gap Classification
# ---------------------------------------------------------------------------

class EvidenceGapSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class EvidenceGapRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")
    gap_id: str = Field(default_factory=lambda: f"evg-{uuid.uuid4().hex[:12]}")
    control_id: Optional[str] = None
    gap_description: str
    gap_type: str = Field(..., description="e.g., missing_evaluation, stale_evidence, missing_denominator")
    severity: EvidenceGapSeverity = EvidenceGapSeverity.LOW
    remediation_required: bool = False


# ---------------------------------------------------------------------------
# Aggregate Assurance Findings
# ---------------------------------------------------------------------------

class ControlAssuranceDistribution(BaseModel):
    """Aggregate distribution of control effectiveness states."""
    model_config = ConfigDict(extra="ignore")
    total_controls_evaluated: int = 0
    effective_observed: int = 0
    partially_effective: int = 0
    degraded: int = 0
    failed: int = 0
    insufficient_evidence: int = 0
    effectiveness_unclear: int = 0
    requires_reassessment: int = 0

class ControlFinding(BaseModel):
    """A consolidated finding for a specific control within the report scope."""
    model_config = ConfigDict(extra="ignore")
    control_id: str
    control_version: str
    control_category: ControlCategory
    effectiveness_state: ControlEffectivenessState
    degradation_state: DegradationState = DegradationState.STABLE
    evidence_quality: EvidenceQualityState
    evaluation_id: Optional[str] = None
    bypass_count: int = 0
    regression_detected: bool = False
    evidence_gap_ids: List[str] = Field(default_factory=list)
    linked_incident_ids: List[str] = Field(default_factory=list)
    linked_risk_ids: List[str] = Field(default_factory=list)
    linked_change_ids: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Report Domain Models
# ---------------------------------------------------------------------------

class SafetyReportScope(BaseModel):
    model_config = ConfigDict(extra="ignore")
    organization_id: Optional[str] = None
    facility_id: Optional[str] = None
    department_id: Optional[str] = None
    workflow_id: Optional[str] = None
    control_id: Optional[str] = None
    control_category: Optional[ControlCategory] = None
    provider_id: Optional[str] = None
    deployment_version: Optional[str] = None
    feature_flag_id: Optional[str] = None
    safety_policy_version: Optional[str] = None
    rule_version: Optional[str] = None
    ai_model_version: Optional[str] = None
    time_period_start: datetime
    time_period_end: datetime


class SafetyReportRecord(BaseModel):
    """Authoritative record of a safety oversight report."""
    model_config = ConfigDict(extra="ignore")
    
    report_id: str = Field(default_factory=lambda: f"srep-{uuid.uuid4().hex[:14]}")
    report_type: SafetyReportType
    report_version: int = 1
    
    scope: SafetyReportScope
    
    lifecycle_state: SafetyReportLifecycleState = SafetyReportLifecycleState.REQUESTED
    quality_state: SafetyReportQualityState = SafetyReportQualityState.UNVERIFIED_EVIDENCE
    
    distribution: Optional[ControlAssuranceDistribution] = None
    control_findings: List[ControlFinding] = Field(default_factory=list)
    evidence_gaps: List[EvidenceGapRecord] = Field(default_factory=list)
    
    # Trends & Insights (No causation claims)
    degradations_detected: int = 0
    regressions_detected: int = 0
    recurring_failures: int = 0
    
    # AI Assistance
    ai_generated_summary: Optional[str] = None
    ai_suggested_gaps: List[str] = Field(default_factory=list)
    ai_status_acknowledged: bool = False
    
    # Lifecycle Tracking
    requested_by_id: str
    requested_by_role: str
    organization_id: Optional[str] = None
    facility_id: Optional[str] = None
    
    # Review
    reviewer_id: Optional[str] = None
    reviewer_role: Optional[str] = None
    reviewer_authorization_basis: Optional[str] = None
    review_decision: Optional[SafetyReportReviewDecision] = None
    review_summary: Optional[str] = None
    review_limitations: List[str] = Field(default_factory=list)
    
    # Timestamps
    requested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    generated_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None
    published_at: Optional[datetime] = None
    superseded_at: Optional[datetime] = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    idempotency_key: Optional[str] = None
    request_id: Optional[str] = None
    job_id: Optional[str] = None

    disclaimer: str = Field(
        default=(
            "This report is an evidence consolidation artifact. It does not certify "
            "permanent clinical safety or eliminate risk. Aggregate metrics "
            "do not represent clinical outcomes or probability of patient safety."
        )
    )


# ---------------------------------------------------------------------------
# API Request / Response Models
# ---------------------------------------------------------------------------

class SafetyReportRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    report_type: SafetyReportType
    organization_id: Optional[str] = None
    facility_id: Optional[str] = None
    department_id: Optional[str] = None
    workflow_id: Optional[str] = None
    control_id: Optional[str] = None
    control_category: Optional[ControlCategory] = None
    time_period_start: datetime
    time_period_end: datetime
    idempotency_key: Optional[str] = None

class SafetyReportReviewSubmission(BaseModel):
    model_config = ConfigDict(extra="ignore")
    report_version: int
    decision: SafetyReportReviewDecision
    review_summary: str = Field(..., min_length=10)
    review_limitations: List[str] = Field(default_factory=list)
    ai_material_reviewed: bool = False
