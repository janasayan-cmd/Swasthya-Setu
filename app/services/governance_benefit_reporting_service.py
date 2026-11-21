"""Phase 76: Benefit Reporting & Executive Analytics Service.

Coordinates:
- Consolidated benefit realization reports
- Delayed and unrealized benefit inventories
- Longitudinal sustainability reports
- Portfolio benefit performance analytics
- Independent verification status tracking
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.repositories.governance_benefit_assurance_repository import (
    GovernanceBenefitAssuranceRepository,
    get_governance_benefit_assurance_repository,
)
from app.repositories.governance_change_portfolio_repository import (
    get_governance_change_portfolio_repository,
)
from app.schemas.user import AuthenticatedUserContext
from app.schemas.governance_benefit_register import BenefitStatus
from app.schemas.governance_benefit_sustainability_verification import (
    SustainabilityTrend,
    VerificationStatus,
)
from app.schemas.governance_benefit_reporting import (
    BenefitRealizationReportResponse,
    BenefitSustainabilityReportResponse,
    BenefitVerificationReportResponse,
    DelayedBenefitsReportResponse,
    PortfolioBenefitPerformanceReportResponse,
    UnrealizedBenefitsReportResponse,
)


class GovernanceBenefitReportingService:
    """Service generating executive and operational reports for Phase 76 benefit assurance."""

    def __init__(
        self,
        repository: Optional[GovernanceBenefitAssuranceRepository] = None,
    ) -> None:
        self.repo = repository or get_governance_benefit_assurance_repository()
        self.phase75_repo = get_governance_change_portfolio_repository()

    def get_benefit_realization_report(
        self,
        current_user: AuthenticatedUserContext,
    ) -> BenefitRealizationReportResponse:
        user_tenant = current_user.tenant_id or current_user.organization_id or "default_tenant"
        now = datetime.now(timezone.utc).isoformat()
        benefits = self.repo.list_benefits(tenant_id=user_tenant, limit=1000)

        realized = sum(1 for b in benefits if b.status == BenefitStatus.REALIZED)
        partially = sum(1 for b in benefits if b.status == BenefitStatus.PARTIALLY_REALIZED)
        delayed = sum(1 for b in benefits if b.status == BenefitStatus.DELAYED)
        unrealized = sum(1 for b in benefits if b.status == BenefitStatus.NOT_REALIZED)

        by_cat: Dict[str, int] = {}
        for b in benefits:
            by_cat[b.category.value] = by_cat.get(b.category.value, 0) + 1

        return BenefitRealizationReportResponse(
            tenant_id=user_tenant,
            report_generated_at=now,
            total_benefits=len(benefits),
            realized_count=realized,
            partially_realized_count=partially,
            delayed_count=delayed,
            not_realized_count=unrealized,
            insufficient_evidence_count=0,
            benefits_by_category=by_cat,
        )

    def get_delayed_benefits_report(
        self,
        current_user: AuthenticatedUserContext,
    ) -> DelayedBenefitsReportResponse:
        user_tenant = current_user.tenant_id or current_user.organization_id or "default_tenant"
        now_dt = datetime.now(timezone.utc)
        now = now_dt.isoformat()
        benefits = self.repo.list_benefits(tenant_id=user_tenant, limit=1000)

        delayed = []
        for b in benefits:
            if b.status == BenefitStatus.DELAYED:
                delayed.append({"benefit_id": b.benefit_id, "title": b.title, "expected_realization_date": b.expected_realization_date})
            elif b.status in [BenefitStatus.REGISTERED, BenefitStatus.ACTIVE_MONITORING]:
                try:
                    if datetime.fromisoformat(b.expected_realization_date) < now_dt:
                        delayed.append({"benefit_id": b.benefit_id, "title": b.title, "expected_realization_date": b.expected_realization_date})
                except Exception:
                    pass

        return DelayedBenefitsReportResponse(
            tenant_id=user_tenant,
            report_generated_at=now,
            delayed_benefits_count=len(delayed),
            delayed_benefits=delayed,
        )

    def get_unrealized_benefits_report(
        self,
        current_user: AuthenticatedUserContext,
    ) -> UnrealizedBenefitsReportResponse:
        user_tenant = current_user.tenant_id or current_user.organization_id or "default_tenant"
        now = datetime.now(timezone.utc).isoformat()
        benefits = self.repo.list_benefits(tenant_id=user_tenant, limit=1000)

        unrealized = [
            {"benefit_id": b.benefit_id, "title": b.title, "category": b.category.value, "status": b.status.value}
            for b in benefits
            if b.status == BenefitStatus.NOT_REALIZED
        ]

        return UnrealizedBenefitsReportResponse(
            tenant_id=user_tenant,
            report_generated_at=now,
            unrealized_benefits_count=len(unrealized),
            unrealized_benefits=unrealized,
        )

    def get_benefit_sustainability_report(
        self,
        current_user: AuthenticatedUserContext,
    ) -> BenefitSustainabilityReportResponse:
        user_tenant = current_user.tenant_id or current_user.organization_id or "default_tenant"
        now = datetime.now(timezone.utc).isoformat()
        benefits = self.repo.list_benefits(tenant_id=user_tenant, limit=1000)

        sustained = 0
        declining = 0
        reversed_cnt = 0
        trends = []

        for b in benefits:
            s_list = self.repo.list_sustainabilities_for_benefit(b.benefit_id, user_tenant)
            if s_list:
                latest = s_list[0]
                if latest.trend == SustainabilityTrend.SUSTAINED:
                    sustained += 1
                elif latest.trend == SustainabilityTrend.DECLINING:
                    declining += 1
                elif latest.trend == SustainabilityTrend.REVERSED:
                    reversed_cnt += 1
                trends.append({
                    "benefit_id": b.benefit_id,
                    "trend": latest.trend.value,
                    "stability_score": latest.performance_stability_score,
                })

        return BenefitSustainabilityReportResponse(
            tenant_id=user_tenant,
            report_generated_at=now,
            total_monitored_benefits=len(trends),
            sustained_count=sustained,
            declining_count=declining,
            reversed_count=reversed_cnt,
            stale_data_count=0,
            sustainability_trends=trends,
        )

    def get_portfolio_benefit_performance_report(
        self,
        current_user: AuthenticatedUserContext,
    ) -> PortfolioBenefitPerformanceReportResponse:
        user_tenant = current_user.tenant_id or current_user.organization_id or "default_tenant"
        now = datetime.now(timezone.utc).isoformat()

        portfolios = self.phase75_repo.list_portfolios(tenant_id=user_tenant, limit=100)
        metrics = []

        for p in portfolios:
            b_list = self.repo.list_benefits(tenant_id=user_tenant, portfolio_id=p.portfolio_id)
            metrics.append({
                "portfolio_id": p.portfolio_id,
                "portfolio_name": p.name,
                "total_benefits": len(b_list),
                "realized": sum(1 for b in b_list if b.status == BenefitStatus.REALIZED),
            })

        return PortfolioBenefitPerformanceReportResponse(
            tenant_id=user_tenant,
            report_generated_at=now,
            total_portfolios_evaluated=len(portfolios),
            portfolio_benefit_metrics=metrics,
        )

    def get_benefit_verification_report(
        self,
        current_user: AuthenticatedUserContext,
    ) -> BenefitVerificationReportResponse:
        user_tenant = current_user.tenant_id or current_user.organization_id or "default_tenant"
        now = datetime.now(timezone.utc).isoformat()

        verifications = self.repo.list_all_verifications(user_tenant)
        verified = sum(1 for v in verifications if v.status == VerificationStatus.VERIFIED)
        verified_lim = sum(1 for v in verifications if v.status == VerificationStatus.VERIFIED_WITH_LIMITATIONS)
        not_verified = sum(1 for v in verifications if v.status == VerificationStatus.NOT_VERIFIED)
        pending = sum(1 for v in verifications if v.status in [VerificationStatus.REQUESTED, VerificationStatus.ASSIGNED, VerificationStatus.IN_REVIEW])

        items = [
            {"verification_id": v.verification_id, "benefit_id": v.benefit_id, "status": v.status.value}
            for v in verifications
        ]

        return BenefitVerificationReportResponse(
            tenant_id=user_tenant,
            report_generated_at=now,
            total_verifications=len(verifications),
            verified_count=verified,
            verified_with_limitations_count=verified_lim,
            not_verified_count=not_verified,
            pending_verification_count=pending,
            verifications=items,
        )
