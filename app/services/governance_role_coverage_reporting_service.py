"""Phase 85: Role-Coverage and Succession Reporting Service.

Compiles executive role-coverage summaries, single-person dependency analyses,
backup readiness deficiency audits, and expiring delegation schedules.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional

from app.repositories.governance_role_coverage_repository import (
    GovernanceRoleCoverageRepository,
    get_governance_role_coverage_repository,
)
from app.schemas.governance_role_coverage_common import (
    BackupVerificationStatus,
    CoverageArrangementStatus,
    CoverageGapStatus,
    CriticalityTier,
    DependencyRiskRating,
    HandoverStatus,
)
from app.schemas.governance_role_coverage_reporting import (
    BackupReadinessDeficienciesReport,
    ExpiringCoverageScheduleItem,
    ExpiringCoverageScheduleReport,
    RoleCoverageSummaryReport,
    SinglePersonDependencyReport,
)
from app.schemas.governance_role_dependency_analysis import (
    RunDependencyAnalysisRequest,
)
from app.services.governance_role_dependency_analysis_service import (
    get_governance_role_dependency_analysis_service,
)


class GovernanceRoleCoverageReportingService:
    """Service for generating executive and operational role-coverage reports."""

    def __init__(self, repository: GovernanceRoleCoverageRepository) -> None:
        self.repository = repository
        self.dependency_service = get_governance_role_dependency_analysis_service()

    def generate_summary_report(self, tenant_id: str) -> RoleCoverageSummaryReport:
        responsibilities = self.repository.list_responsibilities(tenant_id)
        total_resp = len(responsibilities)

        tier_counts: Dict[str, int] = {
            CriticalityTier.TIER_1_ESSENTIAL.value: 0,
            CriticalityTier.TIER_2_CRITICAL.value: 0,
            CriticalityTier.TIER_3_IMPORTANT.value: 0,
            CriticalityTier.TIER_4_SUPPORTING.value: 0,
        }
        with_backup = 0
        without_backup = 0

        for r in responsibilities:
            tier_counts[r.criticality_tier.value] = (
                tier_counts.get(r.criticality_tier.value, 0) + 1
            )
            coverage = self.repository.get_coverage_by_responsibility(
                r.responsibility_id, tenant_id
            )
            has_verified = False
            if coverage and coverage.status in (CoverageArrangementStatus.ACTIVE, CoverageArrangementStatus.APPROVED):
                for b in coverage.designated_backups:
                    if b.capability_verified and b.authorization_verified and b.is_available:
                        has_verified = True
                        break
            if has_verified:
                with_backup += 1
            else:
                without_backup += 1

        health_pct = 0.0
        if total_resp > 0:
            health_pct = round((with_backup / total_resp) * 100, 2)

        active_arrangements = len(
            self.repository.list_coverages(tenant_id, CoverageArrangementStatus.ACTIVE)
        )
        open_gaps = len(
            [
                g
                for g in self.repository.list_coverage_gaps(tenant_id)
                if g.status not in (CoverageGapStatus.VERIFIED_RESOLVED, CoverageGapStatus.WAIVED_WITH_JUSTIFICATION)
            ]
        )
        active_handovers = len(
            [
                h
                for h in self.repository.list_handovers(tenant_id)
                if h.status in (HandoverStatus.INITIATED, HandoverStatus.PENDING_INCOMING_ACKNOWLEDGEMENT, HandoverStatus.ACKNOWLEDGED)
            ]
        )

        return RoleCoverageSummaryReport(
            tenant_id=tenant_id,
            total_critical_responsibilities=total_resp,
            tier_distribution=tier_counts,
            responsibilities_with_verified_backup=with_backup,
            responsibilities_without_verified_backup=without_backup,
            overall_coverage_health_percentage=health_pct,
            active_coverage_arrangements_count=active_arrangements,
            open_coverage_gaps_count=open_gaps,
            active_handovers_count=active_handovers,
        )

    def generate_dependency_report(self, tenant_id: str) -> SinglePersonDependencyReport:
        single_person_deps, concentrations = self.dependency_service.run_dependency_analysis(
            tenant_id, RunDependencyAnalysisRequest(include_tier2=True, bottleneck_threshold=3)
        )

        critical_deps = sum(
            1 for d in single_person_deps if d.risk_rating in (DependencyRiskRating.CRITICAL, DependencyRiskRating.HIGH)
        )
        high_risk_bottlenecks = sum(
            1 for c in concentrations if c.risk_rating in (DependencyRiskRating.CRITICAL, DependencyRiskRating.HIGH)
        )

        return SinglePersonDependencyReport(
            tenant_id=tenant_id,
            single_person_dependencies=single_person_deps,
            key_person_bottlenecks=concentrations,
            critical_dependencies_count=critical_deps,
            high_risk_bottlenecks_count=high_risk_bottlenecks,
        )

    def generate_backup_deficiencies_report(
        self, tenant_id: str
    ) -> BackupReadinessDeficienciesReport:
        verifications = self.repository.list_backup_verifications(tenant_id)
        deficient = [v for v in verifications if v.status == BackupVerificationStatus.DEFICIENT]

        unverified_cap = sum(1 for v in deficient if not v.capability_verified)
        missing_auth = sum(1 for v in deficient if not v.authorization_verified)

        return BackupReadinessDeficienciesReport(
            tenant_id=tenant_id,
            deficient_verifications=deficient,
            total_deficient_count=len(deficient),
            unverified_capability_count=unverified_cap,
            missing_authorization_count=missing_auth,
        )

    def generate_expiring_schedule_report(
        self, tenant_id: str, days_threshold: int = 60
    ) -> ExpiringCoverageScheduleReport:
        now = datetime.utcnow()
        cutoff = now + timedelta(days=days_threshold)
        expiring_items: List[ExpiringCoverageScheduleItem] = []

        # Check verifications for expiring authorizations
        for v in self.repository.list_backup_verifications(tenant_id):
            if v.authorization_expires_at and v.authorization_expires_at <= cutoff:
                days_left = max(0, (v.authorization_expires_at - now).days)
                expiring_items.append(
                    ExpiringCoverageScheduleItem(
                        coverage_id=v.coverage_id,
                        responsibility_id=v.responsibility_id,
                        backup_user_id=v.backup_user_id,
                        item_type="DELEGATION_AUTHORIZATION",
                        reference_id=v.authorization_ref,
                        expires_at=v.authorization_expires_at,
                        days_remaining=days_left,
                    )
                )

        # Check coverage arrangements for effective_end_date
        for c in self.repository.list_coverages(tenant_id):
            if c.effective_end_date and c.effective_end_date <= cutoff:
                days_left = max(0, (c.effective_end_date - now).days)
                for b in c.designated_backups:
                    expiring_items.append(
                        ExpiringCoverageScheduleItem(
                            coverage_id=c.coverage_id,
                            responsibility_id=c.responsibility_id,
                            backup_user_id=b.backup_user_id,
                            item_type="COVERAGE_ARRANGEMENT_WINDOW",
                            reference_id=c.coverage_id,
                            expires_at=c.effective_end_date,
                            days_remaining=days_left,
                        )
                    )

        return ExpiringCoverageScheduleReport(
            tenant_id=tenant_id,
            expiring_items=expiring_items,
            total_expiring_soon_count=len(expiring_items),
        )


_coverage_reporting_service: Optional[GovernanceRoleCoverageReportingService] = None


def get_governance_role_coverage_reporting_service() -> GovernanceRoleCoverageReportingService:
    global _coverage_reporting_service
    if _coverage_reporting_service is None:
        _coverage_reporting_service = GovernanceRoleCoverageReportingService(
            get_governance_role_coverage_repository()
        )
    return _coverage_reporting_service
