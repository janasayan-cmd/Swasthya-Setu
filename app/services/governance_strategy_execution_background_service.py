"""Phase 79: Strategic Execution Background Scheduled Maintenance Service.

Performs idempotent background routine scans evaluating execution health,
detecting stale evidence, unresolved dependency conflicts, invalidated assumptions,
and active signals.
"""

from typing import Optional, Set

from app.repositories.governance_strategy_execution_repository import (
    GovernanceStrategyExecutionRepository,
    get_governance_strategy_execution_repository,
)
from app.schemas.governance_strategy_review_packages import (
    ExecutionRoutineScanJobResult,
)
from app.schemas.governance_strategy_execution_monitoring import (
    MonitoringHealthStatus,
)
from app.schemas.governance_cross_roadmap_dependency import (
    CrossDependencyStatus,
)
from app.schemas.governance_strategy_assumption import (
    AssumptionStatus,
)
from app.schemas.governance_strategy_signals import (
    SignalDisposition,
)


class GovernanceStrategyExecutionBackgroundService:
    """Performs scheduled idempotent strategic execution scans and integrity maintenance."""

    def __init__(
        self,
        repository: Optional[GovernanceStrategyExecutionRepository] = None,
    ) -> None:
        self.repository = repository or get_governance_strategy_execution_repository()

    def run_routine_scan(self, tenant_id: str) -> ExecutionRoutineScanJobResult:
        all_monitored = self.repository.list_monitoring_records(tenant_id, limit=1000)
        unique_roadmaps: Set[str] = {m.roadmap_id for m in all_monitored}

        stale_count = sum(
            1 for m in all_monitored
            if m.health_status == MonitoringHealthStatus.STALE_EVIDENCE or m.is_stale
        )

        all_deps = self.repository.list_all_cross_dependencies(tenant_id)
        conflict_count = sum(
            1 for d in all_deps if d.status == CrossDependencyStatus.CONFLICT_DETECTED
        )

        all_assumptions = self.repository.list_assumptions(tenant_id, limit=1000)
        invalidated_count = sum(
            1 for a in all_assumptions
            if a.status in (AssumptionStatus.INVALIDATED, AssumptionStatus.EXPIRED)
        )

        all_signals = self.repository.list_signals(tenant_id, limit=1000)
        active_signal_count = sum(
            1 for s in all_signals if s.disposition == SignalDisposition.ACTIVE
        )

        return ExecutionRoutineScanJobResult(
            scanned_roadmaps=len(unique_roadmaps),
            scanned_monitored_items=len(all_monitored),
            stale_evidence_flagged=stale_count,
            dependency_conflicts_flagged=conflict_count,
            invalidated_assumptions_flagged=invalidated_count,
            active_signals_flagged=active_signal_count,
            status="COMPLETED",
        )
