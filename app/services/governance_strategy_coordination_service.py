"""Phase 78: Governance Strategy Coordination and Issue Routing Service.

Coordinates strategic roadmaps with Phase 75 portfolios, Phase 73 implementations,
and routes governance issues to authoritative workflows (Phase 63, 67, 49, 54, 72).
"""

from datetime import datetime, timezone
import uuid
from typing import List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_strategy_repository import (
    GovernanceStrategyRepository,
    get_governance_strategy_repository,
)
from app.schemas.governance_strategy_coordination import (
    CreateStrategyIssueRequest,
    EscalateStrategyIssueRequest,
    GovernanceStrategyIssueRecord,
    ImplementationLinkRecord,
    LinkImplementationRequest,
    LinkPortfolioRequest,
    PortfolioLinkRecord,
    ResolveStrategyIssueRequest,
    StrategyIssueStatus,
)
from app.schemas.governance_strategy_objective import CLINICAL_SAFETY_STRATEGY_DISCLAIMER


def _get_utc_now_str() -> str:
    return datetime.now(timezone.utc).isoformat()


_VALID_ESCALATION_TARGETS = {
    "PHASE_49_INCIDENT",
    "PHASE_54_CAPA",
    "PHASE_55_EFFECTIVENESS",
    "PHASE_63_RISK",
    "PHASE_67_ESCALATION",
    "PHASE_72_MANAGEMENT_REVIEW",
}


class GovernanceStrategyCoordinationService:
    """Manages strategy-to-portfolio linking, implementation references, and issue escalation."""

    def __init__(
        self,
        repository: Optional[GovernanceStrategyRepository] = None,
    ) -> None:
        self.repository = repository or get_governance_strategy_repository()

    def link_portfolio(
        self,
        tenant_id: str,
        roadmap_id: str,
        request: LinkPortfolioRequest,
    ) -> PortfolioLinkRecord:
        roadmap = self.repository.get_roadmap(roadmap_id)
        if not roadmap or roadmap.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.STRATEGY_ROADMAP_NOT_FOUND,
                message=f"Roadmap '{roadmap_id}' was not found.",
                status_code=404,
            )

        objective = self.repository.get_objective(request.objective_id)
        if not objective or objective.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.STRATEGY_OBJECTIVE_NOT_FOUND,
                message=f"Objective '{request.objective_id}' was not found.",
                status_code=404,
            )

        now = _get_utc_now_str()
        link = PortfolioLinkRecord(
            link_id=f"gpl-{uuid.uuid4().hex[:12]}",
            tenant_id=tenant_id,
            roadmap_id=roadmap_id,
            objective_id=request.objective_id,
            portfolio_id=request.portfolio_id,
            status="ACTIVE",
            linked_at=now,
        )
        return self.repository.save_portfolio_link(link)

    def link_implementation(
        self,
        tenant_id: str,
        roadmap_id: str,
        request: LinkImplementationRequest,
    ) -> ImplementationLinkRecord:
        roadmap = self.repository.get_roadmap(roadmap_id)
        if not roadmap or roadmap.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.STRATEGY_ROADMAP_NOT_FOUND,
                message=f"Roadmap '{roadmap_id}' was not found.",
                status_code=404,
            )

        milestone = self.repository.get_milestone(request.milestone_id)
        if not milestone or milestone.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.STRATEGY_MILESTONE_NOT_FOUND,
                message=f"Milestone '{request.milestone_id}' was not found.",
                status_code=404,
            )

        now = _get_utc_now_str()
        link = ImplementationLinkRecord(
            link_id=f"gil-{uuid.uuid4().hex[:12]}",
            tenant_id=tenant_id,
            roadmap_id=roadmap_id,
            milestone_id=request.milestone_id,
            implementation_id=request.implementation_id,
            status="ACTIVE",
            linked_at=now,
        )
        saved_link = self.repository.save_implementation_link(link)

        # Update milestone's related_implementation_id
        milestone = milestone.model_copy(
            update={"related_implementation_id": request.implementation_id, "updated_at": now}
        )
        self.repository.save_milestone(milestone)
        return saved_link

    def create_issue(
        self,
        tenant_id: str,
        detector_id: str,
        request: CreateStrategyIssueRequest,
    ) -> GovernanceStrategyIssueRecord:
        roadmap = self.repository.get_roadmap(request.roadmap_id)
        if not roadmap or roadmap.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.STRATEGY_ROADMAP_NOT_FOUND,
                message=f"Roadmap '{request.roadmap_id}' was not found.",
                status_code=404,
            )

        now = _get_utc_now_str()
        issue = GovernanceStrategyIssueRecord(
            issue_id=f"gsi-{uuid.uuid4().hex[:12]}",
            tenant_id=tenant_id,
            roadmap_id=request.roadmap_id,
            affected_objective_ids=request.affected_objective_ids or [],
            affected_milestone_ids=request.affected_milestone_ids or [],
            classification=request.classification,
            title=request.title,
            description=request.description,
            impact_description=request.impact_description,
            status=StrategyIssueStatus.OPEN,
            detected_by=detector_id,
            detection_timestamp=now,
            escalation_target=None,
            escalation_reference=None,
            resolution_notes=None,
            disclaimer=CLINICAL_SAFETY_STRATEGY_DISCLAIMER,
        )
        return self.repository.save_issue(issue)

    def escalate_issue(
        self,
        tenant_id: str,
        issue_id: str,
        request: EscalateStrategyIssueRequest,
    ) -> GovernanceStrategyIssueRecord:
        issue = self.repository.get_issue(issue_id)
        if not issue or issue.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.STRATEGY_ISSUE_NOT_FOUND,
                message=f"Strategic issue '{issue_id}' was not found.",
                status_code=404,
            )

        if request.escalation_target not in _VALID_ESCALATION_TARGETS:
            raise AppException(
                code=ErrorCode.INVALID_STRATEGY_ISSUE_STATE,
                message=f"Escalation target '{request.escalation_target}' is not a recognized authoritative workflow.",
                status_code=400,
            )

        now = _get_utc_now_str()
        esc_ref = request.escalation_reference or f"esc-{uuid.uuid4().hex[:8]}"
        issue = issue.model_copy(
            update={
                "status": StrategyIssueStatus.ESCALATED,
                "escalation_target": request.escalation_target,
                "escalation_reference": esc_ref,
                "resolution_notes": request.notes or issue.resolution_notes,
            }
        )
        return self.repository.save_issue(issue)

    def resolve_issue(
        self,
        tenant_id: str,
        issue_id: str,
        request: ResolveStrategyIssueRequest,
    ) -> GovernanceStrategyIssueRecord:
        issue = self.repository.get_issue(issue_id)
        if not issue or issue.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.STRATEGY_ISSUE_NOT_FOUND,
                message=f"Strategic issue '{issue_id}' was not found.",
                status_code=404,
            )

        issue = issue.model_copy(
            update={
                "status": StrategyIssueStatus.RESOLVED,
                "resolution_notes": request.resolution_notes,
            }
        )
        return self.repository.save_issue(issue)

    def get_issue(
        self,
        tenant_id: str,
        issue_id: str,
    ) -> GovernanceStrategyIssueRecord:
        issue = self.repository.get_issue(issue_id)
        if not issue or issue.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.STRATEGY_ISSUE_NOT_FOUND,
                message=f"Strategic issue '{issue_id}' was not found.",
                status_code=404,
            )
        return issue

    def list_issues(
        self,
        tenant_id: str,
        roadmap_id: Optional[str] = None,
        status: Optional[StrategyIssueStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[GovernanceStrategyIssueRecord]:
        return self.repository.list_issues(
            tenant_id=tenant_id,
            roadmap_id=roadmap_id,
            status=status,
            skip=skip,
            limit=limit,
        )

    def list_portfolio_links(
        self,
        tenant_id: str,
        roadmap_id: Optional[str] = None,
        objective_id: Optional[str] = None,
    ) -> List[PortfolioLinkRecord]:
        return self.repository.list_portfolio_links(
            tenant_id=tenant_id,
            roadmap_id=roadmap_id,
            objective_id=objective_id,
        )

    def list_implementation_links(
        self,
        tenant_id: str,
        roadmap_id: Optional[str] = None,
        milestone_id: Optional[str] = None,
    ) -> List[ImplementationLinkRecord]:
        return self.repository.list_implementation_links(
            tenant_id=tenant_id,
            roadmap_id=roadmap_id,
            milestone_id=milestone_id,
        )
