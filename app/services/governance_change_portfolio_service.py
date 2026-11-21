"""Phase 75: Governance Change Portfolio Service.

Coordinates:
- Portfolio registration, scoping, and metadata management
- Governed lifecycle transitions (draft, submit, approve, activate, suspend, archive)
- Strict separation of duties on portfolio approval
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
from app.schemas.user import AuthenticatedUserContext
from app.schemas.governance_change_portfolio import (
    ApprovePortfolioRequest,
    ArchivePortfolioRequest,
    CreatePortfolioRequest,
    GovernanceChangePortfolioRecord,
    PortfolioStatus,
    SubmitPortfolioRequest,
    SuspendPortfolioRequest,
    UpdatePortfolioRequest,
)


class GovernanceChangePortfolioService:
    """Service governing change portfolios and lifecycle state transitions."""

    def __init__(
        self,
        repository: Optional[GovernanceChangePortfolioRepository] = None,
    ) -> None:
        self.repo = repository or get_governance_change_portfolio_repository()

    def create_portfolio(
        self,
        request: CreatePortfolioRequest,
        current_user: AuthenticatedUserContext,
    ) -> GovernanceChangePortfolioRecord:
        """Creates a new governance change portfolio in DRAFT state."""
        user_tenant = current_user.tenant_id or current_user.organization_id or "default_tenant"
        now = datetime.now(timezone.utc).isoformat()
        port_id = f"port_{uuid.uuid4().hex[:12]}"

        record = GovernanceChangePortfolioRecord(
            portfolio_id=port_id,
            tenant_id=user_tenant,
            name=request.name,
            description=request.description,
            governance_purpose=request.governance_purpose,
            portfolio_owner_id=request.portfolio_owner_id,
            executive_sponsor_id=request.executive_sponsor_id,
            participating_organizations=request.participating_organizations or [user_tenant],
            participating_facilities=request.participating_facilities,
            participating_departments=request.participating_departments,
            participating_teams=request.participating_teams,
            priority=request.priority,
            planned_start_date=request.planned_start_date,
            target_review_date=request.target_review_date,
            status=PortfolioStatus.DRAFT,
            inclusion_criteria=request.inclusion_criteria,
            exclusion_criteria=request.exclusion_criteria,
            related_management_review_ids=request.related_management_review_ids,
            version=1,
            created_by=current_user.user_id,
            created_at=now,
            updated_at=now,
        )

        saved = self.repo.save_portfolio(record)
        self.repo.log_timeline_event(
            portfolio_id=port_id,
            event_type="governance_portfolio.created",
            actor_id=current_user.user_id,
            summary=f"Portfolio '{saved.name}' created in DRAFT.",
            details={"portfolio_id": saved.portfolio_id, "priority": saved.priority.value},
        )
        return saved

    def get_portfolio(
        self, portfolio_id: str, current_user: AuthenticatedUserContext
    ) -> GovernanceChangePortfolioRecord:
        """Retrieves a portfolio with tenant isolation."""
        user_tenant = current_user.tenant_id or current_user.organization_id or "default_tenant"
        port = self.repo.get_portfolio(portfolio_id)
        if not port or port.tenant_id != user_tenant:
            raise AppException(
                code=ErrorCode.GOVERNANCE_PORTFOLIO_NOT_FOUND,
                message=f"Governance change portfolio '{portfolio_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return port

    def list_portfolios(
        self,
        current_user: AuthenticatedUserContext,
        status_filter: Optional[PortfolioStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[GovernanceChangePortfolioRecord]:
        """Lists portfolios for current tenant."""
        user_tenant = current_user.tenant_id or current_user.organization_id or "default_tenant"
        return self.repo.list_portfolios(
            tenant_id=user_tenant,
            status=status_filter,
            skip=skip,
            limit=limit,
        )

    def update_portfolio(
        self,
        portfolio_id: str,
        request: UpdatePortfolioRequest,
        current_user: AuthenticatedUserContext,
    ) -> GovernanceChangePortfolioRecord:
        """Updates portfolio metadata, participating scopes, and criteria."""
        port = self.get_portfolio(portfolio_id, current_user)
        if port.status in [PortfolioStatus.ARCHIVED, PortfolioStatus.CANCELLED]:
            raise AppException(
                code=ErrorCode.INVALID_GOVERNANCE_PORTFOLIO_STATE,
                message=f"Cannot update portfolio in terminal status '{port.status.value}'.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        now = datetime.now(timezone.utc).isoformat()
        p_dict = port.model_dump()
        if request.name is not None:
            p_dict["name"] = request.name
        if request.description is not None:
            p_dict["description"] = request.description
        if request.governance_purpose is not None:
            p_dict["governance_purpose"] = request.governance_purpose
        if request.portfolio_owner_id is not None:
            p_dict["portfolio_owner_id"] = request.portfolio_owner_id
        if request.executive_sponsor_id is not None:
            p_dict["executive_sponsor_id"] = request.executive_sponsor_id
        if request.participating_organizations is not None:
            p_dict["participating_organizations"] = request.participating_organizations
        if request.participating_facilities is not None:
            p_dict["participating_facilities"] = request.participating_facilities
        if request.participating_departments is not None:
            p_dict["participating_departments"] = request.participating_departments
        if request.participating_teams is not None:
            p_dict["participating_teams"] = request.participating_teams
        if request.priority is not None:
            p_dict["priority"] = request.priority
        if request.target_review_date is not None:
            p_dict["target_review_date"] = request.target_review_date
        if request.inclusion_criteria is not None:
            p_dict["inclusion_criteria"] = request.inclusion_criteria
        if request.exclusion_criteria is not None:
            p_dict["exclusion_criteria"] = request.exclusion_criteria

        p_dict["version"] = port.version + 1
        p_dict["updated_at"] = now

        saved = self.repo.save_portfolio(GovernanceChangePortfolioRecord(**p_dict))
        self.repo.log_timeline_event(
            portfolio_id=portfolio_id,
            event_type="governance_portfolio.updated",
            actor_id=current_user.user_id,
            summary=f"Portfolio updated to version {saved.version}.",
            details={"change_reason": request.change_reason},
        )
        return saved

    def submit_portfolio(
        self,
        portfolio_id: str,
        request: SubmitPortfolioRequest,
        current_user: AuthenticatedUserContext,
    ) -> GovernanceChangePortfolioRecord:
        """Submits a draft portfolio for governance approval."""
        port = self.get_portfolio(portfolio_id, current_user)
        if port.status != PortfolioStatus.DRAFT:
            raise AppException(
                code=ErrorCode.INVALID_GOVERNANCE_PORTFOLIO_STATE,
                message=f"Portfolio cannot be submitted from status '{port.status.value}'. Must be DRAFT.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        now = datetime.now(timezone.utc).isoformat()
        p_dict = port.model_dump()
        p_dict["status"] = PortfolioStatus.SUBMITTED
        p_dict["submitted_by"] = current_user.user_id
        p_dict["submitted_at"] = now
        p_dict["updated_at"] = now

        saved = self.repo.save_portfolio(GovernanceChangePortfolioRecord(**p_dict))
        self.repo.log_timeline_event(
            portfolio_id=portfolio_id,
            event_type="governance_portfolio.submitted",
            actor_id=current_user.user_id,
            summary=f"Portfolio '{saved.name}' submitted for approval.",
            details={"notes": request.submission_notes},
        )
        return saved

    def approve_portfolio(
        self,
        portfolio_id: str,
        request: ApprovePortfolioRequest,
        current_user: AuthenticatedUserContext,
    ) -> GovernanceChangePortfolioRecord:
        """Approves a submitted portfolio.
        
        Strict Separation of Duties:
        Portfolio creator or owner cannot approve their own portfolio.
        """
        port = self.get_portfolio(portfolio_id, current_user)
        if port.status != PortfolioStatus.SUBMITTED:
            raise AppException(
                code=ErrorCode.INVALID_GOVERNANCE_PORTFOLIO_STATE,
                message=f"Portfolio cannot be approved from status '{port.status.value}'. Must be SUBMITTED.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Separation of duties check
        if current_user.user_id in [port.created_by, port.portfolio_owner_id]:
            raise AppException(
                code=ErrorCode.PORTFOLIO_SEPARATION_OF_DUTIES_VIOLATION,
                message="Separation of duties violation: portfolio creator or owner cannot approve their own portfolio.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        now = datetime.now(timezone.utc).isoformat()
        p_dict = port.model_dump()
        p_dict["status"] = PortfolioStatus.APPROVED
        p_dict["approved_by"] = current_user.user_id
        p_dict["approved_at"] = now
        p_dict["approval_comments"] = request.approval_comments
        p_dict["updated_at"] = now

        saved = self.repo.save_portfolio(GovernanceChangePortfolioRecord(**p_dict))
        self.repo.log_timeline_event(
            portfolio_id=portfolio_id,
            event_type="governance_portfolio.approved",
            actor_id=current_user.user_id,
            summary=f"Portfolio '{saved.name}' approved by {current_user.user_id}.",
            details={"comments": request.approval_comments},
        )
        return saved

    def activate_portfolio(
        self, portfolio_id: str, current_user: AuthenticatedUserContext
    ) -> GovernanceChangePortfolioRecord:
        """Activates an approved or on-hold portfolio for operational coordination."""
        port = self.get_portfolio(portfolio_id, current_user)
        if port.status not in [PortfolioStatus.APPROVED, PortfolioStatus.ON_HOLD]:
            raise AppException(
                code=ErrorCode.INVALID_GOVERNANCE_PORTFOLIO_STATE,
                message=f"Portfolio cannot be activated from status '{port.status.value}'. Must be APPROVED or ON_HOLD.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        now = datetime.now(timezone.utc).isoformat()
        p_dict = port.model_dump()
        p_dict["status"] = PortfolioStatus.ACTIVE
        p_dict["updated_at"] = now

        saved = self.repo.save_portfolio(GovernanceChangePortfolioRecord(**p_dict))
        self.repo.log_timeline_event(
            portfolio_id=portfolio_id,
            event_type="governance_portfolio.activated",
            actor_id=current_user.user_id,
            summary=f"Portfolio '{saved.name}' activated.",
        )
        return saved

    def suspend_portfolio(
        self,
        portfolio_id: str,
        request: SuspendPortfolioRequest,
        current_user: AuthenticatedUserContext,
    ) -> GovernanceChangePortfolioRecord:
        """Suspends an active portfolio to ON_HOLD."""
        port = self.get_portfolio(portfolio_id, current_user)
        if port.status != PortfolioStatus.ACTIVE:
            raise AppException(
                code=ErrorCode.INVALID_GOVERNANCE_PORTFOLIO_STATE,
                message=f"Portfolio cannot be suspended from status '{port.status.value}'. Must be ACTIVE.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        now = datetime.now(timezone.utc).isoformat()
        p_dict = port.model_dump()
        p_dict["status"] = PortfolioStatus.ON_HOLD
        p_dict["updated_at"] = now

        saved = self.repo.save_portfolio(GovernanceChangePortfolioRecord(**p_dict))
        self.repo.log_timeline_event(
            portfolio_id=portfolio_id,
            event_type="governance_portfolio.suspended",
            actor_id=current_user.user_id,
            summary=f"Portfolio '{saved.name}' placed ON_HOLD: {request.suspension_reason}",
            details={"reason": request.suspension_reason},
        )
        return saved

    def archive_portfolio(
        self,
        portfolio_id: str,
        request: ArchivePortfolioRequest,
        current_user: AuthenticatedUserContext,
    ) -> GovernanceChangePortfolioRecord:
        """Archives a completed or cancelled portfolio."""
        port = self.get_portfolio(portfolio_id, current_user)
        if port.status not in [PortfolioStatus.COMPLETED, PortfolioStatus.CANCELLED, PortfolioStatus.ON_HOLD]:
            raise AppException(
                code=ErrorCode.INVALID_GOVERNANCE_PORTFOLIO_STATE,
                message=f"Portfolio cannot be archived from status '{port.status.value}'. Must be COMPLETED, CANCELLED, or ON_HOLD.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        now = datetime.now(timezone.utc).isoformat()
        p_dict = port.model_dump()
        p_dict["status"] = PortfolioStatus.ARCHIVED
        p_dict["updated_at"] = now

        saved = self.repo.save_portfolio(GovernanceChangePortfolioRecord(**p_dict))
        self.repo.log_timeline_event(
            portfolio_id=portfolio_id,
            event_type="governance_portfolio.archived",
            actor_id=current_user.user_id,
            summary=f"Portfolio '{saved.name}' archived: {request.archival_justification}",
            details={"justification": request.archival_justification},
        )
        return saved
