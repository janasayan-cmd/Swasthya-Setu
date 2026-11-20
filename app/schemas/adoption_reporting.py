"""Phase 74: Governance Change Adoption Reporting & Analytics Schemas.

Defines schemas and models for:
- Initiative-level adoption summaries and indicator progress
- Sustainability summaries with strict clinical safety notices
- Historical timeline and audit trail
- Organization-wide adoption and operational drift reports
- Background monitoring job results
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class AdoptionSummaryResponse(BaseModel):
    """Structured summary of adoption monitoring state for an initiative."""
    model_config = ConfigDict(extra="forbid")

    registration_id: str
    tenant_id: str
    title: str
    status: str
    current_baseline_version: Optional[str] = None
    total_indicators: int = 0
    achieved_indicators: int = 0
    in_progress_indicators: int = 0
    not_achieved_indicators: int = 0
    unable_to_determine_indicators: int = 0
    total_evidence_items: int = 0
    verified_evidence_items: int = 0
    pending_evidence_items: int = 0
    rejected_evidence_items: int = 0
    expired_evidence_items: int = 0
    active_exceptions_count: int = 0
    open_drift_signals_count: int = 0
    milestone_progress_pct: float = 0.0
    disclosures_and_limitations: List[str] = Field(default_factory=list)


class SustainabilitySummaryResponse(BaseModel):
    """Structured summary of operational sustainability state."""
    model_config = ConfigDict(extra="forbid")

    registration_id: str
    tenant_id: str
    latest_assessment_id: Optional[str] = None
    latest_disposition: Optional[str] = None
    assessment_status: Optional[str] = None
    evaluated_dimensions: Dict[str, str] = Field(default_factory=dict)
    active_concerns_count: int = 0
    clinical_safety_notice: str = (
        "Operational sustainability assessment only. Does not replace Phase 55 clinical effectiveness."
    )


class TimelineEvent(BaseModel):
    """An individual event entry in the monitoring history."""
    model_config = ConfigDict(extra="forbid")

    event_id: str
    event_type: str
    timestamp: str
    actor_id: str
    summary: str
    details: Dict[str, Any] = Field(default_factory=dict)


class MonitoringHistoryResponse(BaseModel):
    """Complete history of monitoring actions and state transitions."""
    model_config = ConfigDict(extra="forbid")

    registration_id: str
    tenant_id: str
    events_count: int
    events: List[TimelineEvent] = Field(default_factory=list)


class OrganizationAdoptionReportResponse(BaseModel):
    """Executive cross-initiative adoption report across facilities and departments."""
    model_config = ConfigDict(extra="forbid")

    tenant_id: str
    report_generated_at: str
    total_registered_initiatives: int = 0
    active_monitoring_count: int = 0
    concluded_count: int = 0
    initiatives_with_unresolved_drift: int = 0
    initiatives_with_sustainability_concerns: int = 0
    department_adoption_rates: Dict[str, float] = Field(default_factory=dict)
    facility_adoption_rates: Dict[str, float] = Field(default_factory=dict)
    governance_caveat: str = (
        "Operational adoption metrics reflect workflow integration only and do not establish clinical efficacy."
    )


class OperationalDriftReportResponse(BaseModel):
    """System-wide summary of implementation drift signals and dispositions."""
    model_config = ConfigDict(extra="forbid")

    tenant_id: str
    report_generated_at: str
    total_drift_signals: int = 0
    open_signals: int = 0
    under_review_signals: int = 0
    confirmed_deviations: int = 0
    false_alarms: int = 0
    approved_exceptions: int = 0
    signals_by_classification: Dict[str, int] = Field(default_factory=dict)


class BackgroundJobRunResult(BaseModel):
    """Result of an asynchronous / scheduled background monitoring cycle."""
    model_config = ConfigDict(extra="forbid")

    job_name: str
    run_timestamp: str
    overdue_milestones_flagged: int = 0
    stale_evidence_flagged: int = 0
    expired_exceptions_flagged: int = 0
    drift_signals_generated: int = 0
    details: List[str] = Field(default_factory=list)
