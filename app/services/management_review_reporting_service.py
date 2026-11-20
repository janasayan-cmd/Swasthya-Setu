"""Phase 71: Management Review & Governance Reporting Service.

Coordinates:
- Generation of structured, reproducible management review preparation reports
- Synthesis of audit coverage, findings distribution, repeat findings, systemic patterns, and CAPA status
- Governance approval workflow for management reports
- Controlled, audited export of analytical reports
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_audit_intelligence_repository import (
    GovernanceAuditIntelligenceRepository,
    get_governance_audit_intelligence_repository,
)
from app.repositories.governance_audit_repository import (
    GovernanceAuditRepository,
    get_governance_audit_repository,
)
from app.schemas.auth import UserRole
from app.schemas.audit_analytics_source import (
    DataQualityStatus,
    ReportingPeriodType,
)
from app.schemas.audit_governance_report import (
    ApproveManagementReportRequest,
    GenerateManagementReportRequest,
    ManagementReportRecord,
)
from app.schemas.user import AuthenticatedUserContext
from app.services.audit_analytics_config_service import (
    AuditAnalyticsConfigService,
    get_audit_analytics_config_service,
)
from app.services.historical_audit_analytics_service import (
    HistoricalAuditAnalyticsService,
    get_historical_audit_analytics_service,
)


class ManagementReviewReportingService:
    """Service compiling reproducible governance review reports for management leadership."""

    def __init__(
        self,
        audit_repo: Optional[GovernanceAuditRepository] = None,
        intel_repo: Optional[GovernanceAuditIntelligenceRepository] = None,
        analytics_service: Optional[HistoricalAuditAnalyticsService] = None,
        config_service: Optional[AuditAnalyticsConfigService] = None,
    ) -> None:
        self.audit_repo = audit_repo or get_governance_audit_repository()
        self.intel_repo = intel_repo or get_governance_audit_intelligence_repository()
        self.analytics_service = analytics_service or get_historical_audit_analytics_service()
        self.config_service = config_service or get_audit_analytics_config_service()

    def generate_report(
        self, user: AuthenticatedUserContext, payload: GenerateManagementReportRequest
    ) -> ManagementReportRecord:
        """Compile a reproducible management review preparation report."""
        if user.role not in {UserRole.ADMIN, UserRole.DOCTOR}:
            raise AppException(
                code=ErrorCode.INSUFFICIENT_PERMISSIONS,
                message="Only administrative or clinical governance roles can generate management reports.",
                status_code=403,
            )

        config = self.config_service.get_or_create_default_config(user.organization_id)

        # 1. Gather historical overview
        overview = self.analytics_service.get_overview(
            user,
            facility_id=payload.facility_id,
            period_type=ReportingPeriodType.CUSTOM if payload.reporting_period_start else ReportingPeriodType.LAST_90_DAYS,
            start_date=payload.reporting_period_start,
            end_date=payload.reporting_period_end,
        )

        # 2. Gather trends
        trends = self.analytics_service.get_trends(
            user,
            facility_id=payload.facility_id,
            period_type=ReportingPeriodType.LAST_12_MONTHS,
        )

        # 3. Gather repeat finding metrics
        repeat_candidates = self.intel_repo.list_repeat_candidates(
            organization_id=user.organization_id, facility_id=payload.facility_id
        )
        repeat_summary = {
            "total_candidates": len(repeat_candidates),
            "confirmed_repeats": sum(1 for r in repeat_candidates if r.review_status.value == "CONFIRMED"),
            "pending_review": sum(1 for r in repeat_candidates if r.review_status.value == "PENDING_REVIEW"),
            "rejected": sum(1 for r in repeat_candidates if r.review_status.value == "REJECTED"),
        }

        # 4. Gather systemic issue metrics
        systemic_candidates = self.intel_repo.list_systemic_candidates(
            organization_id=user.organization_id
        )
        systemic_summary = {
            "total_candidates": len(systemic_candidates),
            "confirmed_systemic_issues": sum(1 for s in systemic_candidates if s.status.value in {"CONFIRMED_PATTERN", "SYSTEMIC_ISSUE_CANDIDATE"}),
            "escalated_issues": sum(1 for s in systemic_candidates if s.status.value == "ESCALATED"),
            "referred_for_risk": sum(1 for s in systemic_candidates if s.status.value == "REFERRED_FOR_RISK_REVIEW"),
        }

        # 5. Gather CAPA recurrence metrics
        capa_records = self.intel_repo.list_capa_recurrences(organization_id=user.organization_id)
        capa_summary = {
            "total_analyzed_actions": len(capa_records),
            "no_recurrence_observed": sum(1 for c in capa_records if c.recurrence_status.value == "NO_RECURRENCE_OBSERVED"),
            "recurrence_confirmed": sum(1 for c in capa_records if c.recurrence_status.value == "RECURRENCE_CONFIRMED"),
            "recurrence_suspected": sum(1 for c in capa_records if c.recurrence_status.value == "RECURRENCE_SUSPECTED"),
        }

        # 6. Formulate recommended review areas
        recommended_areas = []
        if repeat_summary["confirmed_repeats"] > 0:
            recommended_areas.append("Examine root causes for confirmed repeat findings across audits.")
        if systemic_summary["confirmed_systemic_issues"] > 0:
            recommended_areas.append("Review confirmed systemic issue candidates with clinical safety committee.")
        if capa_summary["recurrence_confirmed"] > 0:
            recommended_areas.append("Trigger Phase 55 effectiveness reassessments on recurring CAPA items.")
        if not recommended_areas:
            recommended_areas.append("Maintain routine quarterly clinical safety audit surveillance.")

        now = datetime.now(timezone.utc)
        record = ManagementReportRecord(
            title=payload.title,
            executive_summary=payload.executive_summary,
            reporting_period_start=payload.reporting_period_start or (now - timedelta(days=90)),
            reporting_period_end=payload.reporting_period_end or now,
            audit_coverage_summary=overview.audit_coverage_summary,
            findings_summary={
                "total_findings": overview.total_findings,
                "confirmed_findings": overview.confirmed_findings,
                "open_findings": overview.open_findings,
                "disputed_findings": overview.disputed_findings,
                "closed_findings": overview.closed_findings,
                "by_severity": overview.findings_by_severity,
                "by_category": overview.findings_by_category,
            },
            repeat_findings_summary=repeat_summary,
            systemic_issues_summary=systemic_summary,
            capa_recurrence_summary=capa_summary,
            governance_trends={
                "new_findings_trend": trends.new_findings_trend,
                "repeat_finding_trend": trends.repeat_finding_trend,
                "backlog_trend": trends.backlog_trend,
            },
            recommended_review_areas=recommended_areas,
            calculation_methodology="DETERMINISTIC_AUDIT_INTELLIGENCE_AGGREGATION_V1",
            configuration_version=config.version,
            inclusion_exclusion_rules=[
                "Withdrawn findings excluded from active aggregations.",
                "Tenant and facility boundaries strictly partitioned.",
                "Patient identifiers excluded from analytical output.",
            ],
            data_quality_status=overview.data_quality_status,
            known_data_limitations=overview.known_data_limitations,
            is_approved=False,
            created_by=user.user_id,
            created_at=now,
            organization_id=user.organization_id,
            facility_id=payload.facility_id,
            metadata=payload.metadata or {},
        )
        return self.intel_repo.save_management_report(record)

    def get_report(
        self, user: AuthenticatedUserContext, report_id: str
    ) -> ManagementReportRecord:
        """Retrieve a management report ensuring tenant isolation."""
        rep = self.intel_repo.get_management_report(report_id)
        if not rep:
            raise AppException(
                code=ErrorCode.MANAGEMENT_REPORT_NOT_FOUND,
                message=f"Management report {report_id} not found.",
                status_code=404,
            )
        if rep.organization_id != user.organization_id:
            raise AppException(
                code=ErrorCode.CROSS_TENANT_ACCESS_FORBIDDEN,
                message="Cannot access report across tenant boundaries.",
                status_code=403,
            )
        return rep

    def list_reports(
        self,
        user: AuthenticatedUserContext,
        facility_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ManagementReportRecord]:
        """List management reports within tenant scope."""
        return self.intel_repo.list_management_reports(
            organization_id=user.organization_id,
            facility_id=facility_id,
            limit=limit,
            offset=offset,
        )

    def approve_report(
        self,
        user: AuthenticatedUserContext,
        report_id: str,
        payload: ApproveManagementReportRequest,
    ) -> ManagementReportRecord:
        """Formally approve a management review report."""
        if user.role not in {UserRole.ADMIN, UserRole.DOCTOR}:
            raise AppException(
                code=ErrorCode.INSUFFICIENT_PERMISSIONS,
                message="Only administrative or clinical governance roles can approve management reports.",
                status_code=403,
            )

        rep = self.get_report(user, report_id)
        now = datetime.now(timezone.utc)
        rep.is_approved = True
        rep.approved_by = user.user_id
        rep.approved_at = now
        rep.approval_comments = payload.approval_comments
        return self.intel_repo.save_management_report(rep)

    def export_report(
        self, user: AuthenticatedUserContext, report_id: str
    ) -> Dict[str, Any]:
        """Export structured, verifiable report package."""
        rep = self.get_report(user, report_id)
        return {
            "export_metadata": {
                "report_id": rep.report_id,
                "exported_by": user.user_id,
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "organization_id": rep.organization_id,
                "configuration_version": rep.configuration_version,
                "data_quality_status": rep.data_quality_status.value,
            },
            "report_content": rep.model_dump(mode="json"),
        }


# Global singleton
_global_management_service = ManagementReviewReportingService()


def get_management_review_reporting_service() -> ManagementReviewReportingService:
    """Dependency provider for management review reporting service."""
    return _global_management_service
