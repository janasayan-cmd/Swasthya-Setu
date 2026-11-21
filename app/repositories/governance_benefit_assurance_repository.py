"""Phase 76: Governance Benefit Assurance In-Memory Thread-Safe Repository.

Provides persistence and query capabilities for:
- Benefit registrations, baselines, and targets
- Performance indicators and validated measurements
- Benefit realization assessments and portfolio aggregates
- Attribution analysis, unintended consequences, and trade-offs
- Longitudinal sustainability records and independent verifications
- Benefit exceptions and management review packages
"""

from datetime import datetime, timezone
import threading
from typing import Dict, List, Optional

from app.schemas.governance_benefit_register import GovernanceBenefitRecord
from app.schemas.governance_benefit_baseline_target import (
    BenefitBaselineRecord,
    BenefitTargetRecord,
)
from app.schemas.governance_benefit_indicator_measurement import (
    BenefitIndicatorRecord,
    BenefitMeasurementRecord,
)
from app.schemas.governance_benefit_assessment import (
    BenefitRealizationAssessmentRecord,
    PortfolioBenefitAssessmentRecord,
)
from app.schemas.governance_benefit_attribution_consequences import (
    BenefitAttributionRecord,
    UnintendedConsequenceRecord,
)
from app.schemas.governance_benefit_sustainability_verification import (
    BenefitSustainabilityRecord,
    BenefitVerificationRecord,
)
from app.schemas.governance_benefit_exceptions_reviews import (
    BenefitExceptionRecord,
    BenefitReviewPackageRecord,
)


class GovernanceBenefitAssuranceRepository:
    """Thread-safe in-memory repository for Phase 76 benefit assurance data."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._benefits: Dict[str, GovernanceBenefitRecord] = {}
        self._baselines: Dict[str, BenefitBaselineRecord] = {}
        self._targets: Dict[str, BenefitTargetRecord] = {}
        self._indicators: Dict[str, BenefitIndicatorRecord] = {}
        self._measurements: Dict[str, BenefitMeasurementRecord] = {}
        self._assessments: Dict[str, BenefitRealizationAssessmentRecord] = {}
        self._portfolio_assessments: Dict[str, PortfolioBenefitAssessmentRecord] = {}
        self._attributions: Dict[str, BenefitAttributionRecord] = {}
        self._consequences: Dict[str, UnintendedConsequenceRecord] = {}
        self._sustainabilities: Dict[str, BenefitSustainabilityRecord] = {}
        self._verifications: Dict[str, BenefitVerificationRecord] = {}
        self._exceptions: Dict[str, BenefitExceptionRecord] = {}
        self._reviews: Dict[str, BenefitReviewPackageRecord] = {}

    def clear(self) -> None:
        """Clears all stored records (useful for test isolation)."""
        with self._lock:
            self._benefits.clear()
            self._baselines.clear()
            self._targets.clear()
            self._indicators.clear()
            self._measurements.clear()
            self._assessments.clear()
            self._portfolio_assessments.clear()
            self._attributions.clear()
            self._consequences.clear()
            self._sustainabilities.clear()
            self._verifications.clear()
            self._exceptions.clear()
            self._reviews.clear()

    # -------------------------------------------------------------------------
    # Benefits
    # -------------------------------------------------------------------------

    def save_benefit(self, benefit: GovernanceBenefitRecord) -> GovernanceBenefitRecord:
        with self._lock:
            self._benefits[benefit.benefit_id] = benefit
            return benefit

    def get_benefit(self, benefit_id: str) -> Optional[GovernanceBenefitRecord]:
        with self._lock:
            return self._benefits.get(benefit_id)

    def list_benefits(
        self,
        tenant_id: str,
        portfolio_id: Optional[str] = None,
        implementation_id: Optional[str] = None,
        category: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[GovernanceBenefitRecord]:
        with self._lock:
            records = [b for b in self._benefits.values() if b.tenant_id == tenant_id]
            if portfolio_id:
                records = [b for b in records if b.portfolio_id == portfolio_id]
            if implementation_id:
                records = [b for b in records if b.implementation_id == implementation_id]
            if category:
                records = [b for b in records if b.category.value == category]
            records.sort(key=lambda x: x.created_at, reverse=True)
            return records[skip : skip + limit]

    # -------------------------------------------------------------------------
    # Baselines
    # -------------------------------------------------------------------------

    def save_baseline(self, baseline: BenefitBaselineRecord) -> BenefitBaselineRecord:
        with self._lock:
            self._baselines[baseline.baseline_id] = baseline
            return baseline

    def get_baseline(self, baseline_id: str) -> Optional[BenefitBaselineRecord]:
        with self._lock:
            return self._baselines.get(baseline_id)

    def list_baselines_for_benefit(self, benefit_id: str, tenant_id: str) -> List[BenefitBaselineRecord]:
        with self._lock:
            records = [
                b for b in self._baselines.values()
                if b.benefit_id == benefit_id and b.tenant_id == tenant_id
            ]
            records.sort(key=lambda x: x.version, reverse=True)
            return records

    # -------------------------------------------------------------------------
    # Targets
    # -------------------------------------------------------------------------

    def save_target(self, target: BenefitTargetRecord) -> BenefitTargetRecord:
        with self._lock:
            self._targets[target.target_id] = target
            return target

    def get_target(self, target_id: str) -> Optional[BenefitTargetRecord]:
        with self._lock:
            return self._targets.get(target_id)

    def list_targets_for_benefit(self, benefit_id: str, tenant_id: str) -> List[BenefitTargetRecord]:
        with self._lock:
            records = [
                t for t in self._targets.values()
                if t.benefit_id == benefit_id and t.tenant_id == tenant_id
            ]
            records.sort(key=lambda x: x.version, reverse=True)
            return records

    # -------------------------------------------------------------------------
    # Indicators
    # -------------------------------------------------------------------------

    def save_indicator(self, indicator: BenefitIndicatorRecord) -> BenefitIndicatorRecord:
        with self._lock:
            self._indicators[indicator.indicator_id] = indicator
            return indicator

    def get_indicator(self, indicator_id: str) -> Optional[BenefitIndicatorRecord]:
        with self._lock:
            return self._indicators.get(indicator_id)

    def list_indicators_for_benefit(self, benefit_id: str, tenant_id: str) -> List[BenefitIndicatorRecord]:
        with self._lock:
            return [
                i for i in self._indicators.values()
                if i.benefit_id == benefit_id and i.tenant_id == tenant_id
            ]

    # -------------------------------------------------------------------------
    # Measurements
    # -------------------------------------------------------------------------

    def save_measurement(self, measurement: BenefitMeasurementRecord) -> BenefitMeasurementRecord:
        with self._lock:
            self._measurements[measurement.measurement_id] = measurement
            return measurement

    def get_measurement(self, measurement_id: str) -> Optional[BenefitMeasurementRecord]:
        with self._lock:
            return self._measurements.get(measurement_id)

    def list_measurements_for_benefit(self, benefit_id: str, tenant_id: str) -> List[BenefitMeasurementRecord]:
        with self._lock:
            records = [
                m for m in self._measurements.values()
                if m.benefit_id == benefit_id and m.tenant_id == tenant_id
            ]
            records.sort(key=lambda x: x.collection_timestamp, reverse=True)
            return records

    # -------------------------------------------------------------------------
    # Realization Assessments
    # -------------------------------------------------------------------------

    def save_assessment(self, assessment: BenefitRealizationAssessmentRecord) -> BenefitRealizationAssessmentRecord:
        with self._lock:
            self._assessments[assessment.assessment_id] = assessment
            return assessment

    def get_assessment(self, assessment_id: str) -> Optional[BenefitRealizationAssessmentRecord]:
        with self._lock:
            return self._assessments.get(assessment_id)

    def list_assessments_for_benefit(self, benefit_id: str, tenant_id: str) -> List[BenefitRealizationAssessmentRecord]:
        with self._lock:
            records = [
                a for a in self._assessments.values()
                if a.benefit_id == benefit_id and a.tenant_id == tenant_id
            ]
            records.sort(key=lambda x: x.created_at, reverse=True)
            return records

    def save_portfolio_assessment(self, assessment: PortfolioBenefitAssessmentRecord) -> PortfolioBenefitAssessmentRecord:
        with self._lock:
            self._portfolio_assessments[assessment.assessment_id] = assessment
            return assessment

    def list_portfolio_assessments(self, portfolio_id: str, tenant_id: str) -> List[PortfolioBenefitAssessmentRecord]:
        with self._lock:
            records = [
                a for a in self._portfolio_assessments.values()
                if a.portfolio_id == portfolio_id and a.tenant_id == tenant_id
            ]
            records.sort(key=lambda x: x.created_at, reverse=True)
            return records

    # -------------------------------------------------------------------------
    # Attribution
    # -------------------------------------------------------------------------

    def save_attribution(self, attribution: BenefitAttributionRecord) -> BenefitAttributionRecord:
        with self._lock:
            self._attributions[attribution.attribution_id] = attribution
            return attribution

    def get_attribution(self, attribution_id: str) -> Optional[BenefitAttributionRecord]:
        with self._lock:
            return self._attributions.get(attribution_id)

    def list_attributions_for_benefit(self, benefit_id: str, tenant_id: str) -> List[BenefitAttributionRecord]:
        with self._lock:
            records = [
                a for a in self._attributions.values()
                if a.benefit_id == benefit_id and a.tenant_id == tenant_id
            ]
            records.sort(key=lambda x: x.created_at, reverse=True)
            return records

    # -------------------------------------------------------------------------
    # Unintended Consequences
    # -------------------------------------------------------------------------

    def save_consequence(self, consequence: UnintendedConsequenceRecord) -> UnintendedConsequenceRecord:
        with self._lock:
            self._consequences[consequence.consequence_id] = consequence
            return consequence

    def get_consequence(self, consequence_id: str) -> Optional[UnintendedConsequenceRecord]:
        with self._lock:
            return self._consequences.get(consequence_id)

    def list_consequences_for_benefit(self, benefit_id: str, tenant_id: str) -> List[UnintendedConsequenceRecord]:
        with self._lock:
            records = [
                c for c in self._consequences.values()
                if c.benefit_id == benefit_id and c.tenant_id == tenant_id
            ]
            records.sort(key=lambda x: x.created_at, reverse=True)
            return records

    # -------------------------------------------------------------------------
    # Sustainability
    # -------------------------------------------------------------------------

    def save_sustainability(self, sustainability: BenefitSustainabilityRecord) -> BenefitSustainabilityRecord:
        with self._lock:
            self._sustainabilities[sustainability.sustainability_id] = sustainability
            return sustainability

    def list_sustainabilities_for_benefit(self, benefit_id: str, tenant_id: str) -> List[BenefitSustainabilityRecord]:
        with self._lock:
            records = [
                s for s in self._sustainabilities.values()
                if s.benefit_id == benefit_id and s.tenant_id == tenant_id
            ]
            records.sort(key=lambda x: x.created_at, reverse=True)
            return records

    # -------------------------------------------------------------------------
    # Verification
    # -------------------------------------------------------------------------

    def save_verification(self, verification: BenefitVerificationRecord) -> BenefitVerificationRecord:
        with self._lock:
            self._verifications[verification.verification_id] = verification
            return verification

    def get_verification(self, verification_id: str) -> Optional[BenefitVerificationRecord]:
        with self._lock:
            return self._verifications.get(verification_id)

    def list_verifications_for_benefit(self, benefit_id: str, tenant_id: str) -> List[BenefitVerificationRecord]:
        with self._lock:
            records = [
                v for v in self._verifications.values()
                if v.benefit_id == benefit_id and v.tenant_id == tenant_id
            ]
            records.sort(key=lambda x: x.created_at, reverse=True)
            return records

    def list_all_verifications(self, tenant_id: str) -> List[BenefitVerificationRecord]:
        with self._lock:
            return [v for v in self._verifications.values() if v.tenant_id == tenant_id]

    # -------------------------------------------------------------------------
    # Exceptions
    # -------------------------------------------------------------------------

    def save_exception(self, exc: BenefitExceptionRecord) -> BenefitExceptionRecord:
        with self._lock:
            self._exceptions[exc.exception_id] = exc
            return exc

    def get_exception(self, exception_id: str) -> Optional[BenefitExceptionRecord]:
        with self._lock:
            return self._exceptions.get(exception_id)

    def list_exceptions_for_benefit(self, benefit_id: str, tenant_id: str) -> List[BenefitExceptionRecord]:
        with self._lock:
            records = [
                e for e in self._exceptions.values()
                if e.benefit_id == benefit_id and e.tenant_id == tenant_id
            ]
            records.sort(key=lambda x: x.created_at, reverse=True)
            return records

    def list_all_exceptions(self, tenant_id: str) -> List[BenefitExceptionRecord]:
        with self._lock:
            return [e for e in self._exceptions.values() if e.tenant_id == tenant_id]

    # -------------------------------------------------------------------------
    # Reviews
    # -------------------------------------------------------------------------

    def save_review(self, review: BenefitReviewPackageRecord) -> BenefitReviewPackageRecord:
        with self._lock:
            self._reviews[review.review_id] = review
            return review

    def get_review(self, review_id: str) -> Optional[BenefitReviewPackageRecord]:
        with self._lock:
            return self._reviews.get(review_id)

    def list_reviews_for_portfolio(self, portfolio_id: str, tenant_id: str) -> List[BenefitReviewPackageRecord]:
        with self._lock:
            records = [
                r for r in self._reviews.values()
                if r.portfolio_id == portfolio_id and r.tenant_id == tenant_id
            ]
            records.sort(key=lambda x: x.created_at, reverse=True)
            return records


# Global Singleton
_repository_instance: Optional[GovernanceBenefitAssuranceRepository] = None
_repo_lock = threading.Lock()


def get_governance_benefit_assurance_repository() -> GovernanceBenefitAssuranceRepository:
    """Returns the singleton instance of GovernanceBenefitAssuranceRepository."""
    global _repository_instance
    if _repository_instance is None:
        with _repo_lock:
            if _repository_instance is None:
                _repository_instance = GovernanceBenefitAssuranceRepository()
    return _repository_instance
