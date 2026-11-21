"""Phase 76: Benefit Exceptions & Management Review Packages Service.

Coordinates:
- Controlled benefit realization exception handling with explicit authorization
- Packaging benefit performance summaries into reviews for Phase 72 Management Review referral
"""

from datetime import datetime, timezone
import uuid
from typing import List, Optional
from fastapi import status

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_benefit_assurance_repository import (
    GovernanceBenefitAssuranceRepository,
    get_governance_benefit_assurance_repository,
)
from app.schemas.user import AuthenticatedUserContext
from app.schemas.governance_benefit_register import BenefitStatus
from app.schemas.governance_benefit_exceptions_reviews import (
    BenefitExceptionRecord,
    BenefitExceptionStatus,
    BenefitReviewPackageRecord,
    CreateBenefitExceptionRequest,
    CreateBenefitReviewRequest,
    EscalateBenefitExceptionRequest,
    ReferBenefitReviewRequest,
    ReviewBenefitExceptionRequest,
    SubmitBenefitExceptionRequest,
    SubmitBenefitReviewRequest,
)


class GovernanceBenefitExceptionsReviewsService:
    """Service governing benefit realization exceptions and strategic management review packages."""

    def __init__(
        self,
        repository: Optional[GovernanceBenefitAssuranceRepository] = None,
    ) -> None:
        self.repo = repository or get_governance_benefit_assurance_repository()

    # -------------------------------------------------------------------------
    # Exceptions
    # -------------------------------------------------------------------------

    def create_exception(
        self,
        benefit_id: str,
        request: CreateBenefitExceptionRequest,
        current_user: AuthenticatedUserContext,
    ) -> BenefitExceptionRecord:
        user_tenant = current_user.tenant_id or current_user.organization_id or "default_tenant"
        benefit = self.repo.get_benefit(benefit_id)
        if not benefit or benefit.tenant_id != user_tenant:
            raise AppException(
                code=ErrorCode.BENEFIT_NOT_FOUND,
                message=f"Benefit '{benefit_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        now = datetime.now(timezone.utc).isoformat()
        exception_id = f"bex_{uuid.uuid4().hex[:12]}"

        record = BenefitExceptionRecord(
            exception_id=exception_id,
            benefit_id=benefit_id,
            portfolio_id=benefit.portfolio_id,
            tenant_id=user_tenant,
            exception_category=request.exception_category,
            description=request.description,
            supporting_evidence=request.supporting_evidence,
            impact_on_measurement=request.impact_on_measurement,
            requested_duration_days=request.requested_duration_days,
            responsible_owner_id=current_user.user_id,
            review_date=request.review_date,
            status=BenefitExceptionStatus.DRAFT,
            created_by=current_user.user_id,
            created_at=now,
            updated_at=now,
        )
        return self.repo.save_exception(record)

    def list_exceptions(
        self,
        benefit_id: str,
        current_user: AuthenticatedUserContext,
    ) -> List[BenefitExceptionRecord]:
        user_tenant = current_user.tenant_id or current_user.organization_id or "default_tenant"
        benefit = self.repo.get_benefit(benefit_id)
        if not benefit or benefit.tenant_id != user_tenant:
            raise AppException(
                code=ErrorCode.BENEFIT_NOT_FOUND,
                message=f"Benefit '{benefit_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return self.repo.list_exceptions_for_benefit(benefit_id, user_tenant)

    def get_exception(
        self,
        exception_id: str,
        current_user: AuthenticatedUserContext,
    ) -> BenefitExceptionRecord:
        user_tenant = current_user.tenant_id or current_user.organization_id or "default_tenant"
        exc = self.repo.get_exception(exception_id)
        if not exc or exc.tenant_id != user_tenant:
            raise AppException(
                code=ErrorCode.BENEFIT_EXCEPTION_NOT_FOUND,
                message=f"Exception '{exception_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return exc

    def submit_exception(
        self,
        exception_id: str,
        request: SubmitBenefitExceptionRequest,
        current_user: AuthenticatedUserContext,
    ) -> BenefitExceptionRecord:
        user_tenant = current_user.tenant_id or current_user.organization_id or "default_tenant"
        exc = self.get_exception(exception_id, current_user)
        if exc.status != BenefitExceptionStatus.DRAFT:
            raise AppException(
                code=ErrorCode.INVALID_BENEFIT_EXCEPTION_STATE,
                message=f"Exception is in status '{exc.status.value}', only DRAFT exceptions can be submitted.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        now = datetime.now(timezone.utc).isoformat()
        exc.status = BenefitExceptionStatus.SUBMITTED
        exc.updated_at = now
        return self.repo.save_exception(exc)

    def review_exception(
        self,
        exception_id: str,
        request: ReviewBenefitExceptionRequest,
        current_user: AuthenticatedUserContext,
    ) -> BenefitExceptionRecord:
        user_tenant = current_user.tenant_id or current_user.organization_id or "default_tenant"
        exc = self.get_exception(exception_id, current_user)

        # Explicit authorization reference is required for approval
        if request.approved and not request.authorization_reference:
            raise AppException(
                code=ErrorCode.INVALID_BENEFIT_EXCEPTION_STATE,
                message="An authorized approval reference is required to approve a benefit exception.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        now = datetime.now(timezone.utc).isoformat()
        exc.status = BenefitExceptionStatus.APPROVED if request.approved else BenefitExceptionStatus.REJECTED
        exc.authorization_reference = request.authorization_reference
        exc.review_notes = request.review_notes
        exc.reviewed_by = current_user.user_id
        exc.reviewed_at = now
        exc.updated_at = now
        return self.repo.save_exception(exc)

    def escalate_exception(
        self,
        exception_id: str,
        request: EscalateBenefitExceptionRequest,
        current_user: AuthenticatedUserContext,
    ) -> BenefitExceptionRecord:
        user_tenant = current_user.tenant_id or current_user.organization_id or "default_tenant"
        exc = self.get_exception(exception_id, current_user)

        now = datetime.now(timezone.utc).isoformat()
        exc.status = BenefitExceptionStatus.ESCALATED
        exc.escalated_to = request.target_authority
        exc.escalation_reason = request.escalation_reason
        exc.updated_at = now
        return self.repo.save_exception(exc)

    # -------------------------------------------------------------------------
    # Management Review Packages
    # -------------------------------------------------------------------------

    def create_review(
        self,
        portfolio_id: str,
        request: CreateBenefitReviewRequest,
        current_user: AuthenticatedUserContext,
    ) -> BenefitReviewPackageRecord:
        user_tenant = current_user.tenant_id or current_user.organization_id or "default_tenant"
        benefits = self.repo.list_benefits(user_tenant, portfolio_id=portfolio_id)

        snapshot = [
            {"benefit_id": b.benefit_id, "title": b.title, "status": b.status.value, "category": b.category.value}
            for b in benefits
        ]
        delayed = [b.benefit_id for b in benefits if b.status == BenefitStatus.DELAYED]
        unrealized = [b.benefit_id for b in benefits if b.status == BenefitStatus.NOT_REALIZED]

        now = datetime.now(timezone.utc).isoformat()
        review_id = f"brev_{uuid.uuid4().hex[:12]}"

        record = BenefitReviewPackageRecord(
            review_id=review_id,
            portfolio_id=portfolio_id,
            tenant_id=user_tenant,
            review_period=request.review_period,
            title=request.title,
            participants=request.participants,
            benefits_snapshot=snapshot,
            delayed_benefits=delayed,
            unrealized_benefits=unrealized,
            trade_offs_identified=[],
            independent_verification_summaries=[],
            recommendations=request.recommendations,
            management_review_reference=None,
            referral_notes=None,
            status="DRAFT",
            created_by=current_user.user_id,
            created_at=now,
            updated_at=now,
        )
        return self.repo.save_review(record)

    def list_reviews(
        self,
        portfolio_id: str,
        current_user: AuthenticatedUserContext,
    ) -> List[BenefitReviewPackageRecord]:
        user_tenant = current_user.tenant_id or current_user.organization_id or "default_tenant"
        return self.repo.list_reviews_for_portfolio(portfolio_id, user_tenant)

    def get_review(
        self,
        review_id: str,
        current_user: AuthenticatedUserContext,
    ) -> BenefitReviewPackageRecord:
        user_tenant = current_user.tenant_id or current_user.organization_id or "default_tenant"
        rev = self.repo.get_review(review_id)
        if not rev or rev.tenant_id != user_tenant:
            raise AppException(
                code=ErrorCode.BENEFIT_REVIEW_NOT_FOUND,
                message=f"Benefit review package '{review_id}' was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return rev

    def submit_review(
        self,
        review_id: str,
        request: SubmitBenefitReviewRequest,
        current_user: AuthenticatedUserContext,
    ) -> BenefitReviewPackageRecord:
        user_tenant = current_user.tenant_id or current_user.organization_id or "default_tenant"
        rev = self.get_review(review_id, current_user)
        if rev.status != "DRAFT":
            raise AppException(
                code=ErrorCode.INVALID_BENEFIT_REVIEW_STATE,
                message=f"Review package is in status '{rev.status}', only DRAFT packages can be submitted.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        now = datetime.now(timezone.utc).isoformat()
        rev.status = "SUBMITTED"
        rev.updated_at = now
        return self.repo.save_review(rev)

    def refer_to_management(
        self,
        review_id: str,
        request: ReferBenefitReviewRequest,
        current_user: AuthenticatedUserContext,
    ) -> BenefitReviewPackageRecord:
        user_tenant = current_user.tenant_id or current_user.organization_id or "default_tenant"
        rev = self.get_review(review_id, current_user)

        now = datetime.now(timezone.utc).isoformat()
        rev.status = "REFERRED_TO_MANAGEMENT"
        rev.management_review_reference = request.management_review_reference
        rev.referral_notes = request.referral_notes
        rev.updated_at = now
        return self.repo.save_review(rev)
