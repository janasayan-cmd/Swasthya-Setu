"""Phase 75: Cross-Initiative Dependency & Graph Service.

Coordinates:
- Cross-initiative dependency registration and lifecycle
- Rigorous circular dependency detection
- Dependency graph generation and blocked initiative identification
"""

from datetime import datetime, timezone
import uuid
from typing import Dict, List, Optional, Set
from fastapi import status

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_change_portfolio_repository import (
    GovernanceChangePortfolioRepository,
    get_governance_change_portfolio_repository,
)
from app.schemas.user import AuthenticatedUserContext
from app.schemas.portfolio_initiative import (
    InitiativeCoordinationStatus,
    PortfolioInitiativeRecord,
)
from app.schemas.portfolio_dependencies_conflicts import (
    ConfirmDependencyRequest,
    CreateDependencyRequest,
    CrossInitiativeDependencyRecord,
    DependencyGraphResponse,
    DependencyStatus,
    DependencyType,
    DisputeDependencyRequest,
    ResolveDependencyRequest,
)


class PortfolioDependencyService:
    """Service governing cross-initiative dependencies and graph analysis."""

    def __init__(
        self,
        repository: Optional[GovernanceChangePortfolioRepository] = None,
    ) -> None:
        self.repo = repository or get_governance_change_portfolio_repository()

    def _path_exists(
        self,
        adj: Dict[str, List[str]],
        start: str,
        goal: str,
        visited: Optional[Set[str]] = None,
    ) -> bool:
        """DFS to check if there is a directed path from start to goal."""
        if start == goal:
            return True
        if visited is None:
            visited = set()
        visited.add(start)
        for neighbor in adj.get(start, []):
            if neighbor not in visited:
                if self._path_exists(adj, neighbor, goal, visited):
                    return True
        return False

    def create_dependency(
        self,
        source_initiative_id: str,
        request: CreateDependencyRequest,
        current_user: AuthenticatedUserContext,
    ) -> CrossInitiativeDependencyRecord:
        """Declares a dependency from source_initiative to target_initiative."""
        user_tenant = current_user.tenant_id or current_user.organization_id or "default_tenant"

        source_init = self.repo.get_initiative(source_initiative_id)
        if not source_init or source_init.tenant_id != user_tenant:
            raise AppException(
                code=ErrorCode.PORTFOLIO_INITIATIVE_NOT_FOUND,
                message=f"Source initiative '{source_initiative_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        if source_initiative_id == request.target_initiative_id:
            raise AppException(
                code=ErrorCode.CIRCULAR_INITIATIVE_DEPENDENCY_DETECTED,
                message="An initiative cannot depend on itself.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        target_init = self.repo.get_initiative(request.target_initiative_id)
        if not target_init or target_init.tenant_id != user_tenant:
            raise AppException(
                code=ErrorCode.PORTFOLIO_INITIATIVE_NOT_FOUND,
                message=f"Target initiative '{request.target_initiative_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        if source_init.portfolio_id != target_init.portfolio_id:
            raise AppException(
                code=ErrorCode.INVALID_DEPENDENCY_STATE,
                message="Dependencies must be established between initiatives in the same portfolio.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Circular dependency check:
        # Build existing graph for portfolio
        existing_deps = self.repo.list_dependencies_for_portfolio(source_init.portfolio_id, user_tenant)
        adj: Dict[str, List[str]] = {}
        for d in existing_deps:
            if d.status not in [DependencyStatus.REMOVED, DependencyStatus.CANCELLED]:
                adj.setdefault(d.source_initiative_id, []).append(d.target_initiative_id)

        # If a path already exists from target_initiative to source_initiative, adding source -> target will cause a cycle
        if self._path_exists(adj, request.target_initiative_id, source_initiative_id):
            raise AppException(
                code=ErrorCode.CIRCULAR_INITIATIVE_DEPENDENCY_DETECTED,
                message=(
                    f"Circular dependency detected: Initiative '{request.target_initiative_id}' "
                    f"already directly or indirectly depends on '{source_initiative_id}'."
                ),
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        now = datetime.now(timezone.utc).isoformat()
        dep_id = f"dep_{uuid.uuid4().hex[:12]}"

        record = CrossInitiativeDependencyRecord(
            dependency_id=dep_id,
            portfolio_id=source_init.portfolio_id,
            tenant_id=user_tenant,
            source_initiative_id=source_initiative_id,
            target_initiative_id=request.target_initiative_id,
            dependency_type=request.dependency_type,
            description=request.description,
            dependency_owner_id=request.dependency_owner_id,
            required_condition=request.required_condition,
            expected_resolution_date=request.expected_resolution_date,
            status=DependencyStatus.PROPOSED,
            supporting_evidence_reference=request.supporting_evidence_reference,
            dispute_reason=None,
            verified_by=None,
            verified_at=None,
            created_by=current_user.user_id,
            created_at=now,
            updated_at=now,
        )

        saved = self.repo.save_dependency(record)
        self.repo.log_timeline_event(
            portfolio_id=source_init.portfolio_id,
            event_type="governance_portfolio.dependency_registered",
            actor_id=current_user.user_id,
            summary=f"Dependency ({request.dependency_type.value}) created: '{source_init.title}' -> '{target_init.title}'.",
            details={"dependency_id": saved.dependency_id},
        )
        return saved

    def get_dependency(
        self, dependency_id: str, current_user: AuthenticatedUserContext
    ) -> CrossInitiativeDependencyRecord:
        """Retrieves a dependency by ID with tenant isolation."""
        user_tenant = current_user.tenant_id or current_user.organization_id or "default_tenant"
        dep = self.repo.get_dependency(dependency_id)
        if not dep or dep.tenant_id != user_tenant:
            raise AppException(
                code=ErrorCode.CROSS_INITIATIVE_DEPENDENCY_NOT_FOUND,
                message=f"Cross-initiative dependency '{dependency_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return dep

    def list_dependencies_for_initiative(
        self, initiative_id: str, current_user: AuthenticatedUserContext
    ) -> List[CrossInitiativeDependencyRecord]:
        """Lists dependencies involving an initiative."""
        user_tenant = current_user.tenant_id or current_user.organization_id or "default_tenant"
        init = self.repo.get_initiative(initiative_id)
        if not init or init.tenant_id != user_tenant:
            raise AppException(
                code=ErrorCode.PORTFOLIO_INITIATIVE_NOT_FOUND,
                message=f"Portfolio initiative '{initiative_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return self.repo.list_dependencies_for_initiative(initiative_id, user_tenant)

    def confirm_dependency(
        self,
        dependency_id: str,
        request: ConfirmDependencyRequest,
        current_user: AuthenticatedUserContext,
    ) -> CrossInitiativeDependencyRecord:
        """Confirms a proposed cross-initiative dependency."""
        dep = self.get_dependency(dependency_id, current_user)
        if dep.status not in [DependencyStatus.PROPOSED, DependencyStatus.UNDER_REVIEW]:
            raise AppException(
                code=ErrorCode.INVALID_DEPENDENCY_STATE,
                message=f"Dependency cannot be confirmed from status '{dep.status.value}'.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        now = datetime.now(timezone.utc).isoformat()
        d_dict = dep.model_dump()
        d_dict["status"] = DependencyStatus.CONFIRMED
        d_dict["verified_by"] = current_user.user_id
        d_dict["verified_at"] = now
        d_dict["updated_at"] = now

        saved = self.repo.save_dependency(CrossInitiativeDependencyRecord(**d_dict))
        self.repo.log_timeline_event(
            portfolio_id=dep.portfolio_id,
            event_type="governance_portfolio.dependency_confirmed",
            actor_id=current_user.user_id,
            summary=f"Dependency '{saved.dependency_id}' confirmed.",
            details={"notes": request.confirmation_notes},
        )
        return saved

    def resolve_dependency(
        self,
        dependency_id: str,
        request: ResolveDependencyRequest,
        current_user: AuthenticatedUserContext,
    ) -> CrossInitiativeDependencyRecord:
        """Marks a dependency SATISFIED upon verified condition completion."""
        dep = self.get_dependency(dependency_id, current_user)

        now = datetime.now(timezone.utc).isoformat()
        d_dict = dep.model_dump()
        d_dict["status"] = DependencyStatus.SATISFIED
        d_dict["supporting_evidence_reference"] = request.resolution_evidence
        d_dict["updated_at"] = now

        saved = self.repo.save_dependency(CrossInitiativeDependencyRecord(**d_dict))
        self.repo.log_timeline_event(
            portfolio_id=dep.portfolio_id,
            event_type="governance_portfolio.dependency_resolved",
            actor_id=current_user.user_id,
            summary=f"Dependency '{saved.dependency_id}' satisfied.",
            details={"evidence": request.resolution_evidence},
        )
        return saved

    def dispute_dependency(
        self,
        dependency_id: str,
        request: DisputeDependencyRequest,
        current_user: AuthenticatedUserContext,
    ) -> CrossInitiativeDependencyRecord:
        """Marks a dependency DISPUTED with stated reason."""
        dep = self.get_dependency(dependency_id, current_user)

        now = datetime.now(timezone.utc).isoformat()
        d_dict = dep.model_dump()
        d_dict["status"] = DependencyStatus.DISPUTED
        d_dict["dispute_reason"] = request.dispute_reason
        d_dict["updated_at"] = now

        saved = self.repo.save_dependency(CrossInitiativeDependencyRecord(**d_dict))
        self.repo.log_timeline_event(
            portfolio_id=dep.portfolio_id,
            event_type="governance_portfolio.dependency_disputed",
            actor_id=current_user.user_id,
            summary=f"Dependency '{saved.dependency_id}' disputed: {request.dispute_reason}",
            details={"reason": request.dispute_reason},
        )
        return saved

    def get_dependency_graph(
        self, portfolio_id: str, current_user: AuthenticatedUserContext
    ) -> DependencyGraphResponse:
        """Generates graph representation and computes blocked nodes."""
        user_tenant = current_user.tenant_id or current_user.organization_id or "default_tenant"

        port = self.repo.get_portfolio(portfolio_id)
        if not port or port.tenant_id != user_tenant:
            raise AppException(
                code=ErrorCode.GOVERNANCE_PORTFOLIO_NOT_FOUND,
                message=f"Portfolio '{portfolio_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        initiatives = self.repo.list_initiatives_for_portfolio(portfolio_id, user_tenant)
        dependencies = self.repo.list_dependencies_for_portfolio(portfolio_id, user_tenant)

        nodes = []
        for init in initiatives:
            nodes.append({
                "id": init.initiative_id,
                "label": init.title,
                "coordination_status": init.coordination_status.value,
                "is_blocked": init.is_blocked,
            })

        edges = []
        blocked_initiatives: Set[str] = set()

        for d in dependencies:
            if d.status not in [DependencyStatus.REMOVED, DependencyStatus.CANCELLED]:
                edges.append({
                    "id": d.dependency_id,
                    "source": d.source_initiative_id,
                    "target": d.target_initiative_id,
                    "type": d.dependency_type.value,
                    "status": d.status.value,
                })
                # If dependency is BLOCKED or DISPUTED or un-satisfied MUST_COMPLETE_BEFORE, mark source as blocked
                if d.status in [DependencyStatus.BLOCKED, DependencyStatus.DISPUTED]:
                    blocked_initiatives.add(d.source_initiative_id)

        # Check for circular cycles in current active edges
        adj: Dict[str, List[str]] = {}
        for e in edges:
            adj.setdefault(e["source"], []).append(e["target"])

        cycles: List[List[str]] = []
        for init in initiatives:
            u = init.initiative_id
            for v in adj.get(u, []):
                if self._path_exists(adj, v, u):
                    cycle = [u, v]
                    if cycle not in cycles and [v, u] not in cycles:
                        cycles.append(cycle)

        return DependencyGraphResponse(
            portfolio_id=portfolio_id,
            nodes=nodes,
            edges=edges,
            circular_dependency_detected=len(cycles) > 0,
            circular_paths=cycles,
            blocked_initiative_ids=sorted(list(blocked_initiatives)),
        )
