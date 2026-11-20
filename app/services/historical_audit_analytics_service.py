"""Phase 71: Historical Audit Findings & Trend Analytics Service.

Coordinates:
- Multi-dimensional historical audit finding aggregation
- Strict status filtering (draft/withdrawn findings excluded from confirmed counts)
- Configurable reporting periods (30d, 90d, 6m, 12m, custom)
- Time-series trends for new findings, repeat findings, backlogs, and CAPA recurrence
- Analytical data quality status evaluation and limitation disclosure
"""

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

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
from app.schemas.audit_finding_response import AuditFindingStatus
from app.schemas.audit_governance_report import (
    GovernanceTrendsResponse,
    HistoricalFindingsOverviewResponse,
)
from app.schemas.user import AuthenticatedUserContext


class HistoricalAuditAnalyticsService:
    """Service providing historical finding aggregation and governance time-series analysis."""

    def __init__(
        self,
        audit_repo: Optional[GovernanceAuditRepository] = None,
        intel_repo: Optional[GovernanceAuditIntelligenceRepository] = None,
    ) -> None:
        self.audit_repo = audit_repo or get_governance_audit_repository()
        self.intel_repo = intel_repo or get_governance_audit_intelligence_repository()

    def resolve_date_range(
        self,
        period_type: ReportingPeriodType,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Tuple[datetime, datetime, str]:
        """Resolve start and end dates from reporting period type."""
        now = datetime.now(timezone.utc)
        if period_type == ReportingPeriodType.LAST_30_DAYS:
            return now - timedelta(days=30), now, "LAST_30_DAYS"
        elif period_type == ReportingPeriodType.LAST_90_DAYS:
            return now - timedelta(days=90), now, "LAST_90_DAYS"
        elif period_type == ReportingPeriodType.LAST_6_MONTHS:
            return now - timedelta(days=180), now, "LAST_6_MONTHS"
        elif period_type == ReportingPeriodType.LAST_12_MONTHS:
            return now - timedelta(days=365), now, "LAST_12_MONTHS"
        elif period_type == ReportingPeriodType.CUSTOM:
            s = start_date or (now - timedelta(days=90))
            e = end_date or now
            return s, e, f"CUSTOM_{s.date().isoformat()}_TO_{e.date().isoformat()}"
        return now - timedelta(days=90), now, "LAST_90_DAYS"

    def get_overview(
        self,
        user: AuthenticatedUserContext,
        facility_id: Optional[str] = None,
        period_type: ReportingPeriodType = ReportingPeriodType.LAST_90_DAYS,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> HistoricalFindingsOverviewResponse:
        """Aggregate historical finding metrics ensuring tenant boundary enforcement."""
        if user.role == UserRole.PATIENT:
            raise AppException(
                code=ErrorCode.INSUFFICIENT_PERMISSIONS,
                message="Patient role is not authorized to access audit intelligence.",
                status_code=403,
            )

        range_start, range_end, period_label = self.resolve_date_range(
            period_type, start_date, end_date
        )

        # 1. Fetch tenant audits
        all_audits = self.audit_repo.list_audits(organization_id=user.organization_id)
        if facility_id:
            all_audits = [a for a in all_audits if a.facility_id == facility_id]
        audit_map = {a.audit_id: a for a in all_audits}

        # 2. Fetch all tenant findings
        all_findings = self.audit_repo.list_findings_for_audit()
        tenant_findings = []
        for f in all_findings:
            if f.audit_id in audit_map:
                f_time = f.created_at
                if range_start <= f_time <= range_end:
                    tenant_findings.append(f)

        # 3. Categorize authoritative statuses (draft/withdrawn cannot be confirmed)
        total = len(tenant_findings)
        confirmed = sum(1 for f in tenant_findings if f.is_confirmed and f.status != AuditFindingStatus.WITHDRAWN)
        open_count = sum(1 for f in tenant_findings if not f.is_closed and f.status != AuditFindingStatus.WITHDRAWN)
        disputed = sum(1 for f in tenant_findings if f.is_disputed)
        closed = sum(1 for f in tenant_findings if f.is_closed)
        withdrawn = sum(1 for f in tenant_findings if f.status == AuditFindingStatus.WITHDRAWN)

        by_severity: Dict[str, int] = defaultdict(int)
        by_category: Dict[str, int] = defaultdict(int)
        by_control: Dict[str, int] = defaultdict(int)
        by_process: Dict[str, int] = defaultdict(int)
        by_facility: Dict[str, int] = defaultdict(int)

        for f in tenant_findings:
            # Exclude withdrawn from active analytical aggregations
            if f.status == AuditFindingStatus.WITHDRAWN:
                continue

            by_severity[f.severity.value] += 1
            by_category[f.category.value] += 1

            # Control reference (criterion_id or metadata control)
            ctrl = f.criterion_id or f.metadata.get("control_id", "GENERAL_CONTROL")
            by_control[ctrl] += 1

            # Process reference
            proc = f.metadata.get("governance_process", "CLINICAL_SAFETY_GOVERNANCE")
            by_process[proc] += 1

            # Facility reference from parent audit
            parent_audit = audit_map.get(f.audit_id)
            fac = (parent_audit.facility_id if parent_audit else None) or "ORGANIZATION_WIDE"
            by_facility[fac] += 1

        # 4. Audit coverage
        coverage_by_status: Dict[str, int] = defaultdict(int)
        coverage_by_category: Dict[str, int] = defaultdict(int)
        for a in all_audits:
            coverage_by_status[a.lifecycle_status.value] += 1
            coverage_by_category[a.category.value] += 1

        coverage_summary = {
            "total_audits": len(all_audits),
            "audits_by_status": dict(coverage_by_status),
            "audits_by_category": dict(coverage_by_category),
        }

        # 5. Data quality status
        quality_status = DataQualityStatus.COMPLETE
        limitations = []
        if total == 0:
            quality_status = DataQualityStatus.PARTIALLY_COMPLETE
            limitations.append("No audit findings recorded during the selected reporting period.")
        if any(f.criterion_id is None for f in tenant_findings):
            limitations.append("Some findings lack explicit criterion_id mappings.")

        return HistoricalFindingsOverviewResponse(
            organization_id=user.organization_id,
            facility_id=facility_id,
            reporting_period=period_label,
            total_findings=total,
            confirmed_findings=confirmed,
            open_findings=open_count,
            disputed_findings=disputed,
            closed_findings=closed,
            withdrawn_findings=withdrawn,
            findings_by_severity=dict(by_severity),
            findings_by_category=dict(by_category),
            findings_by_control=dict(by_control),
            findings_by_process=dict(by_process),
            findings_by_facility=dict(by_facility),
            audit_coverage_summary=coverage_summary,
            data_quality_status=quality_status,
            known_data_limitations=limitations,
            generated_at=datetime.now(timezone.utc),
        )

    def get_trends(
        self,
        user: AuthenticatedUserContext,
        facility_id: Optional[str] = None,
        period_type: ReportingPeriodType = ReportingPeriodType.LAST_12_MONTHS,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> GovernanceTrendsResponse:
        """Calculate time-series trends across findings, repeat candidates, and CAPA recurrence."""
        if user.role == UserRole.PATIENT:
            raise AppException(
                code=ErrorCode.INSUFFICIENT_PERMISSIONS,
                message="Patient role cannot access governance trends.",
                status_code=403,
            )

        range_start, range_end, period_label = self.resolve_date_range(
            period_type, start_date, end_date
        )

        all_audits = self.audit_repo.list_audits(organization_id=user.organization_id)
        if facility_id:
            all_audits = [a for a in all_audits if a.facility_id == facility_id]
        audit_map = {a.audit_id: a for a in all_audits}

        all_findings = self.audit_repo.list_findings_for_audit()
        tenant_findings = [
            f for f in all_findings
            if f.audit_id in audit_map and range_start <= f.created_at <= range_end
        ]

        # Monthly buckets: YYYY-MM
        new_findings_by_month: Dict[str, int] = defaultdict(int)
        backlog_by_month: Dict[str, int] = defaultdict(int)

        for f in tenant_findings:
            if f.status == AuditFindingStatus.WITHDRAWN:
                continue
            month_key = f.created_at.strftime("%Y-%m")
            new_findings_by_month[month_key] += 1
            if not f.is_closed:
                backlog_by_month[month_key] += 1

        # Repeat findings by month
        repeat_candidates = self.intel_repo.list_repeat_candidates(
            organization_id=user.organization_id, facility_id=facility_id
        )
        repeats_by_month: Dict[str, int] = defaultdict(int)
        for r in repeat_candidates:
            if range_start <= r.detection_timestamp <= range_end:
                month_key = r.detection_timestamp.strftime("%Y-%m")
                repeats_by_month[month_key] += 1

        # CAPA recurrence by month
        capa_records = self.intel_repo.list_capa_recurrences(
            organization_id=user.organization_id
        )
        capa_by_month: Dict[str, int] = defaultdict(int)
        for c in capa_records:
            if range_start <= c.created_at <= range_end:
                month_key = c.created_at.strftime("%Y-%m")
                capa_by_month[month_key] += 1

        all_months = sorted(
            list(
                set(new_findings_by_month.keys())
                | set(repeats_by_month.keys())
                | set(capa_by_month.keys())
            )
        )
        if not all_months:
            all_months = [datetime.now(timezone.utc).strftime("%Y-%m")]

        new_findings_trend = [{"period": m, "count": new_findings_by_month.get(m, 0)} for m in all_months]
        repeat_trend = [{"period": m, "count": repeats_by_month.get(m, 0)} for m in all_months]
        backlog_trend = [{"period": m, "count": backlog_by_month.get(m, 0)} for m in all_months]
        capa_trend = [{"period": m, "count": capa_by_month.get(m, 0)} for m in all_months]

        return GovernanceTrendsResponse(
            organization_id=user.organization_id,
            facility_id=facility_id,
            reporting_period=period_label,
            new_findings_trend=new_findings_trend,
            repeat_finding_trend=repeat_trend,
            backlog_trend=backlog_trend,
            capa_recurrence_trend=capa_trend,
            generated_at=datetime.now(timezone.utc),
        )


# Global singleton
_global_historical_service = HistoricalAuditAnalyticsService()


def get_historical_audit_analytics_service() -> HistoricalAuditAnalyticsService:
    """Dependency provider for historical audit analytics service."""
    return _global_historical_service
