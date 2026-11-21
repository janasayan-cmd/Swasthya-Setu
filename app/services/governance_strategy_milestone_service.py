"""Phase 78: Governance Strategic Milestone and Dependency Service.

Manages roadmap milestones, typed dependencies, graph cycle detection,
and verified completion workflows.
"""

from datetime import datetime, timezone
import uuid
from typing import Dict, List, Optional, Set

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_strategy_repository import (
    GovernanceStrategyRepository,
    get_governance_strategy_repository,
)
from app.schemas.governance_strategy_milestone import (
    AddDependencyRequest,
    CreateMilestoneRequest,
    DependencyType,
    DependencyValidationResult,
    GovernanceStrategyMilestoneRecord,
    MilestoneDependency,
    MilestoneStatus,
    SubmitMilestoneCompletionRequest,
    UpdateMilestoneRequest,
    VerifyMilestoneCompletionRequest,
)
from app.schemas.governance_strategy_objective import CLINICAL_SAFETY_STRATEGY_DISCLAIMER


def _get_utc_now_str() -> str:
    return datetime.now(timezone.utc).isoformat()


class GovernanceStrategyMilestoneService:
    """Manages strategic milestones, delivery tracking, and dependency graph integrity."""

    def __init__(
        self,
        repository: Optional[GovernanceStrategyRepository] = None,
    ) -> None:
        self.repository = repository or get_governance_strategy_repository()

    def create_milestone(
        self,
        tenant_id: str,
        request: CreateMilestoneRequest,
    ) -> GovernanceStrategyMilestoneRecord:
        roadmap = self.repository.get_roadmap(request.roadmap_id)
        if not roadmap or roadmap.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.STRATEGY_ROADMAP_NOT_FOUND,
                message=f"Parent roadmap '{request.roadmap_id}' was not found.",
                status_code=404,
            )

        now = _get_utc_now_str()
        milestone_id = f"gsm-{uuid.uuid4().hex[:12]}"
        milestone = GovernanceStrategyMilestoneRecord(
            milestone_id=milestone_id,
            tenant_id=tenant_id,
            roadmap_id=request.roadmap_id,
            related_objective_id=request.related_objective_id,
            title=request.title,
            description=request.description,
            planned_start_date=request.planned_start_date,
            planned_completion_date=request.planned_completion_date,
            actual_start_date=None,
            actual_completion_date=None,
            responsible_owner_id=request.responsible_owner_id,
            expected_deliverables=request.expected_deliverables or [],
            evidence_requirements=request.evidence_requirements or [],
            completion_evidence_reference=None,
            related_portfolio_id=request.related_portfolio_id,
            related_implementation_id=request.related_implementation_id,
            status=MilestoneStatus.PENDING,
            delay_reason=None,
            dependencies=[],
            verified_by=None,
            verified_at=None,
            disclaimer=CLINICAL_SAFETY_STRATEGY_DISCLAIMER,
            created_at=now,
            updated_at=now,
        )
        saved_ms = self.repository.save_milestone(milestone)

        # Append to roadmap's milestone_ids
        if milestone_id not in roadmap.milestone_ids:
            ms_ids = list(roadmap.milestone_ids)
            ms_ids.append(milestone_id)
            roadmap = roadmap.model_copy(update={"milestone_ids": ms_ids, "updated_at": now})
            self.repository.save_roadmap(roadmap)

        return saved_ms

    def update_milestone(
        self,
        tenant_id: str,
        milestone_id: str,
        request: UpdateMilestoneRequest,
    ) -> GovernanceStrategyMilestoneRecord:
        milestone = self.repository.get_milestone(milestone_id)
        if not milestone or milestone.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.STRATEGY_MILESTONE_NOT_FOUND,
                message=f"Milestone '{milestone_id}' was not found.",
                status_code=404,
            )

        now = _get_utc_now_str()
        update_data = {}
        if request.title is not None:
            update_data["title"] = request.title
        if request.description is not None:
            update_data["description"] = request.description
        if request.planned_start_date is not None:
            update_data["planned_start_date"] = request.planned_start_date
        if request.planned_completion_date is not None:
            update_data["planned_completion_date"] = request.planned_completion_date
        if request.status is not None:
            update_data["status"] = request.status
        if request.delay_reason is not None:
            update_data["delay_reason"] = request.delay_reason
        if request.related_portfolio_id is not None:
            update_data["related_portfolio_id"] = request.related_portfolio_id
        if request.related_implementation_id is not None:
            update_data["related_implementation_id"] = request.related_implementation_id

        update_data["updated_at"] = now
        milestone = milestone.model_copy(update=update_data)
        return self.repository.save_milestone(milestone)

    def add_dependency(
        self,
        tenant_id: str,
        milestone_id: str,
        request: AddDependencyRequest,
    ) -> GovernanceStrategyMilestoneRecord:
        milestone = self.repository.get_milestone(milestone_id)
        if not milestone or milestone.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.STRATEGY_MILESTONE_NOT_FOUND,
                message=f"Milestone '{milestone_id}' was not found.",
                status_code=404,
            )

        target_ms = self.repository.get_milestone(request.depends_on_milestone_id)
        if not target_ms or target_ms.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.STRATEGY_DEPENDENCY_INVALID,
                message=f"Target dependency milestone '{request.depends_on_milestone_id}' was not found.",
                status_code=404,
            )

        if milestone_id == request.depends_on_milestone_id:
            raise AppException(
                code=ErrorCode.STRATEGY_DEPENDENCY_CYCLE_DETECTED,
                message="Circular dependency detected: Milestone cannot depend on itself.",
                status_code=400,
            )

        # Detect indirect cycles: Does target_ms depend on milestone_id directly or indirectly?
        visited: Set[str] = set()
        queue = [request.depends_on_milestone_id]
        while queue:
            curr_id = queue.pop(0)
            if curr_id in visited:
                continue
            visited.add(curr_id)

            curr_ms = self.repository.get_milestone(curr_id)
            if curr_ms:
                for dep in curr_ms.dependencies:
                    if dep.depends_on_milestone_id == milestone_id:
                        raise AppException(
                            code=ErrorCode.STRATEGY_DEPENDENCY_CYCLE_DETECTED,
                            message=f"Circular dependency detected between milestone '{milestone_id}' and '{request.depends_on_milestone_id}'.",
                            status_code=400,
                        )
                    queue.append(dep.depends_on_milestone_id)

        now = _get_utc_now_str()
        new_dep = MilestoneDependency(
            dependency_id=f"dep-{uuid.uuid4().hex[:8]}",
            milestone_id=milestone_id,
            depends_on_milestone_id=request.depends_on_milestone_id,
            dependency_type=request.dependency_type,
            description=request.description,
        )

        deps = [d for d in milestone.dependencies if d.depends_on_milestone_id != request.depends_on_milestone_id]
        deps.append(new_dep)

        milestone = milestone.model_copy(update={"dependencies": deps, "updated_at": now})
        return self.repository.save_milestone(milestone)

    def validate_dependencies(
        self,
        tenant_id: str,
        roadmap_id: str,
    ) -> DependencyValidationResult:
        milestones = self.repository.list_milestones(tenant_id=tenant_id, roadmap_id=roadmap_id, limit=200)
        ms_map = {m.milestone_id: m for m in milestones}

        missing_prereqs = []
        date_conflicts = []
        cycles = []

        # Graph build
        adj: Dict[str, List[str]] = {m.milestone_id: [] for m in milestones}
        for m in milestones:
            for dep in m.dependencies:
                if dep.depends_on_milestone_id not in ms_map:
                    missing_prereqs.append(f"Milestone '{m.milestone_id}' depends on missing '{dep.depends_on_milestone_id}'.")
                else:
                    adj[m.milestone_id].append(dep.depends_on_milestone_id)
                    parent_ms = ms_map[dep.depends_on_milestone_id]
                    # Date conflict: parent completes after dependent starts
                    if parent_ms.planned_completion_date > m.planned_start_date:
                        date_conflicts.append(
                            f"Sequencing conflict: prerequisite '{parent_ms.milestone_id}' completes on {parent_ms.planned_completion_date} which is after '{m.milestone_id}' starts on {m.planned_start_date}."
                        )

        # Check cycles with DFS
        visited: Dict[str, int] = {}  # 0: unvisited, 1: visiting, 2: visited

        def dfs(node: str, path: List[str]):
            visited[node] = 1
            path.append(node)
            for neighbor in adj.get(node, []):
                if neighbor in adj:
                    if visited.get(neighbor, 0) == 1:
                        cycle_path = path[path.index(neighbor):] + [neighbor]
                        cycles.append(cycle_path)
                    elif visited.get(neighbor, 0) == 0:
                        dfs(neighbor, path)
            path.pop()
            visited[node] = 2

        for m_id in adj:
            if visited.get(m_id, 0) == 0:
                dfs(m_id, [])

        is_valid = len(missing_prereqs) == 0 and len(date_conflicts) == 0 and len(cycles) == 0

        return DependencyValidationResult(
            is_valid=is_valid,
            cycles_detected=cycles,
            missing_prerequisites=missing_prereqs,
            date_conflicts=date_conflicts,
            disclaimer=CLINICAL_SAFETY_STRATEGY_DISCLAIMER,
        )

    def submit_completion(
        self,
        tenant_id: str,
        milestone_id: str,
        request: SubmitMilestoneCompletionRequest,
    ) -> GovernanceStrategyMilestoneRecord:
        milestone = self.repository.get_milestone(milestone_id)
        if not milestone or milestone.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.STRATEGY_MILESTONE_NOT_FOUND,
                message=f"Milestone '{milestone_id}' was not found.",
                status_code=404,
            )

        now = _get_utc_now_str()
        milestone = milestone.model_copy(
            update={
                "status": MilestoneStatus.IN_PROGRESS,
                "completion_evidence_reference": request.completion_evidence_reference,
                "actual_completion_date": request.actual_completion_date or now,
                "updated_at": now,
            }
        )
        return self.repository.save_milestone(milestone)

    def verify_completion(
        self,
        tenant_id: str,
        milestone_id: str,
        verifier_id: str,
        request: VerifyMilestoneCompletionRequest,
    ) -> GovernanceStrategyMilestoneRecord:
        milestone = self.repository.get_milestone(milestone_id)
        if not milestone or milestone.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.STRATEGY_MILESTONE_NOT_FOUND,
                message=f"Milestone '{milestone_id}' was not found.",
                status_code=404,
            )

        # Separation of duties: milestone owner cannot verify their own milestone completion
        if milestone.responsible_owner_id == verifier_id:
            raise AppException(
                code=ErrorCode.STRATEGY_SEPARATION_OF_DUTIES_VIOLATION,
                message="Separation of duties violation: Responsible owner cannot verify their own milestone completion.",
                status_code=403,
            )

        if not milestone.completion_evidence_reference:
            raise AppException(
                code=ErrorCode.INVALID_STRATEGY_MILESTONE_STATE,
                message="Cannot verify milestone without supporting completion evidence reference.",
                status_code=400,
            )

        now = _get_utc_now_str()
        milestone = milestone.model_copy(
            update={
                "status": MilestoneStatus.COMPLETED,
                "verified_by": verifier_id,
                "verified_at": now,
                "updated_at": now,
            }
        )
        return self.repository.save_milestone(milestone)

    def get_milestone(
        self,
        tenant_id: str,
        milestone_id: str,
    ) -> GovernanceStrategyMilestoneRecord:
        milestone = self.repository.get_milestone(milestone_id)
        if not milestone or milestone.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.STRATEGY_MILESTONE_NOT_FOUND,
                message=f"Milestone '{milestone_id}' was not found.",
                status_code=404,
            )
        return milestone

    def list_milestones(
        self,
        tenant_id: str,
        roadmap_id: Optional[str] = None,
        status: Optional[MilestoneStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[GovernanceStrategyMilestoneRecord]:
        return self.repository.list_milestones(
            tenant_id=tenant_id,
            roadmap_id=roadmap_id,
            status=status,
            skip=skip,
            limit=limit,
        )
