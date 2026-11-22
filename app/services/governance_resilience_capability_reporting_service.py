"""Phase 84: Capability Analytics and Management Reporting Service.

Compiles 6 executive and operational capability reports: coverage, role readiness,
team readiness, gaps, development progress, and organizational readiness posture.
"""

from datetime import datetime
from typing import Dict, List, Optional

from app.repositories.governance_resilience_capability_repository import (
    GovernanceResilienceCapabilityRepository,
    get_governance_resilience_capability_repository,
)
from app.schemas.governance_resilience_capability_assessment import (
    AssessmentLifecycleState,
    AssessmentOutcome,
)
from app.schemas.governance_resilience_capability_gap import CapabilityGapStatus
from app.schemas.governance_resilience_capability_development import ProposalStatus
from app.schemas.governance_resilience_operational_readiness import (
    OperationalReadinessOutcome,
)
from app.schemas.governance_resilience_team_readiness import TeamReadinessOutcome
from app.schemas.governance_resilience_capability_reporting import (
    CapabilityCoverageReport,
    CapabilityGapsReport,
    DevelopmentProgressReport,
    OrganizationalReadinessReport,
    RoleReadinessReport,
    TeamReadinessReport,
)


class GovernanceResilienceCapabilityReportingService:
    """Service compiling executive capability analytics and readiness reports."""

    def __init__(
        self,
        repository: Optional[GovernanceResilienceCapabilityRepository] = None,
    ) -> None:
        self.repository = repository or get_governance_resilience_capability_repository()

    def get_capability_coverage_report(self, tenant_id: str) -> CapabilityCoverageReport:
        frameworks = self.repository.list_frameworks(tenant_id=tenant_id)
        by_dom: Dict[str, int] = {}
        by_prof: Dict[str, int] = {}
        total_caps = 0

        for f in frameworks:
            for c in f.capabilities:
                total_caps += 1
                by_dom[c.domain.value] = by_dom.get(c.domain.value, 0) + 1
                by_prof[c.required_proficiency.value] = by_prof.get(c.required_proficiency.value, 0) + 1

        coverage_rate = 100.0 if total_caps > 0 else 0.0

        return CapabilityCoverageReport(
            total_framework_capabilities=total_caps,
            by_domain=by_dom,
            by_proficiency_level=by_prof,
            coverage_rate_percent=coverage_rate,
        )

    def get_role_readiness_report(self, tenant_id: str) -> RoleReadinessReport:
        reqs = self.repository.list_role_requirements(tenant_id=tenant_id)
        assessments = self.repository.list_assessments(tenant_id=tenant_id)

        verified = [a for a in assessments if a.lifecycle_state == AssessmentLifecycleState.VERIFIED]
        assessed_roles = len(set(a.applicable_role for a in assessments))
        verified_roles = len(set(a.applicable_role for a in verified))
        total_reqs = len(reqs)
        missing = max(0, total_reqs - verified_roles)
        rate = (verified_roles / total_reqs * 100.0) if total_reqs > 0 else 0.0

        return RoleReadinessReport(
            total_role_requirements=total_reqs,
            assessed_roles=assessed_roles,
            verified_ready_roles=verified_roles,
            missing_coverage_roles=missing,
            role_coverage_percent=round(rate, 2),
        )

    def get_team_readiness_report(self, tenant_id: str) -> TeamReadinessReport:
        teams = self.repository.list_team_readiness(tenant_id=tenant_id)
        verified = [t for t in teams if t.readiness_outcome == TeamReadinessOutcome.VERIFIED_READY]
        vacant = [t for t in teams if t.readiness_outcome == TeamReadinessOutcome.CRITICAL_ROLES_VACANT]
        backup_def = [t for t in teams if t.readiness_outcome == TeamReadinessOutcome.BACKUP_COVERAGE_DEFICIT]

        vacant_roles = set()
        for t in teams:
            vacant_roles.update(t.critical_vacancies)

        return TeamReadinessReport(
            total_teams_assessed=len(teams),
            verified_ready_teams=len(verified),
            teams_with_critical_vacancies=len(vacant),
            teams_with_backup_deficits=len(backup_def),
            critical_vacant_roles=sorted(list(vacant_roles)),
        )

    def get_capability_gaps_report(self, tenant_id: str) -> CapabilityGapsReport:
        gaps = self.repository.list_capability_gaps(tenant_id=tenant_id)
        val = [g for g in gaps if g.status == CapabilityGapStatus.VALIDATED]
        capa = [g for g in gaps if g.status == CapabilityGapStatus.CAPA_REFERRED]
        res = [g for g in gaps if g.status in [CapabilityGapStatus.RESOLVED, CapabilityGapStatus.CLOSED]]

        by_cat: Dict[str, int] = {}
        by_sev: Dict[str, int] = {}

        for g in gaps:
            by_cat[g.category.value] = by_cat.get(g.category.value, 0) + 1
            by_sev[g.severity.value] = by_sev.get(g.severity.value, 0) + 1

        return CapabilityGapsReport(
            total_gaps_detected=len(gaps),
            validated_gaps=len(val),
            capa_referred_gaps=len(capa),
            resolved_gaps=len(res),
            by_category=by_cat,
            by_severity=by_sev,
        )

    def get_development_progress_report(self, tenant_id: str) -> DevelopmentProgressReport:
        proposals = self.repository.list_development_proposals(tenant_id=tenant_id)
        appr = [p for p in proposals if p.status == ProposalStatus.APPROVED]
        prog = [p for p in proposals if p.status == ProposalStatus.IN_PROGRESS]
        comp = [p for p in proposals if p.status == ProposalStatus.COMPLETED]

        by_type: Dict[str, int] = {}
        for p in proposals:
            by_type[p.proposed_intervention.value] = by_type.get(p.proposed_intervention.value, 0) + 1

        return DevelopmentProgressReport(
            total_proposals=len(proposals),
            approved_proposals=len(appr),
            in_progress_proposals=len(prog),
            completed_proposals=len(comp),
            by_intervention_type=by_type,
        )

    def get_organizational_readiness_report(self, tenant_id: str) -> OrganizationalReadinessReport:
        readiness_list = self.repository.list_operational_readiness(tenant_id=tenant_id)
        verified = [r for r in readiness_list if r.outcome == OperationalReadinessOutcome.VERIFIED_READY]
        unresolved_ex = sum(len(r.unresolved_exceptions) for r in readiness_list)
        reassessments = self.repository.list_reassessments(tenant_id=tenant_id)

        score = (len(verified) / len(readiness_list) * 100.0) if readiness_list else 100.0
        posture = "ADVANCED" if score >= 80.0 else ("DEVELOPING" if score >= 50.0 else "INITIAL")

        return OrganizationalReadinessReport(
            overall_readiness_score=round(score, 1),
            readiness_posture=posture,
            verified_ready_scopes_count=len(verified),
            unresolved_exceptions_count=unresolved_ex,
            active_reassessments_count=len(reassessments),
        )


_reporting_service = GovernanceResilienceCapabilityReportingService()


def get_governance_resilience_capability_reporting_service() -> GovernanceResilienceCapabilityReportingService:
    return _reporting_service
