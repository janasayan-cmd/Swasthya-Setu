"""Phase 75: Portfolio Reporting & Executive Analytics Schemas.

Defines schemas and models for:
- Consolidated portfolio implementation and adoption progress
- Dependency and cumulative impact summary responses
- Cross-initiative conflict summaries with coverage disclosures
- Background coordination job run results
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class PortfolioTimelineEvent(BaseModel):
    """An event in the portfolio coordination timeline."""
    model_config = ConfigDict(extra="forbid")

    event_id: str
    event_type: str
    timestamp: str
    actor_id: str
    summary: str
    details: Dict[str, Any] = Field(default_factory=dict)


class PortfolioOverviewResponse(BaseModel):
    """Overview of a single governance portfolio."""
    model_config = ConfigDict(extra="forbid")

    portfolio_id: str
    tenant_id: str
    name: str
    status: str
    priority: str
    initiatives_count: int = 0
    active_dependencies_count: int = 0
    open_conflicts_count: int = 0
    open_issues_count: int = 0
    blocked_initiatives_count: int = 0


class PortfolioProgressResponse(BaseModel):
    """Consolidated implementation progress across portfolio initiatives."""
    model_config = ConfigDict(extra="forbid")

    portfolio_id: str
    tenant_id: str
    total_initiatives: int = 0
    initiatives_in_planning: int = 0
    initiatives_in_progress: int = 0
    initiatives_completed: int = 0
    initiatives_blocked: int = 0
    source_implementation_coverage_pct: float = 100.0


class PortfolioAdoptionSummaryResponse(BaseModel):
    """Consolidated operational adoption metrics from Phase 74 for portfolio initiatives."""
    model_config = ConfigDict(extra="forbid")

    portfolio_id: str
    tenant_id: str
    total_initiatives: int = 0
    initiatives_with_adoption_monitoring: int = 0
    active_adoption_monitoring_count: int = 0
    sustainability_concerns_count: int = 0
    confirmed_deviations_count: int = 0
    clinical_safety_notice: str = (
        "Adoption progress reflects operational workflow integration only and does not establish clinical effectiveness."
    )


class PortfolioDependencySummaryResponse(BaseModel):
    """Summary of dependencies, circular chains, and blocked relationships."""
    model_config = ConfigDict(extra="forbid")

    portfolio_id: str
    tenant_id: str
    total_dependencies: int = 0
    confirmed_dependencies: int = 0
    satisfied_dependencies: int = 0
    blocked_dependencies: int = 0
    disputed_dependencies: int = 0
    circular_dependency_detected: bool = False
    circular_paths: List[List[str]] = Field(default_factory=list)


class PortfolioImpactSummaryResponse(BaseModel):
    """Summary of latest cumulative operational impact assessment."""
    model_config = ConfigDict(extra="forbid")

    portfolio_id: str
    tenant_id: str
    latest_assessment_id: Optional[str] = None
    concurrent_changes_count: int = 0
    affected_departments_count: int = 0
    affected_facilities_count: int = 0
    disruption_risk_level: str = "UNKNOWN"
    limitations: List[str] = Field(default_factory=list)


class CrossInitiativeConflictReportResponse(BaseModel):
    """Executive cross-initiative conflict summary."""
    model_config = ConfigDict(extra="forbid")

    tenant_id: str
    report_generated_at: str
    total_conflicts: int = 0
    potential_conflicts: int = 0
    confirmed_conflicts: int = 0
    resolved_conflicts: int = 0
    conflicts_by_classification: Dict[str, int] = Field(default_factory=dict)


class CumulativeImpactReportResponse(BaseModel):
    """Executive cumulative impact report across all active portfolios."""
    model_config = ConfigDict(extra="forbid")

    tenant_id: str
    report_generated_at: str
    total_active_portfolios: int = 0
    total_concurrent_changes: int = 0
    facilities_impacted: List[str] = Field(default_factory=list)
    departments_impacted: List[str] = Field(default_factory=list)
    methodology_disclosure: str = (
        "Aggregate impact estimates reflect operational scheduling and training workload only. Does not predict clinical outcomes."
    )


class PortfolioExecutiveOverviewResponse(BaseModel):
    """System-wide summary of all governance change portfolios."""
    model_config = ConfigDict(extra="forbid")

    tenant_id: str
    report_generated_at: str
    total_portfolios: int = 0
    active_portfolios: int = 0
    completed_portfolios: int = 0
    on_hold_portfolios: int = 0
    total_coordinated_initiatives: int = 0
    total_open_issues: int = 0


class PortfolioBackgroundJobRunResult(BaseModel):
    """Result of an asynchronous / scheduled portfolio coordination cycle."""
    model_config = ConfigDict(extra="forbid")

    job_name: str
    run_timestamp: str
    circular_dependencies_flagged: int = 0
    schedule_overlaps_detected: int = 0
    stale_source_records_flagged: int = 0
    blocked_initiatives_updated: int = 0
    details: List[str] = Field(default_factory=list)
