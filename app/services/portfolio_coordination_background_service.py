"""Phase 75: Portfolio Coordination Background Service.

Coordinates:
- Asynchronous / scheduled portfolio coordination scans
- Recalculation of circular dependencies and blocked initiatives
- Schedule overlap detection across concurrent initiatives
- Idempotent and thread-safe execution
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Set

from app.repositories.governance_change_portfolio_repository import (
    GovernanceChangePortfolioRepository,
    get_governance_change_portfolio_repository,
)
from app.schemas.portfolio_initiative import (
    InitiativeCoordinationStatus,
    PortfolioInitiativeRecord,
)
from app.schemas.portfolio_dependencies_conflicts import (
    ConflictClassification,
    ConflictStatus,
    DependencyStatus,
    PortfolioConflictRecord,
)
from app.schemas.portfolio_reporting import (
    PortfolioBackgroundJobRunResult,
)


class PortfolioCoordinationBackgroundService:
    """Service governing scheduled and asynchronous portfolio coordination cycles."""

    def __init__(
        self,
        repository: Optional[GovernanceChangePortfolioRepository] = None,
    ) -> None:
        self.repo = repository or get_governance_change_portfolio_repository()

    def run_coordination_cycle(
        self, tenant_id: Optional[str] = None
    ) -> PortfolioBackgroundJobRunResult:
        """Runs a complete idempotent portfolio coordination cycle."""
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()
        details: List[str] = []

        circular_count = 0
        overlap_count = 0
        stale_count = 0
        blocked_count = 0

        portfolios = self.repo.list_portfolios(tenant_id=tenant_id, limit=500)

        for port in portfolios:
            initiatives = self.repo.list_initiatives_for_portfolio(port.portfolio_id, tenant_id)
            dependencies = self.repo.list_dependencies_for_portfolio(port.portfolio_id, tenant_id)

            # 1. Dependency graph cycle check
            adj: Dict[str, List[str]] = {}
            for d in dependencies:
                if d.status not in [DependencyStatus.REMOVED, DependencyStatus.CANCELLED]:
                    adj.setdefault(d.source_initiative_id, []).append(d.target_initiative_id)

            def has_path(u: str, goal: str, visited: Set[str]) -> bool:
                if u == goal:
                    return True
                visited.add(u)
                for v in adj.get(u, []):
                    if v not in visited:
                        if has_path(v, goal, visited):
                            return True
                return False

            for u in adj:
                for v in adj[u]:
                    if has_path(v, u, set()):
                        circular_count += 1
                        details.append(
                            f"Circular dependency detected between '{u}' and '{v}' in portfolio '{port.portfolio_id}'."
                        )

            # 2. Blocked initiative identification
            for init in initiatives:
                incoming_deps = [
                    d for d in dependencies
                    if d.source_initiative_id == init.initiative_id and d.status in [DependencyStatus.BLOCKED, DependencyStatus.DISPUTED]
                ]
                if incoming_deps and not init.is_blocked:
                    blocked_count += 1
                    i_dict = init.model_dump()
                    i_dict["is_blocked"] = True
                    i_dict["blocked_reason"] = f"Blocked by dependency '{incoming_deps[0].dependency_id}'."
                    i_dict["coordination_status"] = InitiativeCoordinationStatus.BLOCKED
                    i_dict["updated_at"] = now_iso
                    self.repo.save_initiative(PortfolioInitiativeRecord(**i_dict))
                    details.append(f"Initiative '{init.initiative_id}' marked as BLOCKED.")

            # 3. Schedule overlap check
            for i in range(len(initiatives)):
                for j in range(i + 1, len(initiatives)):
                    a = initiatives[i]
                    b = initiatives[j]
                    shared_facs = set(a.participating_facilities).intersection(set(b.participating_facilities))
                    if shared_facs:
                        overlap = not (a.planned_target_date < b.planned_start_date or b.planned_target_date < a.planned_start_date)
                        if overlap:
                            overlap_count += 1

        result = PortfolioBackgroundJobRunResult(
            job_name="portfolio_coordination_routine_scan",
            run_timestamp=now_iso,
            circular_dependencies_flagged=circular_count,
            schedule_overlaps_detected=overlap_count,
            stale_source_records_flagged=stale_count,
            blocked_initiatives_updated=blocked_count,
            details=details,
        )
        return self.repo.record_job_run(result)
