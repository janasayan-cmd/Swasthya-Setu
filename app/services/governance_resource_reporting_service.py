"""Phase 86: Resource Dependency Reporting Service.

Compiles executive and operational reports across resource inventory, availability,
fallback readiness, SPOF findings, and gap status.
"""

from datetime import datetime
from typing import Dict, Optional

from app.repositories.governance_resource_dependency_repository import (
    GovernanceResourceDependencyRepository,
    get_governance_resource_dependency_repository,
)
from app.schemas.governance_resource_common import (
    FallbackReadinessOutcome,
    ResourceAvailabilityStatus,
    ResourceGapStatus,
    SPOFSeverity,
)
from app.schemas.governance_resource_reporting import (
    DependencyConcentrationReport,
    FallbackReadinessReport,
    ResourceAvailabilityStatusReport,
    ResourceCoverageSummaryReport,
    ResourceGapsSummaryReport,
)


class GovernanceResourceReportingService:

    def __init__(self, repo: GovernanceResourceDependencyRepository) -> None:
        self.repo = repo

    def coverage_summary_report(self, tenant_id: str) -> ResourceCoverageSummaryReport:
        resources = self.repo.list_resources(tenant_id)
        total = len(resources)

        category_dist: Dict[str, int] = {}
        verified_avail = 0
        unknown_stale = 0
        with_verified_fallback = 0
        without_fallback = 0

        for res in resources:
            cat = res.category.value
            category_dist[cat] = category_dist.get(cat, 0) + 1
            # Availability
            latest = self.repo.get_latest_observation(res.resource_id, tenant_id)
            if latest and latest.observed_status == ResourceAvailabilityStatus.AVAILABLE_VERIFIED:
                verified_avail += 1
            else:
                unknown_stale += 1
            # Fallback
            alts = self.repo.list_alternatives_for_resource(res.resource_id, tenant_id)
            has_verified = any(a.fallback_readiness == FallbackReadinessOutcome.READY_VERIFIED for a in alts)
            if has_verified:
                with_verified_fallback += 1
            else:
                without_fallback += 1

        total_mappings = len(self.repo.list_dependency_mappings(tenant_id))
        open_gaps = len([
            g for g in self.repo.list_resource_gaps(tenant_id)
            if g.status not in (ResourceGapStatus.VERIFIED_RESOLVED, ResourceGapStatus.WAIVED_WITH_JUSTIFICATION)
        ])
        all_analyses = self.repo.list_graph_analyses(tenant_id)
        spof_count = sum(len(a.spof_findings) for a in all_analyses[:1]) if all_analyses else 0
        health_pct = round((verified_avail / total * 100), 2) if total > 0 else 0.0

        return ResourceCoverageSummaryReport(
            tenant_id=tenant_id,
            total_critical_resources=total,
            category_distribution=category_dist,
            resources_with_verified_availability=verified_avail,
            resources_with_unknown_or_stale_availability=unknown_stale,
            resources_with_fallback_verified=with_verified_fallback,
            resources_without_fallback=without_fallback,
            total_dependencies_mapped=total_mappings,
            open_resource_gaps_count=open_gaps,
            spof_findings_count=spof_count,
            overall_coverage_health_pct=health_pct,
        )

    def concentration_report(self, tenant_id: str) -> DependencyConcentrationReport:
        analyses = self.repo.list_graph_analyses(tenant_id)
        if not analyses:
            return DependencyConcentrationReport(
                tenant_id=tenant_id,
                total_spof_findings=0,
                critical_spof_count=0,
                high_spof_count=0,
                shared_resource_count=0,
                capabilities_at_risk_count=0,
            )
        latest = analyses[0]
        spof_findings = latest.spof_findings
        critical_count = sum(1 for f in spof_findings if f.severity == SPOFSeverity.CRITICAL)
        high_count = sum(1 for f in spof_findings if f.severity == SPOFSeverity.HIGH)
        caps_at_risk = set()
        top_spof_res = []
        for f in spof_findings:
            caps_at_risk.update(f.affected_capability_refs)
            top_spof_res.extend(f.affected_resource_refs)

        return DependencyConcentrationReport(
            tenant_id=tenant_id,
            total_spof_findings=len(spof_findings),
            critical_spof_count=critical_count,
            high_spof_count=high_count,
            shared_resource_count=len(latest.shared_dependencies),
            capabilities_at_risk_count=len(caps_at_risk),
            top_spof_resource_ids=list(set(top_spof_res))[:10],
        )

    def fallback_readiness_report(self, tenant_id: str) -> FallbackReadinessReport:
        alts = self.repo.list_alternatives(tenant_id)
        counts = {o.value: 0 for o in FallbackReadinessOutcome}
        for a in alts:
            counts[a.fallback_readiness.value] = counts.get(a.fallback_readiness.value, 0) + 1
        return FallbackReadinessReport(
            tenant_id=tenant_id,
            total_alternatives_documented=len(alts),
            ready_verified_count=counts.get("READY_VERIFIED", 0),
            conditionally_ready_count=counts.get("CONDITIONALLY_READY", 0),
            not_ready_count=counts.get("NOT_READY", 0),
            not_assessed_count=counts.get("NOT_ASSESSED", 0),
            insufficient_evidence_count=counts.get("INSUFFICIENT_EVIDENCE", 0),
            expired_count=counts.get("EXPIRED", 0),
        )

    def availability_status_report(self, tenant_id: str) -> ResourceAvailabilityStatusReport:
        resources = self.repo.list_resources(tenant_id)
        counts = {s.value: 0 for s in ResourceAvailabilityStatus}
        for res in resources:
            latest = self.repo.get_latest_observation(res.resource_id, tenant_id)
            if not latest:
                counts["UNKNOWN"] = counts.get("UNKNOWN", 0) + 1
            else:
                counts[latest.observed_status.value] = counts.get(latest.observed_status.value, 0) + 1
        return ResourceAvailabilityStatusReport(
            tenant_id=tenant_id,
            total_resources=len(resources),
            available_verified_count=counts.get("AVAILABLE_VERIFIED", 0),
            available_unverified_count=counts.get("AVAILABLE_UNVERIFIED", 0),
            degraded_count=counts.get("DEGRADED", 0),
            unavailable_count=counts.get("UNAVAILABLE", 0),
            unknown_count=counts.get("UNKNOWN", 0),
            stale_count=counts.get("STALE", 0),
            conflicting_count=counts.get("CONFLICTING", 0),
        )

    def gaps_summary_report(self, tenant_id: str) -> ResourceGapsSummaryReport:
        gaps = self.repo.list_resource_gaps(tenant_id)
        from app.schemas.governance_resource_common import SPOFSeverity
        open_g = sum(1 for g in gaps if g.status not in (ResourceGapStatus.VERIFIED_RESOLVED, ResourceGapStatus.WAIVED_WITH_JUSTIFICATION))
        escalated = sum(1 for g in gaps if g.status == ResourceGapStatus.ESCALATED)
        resolved = sum(1 for g in gaps if g.status == ResourceGapStatus.VERIFIED_RESOLVED)
        critical = sum(1 for g in gaps if g.severity == SPOFSeverity.CRITICAL)
        high = sum(1 for g in gaps if g.severity == SPOFSeverity.HIGH)
        return ResourceGapsSummaryReport(
            tenant_id=tenant_id,
            total_gaps=len(gaps),
            open_gaps=open_g,
            escalated_gaps=escalated,
            resolved_gaps=resolved,
            critical_gaps=critical,
            high_gaps=high,
        )


_reporting_service: Optional[GovernanceResourceReportingService] = None


def get_governance_resource_reporting_service() -> GovernanceResourceReportingService:
    global _reporting_service
    if _reporting_service is None:
        _reporting_service = GovernanceResourceReportingService(
            get_governance_resource_dependency_repository()
        )
    return _reporting_service
