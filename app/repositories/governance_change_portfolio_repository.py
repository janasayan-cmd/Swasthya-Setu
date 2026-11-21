"""Phase 75: Governance Change Portfolio Repository.

Provides a thread-safe repository layer for:
- Governance change portfolio records
- Portfolio initiatives
- Cross-initiative dependencies
- Portfolio conflicts
- Scheduling assessments
- Cumulative operational impact assessments
- Resource dependencies
- Cross-initiative issues
- Portfolio review packages
- Timeline events and background coordination job records
"""

from datetime import datetime, timezone
import threading
from typing import Any, Dict, List, Optional

from app.schemas.governance_change_portfolio import (
    GovernanceChangePortfolioRecord,
    PortfolioStatus,
)
from app.schemas.portfolio_initiative import (
    InitiativeCoordinationStatus,
    PortfolioInitiativeRecord,
)
from app.schemas.portfolio_dependencies_conflicts import (
    ConflictStatus,
    CrossInitiativeDependencyRecord,
    DependencyStatus,
    PortfolioConflictRecord,
)
from app.schemas.portfolio_scheduling_impact import (
    CumulativeImpactAssessmentRecord,
    ResourceDependencyRecord,
    ScheduleAssessmentRecord,
)
from app.schemas.portfolio_issues_reviews import (
    PortfolioIssueRecord,
    PortfolioReviewRecord,
)
from app.schemas.portfolio_reporting import (
    PortfolioBackgroundJobRunResult,
    PortfolioTimelineEvent,
)


class GovernanceChangePortfolioRepository:
    """Thread-safe in-memory repository for Phase 75 domain entities."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._portfolios: Dict[str, GovernanceChangePortfolioRecord] = {}
        self._initiatives: Dict[str, PortfolioInitiativeRecord] = {}
        self._dependencies: Dict[str, CrossInitiativeDependencyRecord] = {}
        self._conflicts: Dict[str, PortfolioConflictRecord] = {}
        self._schedule_assessments: Dict[str, ScheduleAssessmentRecord] = {}
        self._impact_assessments: Dict[str, CumulativeImpactAssessmentRecord] = {}
        self._resource_dependencies: Dict[str, ResourceDependencyRecord] = {}
        self._issues: Dict[str, PortfolioIssueRecord] = {}
        self._reviews: Dict[str, PortfolioReviewRecord] = {}
        self._timeline_events: Dict[str, List[PortfolioTimelineEvent]] = {}
        self._job_runs: List[PortfolioBackgroundJobRunResult] = []

    def clear(self) -> None:
        """Clears all stored records (used primarily for test isolation)."""
        with self._lock:
            self._portfolios.clear()
            self._initiatives.clear()
            self._dependencies.clear()
            self._conflicts.clear()
            self._schedule_assessments.clear()
            self._impact_assessments.clear()
            self._resource_dependencies.clear()
            self._issues.clear()
            self._reviews.clear()
            self._timeline_events.clear()
            self._job_runs.clear()

    # -------------------------------------------------------------------------
    # Timeline Events
    # -------------------------------------------------------------------------
    def log_timeline_event(
        self,
        portfolio_id: str,
        event_type: str,
        actor_id: str,
        summary: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> PortfolioTimelineEvent:
        with self._lock:
            event = PortfolioTimelineEvent(
                event_id=f"pfe_{len(self._timeline_events.get(portfolio_id, [])) + 1}",
                event_type=event_type,
                timestamp=datetime.now(timezone.utc).isoformat(),
                actor_id=actor_id,
                summary=summary,
                details=details or {},
            )
            if portfolio_id not in self._timeline_events:
                self._timeline_events[portfolio_id] = []
            self._timeline_events[portfolio_id].append(event)
            return event

    def get_timeline_events(self, portfolio_id: str) -> List[PortfolioTimelineEvent]:
        with self._lock:
            return list(self._timeline_events.get(portfolio_id, []))

    # -------------------------------------------------------------------------
    # Portfolios
    # -------------------------------------------------------------------------
    def save_portfolio(self, record: GovernanceChangePortfolioRecord) -> GovernanceChangePortfolioRecord:
        with self._lock:
            self._portfolios[record.portfolio_id] = record
            return record

    def get_portfolio(self, portfolio_id: str) -> Optional[GovernanceChangePortfolioRecord]:
        with self._lock:
            return self._portfolios.get(portfolio_id)

    def list_portfolios(
        self,
        tenant_id: Optional[str] = None,
        status: Optional[PortfolioStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[GovernanceChangePortfolioRecord]:
        with self._lock:
            results = list(self._portfolios.values())
            if tenant_id:
                results = [p for p in results if p.tenant_id == tenant_id]
            if status:
                results = [p for p in results if p.status == status]
            results.sort(key=lambda p: p.created_at, reverse=True)
            return results[skip : skip + limit]

    # -------------------------------------------------------------------------
    # Initiatives
    # -------------------------------------------------------------------------
    def save_initiative(self, record: PortfolioInitiativeRecord) -> PortfolioInitiativeRecord:
        with self._lock:
            self._initiatives[record.initiative_id] = record
            return record

    def get_initiative(self, initiative_id: str) -> Optional[PortfolioInitiativeRecord]:
        with self._lock:
            return self._initiatives.get(initiative_id)

    def list_initiatives_for_portfolio(
        self, portfolio_id: str, tenant_id: Optional[str] = None
    ) -> List[PortfolioInitiativeRecord]:
        with self._lock:
            results = [
                i for i in self._initiatives.values()
                if i.portfolio_id == portfolio_id and (tenant_id is None or i.tenant_id == tenant_id)
            ]
            results.sort(key=lambda i: i.created_at, reverse=True)
            return results

    def list_all_initiatives(self, tenant_id: Optional[str] = None) -> List[PortfolioInitiativeRecord]:
        with self._lock:
            results = list(self._initiatives.values())
            if tenant_id:
                results = [i for i in results if i.tenant_id == tenant_id]
            return results

    # -------------------------------------------------------------------------
    # Dependencies
    # -------------------------------------------------------------------------
    def save_dependency(self, record: CrossInitiativeDependencyRecord) -> CrossInitiativeDependencyRecord:
        with self._lock:
            self._dependencies[record.dependency_id] = record
            return record

    def get_dependency(self, dependency_id: str) -> Optional[CrossInitiativeDependencyRecord]:
        with self._lock:
            return self._dependencies.get(dependency_id)

    def list_dependencies_for_initiative(
        self, initiative_id: str, tenant_id: Optional[str] = None
    ) -> List[CrossInitiativeDependencyRecord]:
        with self._lock:
            results = [
                d for d in self._dependencies.values()
                if (d.source_initiative_id == initiative_id or d.target_initiative_id == initiative_id)
                and (tenant_id is None or d.tenant_id == tenant_id)
            ]
            results.sort(key=lambda d: d.created_at, reverse=True)
            return results

    def list_dependencies_for_portfolio(
        self, portfolio_id: str, tenant_id: Optional[str] = None
    ) -> List[CrossInitiativeDependencyRecord]:
        with self._lock:
            results = [
                d for d in self._dependencies.values()
                if d.portfolio_id == portfolio_id and (tenant_id is None or d.tenant_id == tenant_id)
            ]
            results.sort(key=lambda d: d.created_at, reverse=True)
            return results

    # -------------------------------------------------------------------------
    # Conflicts
    # -------------------------------------------------------------------------
    def save_conflict(self, record: PortfolioConflictRecord) -> PortfolioConflictRecord:
        with self._lock:
            self._conflicts[record.conflict_id] = record
            return record

    def get_conflict(self, conflict_id: str) -> Optional[PortfolioConflictRecord]:
        with self._lock:
            return self._conflicts.get(conflict_id)

    def list_conflicts_for_portfolio(
        self, portfolio_id: str, tenant_id: Optional[str] = None
    ) -> List[PortfolioConflictRecord]:
        with self._lock:
            results = [
                c for c in self._conflicts.values()
                if c.portfolio_id == portfolio_id and (tenant_id is None or c.tenant_id == tenant_id)
            ]
            results.sort(key=lambda c: c.detected_at, reverse=True)
            return results

    def list_all_conflicts(self, tenant_id: Optional[str] = None) -> List[PortfolioConflictRecord]:
        with self._lock:
            results = list(self._conflicts.values())
            if tenant_id:
                results = [c for c in results if c.tenant_id == tenant_id]
            return results

    # -------------------------------------------------------------------------
    # Scheduling & Impact Assessments
    # -------------------------------------------------------------------------
    def save_schedule_assessment(self, record: ScheduleAssessmentRecord) -> ScheduleAssessmentRecord:
        with self._lock:
            self._schedule_assessments[record.assessment_id] = record
            return record

    def get_schedule_assessment(self, assessment_id: str) -> Optional[ScheduleAssessmentRecord]:
        with self._lock:
            return self._schedule_assessments.get(assessment_id)

    def list_schedule_assessments_for_portfolio(
        self, portfolio_id: str, tenant_id: Optional[str] = None
    ) -> List[ScheduleAssessmentRecord]:
        with self._lock:
            results = [
                s for s in self._schedule_assessments.values()
                if s.portfolio_id == portfolio_id and (tenant_id is None or s.tenant_id == tenant_id)
            ]
            results.sort(key=lambda s: s.created_at, reverse=True)
            return results

    def save_impact_assessment(self, record: CumulativeImpactAssessmentRecord) -> CumulativeImpactAssessmentRecord:
        with self._lock:
            self._impact_assessments[record.assessment_id] = record
            return record

    def get_impact_assessment(self, assessment_id: str) -> Optional[CumulativeImpactAssessmentRecord]:
        with self._lock:
            return self._impact_assessments.get(assessment_id)

    def list_impact_assessments_for_portfolio(
        self, portfolio_id: str, tenant_id: Optional[str] = None
    ) -> List[CumulativeImpactAssessmentRecord]:
        with self._lock:
            results = [
                m for m in self._impact_assessments.values()
                if m.portfolio_id == portfolio_id and (tenant_id is None or m.tenant_id == tenant_id)
            ]
            results.sort(key=lambda m: m.created_at, reverse=True)
            return results

    # -------------------------------------------------------------------------
    # Resource Dependencies
    # -------------------------------------------------------------------------
    def save_resource_dependency(self, record: ResourceDependencyRecord) -> ResourceDependencyRecord:
        with self._lock:
            self._resource_dependencies[record.resource_dependency_id] = record
            return record

    def get_resource_dependency(self, resource_dependency_id: str) -> Optional[ResourceDependencyRecord]:
        with self._lock:
            return self._resource_dependencies.get(resource_dependency_id)

    def list_resource_dependencies_for_portfolio(
        self, portfolio_id: str, tenant_id: Optional[str] = None
    ) -> List[ResourceDependencyRecord]:
        with self._lock:
            results = [
                r for r in self._resource_dependencies.values()
                if r.portfolio_id == portfolio_id and (tenant_id is None or r.tenant_id == tenant_id)
            ]
            results.sort(key=lambda r: r.created_at, reverse=True)
            return results

    # -------------------------------------------------------------------------
    # Issues
    # -------------------------------------------------------------------------
    def save_issue(self, record: PortfolioIssueRecord) -> PortfolioIssueRecord:
        with self._lock:
            self._issues[record.issue_id] = record
            return record

    def get_issue(self, issue_id: str) -> Optional[PortfolioIssueRecord]:
        with self._lock:
            return self._issues.get(issue_id)

    def list_issues_for_portfolio(
        self, portfolio_id: str, tenant_id: Optional[str] = None
    ) -> List[PortfolioIssueRecord]:
        with self._lock:
            results = [
                i for i in self._issues.values()
                if i.portfolio_id == portfolio_id and (tenant_id is None or i.tenant_id == tenant_id)
            ]
            results.sort(key=lambda i: i.created_at, reverse=True)
            return results

    def list_all_issues(self, tenant_id: Optional[str] = None) -> List[PortfolioIssueRecord]:
        with self._lock:
            results = list(self._issues.values())
            if tenant_id:
                results = [i for i in results if i.tenant_id == tenant_id]
            return results

    # -------------------------------------------------------------------------
    # Reviews
    # -------------------------------------------------------------------------
    def save_review(self, record: PortfolioReviewRecord) -> PortfolioReviewRecord:
        with self._lock:
            self._reviews[record.review_id] = record
            return record

    def get_review(self, review_id: str) -> Optional[PortfolioReviewRecord]:
        with self._lock:
            return self._reviews.get(review_id)

    def list_reviews_for_portfolio(
        self, portfolio_id: str, tenant_id: Optional[str] = None
    ) -> List[PortfolioReviewRecord]:
        with self._lock:
            results = [
                v for v in self._reviews.values()
                if v.portfolio_id == portfolio_id and (tenant_id is None or v.tenant_id == tenant_id)
            ]
            results.sort(key=lambda v: v.created_at, reverse=True)
            return results

    # -------------------------------------------------------------------------
    # Background Job Results
    # -------------------------------------------------------------------------
    def record_job_run(self, result: PortfolioBackgroundJobRunResult) -> PortfolioBackgroundJobRunResult:
        with self._lock:
            self._job_runs.append(result)
            return result

    def list_job_runs(self) -> List[PortfolioBackgroundJobRunResult]:
        with self._lock:
            return list(self._job_runs)


_repo_instance: Optional[GovernanceChangePortfolioRepository] = None
_repo_lock = threading.Lock()


def get_governance_change_portfolio_repository() -> GovernanceChangePortfolioRepository:
    """Provides singleton instance of GovernanceChangePortfolioRepository."""
    global _repo_instance
    if _repo_instance is None:
        with _repo_lock:
            if _repo_instance is None:
                _repo_instance = GovernanceChangePortfolioRepository()
    return _repo_instance
