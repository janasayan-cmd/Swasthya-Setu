"""Phase 75: Portfolio Initiative Service.

Coordinates:
- Registration of authorized governance change initiatives into portfolios
- Validation against Phase 73 implementations and Phase 74 adoption records
- Lineage reconstruction and controlled initiative removal
"""

from datetime import datetime, timezone
import uuid
from typing import List, Optional
from fastapi import status

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_change_portfolio_repository import (
    GovernanceChangePortfolioRepository,
    get_governance_change_portfolio_repository,
)
from app.repositories.governance_decision_implementation_repository import (
    get_governance_decision_implementation_repository,
)
from app.repositories.governance_change_adoption_repository import (
    get_governance_change_adoption_repository,
)
from app.schemas.user import AuthenticatedUserContext
from app.schemas.portfolio_initiative import (
    InitiativeCoordinationStatus,
    InitiativeLineageResponse,
    PortfolioInitiativeRecord,
    RegisterInitiativeRequest,
    RemoveInitiativeRequest,
)


class PortfolioInitiativeService:
    """Service governing portfolio initiative membership, source validation, and lineage."""

    def __init__(
        self,
        repository: Optional[GovernanceChangePortfolioRepository] = None,
    ) -> None:
        self.repo = repository or get_governance_change_portfolio_repository()
        self.phase73_repo = get_governance_decision_implementation_repository()
        self.phase74_repo = get_governance_change_adoption_repository()

    def register_initiative(
        self,
        portfolio_id: str,
        request: RegisterInitiativeRequest,
        current_user: AuthenticatedUserContext,
    ) -> PortfolioInitiativeRecord:
        """Registers an authorized governance initiative into a portfolio."""
        user_tenant = current_user.tenant_id or current_user.organization_id or "default_tenant"

        port = self.repo.get_portfolio(portfolio_id)
        if not port or port.tenant_id != user_tenant:
            raise AppException(
                code=ErrorCode.GOVERNANCE_PORTFOLIO_NOT_FOUND,
                message=f"Portfolio '{portfolio_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        # Check for duplicate initiative referencing same implementation in this portfolio
        existing = self.repo.list_initiatives_for_portfolio(portfolio_id, user_tenant)
        for init in existing:
            if init.implementation_id == request.implementation_id and init.coordination_status != InitiativeCoordinationStatus.WITHDRAWN:
                raise AppException(
                    code=ErrorCode.INITIATIVE_ALREADY_IN_PORTFOLIO,
                    message=f"Implementation '{request.implementation_id}' is already registered in portfolio '{portfolio_id}'.",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

        # Validate Phase 73 implementation record eligibility
        phase73_rec = self.phase73_repo.get_implementation(request.implementation_id)
        source_impl_status = None
        if phase73_rec is not None:
            rec_tenant = getattr(phase73_rec, "organization_id", None) or getattr(phase73_rec, "tenant_id", None)
            if rec_tenant != user_tenant:
                raise AppException(
                    code=ErrorCode.INITIATIVE_SOURCE_RECORD_INVALID,
                    message="Referenced Phase 73 implementation record belongs to a different tenant.",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
            if phase73_rec.status.value in ["CANCELLED_WITH_AUTHORIZATION"]:
                raise AppException(
                    code=ErrorCode.INITIATIVE_SOURCE_RECORD_INVALID,
                    message=f"Referenced Phase 73 implementation record is cancelled ({phase73_rec.status.value}).",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
            source_impl_status = phase73_rec.status.value
        else:
            if len(request.implementation_id.strip()) < 3:
                raise AppException(
                    code=ErrorCode.INITIATIVE_SOURCE_RECORD_INVALID,
                    message="A valid Phase 73 implementation record reference is mandatory.",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

        # Validate Phase 74 adoption registration if provided
        source_adopt_status = None
        if request.adoption_registration_id:
            phase74_rec = self.phase74_repo.get_registration(request.adoption_registration_id)
            if phase74_rec is not None:
                if phase74_rec.tenant_id != user_tenant:
                    raise AppException(
                        code=ErrorCode.INITIATIVE_SOURCE_RECORD_INVALID,
                        message="Referenced Phase 74 adoption registration belongs to a different tenant.",
                        status_code=status.HTTP_400_BAD_REQUEST,
                    )
                source_adopt_status = phase74_rec.status.value

        now = datetime.now(timezone.utc).isoformat()
        init_id = f"pfi_{uuid.uuid4().hex[:12]}"

        record = PortfolioInitiativeRecord(
            initiative_id=init_id,
            portfolio_id=portfolio_id,
            tenant_id=user_tenant,
            decision_id=request.decision_id,
            implementation_id=request.implementation_id,
            adoption_registration_id=request.adoption_registration_id,
            title=request.title,
            initiative_description=request.initiative_description,
            intended_operational_change=request.intended_operational_change,
            participating_facilities=request.participating_facilities,
            participating_departments=request.participating_departments,
            participating_teams=request.participating_teams,
            accountable_owner_id=request.accountable_owner_id,
            planned_start_date=request.planned_start_date,
            planned_target_date=request.planned_target_date,
            priority=request.priority,
            coordination_status=InitiativeCoordinationStatus.ACCEPTED,
            source_implementation_status=source_impl_status or "IN_PROGRESS",
            source_adoption_status=source_adopt_status,
            is_blocked=False,
            blocked_reason=None,
            created_by=current_user.user_id,
            created_at=now,
            updated_at=now,
        )

        saved = self.repo.save_initiative(record)
        self.repo.log_timeline_event(
            portfolio_id=portfolio_id,
            event_type="governance_portfolio.initiative_added",
            actor_id=current_user.user_id,
            summary=f"Initiative '{saved.title}' added to portfolio.",
            details={"initiative_id": saved.initiative_id, "implementation_id": saved.implementation_id},
        )
        return saved

    def get_initiative(
        self, initiative_id: str, current_user: AuthenticatedUserContext
    ) -> PortfolioInitiativeRecord:
        """Retrieves a portfolio initiative with tenant isolation."""
        user_tenant = current_user.tenant_id or current_user.organization_id or "default_tenant"
        init = self.repo.get_initiative(initiative_id)
        if not init or init.tenant_id != user_tenant:
            raise AppException(
                code=ErrorCode.PORTFOLIO_INITIATIVE_NOT_FOUND,
                message=f"Portfolio initiative '{initiative_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return init

    def list_initiatives_for_portfolio(
        self, portfolio_id: str, current_user: AuthenticatedUserContext
    ) -> List[PortfolioInitiativeRecord]:
        """Lists initiatives belonging to a portfolio."""
        user_tenant = current_user.tenant_id or current_user.organization_id or "default_tenant"
        port = self.repo.get_portfolio(portfolio_id)
        if not port or port.tenant_id != user_tenant:
            raise AppException(
                code=ErrorCode.GOVERNANCE_PORTFOLIO_NOT_FOUND,
                message=f"Portfolio '{portfolio_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return self.repo.list_initiatives_for_portfolio(portfolio_id, user_tenant)

    def remove_initiative(
        self,
        initiative_id: str,
        request: RemoveInitiativeRequest,
        current_user: AuthenticatedUserContext,
    ) -> PortfolioInitiativeRecord:
        """Removes an initiative from portfolio coordination (marks WITHDRAWN)."""
        init = self.get_initiative(initiative_id, current_user)

        # Check if there are active dependencies that block removal
        deps = self.repo.list_dependencies_for_initiative(initiative_id, init.tenant_id)
        active_blocking_deps = [
            d for d in deps
            if d.target_initiative_id == initiative_id and d.status.value in ["CONFIRMED", "ACTIVE"]
        ]
        if active_blocking_deps:
            raise AppException(
                code=ErrorCode.INVALID_PORTFOLIO_INITIATIVE_STATE,
                message=f"Cannot remove initiative '{initiative_id}' because {len(active_blocking_deps)} active dependencies rely on it.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        now = datetime.now(timezone.utc).isoformat()
        i_dict = init.model_dump()
        i_dict["coordination_status"] = InitiativeCoordinationStatus.WITHDRAWN
        i_dict["updated_at"] = now

        saved = self.repo.save_initiative(PortfolioInitiativeRecord(**i_dict))
        self.repo.log_timeline_event(
            portfolio_id=init.portfolio_id,
            event_type="governance_portfolio.initiative_removed",
            actor_id=current_user.user_id,
            summary=f"Initiative '{saved.title}' removed from portfolio: {request.removal_reason}",
            details={"initiative_id": saved.initiative_id, "reason": request.removal_reason},
        )
        return saved

    def get_initiative_lineage(
        self, initiative_id: str, current_user: AuthenticatedUserContext
    ) -> InitiativeLineageResponse:
        """Reconstructs the full lineage from decision to portfolio coordination."""
        init = self.get_initiative(initiative_id, current_user)
        deps = self.repo.list_dependencies_for_initiative(initiative_id, init.tenant_id)
        conflicts = [
            c for c in self.repo.list_conflicts_for_portfolio(init.portfolio_id, init.tenant_id)
            if initiative_id in c.initiative_ids
        ]

        nodes = [
            {"node_type": "GOVERNANCE_DECISION", "id": init.decision_id, "label": "Phase 72 Approved Decision"},
            {"node_type": "IMPLEMENTATION_RECORD", "id": init.implementation_id, "label": "Phase 73 Implementation Record"},
        ]
        if init.adoption_registration_id:
            nodes.append({
                "node_type": "ADOPTION_REGISTRATION",
                "id": init.adoption_registration_id,
                "label": "Phase 74 Adoption Registration",
            })
        nodes.append({
            "node_type": "PORTFOLIO_INITIATIVE",
            "id": init.initiative_id,
            "portfolio_id": init.portfolio_id,
            "label": init.title,
            "coordination_status": init.coordination_status.value,
        })

        return InitiativeLineageResponse(
            initiative_id=init.initiative_id,
            portfolio_id=init.portfolio_id,
            tenant_id=init.tenant_id,
            decision_id=init.decision_id,
            implementation_id=init.implementation_id,
            adoption_registration_id=init.adoption_registration_id,
            title=init.title,
            coordination_status=init.coordination_status.value,
            source_implementation_status=init.source_implementation_status,
            source_adoption_status=init.source_adoption_status,
            dependencies_count=len(deps),
            conflicts_count=len(conflicts),
            lineage_nodes=nodes,
        )
