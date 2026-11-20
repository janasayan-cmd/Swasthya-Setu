"""Phase 73: Implementation Closure & Executive Reporting Schemas.

Defines schemas for:
- Implementation closure readiness validation and controlled completion
- Governed implementation reopening
- Management oversight reporting (overview, overdue, outcomes)
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class ImplementationClosureCheckResponse(BaseModel):
    """Response detailing gating conditions for closing an implementation initiative."""

    model_config = ConfigDict(extra="ignore")

    implementation_id: str
    can_close: bool
    all_milestones_completed: bool
    dependencies_satisfied: bool
    evidence_verified: bool
    outcome_assessed: bool
    pending_blockers: List[str] = Field(default_factory=list)
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ImplementationOverviewResponse(BaseModel):
    """Response providing aggregated management metrics on decision implementations."""

    model_config = ConfigDict(extra="ignore")

    organization_id: str
    total_implementations: int = 0
    implementations_by_status: Dict[str, int] = Field(default_factory=dict)
    implementations_by_category: Dict[str, int] = Field(default_factory=dict)
    plans_awaiting_approval_count: int = 0
    blocked_implementations_count: int = 0
    overdue_milestones_count: int = 0
    failed_verification_count: int = 0
    outcomes_by_state: Dict[str, int] = Field(default_factory=dict)
    open_exceptions_count: int = 0
    data_quality_status: str = "COMPLETE"
    known_limitations: List[str] = Field(default_factory=list)
    calculated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ImplementationReportRecord(BaseModel):
    """Domain model representing a formal oversight report."""

    model_config = ConfigDict(extra="ignore")

    report_id: str = Field(default_factory=lambda: f"gdrp-{uuid.uuid4().hex[:12]}")
    report_type: str = "OVERVIEW"  # OVERVIEW, OVERDUE, OUTCOMES
    reporting_period: str = "Current"
    title: str
    executive_summary: str
    metrics: Dict[str, Any] = Field(default_factory=dict)
    generated_by: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)


# Request Models
class CloseImplementationRequest(BaseModel):
    """Request payload to close an implementation initiative."""

    model_config = ConfigDict(extra="ignore")

    closure_outcome: Optional[str] = "CLOSED"  # CLOSED, CLOSED_WITH_FOLLOW_UP, CLOSED_WITH_LIMITATIONS
    closure_notes: Optional[str] = None
    follow_up_commitments: Optional[List[str]] = Field(default_factory=list)


class ReopenImplementationRequest(BaseModel):
    """Request payload to reopen a closed implementation."""

    model_config = ConfigDict(extra="ignore")

    reopening_reason: str


class GenerateImplementationReportRequest(BaseModel):
    """Request payload to generate a formal oversight report."""

    model_config = ConfigDict(extra="ignore")

    report_type: Optional[str] = "OVERVIEW"
    reporting_period: Optional[str] = "Current"
    title: Optional[str] = None
    executive_summary: Optional[str] = None
