"""Phase 73: Dependency & Prerequisite Management Service.

Handles:
- Dependency tracking across Phase 49-72 workflows
- Circular dependency cycle detection
- Dependency reconciliation against destination workflows
- Authorized governance dependency waivers
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple

from fastapi import status

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_decision_implementation_repository import (
    GovernanceDecisionImplementationRepository,
    get_governance_decision_implementation_repository,
)
from app.schemas.decision_implementation_ownership_dependencies import (
    CreateDependencyRequest,
    DependencyStatus,
    DependencyType,
    ImplementationDependencyRecord,
    ReconcileDependencyRequest,
    WaiveDependencyRequest,
)


class ImplementationDependencyService:
    """Service governing implementation dependencies, prerequisites, and waivers."""

    def __init__(
        self,
        repository: Optional[GovernanceDecisionImplementationRepository] = None,
    ) -> None:
        self.repository = (
            repository or get_governance_decision_implementation_repository()
        )

    def _detect_circular_dependency(
        self, start_imp_id: str, candidate_source_id: str
    ) -> bool:
        """Performs cycle detection to ensure candidate dependency does not create a circular loop."""
        visited: Set[str] = set()
        stack: Set[str] = set()

        def dfs(node: str) -> bool:
            visited.add(node)
            stack.add(node)

            deps = self.repository.list_dependencies(node)
            for d in deps:
                neighbor = d.source_record_id
                # Only check dependencies that reference other implementations
                if neighbor in self.repository._implementations:
                    if neighbor not in visited:
                        if dfs(neighbor):
                            return True
                    elif neighbor in stack:
                        return True

            stack.remove(node)
            return False

        # Temporarily check if adding start_imp_id -> candidate_source_id forms a cycle
        if candidate_source_id == start_imp_id:
            return True

        # Check path from candidate_source_id to start_imp_id
        if candidate_source_id in self.repository._implementations:
            visited_chain: Set[str] = set()
            to_explore = [candidate_source_id]
            while to_explore:
                curr = to_explore.pop()
                if curr == start_imp_id:
                    return True
                if curr not in visited_chain:
                    visited_chain.add(curr)
                    curr_deps = self.repository.list_dependencies(curr)
                    for d in curr_deps:
                        if d.source_record_id in self.repository._implementations:
                            to_explore.append(d.source_record_id)

        return False

    def create_dependency(
        self,
        implementation_id: str,
        request: CreateDependencyRequest,
    ) -> ImplementationDependencyRecord:
        """Adds a gating dependency, preventing circular dependencies."""
        imp = self.repository.get_implementation(implementation_id)
        if not imp:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code=ErrorCode.DECISION_IMPLEMENTATION_NOT_FOUND,
                message=f"Implementation '{implementation_id}' not found.",
            )

        # Detect circular dependency
        if self._detect_circular_dependency(implementation_id, request.source_record_id):
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code=ErrorCode.CIRCULAR_DEPENDENCY_DETECTED,
                message=(
                    f"Circular dependency detected between implementation '{implementation_id}' "
                    f"and prerequisite '{request.source_record_id}'."
                ),
            )

        dependency = ImplementationDependencyRecord(
            implementation_id=implementation_id,
            dependency_type=request.dependency_type,
            source_workflow=request.source_workflow,
            source_record_id=request.source_record_id,
            required_state=request.required_state or "COMPLETED",
            status=DependencyStatus.PENDING,
            responsible_owner_id=request.responsible_owner_id,
            metadata=request.metadata or {},
        )

        return self.repository.save_dependency(dependency)

    def get_dependency(
        self, dependency_id: str
    ) -> ImplementationDependencyRecord:
        """Retrieves a dependency by ID."""
        dep = self.repository.get_dependency(dependency_id)
        if not dep:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code=ErrorCode.IMPLEMENTATION_DEPENDENCY_NOT_FOUND,
                message=f"Implementation dependency '{dependency_id}' not found.",
            )
        return dep

    def list_dependencies(
        self, implementation_id: str, status_filter: Optional[str] = None
    ) -> List[ImplementationDependencyRecord]:
        """Lists dependencies for an implementation."""
        return self.repository.list_dependencies(
            implementation_id=implementation_id, status=status_filter
        )

    def reconcile_dependency(
        self, dependency_id: str, request: ReconcileDependencyRequest
    ) -> ImplementationDependencyRecord:
        """Updates dependency status based on external/destination workflow state."""
        dep = self.get_dependency(dependency_id)
        dep.status = request.new_status
        dep.last_verified_at = datetime.now(timezone.utc)
        if request.notes:
            dep.metadata["reconciliation_notes"] = request.notes

        return self.repository.save_dependency(dep)

    def waive_dependency(
        self,
        dependency_id: str,
        request: WaiveDependencyRequest,
        authorizer_id: str,
        authorizer_role: str,
    ) -> ImplementationDependencyRecord:
        """Formally waives a dependency with documented governance authorization."""
        dep = self.get_dependency(dependency_id)

        # Enforce that only executive/authorized roles can waive dependencies
        if authorizer_role not in ["ADMIN", "DOCTOR", "EXECUTIVE"]:
            raise AppException(
                status_code=status.HTTP_403_FORBIDDEN,
                code=ErrorCode.DEPENDENCY_WAIVER_UNAUTHORIZED,
                message=f"Role '{authorizer_role}' is not authorized to grant dependency waivers.",
            )

        dep.status = DependencyStatus.WAIVED_WITH_AUTHORIZATION
        dep.waiver_authorized_by = authorizer_id
        dep.waiver_rationale = request.waiver_rationale
        dep.waived_at = datetime.now(timezone.utc)

        return self.repository.save_dependency(dep)

    def check_prerequisites_satisfied(
        self, implementation_id: str
    ) -> Tuple[bool, List[str]]:
        """Verifies if all dependencies for an implementation are satisfied or waived."""
        deps = self.repository.list_dependencies(implementation_id)
        blockers = []
        for d in deps:
            if d.status not in [
                DependencyStatus.SATISFIED,
                DependencyStatus.WAIVED_WITH_AUTHORIZATION,
                DependencyStatus.NOT_APPLICABLE,
            ]:
                blockers.append(
                    f"Dependency {d.dependency_id} ({d.dependency_type.value} from {d.source_workflow}) is {d.status.value}"
                )

        return (len(blockers) == 0, blockers)
