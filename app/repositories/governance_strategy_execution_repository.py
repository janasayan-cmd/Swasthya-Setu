"""Phase 79: Clinical Safety Governance Strategy Execution In-Memory Thread-Safe Repository.

Provides thread-safe persistence and query capabilities for:
- Strategic execution monitoring records across roadmaps, objectives, and milestones
- Cross-roadmap dependency records
- Strategic alignment finding records
- Strategic assumption records
- Strategic change signal records
- Strategic adaptation proposals and follow-through records
- Strategic scenario records
- Strategic execution exception records
- Strategic review package records
"""

import threading
from typing import Dict, List, Optional

from app.schemas.governance_strategy_execution_monitoring import (
    MonitoredWorkflowType,
    MonitoringHealthStatus,
    StrategicExecutionMonitoringRecord,
)
from app.schemas.governance_cross_roadmap_dependency import (
    CrossDependencyStatus,
    CrossRoadmapDependencyRecord,
)
from app.schemas.governance_strategy_alignment import (
    AlignmentFindingCategory,
    AlignmentFindingStatus,
    StrategicAlignmentFindingRecord,
)
from app.schemas.governance_strategy_assumption import (
    AssumptionCategory,
    AssumptionStatus,
    StrategicAssumptionRecord,
)
from app.schemas.governance_strategy_signals import (
    SignalCategory,
    SignalDisposition,
    SignalSeverity,
    StrategicChangeSignalRecord,
)
from app.schemas.governance_strategy_adaptation import (
    AdaptationFollowThroughRecord,
    AdaptationProposalStatus,
    AdaptationProposalType,
    StrategicAdaptationProposalRecord,
)
from app.schemas.governance_strategy_scenarios import (
    ScenarioType,
    StrategicScenarioRecord,
)
from app.schemas.governance_strategy_execution_exceptions import (
    ExecutionExceptionCategory,
    ExecutionExceptionStatus,
    StrategicExecutionExceptionRecord,
)
from app.schemas.governance_strategy_review_packages import (
    StrategicReviewPackageRecord,
)


class GovernanceStrategyExecutionRepository:
    """Thread-safe in-memory repository for Phase 79 strategic execution oversight data."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._monitored_items: Dict[str, StrategicExecutionMonitoringRecord] = {}
        self._cross_dependencies: Dict[str, CrossRoadmapDependencyRecord] = {}
        self._alignment_findings: Dict[str, StrategicAlignmentFindingRecord] = {}
        self._assumptions: Dict[str, StrategicAssumptionRecord] = {}
        self._signals: Dict[str, StrategicChangeSignalRecord] = {}
        self._adaptation_proposals: Dict[str, StrategicAdaptationProposalRecord] = {}
        self._adaptation_followthroughs: Dict[str, AdaptationFollowThroughRecord] = {}
        self._scenarios: Dict[str, StrategicScenarioRecord] = {}
        self._exceptions: Dict[str, StrategicExecutionExceptionRecord] = {}
        self._review_packages: Dict[str, StrategicReviewPackageRecord] = {}

    def clear(self) -> None:
        """Clears all stored records (useful for test isolation)."""
        with self._lock:
            self._monitored_items.clear()
            self._cross_dependencies.clear()
            self._alignment_findings.clear()
            self._assumptions.clear()
            self._signals.clear()
            self._adaptation_proposals.clear()
            self._adaptation_followthroughs.clear()
            self._scenarios.clear()
            self._exceptions.clear()
            self._review_packages.clear()

    # -------------------------------------------------------------------------
    # 1. Monitored Execution Records
    # -------------------------------------------------------------------------

    def save_monitoring_record(
        self, record: StrategicExecutionMonitoringRecord
    ) -> StrategicExecutionMonitoringRecord:
        with self._lock:
            self._monitored_items[record.monitoring_id] = record
            return record

    def get_monitoring_record(
        self, monitoring_id: str
    ) -> Optional[StrategicExecutionMonitoringRecord]:
        with self._lock:
            return self._monitored_items.get(monitoring_id)

    def get_monitoring_by_item(
        self,
        tenant_id: str,
        roadmap_id: str,
        monitored_item_type: MonitoredWorkflowType,
        monitored_item_id: str,
    ) -> Optional[StrategicExecutionMonitoringRecord]:
        with self._lock:
            for item in self._monitored_items.values():
                if (
                    item.tenant_id == tenant_id
                    and item.roadmap_id == roadmap_id
                    and item.monitored_item_type == monitored_item_type
                    and item.monitored_item_id == monitored_item_id
                ):
                    return item
            return None

    def list_monitoring_records(
        self,
        tenant_id: str,
        roadmap_id: Optional[str] = None,
        monitored_item_type: Optional[MonitoredWorkflowType] = None,
        health_status: Optional[MonitoringHealthStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[StrategicExecutionMonitoringRecord]:
        with self._lock:
            results = [
                rec
                for rec in self._monitored_items.values()
                if rec.tenant_id == tenant_id
                and (roadmap_id is None or rec.roadmap_id == roadmap_id)
                and (monitored_item_type is None or rec.monitored_item_type == monitored_item_type)
                and (health_status is None or rec.health_status == health_status)
            ]
            results.sort(key=lambda x: x.last_synchronized_at, reverse=True)
            return results[skip : skip + limit]

    # -------------------------------------------------------------------------
    # 2. Cross-Roadmap Dependencies
    # -------------------------------------------------------------------------

    def save_cross_dependency(
        self, record: CrossRoadmapDependencyRecord
    ) -> CrossRoadmapDependencyRecord:
        with self._lock:
            self._cross_dependencies[record.dependency_id] = record
            return record

    def get_cross_dependency(
        self, dependency_id: str
    ) -> Optional[CrossRoadmapDependencyRecord]:
        with self._lock:
            return self._cross_dependencies.get(dependency_id)

    def list_cross_dependencies(
        self,
        tenant_id: str,
        roadmap_id: Optional[str] = None,
        status: Optional[CrossDependencyStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[CrossRoadmapDependencyRecord]:
        with self._lock:
            results = [
                dep
                for dep in self._cross_dependencies.values()
                if dep.tenant_id == tenant_id
                and (
                    roadmap_id is None
                    or dep.source_roadmap_id == roadmap_id
                    or dep.target_roadmap_id == roadmap_id
                )
                and (status is None or dep.status == status)
            ]
            results.sort(key=lambda x: x.created_at, reverse=True)
            return results[skip : skip + limit]

    def list_all_cross_dependencies(
        self, tenant_id: str
    ) -> List[CrossRoadmapDependencyRecord]:
        with self._lock:
            return [
                dep
                for dep in self._cross_dependencies.values()
                if dep.tenant_id == tenant_id
            ]

    # -------------------------------------------------------------------------
    # 3. Strategic Alignment Findings
    # -------------------------------------------------------------------------

    def save_alignment_finding(
        self, record: StrategicAlignmentFindingRecord
    ) -> StrategicAlignmentFindingRecord:
        with self._lock:
            self._alignment_findings[record.finding_id] = record
            return record

    def get_alignment_finding(
        self, finding_id: str
    ) -> Optional[StrategicAlignmentFindingRecord]:
        with self._lock:
            return self._alignment_findings.get(finding_id)

    def list_alignment_findings(
        self,
        tenant_id: str,
        roadmap_id: Optional[str] = None,
        category: Optional[AlignmentFindingCategory] = None,
        status: Optional[AlignmentFindingStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[StrategicAlignmentFindingRecord]:
        with self._lock:
            results = [
                f
                for f in self._alignment_findings.values()
                if f.tenant_id == tenant_id
                and (roadmap_id is None or roadmap_id in f.affected_roadmap_ids)
                and (category is None or f.category == category)
                and (status is None or f.status == status)
            ]
            results.sort(key=lambda x: x.detected_at, reverse=True)
            return results[skip : skip + limit]

    # -------------------------------------------------------------------------
    # 4. Strategic Assumptions
    # -------------------------------------------------------------------------

    def save_assumption(
        self, record: StrategicAssumptionRecord
    ) -> StrategicAssumptionRecord:
        with self._lock:
            self._assumptions[record.assumption_id] = record
            return record

    def get_assumption(
        self, assumption_id: str
    ) -> Optional[StrategicAssumptionRecord]:
        with self._lock:
            return self._assumptions.get(assumption_id)

    def list_assumptions(
        self,
        tenant_id: str,
        roadmap_id: Optional[str] = None,
        category: Optional[AssumptionCategory] = None,
        status: Optional[AssumptionStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[StrategicAssumptionRecord]:
        with self._lock:
            results = [
                a
                for a in self._assumptions.values()
                if a.tenant_id == tenant_id
                and (roadmap_id is None or a.roadmap_id == roadmap_id)
                and (category is None or a.category == category)
                and (status is None or a.status == status)
            ]
            results.sort(key=lambda x: x.created_at, reverse=True)
            return results[skip : skip + limit]

    # -------------------------------------------------------------------------
    # 5. Strategic Change Signals
    # -------------------------------------------------------------------------

    def save_signal(
        self, record: StrategicChangeSignalRecord
    ) -> StrategicChangeSignalRecord:
        with self._lock:
            self._signals[record.signal_id] = record
            return record

    def get_signal(
        self, signal_id: str
    ) -> Optional[StrategicChangeSignalRecord]:
        with self._lock:
            return self._signals.get(signal_id)

    def list_signals(
        self,
        tenant_id: str,
        roadmap_id: Optional[str] = None,
        category: Optional[SignalCategory] = None,
        severity: Optional[SignalSeverity] = None,
        disposition: Optional[SignalDisposition] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[StrategicChangeSignalRecord]:
        with self._lock:
            results = [
                s
                for s in self._signals.values()
                if s.tenant_id == tenant_id
                and (roadmap_id is None or roadmap_id in s.affected_roadmap_ids)
                and (category is None or s.category == category)
                and (severity is None or s.severity == severity)
                and (disposition is None or s.disposition == disposition)
            ]
            results.sort(key=lambda x: x.detected_at, reverse=True)
            return results[skip : skip + limit]

    # -------------------------------------------------------------------------
    # 6. Strategic Adaptation Proposals & Follow-Through
    # -------------------------------------------------------------------------

    def save_adaptation_proposal(
        self, record: StrategicAdaptationProposalRecord
    ) -> StrategicAdaptationProposalRecord:
        with self._lock:
            self._adaptation_proposals[record.proposal_id] = record
            return record

    def get_adaptation_proposal(
        self, proposal_id: str
    ) -> Optional[StrategicAdaptationProposalRecord]:
        with self._lock:
            return self._adaptation_proposals.get(proposal_id)

    def list_adaptation_proposals(
        self,
        tenant_id: str,
        roadmap_id: Optional[str] = None,
        status: Optional[AdaptationProposalStatus] = None,
        proposal_type: Optional[AdaptationProposalType] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[StrategicAdaptationProposalRecord]:
        with self._lock:
            results = [
                p
                for p in self._adaptation_proposals.values()
                if p.tenant_id == tenant_id
                and (roadmap_id is None or p.source_roadmap_id == roadmap_id)
                and (status is None or p.status == status)
                and (proposal_type is None or p.proposal_type == proposal_type)
            ]
            results.sort(key=lambda x: x.created_at, reverse=True)
            return results[skip : skip + limit]

    def save_adaptation_followthrough(
        self, record: AdaptationFollowThroughRecord
    ) -> AdaptationFollowThroughRecord:
        with self._lock:
            self._adaptation_followthroughs[record.followthrough_id] = record
            return record

    def get_adaptation_followthrough(
        self, followthrough_id: str
    ) -> Optional[AdaptationFollowThroughRecord]:
        with self._lock:
            return self._adaptation_followthroughs.get(followthrough_id)

    def get_followthrough_by_proposal(
        self, tenant_id: str, proposal_id: str
    ) -> Optional[AdaptationFollowThroughRecord]:
        with self._lock:
            for ft in self._adaptation_followthroughs.values():
                if ft.tenant_id == tenant_id and ft.proposal_id == proposal_id:
                    return ft
            return None

    def list_adaptation_followthroughs(
        self,
        tenant_id: str,
        skip: int = 0,
        limit: int = 50,
    ) -> List[AdaptationFollowThroughRecord]:
        with self._lock:
            results = [
                ft
                for ft in self._adaptation_followthroughs.values()
                if ft.tenant_id == tenant_id
            ]
            results.sort(key=lambda x: x.updated_at, reverse=True)
            return results[skip : skip + limit]

    # -------------------------------------------------------------------------
    # 7. Strategic Scenarios
    # -------------------------------------------------------------------------

    def save_scenario(
        self, record: StrategicScenarioRecord
    ) -> StrategicScenarioRecord:
        with self._lock:
            self._scenarios[record.scenario_id] = record
            return record

    def get_scenario(
        self, scenario_id: str
    ) -> Optional[StrategicScenarioRecord]:
        with self._lock:
            return self._scenarios.get(scenario_id)

    def list_scenarios(
        self,
        tenant_id: str,
        roadmap_id: Optional[str] = None,
        scenario_type: Optional[ScenarioType] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[StrategicScenarioRecord]:
        with self._lock:
            results = [
                s
                for s in self._scenarios.values()
                if s.tenant_id == tenant_id
                and (roadmap_id is None or s.input_roadmap_id == roadmap_id)
                and (scenario_type is None or s.scenario_type == scenario_type)
            ]
            results.sort(key=lambda x: x.created_at, reverse=True)
            return results[skip : skip + limit]

    # -------------------------------------------------------------------------
    # 8. Strategic Execution Exceptions
    # -------------------------------------------------------------------------

    def save_exception(
        self, record: StrategicExecutionExceptionRecord
    ) -> StrategicExecutionExceptionRecord:
        with self._lock:
            self._exceptions[record.exception_id] = record
            return record

    def get_exception(
        self, exception_id: str
    ) -> Optional[StrategicExecutionExceptionRecord]:
        with self._lock:
            return self._exceptions.get(exception_id)

    def list_exceptions(
        self,
        tenant_id: str,
        roadmap_id: Optional[str] = None,
        category: Optional[ExecutionExceptionCategory] = None,
        status: Optional[ExecutionExceptionStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[StrategicExecutionExceptionRecord]:
        with self._lock:
            results = [
                e
                for e in self._exceptions.values()
                if e.tenant_id == tenant_id
                and (roadmap_id is None or roadmap_id in e.affected_roadmap_ids)
                and (category is None or e.category == category)
                and (status is None or e.status == status)
            ]
            results.sort(key=lambda x: x.created_at, reverse=True)
            return results[skip : skip + limit]

    # -------------------------------------------------------------------------
    # 9. Strategic Review Packages
    # -------------------------------------------------------------------------

    def save_review_package(
        self, record: StrategicReviewPackageRecord
    ) -> StrategicReviewPackageRecord:
        with self._lock:
            self._review_packages[record.package_id] = record
            return record

    def get_review_package(
        self, package_id: str
    ) -> Optional[StrategicReviewPackageRecord]:
        with self._lock:
            return self._review_packages.get(package_id)

    def list_review_packages(
        self,
        tenant_id: str,
        roadmap_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[StrategicReviewPackageRecord]:
        with self._lock:
            results = [
                p
                for p in self._review_packages.values()
                if p.tenant_id == tenant_id
                and (roadmap_id is None or roadmap_id in p.included_roadmap_ids)
            ]
            results.sort(key=lambda x: x.created_at, reverse=True)
            return results[skip : skip + limit]


_governance_strategy_execution_repo = GovernanceStrategyExecutionRepository()


def get_governance_strategy_execution_repository() -> GovernanceStrategyExecutionRepository:
    """Returns the singleton instance of the Governance Strategy Execution repository."""
    return _governance_strategy_execution_repo
