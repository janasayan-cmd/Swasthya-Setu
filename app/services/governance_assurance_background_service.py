"""Phase 77: Governance Assurance Background Service.

Executes idempotent routine background scans to flag stale assurance evidence,
detect overdue assessments, and monitor governance improvement milestones.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional

from app.repositories.governance_strategic_assurance_repository import (
    GovernanceStrategicAssuranceRepository,
    get_strategic_assurance_repository,
)
from app.schemas.governance_assurance_reporting import AssuranceRoutineScanJobResult
from app.schemas.governance_improvement_plan import ImprovementMilestoneStatus
from app.schemas.governance_maturity_assessment import AssessmentStatus


class GovernanceAssuranceBackgroundService:
    """Provides idempotent background maintenance processing for strategic assurance."""

    def __init__(
        self,
        repository: Optional[GovernanceStrategicAssuranceRepository] = None,
    ) -> None:
        self.repository = repository or get_strategic_assurance_repository()

    def run_assurance_routine_scan(
        self,
        tenant_id: str,
    ) -> AssuranceRoutineScanJobResult:
        now = datetime.now(timezone.utc)
        assessments = self.repository.list_assessments(tenant_id=tenant_id, limit=200)

        stale_evidence_count = 0
        overdue_assessments_count = 0
        milestone_alerts_count = 0

        # Scan evidence across assessments
        for asmt in assessments:
            evidence_items = self.repository.list_evidence_for_assessment(
                tenant_id=tenant_id,
                assessment_id=asmt.assessment_id,
            )
            for ev in evidence_items:
                try:
                    freshness_dt = datetime.fromisoformat(ev.freshness_timestamp.replace("Z", "+00:00"))
                    if now - freshness_dt > timedelta(days=180):
                        if not ev.is_stale:
                            updated_ev = ev.model_copy(update={"is_stale": True})
                            self.repository.save_evidence(updated_ev)
                            stale_evidence_count += 1
                except Exception:
                    pass

            # Check overdue assessments (> 90 days in DRAFT/IN_PROGRESS)
            if asmt.status in (AssessmentStatus.DRAFT, AssessmentStatus.IN_PROGRESS):
                try:
                    created_dt = datetime.fromisoformat(asmt.created_at.replace("Z", "+00:00"))
                    if now - created_dt > timedelta(days=90):
                        overdue_assessments_count += 1
                except Exception:
                    pass

        # Scan improvement plans for overdue milestones
        plans = self.repository.list_plans(tenant_id=tenant_id, limit=100)
        for plan in plans:
            for ms in plan.milestones:
                if ms.status in (ImprovementMilestoneStatus.PENDING, ImprovementMilestoneStatus.IN_PROGRESS):
                    try:
                        target_dt = datetime.fromisoformat(ms.target_date.replace("Z", "+00:00"))
                        if now > target_dt:
                            milestone_alerts_count += 1
                    except Exception:
                        pass

        return AssuranceRoutineScanJobResult(
            scanned_assessments=len(assessments),
            stale_evidence_flagged=stale_evidence_count,
            overdue_assessments_flagged=overdue_assessments_count,
            milestone_alerts_generated=milestone_alerts_count,
            status="COMPLETED",
        )
