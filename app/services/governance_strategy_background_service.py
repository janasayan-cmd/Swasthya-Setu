"""Phase 78: Governance Strategy Background Service.

Executes idempotent background scheduled maintenance scans for strategic roadmaps,
milestone due dates, and dependency integrity.
"""

from datetime import datetime, timezone
from typing import Optional

from app.repositories.governance_strategy_repository import (
    GovernanceStrategyRepository,
    get_governance_strategy_repository,
)
from app.schemas.governance_strategy_milestone import MilestoneStatus
from app.schemas.governance_strategy_reporting import StrategyRoutineScanJobResult
from app.schemas.governance_strategy_roadmap import RoadmapStatus


class GovernanceStrategyBackgroundService:
    """Provides idempotent background scheduled processing for strategic roadmaps."""

    def __init__(
        self,
        repository: Optional[GovernanceStrategyRepository] = None,
    ) -> None:
        self.repository = repository or get_governance_strategy_repository()

    def run_strategy_routine_scan(
        self,
        tenant_id: str,
    ) -> StrategyRoutineScanJobResult:
        now_dt = datetime.now(timezone.utc)
        roadmaps = self.repository.list_roadmaps(tenant_id=tenant_id, limit=100)

        total_milestones_scanned = 0
        overdue_flagged = 0
        conflicts_detected = 0
        reminders_generated = 0

        for rm in roadmaps:
            if rm.status in (RoadmapStatus.APPROVED, RoadmapStatus.ACTIVE):
                reminders_generated += 1

            milestones = self.repository.list_milestones(tenant_id=tenant_id, roadmap_id=rm.roadmap_id, limit=200)
            total_milestones_scanned += len(milestones)

            for ms in milestones:
                if ms.status in (MilestoneStatus.PENDING, MilestoneStatus.IN_PROGRESS):
                    try:
                        planned_dt = datetime.fromisoformat(ms.planned_completion_date.replace("Z", "+00:00"))
                        if now_dt > planned_dt:
                            overdue_flagged += 1
                            # Update to DELAYED if not already
                            if ms.status != MilestoneStatus.DELAYED:
                                updated_ms = ms.model_copy(
                                    update={
                                        "status": MilestoneStatus.DELAYED,
                                        "delay_reason": "Planned completion date elapsed during background monitoring scan.",
                                    }
                                )
                                self.repository.save_milestone(updated_ms)
                    except Exception:
                        pass

                # Check dependencies
                for dep in ms.dependencies:
                    dep_ms = self.repository.get_milestone(dep.depends_on_milestone_id)
                    if not dep_ms or dep_ms.status == MilestoneStatus.CANCELLED:
                        conflicts_detected += 1

        return StrategyRoutineScanJobResult(
            scanned_roadmaps=len(roadmaps),
            scanned_milestones=total_milestones_scanned,
            overdue_milestones_flagged=overdue_flagged,
            dependency_conflicts_detected=conflicts_detected,
            reminders_generated=reminders_generated,
            status="COMPLETED",
        )
