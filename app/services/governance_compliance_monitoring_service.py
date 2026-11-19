"""Phase 69: Master Governance Compliance Monitoring & Reporting Service.

Aggregates:
- High-level tenant compliance summaries
- Categorized compliance gap reports
- Control mapping conformance and coverage
- Diagnostic evidence completeness and freshness metrics
"""

from datetime import datetime, timezone
from typing import Dict, Optional

from app.repositories.governance_compliance_repository import (
    GovernanceComplianceRepository,
    get_governance_compliance_repository,
)
from app.schemas.compliance_assessment import ComplianceStatus
from app.schemas.compliance_evidence import EvidenceValidityStatus
from app.schemas.compliance_finding import CompliancePriority
from app.schemas.compliance_package_report import (
    ComplianceGapReport,
    ComplianceSummaryReport,
    ControlConformanceReport,
    CorrectiveActionStatus,
    EvidenceCompletenessReport,
)
from app.schemas.user import AuthenticatedUserContext


class GovernanceComplianceMonitoringService:
    """Master service providing compliance observability and aggregated reporting."""

    def __init__(self, repository: Optional[GovernanceComplianceRepository] = None) -> None:
        self.repository = repository or get_governance_compliance_repository()

    def generate_summary_report(
        self, user: AuthenticatedUserContext, facility_id: Optional[str] = None
    ) -> ComplianceSummaryReport:
        """Generate high-level compliance summary report for tenant."""
        frameworks = self.repository.list_frameworks(user.organization_id, facility_id)
        requirements = self.repository.list_requirements(user.organization_id)

        compliant = 0
        with_lims = 0
        partially = 0
        non_compliant = 0
        insufficient = 0

        for req in requirements:
            latest = self.repository.get_latest_assessment_for_requirement(req.requirement_id)
            if latest:
                if latest.status == ComplianceStatus.COMPLIANT:
                    compliant += 1
                elif latest.status == ComplianceStatus.COMPLIANT_WITH_LIMITATIONS:
                    with_lims += 1
                elif latest.status == ComplianceStatus.PARTIALLY_COMPLIANT:
                    partially += 1
                elif latest.status in {ComplianceStatus.NON_COMPLIANT, ComplianceStatus.CONTROL_NOT_IMPLEMENTED}:
                    non_compliant += 1
                elif latest.status in {ComplianceStatus.EVIDENCE_INSUFFICIENT, ComplianceStatus.EVIDENCE_UNAVAILABLE}:
                    insufficient += 1

        all_findings = self.repository.list_findings()
        active_findings = sum(1 for f in all_findings if not f.is_resolved)
        critical_findings = sum(
            1 for f in all_findings if not f.is_resolved and f.priority in {CompliancePriority.CRITICAL, CompliancePriority.HIGH}
        )

        all_cas = self.repository._corrective_actions.values()
        open_cas = sum(
            1 for ca in all_cas if ca.status not in {CorrectiveActionStatus.COMPLETED, CorrectiveActionStatus.VERIFIED_EFFECTIVE}
        )

        return ComplianceSummaryReport(
            organization_id=user.organization_id,
            facility_id=facility_id,
            total_frameworks=len(frameworks),
            total_requirements=len(requirements),
            compliant_count=compliant,
            compliant_with_limitations_count=with_lims,
            partially_compliant_count=partially,
            non_compliant_count=non_compliant,
            evidence_insufficient_count=insufficient,
            active_findings_count=active_findings,
            critical_findings_count=critical_findings,
            open_corrective_actions_count=open_cas,
            generated_at=datetime.now(timezone.utc),
        )

    def generate_gap_report(
        self, user: AuthenticatedUserContext, facility_id: Optional[str] = None
    ) -> ComplianceGapReport:
        """Generate categorized summary of identified compliance gaps."""
        findings = [f for f in self.repository.list_findings() if not f.is_resolved]
        crit = sum(1 for f in findings if f.priority == CompliancePriority.CRITICAL)
        high = sum(1 for f in findings if f.priority == CompliancePriority.HIGH)
        other = len(findings) - crit - high

        cat_counts: Dict[str, int] = {}
        for f in findings:
            cat_name = f.gap_category.value
            cat_counts[cat_name] = cat_counts.get(cat_name, 0) + 1

        return ComplianceGapReport(
            organization_id=user.organization_id,
            facility_id=facility_id,
            total_gaps=len(findings),
            critical_gaps=crit,
            high_gaps=high,
            medium_or_lower_gaps=other,
            gaps_by_category=cat_counts,
            generated_at=datetime.now(timezone.utc),
        )

    def generate_control_conformance_report(
        self, user: AuthenticatedUserContext, facility_id: Optional[str] = None
    ) -> ControlConformanceReport:
        """Generate report on control mapping coverage across requirements."""
        requirements = self.repository.list_requirements(user.organization_id)
        total_reqs = len(requirements)
        mapped = 0
        for req in requirements:
            mappings = self.repository.list_control_mappings(req.requirement_id)
            if len(mappings) > 0:
                mapped += 1

        unmapped = total_reqs - mapped
        coverage = (mapped / total_reqs * 100.0) if total_reqs > 0 else 0.0

        return ControlConformanceReport(
            organization_id=user.organization_id,
            facility_id=facility_id,
            total_requirements=total_reqs,
            mapped_requirements=mapped,
            unmapped_requirements=unmapped,
            mapping_coverage_percentage=round(coverage, 2),
            generated_at=datetime.now(timezone.utc),
        )

    def generate_evidence_completeness_report(
        self, user: AuthenticatedUserContext, facility_id: Optional[str] = None
    ) -> EvidenceCompletenessReport:
        """Generate diagnostic report on evidence item freshness and integrity."""
        evidence_items = self.repository.list_evidence()
        valid_count = sum(1 for ev in evidence_items if ev.validity_status == EvidenceValidityStatus.VALID and ev.is_accessible)
        stale_count = sum(1 for ev in evidence_items if ev.validity_status == EvidenceValidityStatus.STALE)
        invalid_count = sum(1 for ev in evidence_items if ev.validity_status == EvidenceValidityStatus.INVALIDATED)
        superseded_count = sum(1 for ev in evidence_items if ev.validity_status == EvidenceValidityStatus.SUPERSEDED)
        inaccessible_count = sum(1 for ev in evidence_items if not ev.is_accessible)

        return EvidenceCompletenessReport(
            organization_id=user.organization_id,
            facility_id=facility_id,
            total_evidence_items=len(evidence_items),
            valid_items=valid_count,
            stale_items=stale_count,
            invalidated_items=invalid_count,
            superseded_items=superseded_count,
            inaccessible_items=inaccessible_count,
            generated_at=datetime.now(timezone.utc),
        )


# Global singleton
_global_monitoring_service = GovernanceComplianceMonitoringService()


def get_governance_compliance_monitoring_service() -> GovernanceComplianceMonitoringService:
    """Dependency provider for governance compliance monitoring service."""
    return _global_monitoring_service
