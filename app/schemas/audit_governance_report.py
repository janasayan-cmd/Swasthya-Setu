"""Phase 71: Audit Intelligence Governance & Management Reporting Schemas.

Defines schemas for:
- Historical findings overview and aggregations
- Time-series trend analytics
- Structured, reproducible management review preparation reports
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.audit_analytics_source import DataQualityStatus


class HistoricalFindingsOverviewResponse(BaseModel):
    """Aggregated historical finding metrics across a reporting period."""

    model_config = ConfigDict(extra="ignore")

    organization_id: str
    facility_id: Optional[str] = None
    reporting_period: str
    total_findings: int
    confirmed_findings: int
    open_findings: int
    disputed_findings: int
    closed_findings: int
    withdrawn_findings: int

    findings_by_severity: Dict[str, int] = Field(default_factory=dict)
    findings_by_category: Dict[str, int] = Field(default_factory=dict)
    findings_by_control: Dict[str, int] = Field(default_factory=dict)
    findings_by_process: Dict[str, int] = Field(default_factory=dict)
    findings_by_facility: Dict[str, int] = Field(default_factory=dict)

    audit_coverage_summary: Dict[str, Any] = Field(default_factory=dict)
    data_quality_status: DataQualityStatus = DataQualityStatus.COMPLETE
    known_data_limitations: List[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class GovernanceTrendsResponse(BaseModel):
    """Configurable time-series trend analysis across audit intelligence metrics."""

    model_config = ConfigDict(extra="ignore")

    organization_id: str
    facility_id: Optional[str] = None
    reporting_period: str

    new_findings_trend: List[Dict[str, Any]] = Field(default_factory=list)
    repeat_finding_trend: List[Dict[str, Any]] = Field(default_factory=list)
    backlog_trend: List[Dict[str, Any]] = Field(default_factory=list)
    capa_recurrence_trend: List[Dict[str, Any]] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ManagementReportRecord(BaseModel):
    """Domain model tracking a reproducible governance management review report."""

    model_config = ConfigDict(extra="ignore")

    report_id: str = Field(default_factory=lambda: f"gmgt-{uuid.uuid4().hex[:12]}")
    title: str
    executive_summary: str
    reporting_period_start: Optional[datetime] = None
    reporting_period_end: Optional[datetime] = None

    audit_coverage_summary: Dict[str, Any] = Field(default_factory=dict)
    findings_summary: Dict[str, Any] = Field(default_factory=dict)
    repeat_findings_summary: Dict[str, Any] = Field(default_factory=dict)
    systemic_issues_summary: Dict[str, Any] = Field(default_factory=dict)
    capa_recurrence_summary: Dict[str, Any] = Field(default_factory=dict)
    governance_trends: Dict[str, Any] = Field(default_factory=dict)

    recommended_review_areas: List[str] = Field(default_factory=list)
    calculation_methodology: str = "DETERMINISTIC_AUDIT_INTELLIGENCE_AGGREGATION_V1"
    configuration_version: str = "v1.0.0"
    inclusion_exclusion_rules: List[str] = Field(default_factory=list)

    data_quality_status: DataQualityStatus = DataQualityStatus.COMPLETE
    known_data_limitations: List[str] = Field(default_factory=list)

    is_approved: bool = False
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    approval_comments: Optional[str] = None

    created_by: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    organization_id: str
    facility_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class GenerateManagementReportRequest(BaseModel):
    """Request payload to generate a reproducible management review report."""

    model_config = ConfigDict(extra="ignore")

    title: str
    executive_summary: str
    reporting_period_start: Optional[datetime] = None
    reporting_period_end: Optional[datetime] = None
    facility_id: Optional[str] = None
    configuration_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ApproveManagementReportRequest(BaseModel):
    """Request payload to approve a management review report."""

    model_config = ConfigDict(extra="ignore")

    approval_comments: str
