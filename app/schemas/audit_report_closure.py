"""Phase 70: Audit Report, Review, Closure & Follow-Up Schemas.

Defines schemas for:
- Audit report preparation, versioning, review, and approval
- Separation of duties: author cannot approve their own report
- Governed audit closure, follow-up tracking, and reopening
- Aggregated reporting across programmes, findings, overdue milestones, and follow-ups
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class AuditConclusion(str, Enum):
    """Overall conclusion rendered by an independent clinical safety audit."""

    SATISFACTORY = "SATISFACTORY"
    SATISFACTORY_WITH_CONDITIONS = "SATISFACTORY_WITH_CONDITIONS"
    UNSATISFACTORY = "UNSATISFACTORY"
    INCONCLUSIVE = "INCONCLUSIVE"


class AuditReportStatus(str, Enum):
    """Lifecycle status of an audit report."""

    DRAFT = "DRAFT"
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    PUBLISHED = "PUBLISHED"


class AuditReportRecord(BaseModel):
    """Domain model tracking a formal audit report."""

    model_config = ConfigDict(extra="ignore")

    report_id: str = Field(default_factory=lambda: f"grpt-{uuid.uuid4().hex[:12]}")
    audit_id: str
    version: int = 1
    status: AuditReportStatus = AuditReportStatus.DRAFT

    title: str
    executive_summary: str
    audit_period_start: Optional[datetime] = None
    audit_period_end: Optional[datetime] = None

    scope_summary: str
    scope_limitations: List[str] = Field(default_factory=list)

    auditor_assignments_summary: List[Dict[str, str]] = Field(default_factory=list)
    independence_status_summary: str = "VERIFIED"

    tests_performed_count: int = 0
    tests_passed_count: int = 0
    tests_failed_count: int = 0
    tests_inconclusive_count: int = 0

    findings_summary: Dict[str, int] = Field(default_factory=dict)
    confirmed_finding_ids: List[str] = Field(default_factory=list)
    disputed_finding_ids: List[str] = Field(default_factory=list)
    corrective_action_refs: List[str] = Field(default_factory=list)

    audit_conclusion: AuditConclusion = AuditConclusion.INCONCLUSIVE
    recommendations: List[str] = Field(default_factory=list)

    created_by: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    review_comments: Optional[str] = None

    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    approval_policy_ref: Optional[str] = None

    metadata: Dict[str, Any] = Field(default_factory=dict)


# ===========================================================================
# Request Models
# ===========================================================================

class GenerateAuditReportRequest(BaseModel):
    """Request payload to generate a draft audit report."""

    model_config = ConfigDict(extra="ignore")

    title: str
    executive_summary: str
    audit_conclusion: AuditConclusion
    recommendations: Optional[List[str]] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ReviewAuditReportRequest(BaseModel):
    """Request payload for technical or peer review of an audit report."""

    model_config = ConfigDict(extra="ignore")

    review_comments: str
    requires_revision: Optional[bool] = False


class ApproveAuditReportRequest(BaseModel):
    """Request payload for authorized governance sign-off. Enforces separation of duties."""

    model_config = ConfigDict(extra="ignore")

    approval_policy_ref: str
    approval_comments: Optional[str] = None


class CloseAuditRequest(BaseModel):
    """Request payload to formally close an audit."""

    model_config = ConfigDict(extra="ignore")

    closure_rationale: str
    follow_up_required: Optional[bool] = False


class ReopenAuditRequest(BaseModel):
    """Request payload to reopen an audit following new post-audit safety signals."""

    model_config = ConfigDict(extra="ignore")

    reopening_reason: str
    source_trigger_ref: Optional[str] = None  # e.g. Phase 59 or Phase 66 ref


# ===========================================================================
# Aggregated Reporting Models
# ===========================================================================

class AuditSummaryReportResponse(BaseModel):
    """High-level summary of audit programmes, audits, and completion rates."""

    model_config = ConfigDict(extra="ignore")

    organization_id: str
    facility_id: Optional[str] = None
    total_programmes: int
    total_audits: int
    audits_in_progress: int
    audits_closed: int
    audits_overdue: int
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AuditFindingsReportResponse(BaseModel):
    """Aggregated finding metrics categorized by severity and status."""

    model_config = ConfigDict(extra="ignore")

    organization_id: str
    facility_id: Optional[str] = None
    total_findings: int
    confirmed_findings: int
    disputed_findings: int
    open_findings: int
    closed_findings: int
    findings_by_severity: Dict[str, int] = Field(default_factory=dict)
    findings_by_category: Dict[str, int] = Field(default_factory=dict)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AuditOverdueReportResponse(BaseModel):
    """Report detailing overdue audits, evidence requests, and corrective actions."""

    model_config = ConfigDict(extra="ignore")

    organization_id: str
    facility_id: Optional[str] = None
    overdue_audits_count: int
    overdue_evidence_requests_count: int
    overdue_finding_responses_count: int
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AuditFollowUpStatusResponse(BaseModel):
    """Follow-up monitoring report across closed or follow-up-required audits."""

    model_config = ConfigDict(extra="ignore")

    organization_id: str
    facility_id: Optional[str] = None
    audits_requiring_follow_up: int
    active_corrective_action_links: int
    reopened_audits_count: int
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
