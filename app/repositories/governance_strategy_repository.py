"""Phase 78: Clinical Safety Governance Strategy In-Memory Thread-Safe Repository.

Provides persistence and query capabilities for:
- Strategic objectives and lifecycle states
- Strategic priority proposals and human review outcomes
- Multi-year version-controlled roadmaps and change history
- Capability development target operating states
- Strategic milestones, typed dependencies, and verified completions
- Resource and investment proposals
- Strategy-to-portfolio and milestone-to-implementation linkages
- Strategic risks, delays, delivery conflicts, and issue escalations
"""

from datetime import datetime, timezone
import threading
from typing import Dict, List, Optional

from app.schemas.governance_strategy_objective import (
    GovernanceStrategyObjectiveRecord,
    ObjectiveCategory,
    ObjectiveStatus,
)
from app.schemas.governance_strategy_priority import (
    GovernanceStrategyPriorityRecord,
    PriorityReviewOutcome,
)
from app.schemas.governance_strategy_roadmap import (
    GovernanceStrategyRoadmapRecord,
    RoadmapStatus,
)
from app.schemas.governance_strategy_capability_target import (
    CapabilityDomainEnum,
    GovernanceCapabilityTargetRecord,
)
from app.schemas.governance_strategy_milestone import (
    GovernanceStrategyMilestoneRecord,
    MilestoneStatus,
)
from app.schemas.governance_strategy_resource import (
    GovernanceResourceProposalRecord,
    InvestmentReviewStatus,
)
from app.schemas.governance_strategy_coordination import (
    GovernanceStrategyIssueRecord,
    ImplementationLinkRecord,
    PortfolioLinkRecord,
    StrategyIssueStatus,
)


class GovernanceStrategyRepository:
    """Thread-safe in-memory repository for Phase 78 strategic governance roadmap data."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._objectives: Dict[str, GovernanceStrategyObjectiveRecord] = {}
        self._priorities: Dict[str, GovernanceStrategyPriorityRecord] = {}
        self._roadmaps: Dict[str, GovernanceStrategyRoadmapRecord] = {}
        self._capability_targets: Dict[str, GovernanceCapabilityTargetRecord] = {}
        self._milestones: Dict[str, GovernanceStrategyMilestoneRecord] = {}
        self._resource_proposals: Dict[str, GovernanceResourceProposalRecord] = {}
        self._portfolio_links: Dict[str, PortfolioLinkRecord] = {}
        self._implementation_links: Dict[str, ImplementationLinkRecord] = {}
        self._issues: Dict[str, GovernanceStrategyIssueRecord] = {}

    def clear(self) -> None:
        """Clears all stored records (useful for test isolation)."""
        with self._lock:
            self._objectives.clear()
            self._priorities.clear()
            self._roadmaps.clear()
            self._capability_targets.clear()
            self._milestones.clear()
            self._resource_proposals.clear()
            self._portfolio_links.clear()
            self._implementation_links.clear()
            self._issues.clear()

    # -------------------------------------------------------------------------
    # Objectives
    # -------------------------------------------------------------------------

    def save_objective(
        self, objective: GovernanceStrategyObjectiveRecord
    ) -> GovernanceStrategyObjectiveRecord:
        with self._lock:
            self._objectives[objective.objective_id] = objective
            return objective

    def get_objective(self, objective_id: str) -> Optional[GovernanceStrategyObjectiveRecord]:
        with self._lock:
            return self._objectives.get(objective_id)

    def list_objectives(
        self,
        tenant_id: str,
        category: Optional[ObjectiveCategory] = None,
        status: Optional[ObjectiveStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[GovernanceStrategyObjectiveRecord]:
        with self._lock:
            results = [
                obj
                for obj in self._objectives.values()
                if obj.tenant_id == tenant_id
                and (category is None or obj.category == category)
                and (status is None or obj.status == status)
            ]
            results.sort(key=lambda x: x.created_at, reverse=True)
            return results[skip : skip + limit]

    # -------------------------------------------------------------------------
    # Priorities
    # -------------------------------------------------------------------------

    def save_priority(
        self, priority: GovernanceStrategyPriorityRecord
    ) -> GovernanceStrategyPriorityRecord:
        with self._lock:
            self._priorities[priority.priority_id] = priority
            return priority

    def get_priority(self, priority_id: str) -> Optional[GovernanceStrategyPriorityRecord]:
        with self._lock:
            return self._priorities.get(priority_id)

    def list_priorities(
        self,
        tenant_id: str,
        status: Optional[PriorityReviewOutcome] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[GovernanceStrategyPriorityRecord]:
        with self._lock:
            results = [
                p
                for p in self._priorities.values()
                if p.tenant_id == tenant_id
                and (status is None or p.status == status)
            ]
            results.sort(key=lambda x: x.created_at, reverse=True)
            return results[skip : skip + limit]

    # -------------------------------------------------------------------------
    # Roadmaps
    # -------------------------------------------------------------------------

    def save_roadmap(
        self, roadmap: GovernanceStrategyRoadmapRecord
    ) -> GovernanceStrategyRoadmapRecord:
        with self._lock:
            self._roadmaps[roadmap.roadmap_id] = roadmap
            return roadmap

    def get_roadmap(self, roadmap_id: str) -> Optional[GovernanceStrategyRoadmapRecord]:
        with self._lock:
            return self._roadmaps.get(roadmap_id)

    def list_roadmaps(
        self,
        tenant_id: str,
        status: Optional[RoadmapStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[GovernanceStrategyRoadmapRecord]:
        with self._lock:
            results = [
                rm
                for rm in self._roadmaps.values()
                if rm.tenant_id == tenant_id
                and (status is None or rm.status == status)
            ]
            results.sort(key=lambda x: x.created_at, reverse=True)
            return results[skip : skip + limit]

    # -------------------------------------------------------------------------
    # Capability Targets
    # -------------------------------------------------------------------------

    def save_capability_target(
        self, target: GovernanceCapabilityTargetRecord
    ) -> GovernanceCapabilityTargetRecord:
        with self._lock:
            self._capability_targets[target.target_id] = target
            return target

    def get_capability_target(self, target_id: str) -> Optional[GovernanceCapabilityTargetRecord]:
        with self._lock:
            return self._capability_targets.get(target_id)

    def list_capability_targets(
        self,
        tenant_id: str,
        domain: Optional[CapabilityDomainEnum] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[GovernanceCapabilityTargetRecord]:
        with self._lock:
            results = [
                tgt
                for tgt in self._capability_targets.values()
                if tgt.tenant_id == tenant_id
                and (domain is None or tgt.capability_domain == domain)
            ]
            results.sort(key=lambda x: x.created_at, reverse=True)
            return results[skip : skip + limit]

    # -------------------------------------------------------------------------
    # Milestones
    # -------------------------------------------------------------------------

    def save_milestone(
        self, milestone: GovernanceStrategyMilestoneRecord
    ) -> GovernanceStrategyMilestoneRecord:
        with self._lock:
            self._milestones[milestone.milestone_id] = milestone
            return milestone

    def get_milestone(self, milestone_id: str) -> Optional[GovernanceStrategyMilestoneRecord]:
        with self._lock:
            return self._milestones.get(milestone_id)

    def list_milestones(
        self,
        tenant_id: str,
        roadmap_id: Optional[str] = None,
        status: Optional[MilestoneStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[GovernanceStrategyMilestoneRecord]:
        with self._lock:
            results = [
                ms
                for ms in self._milestones.values()
                if ms.tenant_id == tenant_id
                and (roadmap_id is None or ms.roadmap_id == roadmap_id)
                and (status is None or ms.status == status)
            ]
            results.sort(key=lambda x: x.planned_completion_date)
            return results[skip : skip + limit]

    # -------------------------------------------------------------------------
    # Resource Proposals
    # -------------------------------------------------------------------------

    def save_resource_proposal(
        self, proposal: GovernanceResourceProposalRecord
    ) -> GovernanceResourceProposalRecord:
        with self._lock:
            self._resource_proposals[proposal.proposal_id] = proposal
            return proposal

    def get_resource_proposal(self, proposal_id: str) -> Optional[GovernanceResourceProposalRecord]:
        with self._lock:
            return self._resource_proposals.get(proposal_id)

    def list_resource_proposals(
        self,
        tenant_id: str,
        roadmap_id: Optional[str] = None,
        status: Optional[InvestmentReviewStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[GovernanceResourceProposalRecord]:
        with self._lock:
            results = [
                rp
                for rp in self._resource_proposals.values()
                if rp.tenant_id == tenant_id
                and (roadmap_id is None or rp.roadmap_id == roadmap_id)
                and (status is None or rp.status == status)
            ]
            results.sort(key=lambda x: x.created_at, reverse=True)
            return results[skip : skip + limit]

    # -------------------------------------------------------------------------
    # Portfolio & Implementation Links
    # -------------------------------------------------------------------------

    def save_portfolio_link(self, link: PortfolioLinkRecord) -> PortfolioLinkRecord:
        with self._lock:
            self._portfolio_links[link.link_id] = link
            return link

    def list_portfolio_links(
        self,
        tenant_id: str,
        roadmap_id: Optional[str] = None,
        objective_id: Optional[str] = None,
    ) -> List[PortfolioLinkRecord]:
        with self._lock:
            return [
                lk
                for lk in self._portfolio_links.values()
                if lk.tenant_id == tenant_id
                and (roadmap_id is None or lk.roadmap_id == roadmap_id)
                and (objective_id is None or lk.objective_id == objective_id)
            ]

    def save_implementation_link(self, link: ImplementationLinkRecord) -> ImplementationLinkRecord:
        with self._lock:
            self._implementation_links[link.link_id] = link
            return link

    def list_implementation_links(
        self,
        tenant_id: str,
        roadmap_id: Optional[str] = None,
        milestone_id: Optional[str] = None,
    ) -> List[ImplementationLinkRecord]:
        with self._lock:
            return [
                lk
                for lk in self._implementation_links.values()
                if lk.tenant_id == tenant_id
                and (roadmap_id is None or lk.roadmap_id == roadmap_id)
                and (milestone_id is None or lk.milestone_id == milestone_id)
            ]

    # -------------------------------------------------------------------------
    # Issues
    # -------------------------------------------------------------------------

    def save_issue(self, issue: GovernanceStrategyIssueRecord) -> GovernanceStrategyIssueRecord:
        with self._lock:
            self._issues[issue.issue_id] = issue
            return issue

    def get_issue(self, issue_id: str) -> Optional[GovernanceStrategyIssueRecord]:
        with self._lock:
            return self._issues.get(issue_id)

    def list_issues(
        self,
        tenant_id: str,
        roadmap_id: Optional[str] = None,
        status: Optional[StrategyIssueStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[GovernanceStrategyIssueRecord]:
        with self._lock:
            results = [
                iss
                for iss in self._issues.values()
                if iss.tenant_id == tenant_id
                and (roadmap_id is None or iss.roadmap_id == roadmap_id)
                and (status is None or iss.status == status)
            ]
            results.sort(key=lambda x: x.detection_timestamp, reverse=True)
            return results[skip : skip + limit]


_governance_strategy_repo = GovernanceStrategyRepository()


def get_governance_strategy_repository() -> GovernanceStrategyRepository:
    """Returns the singleton instance of the Governance Strategy repository."""
    return _governance_strategy_repo
