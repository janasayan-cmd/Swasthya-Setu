"""Phase 75: Portfolio Issues, Routing & Reviews Service.

Coordinates:
- Cross-initiative issue management and routing to authoritative workflows (Phases 49, 54, 63, 67, 72, 74)
- Portfolio review packages and advisory referrals to Phase 72 Management Review
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
from app.schemas.portfolio_issues_reviews import (
    ApprovePortfolioReviewRequest,
    CreatePortfolioIssueRequest,
    CreatePortfolioReviewRequest,
    EscalatePortfolioIssueRequest,
    PortfolioIssueRecord,
    PortfolioReviewRecord,
    ReferPortfolioReviewRequest,
    RoutePortfolioIssueRequest,
    SubmitPortfolioReviewRequest,
)


class PortfolioIssuesReviewsService:
    """Service governing cross-initiative issues, destination routing, and governance reviews."""

    def __init__(
        self,
        repository: Optional[GovernanceChangePortfolioRepository] = None,
    ) -> None:
        self.repo = repository or get_governance_change_portfolio_repository()

    # -------------------------------------------------------------------------
    # Issues
    # -------------------------------------------------------------------------
    def create_issue(
        self,
        portfolio_id: str,
        request: CreatePortfolioIssueRequest,
        current_user: AuthenticatedUserContext,
    ) -> PortfolioIssueRecord:
        """Logs a cross-initiative issue."""
        user_tenant = current_user.tenant_id or current_user.organization_id or "default_tenant"

        port = self.repo.get_portfolio(portfolio_id)
        if not port or port.tenant_id != user_tenant:
            raise AppException(
                code=ErrorCode.GOVERNANCE_PORTFOLIO_NOT_FOUND,
                message=f"Portfolio '{portfolio_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        now = datetime.now(timezone.utc).isoformat()
        iid = f"pfi_{uuid.uuid4().hex[:12]}"

        record = PortfolioIssueRecord(
            issue_id=iid,
            portfolio_id=portfolio_id,
            tenant_id=user_tenant,
            related_initiative_ids=request.related_initiative_ids,
            title=request.title,
            description=request.description,
            category=request.category,
            severity=request.severity,
            owner_id=request.owner_id,
            status="OPEN",
            routed_destination=None,
            destination_reference=None,
            routing_notes=None,
            escalated_by=None,
            escalated_at=None,
            created_by=current_user.user_id,
            created_at=now,
            updated_at=now,
        )

        saved = self.repo.save_issue(record)
        self.repo.log_timeline_event(
            portfolio_id=portfolio_id,
            event_type="governance_portfolio.issue_registered",
            actor_id=current_user.user_id,
            summary=f"Portfolio issue '{saved.title}' logged (Severity: {saved.severity}).",
            details={"issue_id": saved.issue_id, "category": saved.category},
        )
        return saved

    def get_issue(
        self, issue_id: str, current_user: AuthenticatedUserContext
    ) -> PortfolioIssueRecord:
        """Retrieves a portfolio issue with tenant isolation."""
        user_tenant = current_user.tenant_id or current_user.organization_id or "default_tenant"
        issue = self.repo.get_issue(issue_id)
        if not issue or issue.tenant_id != user_tenant:
            raise AppException(
                code=ErrorCode.PORTFOLIO_ISSUE_NOT_FOUND,
                message=f"Portfolio issue '{issue_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return issue

    def list_issues(
        self, portfolio_id: str, current_user: AuthenticatedUserContext
    ) -> List[PortfolioIssueRecord]:
        """Lists issues for a portfolio."""
        user_tenant = current_user.tenant_id or current_user.organization_id or "default_tenant"
        port = self.repo.get_portfolio(portfolio_id)
        if not port or port.tenant_id != user_tenant:
            raise AppException(
                code=ErrorCode.GOVERNANCE_PORTFOLIO_NOT_FOUND,
                message=f"Portfolio '{portfolio_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return self.repo.list_issues_for_portfolio(portfolio_id, user_tenant)

    def route_issue(
        self,
        issue_id: str,
        request: RoutePortfolioIssueRequest,
        current_user: AuthenticatedUserContext,
    ) -> PortfolioIssueRecord:
        """Routes an issue to an authoritative workflow (e.g. Phase 49, 54, 63, 67, 72, 74)."""
        issue = self.get_issue(issue_id, current_user)

        now = datetime.now(timezone.utc).isoformat()
        i_dict = issue.model_dump()
        i_dict["status"] = "ROUTED"
        i_dict["routed_destination"] = request.routed_destination
        i_dict["destination_reference"] = request.destination_reference
        i_dict["routing_notes"] = request.routing_notes
        i_dict["updated_at"] = now

        saved = self.repo.save_issue(PortfolioIssueRecord(**i_dict))
        self.repo.log_timeline_event(
            portfolio_id=issue.portfolio_id,
            event_type="governance_portfolio.issue_routed",
            actor_id=current_user.user_id,
            summary=f"Issue '{saved.title}' routed to {request.routed_destination} ({request.destination_reference}).",
            details={"destination": request.routed_destination, "ref": request.destination_reference},
        )
        return saved

    def escalate_issue(
        self,
        issue_id: str,
        request: EscalatePortfolioIssueRequest,
        current_user: AuthenticatedUserContext,
    ) -> PortfolioIssueRecord:
        """Escalates a cross-initiative issue to governance leadership."""
        issue = self.get_issue(issue_id, current_user)

        now = datetime.now(timezone.utc).isoformat()
        i_dict = issue.model_dump()
        i_dict["status"] = "ESCALATED"
        i_dict["escalated_by"] = current_user.user_id
        i_dict["escalated_at"] = now
        i_dict["updated_at"] = now

        saved = self.repo.save_issue(PortfolioIssueRecord(**i_dict))
        self.repo.log_timeline_event(
            portfolio_id=issue.portfolio_id,
            event_type="governance_portfolio.issue_escalated",
            actor_id=current_user.user_id,
            summary=f"Issue '{saved.title}' escalated to {request.target_governance_authority}.",
            details={"authority": request.target_governance_authority, "reason": request.escalation_reason},
        )
        return saved

    # -------------------------------------------------------------------------
    # Reviews
    # -------------------------------------------------------------------------
    def create_review(
        self,
        portfolio_id: str,
        request: CreatePortfolioReviewRequest,
        current_user: AuthenticatedUserContext,
    ) -> PortfolioReviewRecord:
        """Creates a portfolio review package snapshot."""
        user_tenant = current_user.tenant_id or current_user.organization_id or "default_tenant"

        port = self.repo.get_portfolio(portfolio_id)
        if not port or port.tenant_id != user_tenant:
            raise AppException(
                code=ErrorCode.GOVERNANCE_PORTFOLIO_NOT_FOUND,
                message=f"Portfolio '{portfolio_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        initiatives = self.repo.list_initiatives_for_portfolio(portfolio_id, user_tenant)
        deps = self.repo.list_dependencies_for_portfolio(portfolio_id, user_tenant)
        conflicts = self.repo.list_conflicts_for_portfolio(portfolio_id, user_tenant)
        issues = self.repo.list_issues_for_portfolio(portfolio_id, user_tenant)

        snapshot = {
            "initiatives_count": len(initiatives),
            "dependencies_count": len(deps),
            "conflicts_count": len(conflicts),
            "issues_count": len(issues),
            "portfolio_status": port.status.value,
        }

        now = datetime.now(timezone.utc).isoformat()
        rid = f"pfr_{uuid.uuid4().hex[:12]}"

        record = PortfolioReviewRecord(
            review_id=rid,
            portfolio_id=portfolio_id,
            tenant_id=user_tenant,
            review_title=request.review_title,
            review_period=request.review_period,
            participants=request.participants,
            summary_snapshot=snapshot,
            recommendations=request.recommendations,
            referred_to_management_review=False,
            management_review_reference=None,
            referral_notes=None,
            status="DRAFT",
            chair_id=current_user.user_id,
            created_at=now,
            updated_at=now,
        )

        saved = self.repo.save_review(record)
        self.repo.log_timeline_event(
            portfolio_id=portfolio_id,
            event_type="governance_portfolio.review_created",
            actor_id=current_user.user_id,
            summary=f"Portfolio review '{saved.review_title}' drafted for period '{saved.review_period}'.",
            details={"review_id": saved.review_id},
        )
        return saved

    def get_review(
        self, review_id: str, current_user: AuthenticatedUserContext
    ) -> PortfolioReviewRecord:
        """Retrieves a portfolio review with tenant isolation."""
        user_tenant = current_user.tenant_id or current_user.organization_id or "default_tenant"
        review = self.repo.get_review(review_id)
        if not review or review.tenant_id != user_tenant:
            raise AppException(
                code=ErrorCode.PORTFOLIO_REVIEW_NOT_FOUND,
                message=f"Portfolio review '{review_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return review

    def list_reviews(
        self, portfolio_id: str, current_user: AuthenticatedUserContext
    ) -> List[PortfolioReviewRecord]:
        """Lists reviews for a portfolio."""
        user_tenant = current_user.tenant_id or current_user.organization_id or "default_tenant"
        port = self.repo.get_portfolio(portfolio_id)
        if not port or port.tenant_id != user_tenant:
            raise AppException(
                code=ErrorCode.GOVERNANCE_PORTFOLIO_NOT_FOUND,
                message=f"Portfolio '{portfolio_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return self.repo.list_reviews_for_portfolio(portfolio_id, user_tenant)

    def submit_review(
        self,
        review_id: str,
        request: SubmitPortfolioReviewRequest,
        current_user: AuthenticatedUserContext,
    ) -> PortfolioReviewRecord:
        """Submits a portfolio review package for sign-off."""
        review = self.get_review(review_id, current_user)
        if review.status != "DRAFT":
            raise AppException(
                code=ErrorCode.INVALID_PORTFOLIO_REVIEW_STATE,
                message=f"Review cannot be submitted from status '{review.status}'. Must be DRAFT.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        now = datetime.now(timezone.utc).isoformat()
        r_dict = review.model_dump()
        r_dict["status"] = "SUBMITTED"
        r_dict["submitted_by"] = current_user.user_id
        r_dict["updated_at"] = now

        saved = self.repo.save_review(PortfolioReviewRecord(**r_dict))
        self.repo.log_timeline_event(
            portfolio_id=review.portfolio_id,
            event_type="governance_portfolio.review_submitted",
            actor_id=current_user.user_id,
            summary=f"Review '{saved.review_title}' submitted.",
            details={"notes": request.submission_notes},
        )
        return saved

    def approve_review(
        self,
        review_id: str,
        request: ApprovePortfolioReviewRequest,
        current_user: AuthenticatedUserContext,
    ) -> PortfolioReviewRecord:
        """Approves a submitted portfolio review package."""
        review = self.get_review(review_id, current_user)
        if review.status != "SUBMITTED":
            raise AppException(
                code=ErrorCode.INVALID_PORTFOLIO_REVIEW_STATE,
                message=f"Review cannot be approved from status '{review.status}'. Must be SUBMITTED.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        now = datetime.now(timezone.utc).isoformat()
        r_dict = review.model_dump()
        r_dict["status"] = "APPROVED"
        r_dict["approved_by"] = current_user.user_id
        r_dict["updated_at"] = now

        saved = self.repo.save_review(PortfolioReviewRecord(**r_dict))
        self.repo.log_timeline_event(
            portfolio_id=review.portfolio_id,
            event_type="governance_portfolio.review_completed",
            actor_id=current_user.user_id,
            summary=f"Review '{saved.review_title}' approved by {current_user.user_id}.",
            details={"comments": request.approval_comments},
        )
        return saved

    def refer_to_management(
        self,
        review_id: str,
        request: ReferPortfolioReviewRequest,
        current_user: AuthenticatedUserContext,
    ) -> PortfolioReviewRecord:
        """Refers portfolio findings and recommendations to Phase 72 Management Review."""
        review = self.get_review(review_id, current_user)

        now = datetime.now(timezone.utc).isoformat()
        r_dict = review.model_dump()
        r_dict["status"] = "REFERRED"
        r_dict["referred_to_management_review"] = True
        r_dict["management_review_reference"] = request.management_review_reference
        r_dict["referral_notes"] = request.referral_notes
        r_dict["updated_at"] = now

        saved = self.repo.save_review(PortfolioReviewRecord(**r_dict))
        self.repo.log_timeline_event(
            portfolio_id=review.portfolio_id,
            event_type="governance_portfolio.management_referral_created",
            actor_id=current_user.user_id,
            summary=f"Review '{saved.review_title}' referred to Management Review {request.management_review_reference}.",
            details={"ref": request.management_review_reference, "notes": request.referral_notes},
        )
        return saved
