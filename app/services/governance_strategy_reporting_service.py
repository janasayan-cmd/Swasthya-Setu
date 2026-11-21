"""Phase 78: Governance Strategy Reporting Service.

Generates strategic roadmap overviews, milestone schedules, portfolio alignment,
and strategic issue summary reports.
"""

from typing import Dict, List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_strategy_repository import (
    GovernanceStrategyRepository,
    get_governance_strategy_repository,
)
from app.schemas.governance_strategy_milestone import MilestoneStatus
from app.schemas.governance_strategy_objective import CLINICAL_SAFETY_STRATEGY_DISCLAIMER
from app.schemas.governance_strategy_reporting import (
    MilestoneScheduleResponse,
    ObjectiveRegisterResponse,
    PortfolioStrategyAlignmentResponse,
    StrategyIssueSummaryResponse,
    StrategyRoadmapOverviewResponse,
)


class GovernanceStrategyReportingService:
    """Provides reporting and analytical insights for strategic governance roadmaps."""

    def __init__(
        self,
        repository: Optional[GovernanceStrategyRepository] = None,
    ) -> None:
        self.repository = repository or get_governance_strategy_repository()

    def get_roadmap_overview(
        self,
        tenant_id: str,
        roadmap_id: str,
    ) -> StrategyRoadmapOverviewResponse:
        roadmap = self.repository.get_roadmap(roadmap_id)
        if not roadmap or roadmap.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.STRATEGY_ROADMAP_NOT_FOUND,
                message=f"Roadmap '{roadmap_id}' was not found.",
                status_code=404,
            )

        milestones = self.repository.list_milestones(tenant_id=tenant_id, roadmap_id=roadmap_id, limit=200)
        completed_ms = sum(1 for m in milestones if m.status == MilestoneStatus.COMPLETED)
        delayed_ms = sum(1 for m in milestones if m.status == MilestoneStatus.DELAYED)

        proposals = self.repository.list_resource_proposals(tenant_id=tenant_id, roadmap_id=roadmap_id, limit=100)
        total_inv = sum(p.proposed_financial_investment for p in proposals)
        currency = proposals[0].currency if proposals else "INR"

        return StrategyRoadmapOverviewResponse(
            roadmap_id=roadmap.roadmap_id,
            tenant_id=tenant_id,
            title=roadmap.title,
            status=roadmap.status.value,
            current_version=roadmap.current_version,
            planning_horizon=roadmap.planning_horizon.value,
            start_date=roadmap.start_date,
            end_date=roadmap.end_date,
            total_objectives=len(roadmap.strategic_objective_ids),
            total_milestones=len(milestones),
            completed_milestones=completed_ms,
            delayed_milestones=delayed_ms,
            total_investment_proposed=total_inv,
            currency=currency,
            disclaimer=CLINICAL_SAFETY_STRATEGY_DISCLAIMER,
        )

    def get_objective_register(
        self,
        tenant_id: str,
        roadmap_id: Optional[str] = None,
    ) -> ObjectiveRegisterResponse:
        if roadmap_id:
            roadmap = self.repository.get_roadmap(roadmap_id)
            if not roadmap or roadmap.tenant_id != tenant_id:
                raise AppException(
                    code=ErrorCode.STRATEGY_ROADMAP_NOT_FOUND,
                    message=f"Roadmap '{roadmap_id}' was not found.",
                    status_code=404,
                )
            objectives = [
                self.repository.get_objective(obj_id).model_dump()
                for obj_id in roadmap.strategic_objective_ids
                if self.repository.get_objective(obj_id) is not None
            ]
        else:
            obj_records = self.repository.list_objectives(tenant_id=tenant_id, limit=100)
            objectives = [o.model_dump() for o in obj_records]

        return ObjectiveRegisterResponse(
            tenant_id=tenant_id,
            roadmap_id=roadmap_id,
            objectives=objectives,
            total_count=len(objectives),
            disclaimer=CLINICAL_SAFETY_STRATEGY_DISCLAIMER,
        )

    def get_milestone_schedule(
        self,
        tenant_id: str,
        roadmap_id: str,
    ) -> MilestoneScheduleResponse:
        roadmap = self.repository.get_roadmap(roadmap_id)
        if not roadmap or roadmap.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.STRATEGY_ROADMAP_NOT_FOUND,
                message=f"Roadmap '{roadmap_id}' was not found.",
                status_code=404,
            )

        milestones = self.repository.list_milestones(tenant_id=tenant_id, roadmap_id=roadmap_id, limit=200)
        ms_dicts = [m.model_dump() for m in milestones]

        return MilestoneScheduleResponse(
            tenant_id=tenant_id,
            roadmap_id=roadmap_id,
            milestones=ms_dicts,
            total_count=len(ms_dicts),
            disclaimer=CLINICAL_SAFETY_STRATEGY_DISCLAIMER,
        )

    def get_portfolio_alignment(
        self,
        tenant_id: str,
        roadmap_id: str,
    ) -> PortfolioStrategyAlignmentResponse:
        roadmap = self.repository.get_roadmap(roadmap_id)
        if not roadmap or roadmap.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.STRATEGY_ROADMAP_NOT_FOUND,
                message=f"Roadmap '{roadmap_id}' was not found.",
                status_code=404,
            )

        links = self.repository.list_portfolio_links(tenant_id=tenant_id, roadmap_id=roadmap_id)
        linked_obj_ids = {lk.objective_id for lk in links}

        all_obj_ids = set(roadmap.strategic_objective_ids)
        aligned_count = len(linked_obj_ids.intersection(all_obj_ids))
        unlinked_count = len(all_obj_ids) - aligned_count

        link_dicts = [lk.model_dump() for lk in links]

        return PortfolioStrategyAlignmentResponse(
            tenant_id=tenant_id,
            roadmap_id=roadmap_id,
            aligned_objectives_count=aligned_count,
            unlinked_objectives_count=max(0, unlinked_count),
            active_portfolio_links=link_dicts,
            disclaimer=CLINICAL_SAFETY_STRATEGY_DISCLAIMER,
        )

    def get_issue_summary(
        self,
        tenant_id: str,
        roadmap_id: str,
    ) -> StrategyIssueSummaryResponse:
        roadmap = self.repository.get_roadmap(roadmap_id)
        if not roadmap or roadmap.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.STRATEGY_ROADMAP_NOT_FOUND,
                message=f"Roadmap '{roadmap_id}' was not found.",
                status_code=404,
            )

        issues = self.repository.list_issues(tenant_id=tenant_id, roadmap_id=roadmap_id, limit=200)
        open_count = sum(1 for i in issues if i.status.value in ("OPEN", "INVESTIGATING"))
        escalated_count = sum(1 for i in issues if i.status.value == "ESCALATED")

        by_class: Dict[str, int] = {}
        for i in issues:
            c = i.classification.value
            by_class[c] = by_class.get(c, 0) + 1

        return StrategyIssueSummaryResponse(
            tenant_id=tenant_id,
            roadmap_id=roadmap_id,
            total_issues=len(issues),
            open_issues=open_count,
            escalated_issues=escalated_count,
            issues_by_classification=by_class,
            disclaimer=CLINICAL_SAFETY_STRATEGY_DISCLAIMER,
        )
