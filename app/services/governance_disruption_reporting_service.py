"""Phase 87: Disruption Impact Reporting Service.

Aggregates disruption impact intelligence into executive summaries, cascading dependency
reports, compound disruption metrics, fallback comparisons, and overall coverage statistics.
"""

from datetime import datetime
from typing import Optional

from app.repositories.governance_disruption_impact_repository import (
    GovernanceDisruptionImpactRepository,
    get_governance_disruption_impact_repository,
)
from app.repositories.governance_resource_dependency_repository import (
    GovernanceResourceDependencyRepository,
    get_governance_resource_dependency_repository,
)
from app.schemas.governance_disruption_common import (
    AssessmentReviewStatus,
    FollowUpStatus,
    ImpactSeverity,
    ScenarioReviewStatus,
)
from app.schemas.governance_disruption_reporting import (
    CascadingDependenciesReport,
    CompoundDisruptionsReport,
    DisruptionImpactSummaryReport,
    FallbackComparisonReport,
    ImpactAssessmentCoverageReport,
)
from app.schemas.governance_resource_common import DependencyMappingStatus


class GovernanceDisruptionReportingService:

    def __init__(
        self,
        repo: GovernanceDisruptionImpactRepository,
        resource_repo: Optional[GovernanceResourceDependencyRepository] = None,
    ) -> None:
        self.repo = repo
        self.resource_repo = resource_repo or get_governance_resource_dependency_repository()

    def impact_summary_report(self, tenant_id: str) -> DisruptionImpactSummaryReport:
        scenarios = self.repo.list_scenarios(tenant_id)
        assessments = self.repo.list_assessments(tenant_id)
        follow_ups = self.repo.list_follow_ups(tenant_id)

        approved_scenarios = [s for s in scenarios if s.review_status == ScenarioReviewStatus.APPROVED]
        critical_assessments = [a for a in assessments if a.overall_impact_severity == ImpactSeverity.CRITICAL]
        high_assessments = [a for a in assessments if a.overall_impact_severity == ImpactSeverity.HIGH]
        mtpd_exceeded = [a for a in assessments if a.mtpd_exceeded]
        open_follow_ups = [fu for fu in follow_ups if fu.status in (FollowUpStatus.PROPOSED, FollowUpStatus.SUBMITTED)]

        return DisruptionImpactSummaryReport(
            tenant_id=tenant_id,
            generated_at=datetime.utcnow(),
            total_scenarios_registered=len(scenarios),
            approved_scenarios_count=len(approved_scenarios),
            total_assessments_completed=len(assessments),
            critical_impact_assessments_count=len(critical_assessments),
            high_impact_assessments_count=len(high_assessments),
            assessments_exceeding_mtpd=len(mtpd_exceeded),
            open_remediation_follow_ups=len(open_follow_ups),
        )

    def cascading_dependencies_report(self, tenant_id: str) -> CascadingDependenciesReport:
        analyses = self.repo.list_cascading_analyses(tenant_id)
        total_paths = sum(a.total_paths_identified for a in analyses)
        max_depth = max([a.max_depth_traversed for a in analyses], default=0)

        # Collect unique shared upstream bottleneck resources
        bottlenecks = set()
        common_provider_count = 0
        for a in analyses:
            for item in a.shared_upstream_resources:
                if isinstance(item, dict) and "resource_id" in item:
                    bottlenecks.add(str(item["resource_id"]))
            common_provider_count += len(a.common_provider_risks)

        return CascadingDependenciesReport(
            tenant_id=tenant_id,
            generated_at=datetime.utcnow(),
            total_cascading_analyses=len(analyses),
            total_propagation_paths_identified=total_paths,
            max_propagation_depth_recorded=max_depth,
            shared_upstream_bottleneck_resources=sorted(list(bottlenecks)),
            common_provider_dependency_count=common_provider_count,
        )

    def compound_disruptions_report(self, tenant_id: str) -> CompoundDisruptionsReport:
        compounds = self.repo.list_compound_scenarios(tenant_id)
        evaluated = [c for c in compounds if c.evaluated_at is not None]
        non_indep = [c for c in evaluated if len(c.non_independent_fallbacks) > 0]
        crit_compounds = [c for c in evaluated if c.compound_severity == ImpactSeverity.CRITICAL]

        return CompoundDisruptionsReport(
            tenant_id=tenant_id,
            generated_at=datetime.utcnow(),
            total_compound_scenarios=len(compounds),
            compound_scenarios_evaluated=len(evaluated),
            scenarios_with_non_independent_fallbacks=len(non_indep),
            scenarios_with_personnel_overlap=0,
            critical_compound_findings_count=len(crit_compounds),
        )

    def fallback_comparison_report(self, tenant_id: str) -> FallbackComparisonReport:
        comparisons = self.repo.list_fallback_comparisons(tenant_id)
        verified_count = sum(
            1 for c in comparisons
            if any(item.readiness_tier == "READY_VERIFIED" for item in c.comparison_items)
        )
        lacking_count = sum(
            1 for c in comparisons
            if not any(item.readiness_tier in ("READY_VERIFIED", "CONDITIONALLY_READY") for item in c.comparison_items)
        )
        partial_count = len(comparisons) - verified_count - lacking_count
        stale_count = sum(
            1 for c in comparisons
            if any(item.readiness_tier == "STALE_EVIDENCE" for item in c.comparison_items)
        )

        return FallbackComparisonReport(
            tenant_id=tenant_id,
            generated_at=datetime.utcnow(),
            total_resources_compared=len(comparisons),
            resources_with_verified_mitigation=verified_count,
            resources_with_partial_mitigation=max(0, partial_count),
            resources_lacking_effective_fallback=max(0, lacking_count),
            stale_evidence_warnings_count=stale_count,
        )

    def impact_assessment_coverage_report(self, tenant_id: str) -> ImpactAssessmentCoverageReport:
        mappings = self.resource_repo.list_dependency_mappings(
            tenant_id, status=DependencyMappingStatus.APPROVED
        )
        all_caps = {m.governance_capability_ref for m in mappings}
        assessments = self.repo.list_assessments(tenant_id)
        assessed_caps = set()
        for a in assessments:
            assessed_caps.update(a.affected_capability_refs)

        total_caps = len(all_caps) if all_caps else 1
        coverage_pct = round((len(assessed_caps.intersection(all_caps)) / total_caps) * 100.0, 2)
        reassessments = sum(1 for a in assessments if a.review_status == AssessmentReviewStatus.REASSESSMENT_REQUIRED)
        overdue_reviews = sum(1 for a in assessments if a.review_status == AssessmentReviewStatus.EVIDENCE_REVIEW_PENDING)

        return ImpactAssessmentCoverageReport(
            tenant_id=tenant_id,
            generated_at=datetime.utcnow(),
            total_critical_capabilities=len(all_caps),
            capabilities_with_active_assessment=len(assessed_caps.intersection(all_caps)),
            capabilities_coverage_pct=coverage_pct,
            assessments_requiring_reassessment=reassessments,
            overdue_human_reviews_count=overdue_reviews,
        )


_disruption_reporting_service: Optional[GovernanceDisruptionReportingService] = None


def get_governance_disruption_reporting_service() -> GovernanceDisruptionReportingService:
    global _disruption_reporting_service
    if _disruption_reporting_service is None:
        _disruption_reporting_service = GovernanceDisruptionReportingService(
            get_governance_disruption_impact_repository()
        )
    return _disruption_reporting_service
