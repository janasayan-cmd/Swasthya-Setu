"""Phase 72: Management Review Reports, Closure & Analytics Schemas.

Defines schemas for:
- Formal management review summary reports and approvals
- Review closure checks and gating validation
- Previous decisions reconciliation
- Governance management review executive metrics and analytics
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class ReportReviewStatus(str, Enum):
    """Lifecycle status of a formal management review report."""

    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    FINALIZED = "FINALIZED"


class ReviewClosureOutcome(str, Enum):
    """Evaluation result for whether a review meeting can close."""

    CAN_CLOSE = "CAN_CLOSE"
    CANNOT_CLOSE = "CANNOT_CLOSE"


class ManagementReviewReportRecord(BaseModel):
    """Domain record representing an executive summary report of a management review."""

    model_config = ConfigDict(extra="ignore")

    report_id: str = Field(default_factory=lambda: f"gmrp-{uuid.uuid4().hex[:12]}")
    review_id: str
    programme_id: str
    version: int = 1
    status: ReportReviewStatus = ReportReviewStatus.DRAFT
    title: str
    executive_summary: str

    attendees_summary: List[Dict[str, Any]] = Field(default_factory=list)
    agenda_summary: List[Dict[str, Any]] = Field(default_factory=list)
    key_decisions: List[Dict[str, Any]] = Field(default_factory=list)
    commitments_assigned: List[Dict[str, Any]] = Field(default_factory=list)
    previous_actions_reconciliation: List[Dict[str, Any]] = Field(default_factory=list)

    prepared_by: str
    prepared_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    approval_notes: Optional[str] = None

    finalized_by: Optional[str] = None
    finalized_at: Optional[datetime] = None

    distribution_list: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ReviewClosureCheckResponse(BaseModel):
    """Response detailing conditions for review closure."""

    model_config = ConfigDict(extra="ignore")

    review_id: str
    outcome: ReviewClosureOutcome
    can_close: bool
    all_agenda_items_concluded: bool
    decisions_formalized: bool
    commitments_assigned: bool
    report_approved: bool
    pending_blockers: List[str] = Field(default_factory=list)
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ManagementReviewAnalyticsResponse(BaseModel):
    """Response aggregating executive governance review metrics."""

    model_config = ConfigDict(extra="ignore")

    organization_id: str
    total_programmes: int = 0
    total_reviews: int = 0
    reviews_by_status: Dict[str, int] = Field(default_factory=dict)
    total_decisions: int = 0
    decisions_by_category: Dict[str, int] = Field(default_factory=dict)
    total_commitments: int = 0
    commitments_by_status: Dict[str, int] = Field(default_factory=dict)
    overdue_commitments_count: int = 0
    escalated_commitments_count: int = 0
    average_commitment_completion_days: float = 0.0
    compliance_conformance_rate: float = 100.0
    calculated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# Request Models
class GenerateManagementReviewReportRequest(BaseModel):
    """Request payload to generate a summary report from review artifacts."""

    model_config = ConfigDict(extra="ignore")

    title: Optional[str] = None
    executive_summary: Optional[str] = None
    distribution_list: Optional[List[str]] = Field(default_factory=list)


class ApproveReviewReportRequest(BaseModel):
    """Request payload to approve a review report."""

    model_config = ConfigDict(extra="ignore")

    approval_notes: Optional[str] = None


class CloseManagementReviewRequest(BaseModel):
    """Request payload to close a review."""

    model_config = ConfigDict(extra="ignore")

    closure_notes: Optional[str] = None
    closure_status: Optional[str] = "COMPLETED"


class ReopenManagementReviewRequest(BaseModel):
    """Request payload to reopen a completed review meeting."""

    model_config = ConfigDict(extra="ignore")

    reopening_reason: str
    reopened_by: str
