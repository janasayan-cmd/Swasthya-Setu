"""Phase 79: Cross-Roadmap Dependency Service.

Coordinates inter-roadmap dependencies, validates sequencing integrity,
and detects direct and indirect dependency cycles.
"""

from collections import defaultdict
from datetime import datetime, timezone
import uuid
from typing import Dict, List, Optional, Set

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_strategy_execution_repository import (
    GovernanceStrategyExecutionRepository,
    get_governance_strategy_execution_repository,
)
from app.schemas.governance_cross_roadmap_dependency import (
    CreateCrossRoadmapDependencyRequest,
    CrossDependencyStatus,
    CrossRoadmapDependencyRecord,
    CrossRoadmapValidationResult,
    ReviewCrossRoadmapDependencyRequest,
)
from app.schemas.governance_strategy_execution_monitoring import (
    CLINICAL_SAFETY_MONITORING_DISCLAIMER,
)


def _get_utc_now_str() -> str:
    return datetime.now(timezone.utc).isoformat()


class GovernanceCrossRoadmapDependencyService:
    """Manages cross-roadmap dependencies, conflict evaluation, and cycle detection."""

    def __init__(
        self,
        repository: Optional[GovernanceStrategyExecutionRepository] = None,
    ) -> None:
        self.repository = repository or get_governance_strategy_execution_repository()

    def _find_cycles_with_new_edge(
        self,
        tenant_id: str,
        new_source: str,
        new_target: str,
    ) -> List[List[str]]:
        """Detects if adding an edge new_source -> new_target creates a cycle."""
        all_deps = self.repository.list_all_cross_dependencies(tenant_id)
        graph: Dict[str, List[str]] = defaultdict(list)
        for d in all_deps:
            if d.status != CrossDependencyStatus.WAIVED:
                graph[d.source_roadmap_id].append(d.target_roadmap_id)
        graph[new_source].append(new_target)

        # Check for reachability from new_target back to new_source using DFS
        visited: Set[str] = set()
        path: List[str] = [new_target]

        def dfs(node: str) -> Optional[List[str]]:
            if node == new_source:
                return path[:]
            visited.add(node)
            for neighbor in graph[node]:
                if neighbor not in visited or neighbor == new_source:
                    path.append(neighbor)
                    res = dfs(neighbor)
                    if res is not None:
                        return res
                    path.pop()
            return None

        cycle_path = dfs(new_target)
        if cycle_path is not None:
            return [[new_source] + cycle_path]
        return []

    def create_cross_dependency(
        self,
        tenant_id: str,
        request: CreateCrossRoadmapDependencyRequest,
    ) -> CrossRoadmapDependencyRecord:
        # Check for circular dependency
        cycles = self._find_cycles_with_new_edge(
            tenant_id=tenant_id,
            new_source=request.source_roadmap_id,
            new_target=request.target_roadmap_id,
        )
        if cycles:
            cycle_desc = " -> ".join(cycles[0])
            raise AppException(
                code=ErrorCode.CROSS_ROADMAP_CYCLE_DETECTED,
                message=f"Circular cross-roadmap dependency detected: {cycle_desc}",
                status_code=400,
            )

        now_str = _get_utc_now_str()
        dep_id = f"CRD-{uuid.uuid4().hex[:8].upper()}"

        record = CrossRoadmapDependencyRecord(
            dependency_id=dep_id,
            tenant_id=tenant_id,
            source_roadmap_id=request.source_roadmap_id,
            target_roadmap_id=request.target_roadmap_id,
            source_objective_id=request.source_objective_id,
            target_objective_id=request.target_objective_id,
            source_milestone_id=request.source_milestone_id,
            target_milestone_id=request.target_milestone_id,
            category=request.category,
            rationale=request.rationale,
            planned_dependency_date=request.planned_dependency_date,
            status=CrossDependencyStatus.IDENTIFIED,
            responsible_owner_id=request.responsible_owner_id,
            evidence_references=request.evidence_references or [],
            conflict_description=None,
            review_outcome=None,
            disclaimer=CLINICAL_SAFETY_MONITORING_DISCLAIMER,
            created_at=now_str,
            updated_at=now_str,
        )
        return self.repository.save_cross_dependency(record)

    def review_cross_dependency(
        self,
        tenant_id: str,
        reviewer_id: str,
        dependency_id: str,
        request: ReviewCrossRoadmapDependencyRequest,
    ) -> CrossRoadmapDependencyRecord:
        dep = self.repository.get_cross_dependency(dependency_id)
        if not dep or dep.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.CROSS_ROADMAP_DEPENDENCY_NOT_FOUND,
                message=f"Cross-roadmap dependency '{dependency_id}' was not found.",
                status_code=404,
            )

        # Separation of duties: proposer/owner cannot review own dependency
        if reviewer_id == dep.responsible_owner_id:
            raise AppException(
                code=ErrorCode.STRATEGY_EXECUTION_SEPARATION_OF_DUTIES_VIOLATION,
                message="Proposers or designated owners cannot review or disposition their own cross-roadmap dependencies.",
                status_code=403,
            )

        now_str = _get_utc_now_str()
        updated = dep.model_copy(
            update={
                "status": request.status,
                "review_outcome": request.review_outcome,
                "conflict_description": request.conflict_description or dep.conflict_description,
                "updated_at": now_str,
            }
        )
        return self.repository.save_cross_dependency(updated)

    def get_cross_dependency(
        self,
        tenant_id: str,
        dependency_id: str,
    ) -> CrossRoadmapDependencyRecord:
        dep = self.repository.get_cross_dependency(dependency_id)
        if not dep or dep.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.CROSS_ROADMAP_DEPENDENCY_NOT_FOUND,
                message=f"Cross-roadmap dependency '{dependency_id}' was not found.",
                status_code=404,
            )
        return dep

    def list_cross_dependencies(
        self,
        tenant_id: str,
        roadmap_id: Optional[str] = None,
        status: Optional[CrossDependencyStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[CrossRoadmapDependencyRecord]:
        return self.repository.list_cross_dependencies(
            tenant_id=tenant_id,
            roadmap_id=roadmap_id,
            status=status,
            skip=skip,
            limit=limit,
        )

    def validate_cross_dependencies(
        self,
        tenant_id: str,
        roadmap_id: Optional[str] = None,
    ) -> CrossRoadmapValidationResult:
        all_deps = self.repository.list_all_cross_dependencies(tenant_id)
        if roadmap_id:
            all_deps = [
                d for d in all_deps
                if d.source_roadmap_id == roadmap_id or d.target_roadmap_id == roadmap_id
            ]

        graph: Dict[str, List[str]] = defaultdict(list)
        for d in all_deps:
            if d.status != CrossDependencyStatus.WAIVED:
                graph[d.source_roadmap_id].append(d.target_roadmap_id)

        # Detect all cycles using Tarjan or DFS cycle check
        visited: Dict[str, int] = {}  # 0: unvisited, 1: visiting, 2: visited
        cycles: List[List[str]] = []
        path: List[str] = []

        def dfs(node: str):
            visited[node] = 1
            path.append(node)
            for neighbor in graph.get(node, []):
                if visited.get(neighbor, 0) == 1:
                    cycle_start = path.index(neighbor)
                    cycles.append(path[cycle_start:] + [neighbor])
                elif visited.get(neighbor, 0) == 0:
                    dfs(neighbor)
            path.pop()
            visited[node] = 2

        for node in list(graph.keys()):
            if visited.get(node, 0) == 0:
                dfs(node)

        date_conflicts: List[str] = []
        missing_prereqs: List[str] = []

        for d in all_deps:
            if d.status == CrossDependencyStatus.CONFLICT_DETECTED and d.conflict_description:
                date_conflicts.append(f"Dependency '{d.dependency_id}': {d.conflict_description}")
            if not d.target_roadmap_id:
                missing_prereqs.append(f"Dependency '{d.dependency_id}' lacks target roadmap reference.")

        is_valid = len(cycles) == 0 and len(date_conflicts) == 0 and len(missing_prereqs) == 0

        return CrossRoadmapValidationResult(
            is_valid=is_valid,
            cycles_detected=cycles,
            date_conflicts=date_conflicts,
            missing_prerequisites=missing_prereqs,
            disclaimer=CLINICAL_SAFETY_MONITORING_DISCLAIMER,
        )
