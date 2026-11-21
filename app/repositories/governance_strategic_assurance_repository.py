"""Phase 77: Governance Strategic Assurance In-Memory Thread-Safe Repository.

Provides persistence and query capabilities for:
- Clinical safety governance maturity frameworks, dimensions, and criteria
- Organizational maturity assessments, dimension results, and evaluations
- Assurance evidence records, provenance, and verification states
- Systemic governance capability gaps and confirmations
- Governance improvement plans, milestones, and authoritative handoffs
- Independent assessment reviews and conflict-of-interest checks
- Strategic management review packages for Phase 72 referral
"""

from datetime import datetime, timezone
import threading
from typing import Dict, List, Optional

from app.schemas.governance_maturity_framework import (
    FrameworkStatus,
    GovernanceMaturityFrameworkRecord,
)
from app.schemas.governance_maturity_assessment import (
    AssessmentStatus,
    GovernanceMaturityAssessmentRecord,
)
from app.schemas.governance_assurance_evidence import (
    GovernanceAssuranceEvidenceRecord,
)
from app.schemas.governance_systemic_gaps import (
    GapStatus,
    SystemicGovernanceGapRecord,
)
from app.schemas.governance_improvement_plan import (
    GovernanceImprovementPlanRecord,
    ImprovementPlanStatus,
)
from app.schemas.governance_assurance_review import (
    AssuranceReviewRecord,
    AssuranceReviewStatus,
    StrategicManagementReviewPackageRecord,
)


class GovernanceStrategicAssuranceRepository:
    """Thread-safe in-memory repository for Phase 77 strategic assurance data."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._frameworks: Dict[str, GovernanceMaturityFrameworkRecord] = {}
        self._assessments: Dict[str, GovernanceMaturityAssessmentRecord] = {}
        self._evidence: Dict[str, GovernanceAssuranceEvidenceRecord] = {}
        self._gaps: Dict[str, SystemicGovernanceGapRecord] = {}
        self._improvement_plans: Dict[str, GovernanceImprovementPlanRecord] = {}
        self._reviews: Dict[str, AssuranceReviewRecord] = {}
        self._packages: Dict[str, StrategicManagementReviewPackageRecord] = {}

    def clear(self) -> None:
        """Clears all stored records (useful for test isolation)."""
        with self._lock:
            self._frameworks.clear()
            self._assessments.clear()
            self._evidence.clear()
            self._gaps.clear()
            self._improvement_plans.clear()
            self._reviews.clear()
            self._packages.clear()

    # -------------------------------------------------------------------------
    # Frameworks
    # -------------------------------------------------------------------------

    def save_framework(
        self, framework: GovernanceMaturityFrameworkRecord
    ) -> GovernanceMaturityFrameworkRecord:
        with self._lock:
            self._frameworks[framework.framework_id] = framework
            return framework

    def get_framework(self, framework_id: str) -> Optional[GovernanceMaturityFrameworkRecord]:
        with self._lock:
            return self._frameworks.get(framework_id)

    def get_framework_by_code_and_version(
        self, tenant_id: str, framework_code: str, version: str
    ) -> Optional[GovernanceMaturityFrameworkRecord]:
        with self._lock:
            for fw in self._frameworks.values():
                if (
                    fw.tenant_id == tenant_id
                    and fw.framework_code == framework_code
                    and fw.version == version
                ):
                    return fw
            return None

    def get_active_framework(
        self, tenant_id: str
    ) -> Optional[GovernanceMaturityFrameworkRecord]:
        with self._lock:
            for fw in self._frameworks.values():
                if fw.tenant_id == tenant_id and fw.status == FrameworkStatus.ACTIVE:
                    return fw
            return None

    def list_frameworks(
        self,
        tenant_id: str,
        status: Optional[FrameworkStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[GovernanceMaturityFrameworkRecord]:
        with self._lock:
            results = [
                fw
                for fw in self._frameworks.values()
                if fw.tenant_id == tenant_id
                and (status is None or fw.status == status)
            ]
            results.sort(key=lambda x: x.created_at, reverse=True)
            return results[skip : skip + limit]

    # -------------------------------------------------------------------------
    # Assessments
    # -------------------------------------------------------------------------

    def save_assessment(
        self, assessment: GovernanceMaturityAssessmentRecord
    ) -> GovernanceMaturityAssessmentRecord:
        with self._lock:
            self._assessments[assessment.assessment_id] = assessment
            return assessment

    def get_assessment(self, assessment_id: str) -> Optional[GovernanceMaturityAssessmentRecord]:
        with self._lock:
            return self._assessments.get(assessment_id)

    def list_assessments(
        self,
        tenant_id: str,
        scope_id: Optional[str] = None,
        scope_type: Optional[str] = None,
        status: Optional[AssessmentStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[GovernanceMaturityAssessmentRecord]:
        with self._lock:
            results = [
                a
                for a in self._assessments.values()
                if a.tenant_id == tenant_id
                and (scope_id is None or a.scope.scope_id == scope_id)
                and (scope_type is None or a.scope.scope_type.value == scope_type)
                and (status is None or a.status == status)
            ]
            results.sort(key=lambda x: x.assessment_date, reverse=True)
            return results[skip : skip + limit]

    # -------------------------------------------------------------------------
    # Evidence
    # -------------------------------------------------------------------------

    def save_evidence(
        self, evidence: GovernanceAssuranceEvidenceRecord
    ) -> GovernanceAssuranceEvidenceRecord:
        with self._lock:
            self._evidence[evidence.evidence_id] = evidence
            return evidence

    def get_evidence(self, evidence_id: str) -> Optional[GovernanceAssuranceEvidenceRecord]:
        with self._lock:
            return self._evidence.get(evidence_id)

    def list_evidence_for_assessment(
        self,
        tenant_id: str,
        assessment_id: str,
        dimension: Optional[str] = None,
        criterion_id: Optional[str] = None,
    ) -> List[GovernanceAssuranceEvidenceRecord]:
        with self._lock:
            results = [
                ev
                for ev in self._evidence.values()
                if ev.tenant_id == tenant_id
                and ev.assessment_id == assessment_id
                and (dimension is None or ev.dimension.value == dimension)
                and (criterion_id is None or ev.criterion_id == criterion_id)
            ]
            results.sort(key=lambda x: x.collected_at, reverse=True)
            return results

    # -------------------------------------------------------------------------
    # Systemic Gaps
    # -------------------------------------------------------------------------

    def save_gap(self, gap: SystemicGovernanceGapRecord) -> SystemicGovernanceGapRecord:
        with self._lock:
            self._gaps[gap.gap_id] = gap
            return gap

    def get_gap(self, gap_id: str) -> Optional[SystemicGovernanceGapRecord]:
        with self._lock:
            return self._gaps.get(gap_id)

    def list_gaps(
        self,
        tenant_id: str,
        status: Optional[GapStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[SystemicGovernanceGapRecord]:
        with self._lock:
            results = [
                g
                for g in self._gaps.values()
                if g.tenant_id == tenant_id
                and (status is None or g.status == status)
            ]
            results.sort(key=lambda x: x.identified_at, reverse=True)
            return results[skip : skip + limit]

    # -------------------------------------------------------------------------
    # Improvement Plans
    # -------------------------------------------------------------------------

    def save_plan(
        self, plan: GovernanceImprovementPlanRecord
    ) -> GovernanceImprovementPlanRecord:
        with self._lock:
            self._improvement_plans[plan.plan_id] = plan
            return plan

    def get_plan(self, plan_id: str) -> Optional[GovernanceImprovementPlanRecord]:
        with self._lock:
            return self._improvement_plans.get(plan_id)

    def list_plans(
        self,
        tenant_id: str,
        status: Optional[ImprovementPlanStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[GovernanceImprovementPlanRecord]:
        with self._lock:
            results = [
                p
                for p in self._improvement_plans.values()
                if p.tenant_id == tenant_id
                and (status is None or p.status == status)
            ]
            results.sort(key=lambda x: x.created_at, reverse=True)
            return results[skip : skip + limit]

    # -------------------------------------------------------------------------
    # Reviews
    # -------------------------------------------------------------------------

    def save_review(self, review: AssuranceReviewRecord) -> AssuranceReviewRecord:
        with self._lock:
            self._reviews[review.review_id] = review
            return review

    def get_review(self, review_id: str) -> Optional[AssuranceReviewRecord]:
        with self._lock:
            return self._reviews.get(review_id)

    def get_review_by_assessment(
        self, assessment_id: str
    ) -> Optional[AssuranceReviewRecord]:
        with self._lock:
            for rev in self._reviews.values():
                if rev.assessment_id == assessment_id:
                    return rev
            return None

    def list_reviews(
        self,
        tenant_id: str,
        reviewer_id: Optional[str] = None,
        status: Optional[AssuranceReviewStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[AssuranceReviewRecord]:
        with self._lock:
            results = [
                r
                for r in self._reviews.values()
                if r.tenant_id == tenant_id
                and (reviewer_id is None or r.assigned_reviewer_id == reviewer_id)
                and (status is None or r.status == status)
            ]
            results.sort(key=lambda x: x.assigned_at, reverse=True)
            return results[skip : skip + limit]

    # -------------------------------------------------------------------------
    # Management Review Packages
    # -------------------------------------------------------------------------

    def save_package(
        self, package: StrategicManagementReviewPackageRecord
    ) -> StrategicManagementReviewPackageRecord:
        with self._lock:
            self._packages[package.package_id] = package
            return package

    def get_package(
        self, package_id: str
    ) -> Optional[StrategicManagementReviewPackageRecord]:
        with self._lock:
            return self._packages.get(package_id)

    def list_packages(
        self,
        tenant_id: str,
        skip: int = 0,
        limit: int = 50,
    ) -> List[StrategicManagementReviewPackageRecord]:
        with self._lock:
            results = [p for p in self._packages.values() if p.tenant_id == tenant_id]
            results.sort(key=lambda x: x.created_at, reverse=True)
            return results[skip : skip + limit]


_strategic_assurance_repo = GovernanceStrategicAssuranceRepository()


def get_strategic_assurance_repository() -> GovernanceStrategicAssuranceRepository:
    """Returns the singleton instance of the Strategic Assurance repository."""
    return _strategic_assurance_repo
