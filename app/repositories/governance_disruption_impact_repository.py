"""Phase 87: Clinical Safety Governance Resilience Disruption Impact Repository.

Thread-safe in-memory persistence for:
- Disruption scenarios
- Disruption impact assessments
- Cascading failure analyses
- Compound disruption scenarios
- Fallback comparisons
- Impact follow-up remediation records
"""

import threading
from typing import Dict, List, Optional

from app.schemas.governance_disruption_common import (
    AssessmentReviewStatus,
    DisruptionScenarioCategory,
    FollowUpDestinationWorkflow,
    FollowUpStatus,
    ImpactSeverity,
    ScenarioReviewStatus,
)
from app.schemas.governance_disruption_scenario import DisruptionScenarioRecord
from app.schemas.governance_disruption_impact import DisruptionImpactAssessmentRecord
from app.schemas.governance_cascading_failure import CascadingAnalysisRecord
from app.schemas.governance_compound_disruption import CompoundDisruptionScenarioRecord
from app.schemas.governance_fallback_comparison import FallbackComparisonRecord
from app.schemas.governance_impact_remediation import ImpactFollowUpRecord


class GovernanceDisruptionImpactRepository:
    """Thread-safe in-memory repository for Phase 87 disruption impact analysis."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._scenarios: Dict[str, DisruptionScenarioRecord] = {}
        self._assessments: Dict[str, DisruptionImpactAssessmentRecord] = {}
        self._cascading_analyses: Dict[str, CascadingAnalysisRecord] = {}
        self._compound_scenarios: Dict[str, CompoundDisruptionScenarioRecord] = {}
        self._fallback_comparisons: Dict[str, FallbackComparisonRecord] = {}
        self._follow_ups: Dict[str, ImpactFollowUpRecord] = {}

    def clear(self) -> None:
        with self._lock:
            self._scenarios.clear()
            self._assessments.clear()
            self._cascading_analyses.clear()
            self._compound_scenarios.clear()
            self._fallback_comparisons.clear()
            self._follow_ups.clear()

    # =========================================================================
    # 1. Disruption Scenarios
    # =========================================================================

    def save_scenario(self, record: DisruptionScenarioRecord) -> DisruptionScenarioRecord:
        with self._lock:
            self._scenarios[record.scenario_id] = record
            return record

    def get_scenario(self, scenario_id: str, tenant_id: str) -> Optional[DisruptionScenarioRecord]:
        with self._lock:
            rec = self._scenarios.get(scenario_id)
            if rec and rec.tenant_id == tenant_id:
                return rec
            return None

    def list_scenarios(
        self,
        tenant_id: str,
        category: Optional[DisruptionScenarioCategory] = None,
        review_status: Optional[ScenarioReviewStatus] = None,
    ) -> List[DisruptionScenarioRecord]:
        with self._lock:
            results = [s for s in self._scenarios.values() if s.tenant_id == tenant_id]
            if category:
                results = [s for s in results if s.category == category]
            if review_status:
                results = [s for s in results if s.review_status == review_status]
            return results

    # =========================================================================
    # 2. Impact Assessments
    # =========================================================================

    def save_assessment(self, record: DisruptionImpactAssessmentRecord) -> DisruptionImpactAssessmentRecord:
        with self._lock:
            self._assessments[record.assessment_id] = record
            return record

    def get_assessment(self, assessment_id: str, tenant_id: str) -> Optional[DisruptionImpactAssessmentRecord]:
        with self._lock:
            rec = self._assessments.get(assessment_id)
            if rec and rec.tenant_id == tenant_id:
                return rec
            return None

    def list_assessments(
        self,
        tenant_id: str,
        scenario_id: Optional[str] = None,
        review_status: Optional[AssessmentReviewStatus] = None,
        severity: Optional[ImpactSeverity] = None,
    ) -> List[DisruptionImpactAssessmentRecord]:
        with self._lock:
            results = [a for a in self._assessments.values() if a.tenant_id == tenant_id]
            if scenario_id:
                results = [a for a in results if a.scenario_id == scenario_id]
            if review_status:
                results = [a for a in results if a.review_status == review_status]
            if severity:
                results = [a for a in results if a.overall_impact_severity == severity]
            return results

    # =========================================================================
    # 3. Cascading Failure Analyses
    # =========================================================================

    def save_cascading_analysis(self, record: CascadingAnalysisRecord) -> CascadingAnalysisRecord:
        with self._lock:
            self._cascading_analyses[record.analysis_id] = record
            return record

    def get_cascading_analysis(self, analysis_id: str, tenant_id: str) -> Optional[CascadingAnalysisRecord]:
        with self._lock:
            rec = self._cascading_analyses.get(analysis_id)
            if rec and rec.tenant_id == tenant_id:
                return rec
            return None

    def list_cascading_analyses(
        self, tenant_id: str, assessment_id: Optional[str] = None
    ) -> List[CascadingAnalysisRecord]:
        with self._lock:
            results = [c for c in self._cascading_analyses.values() if c.tenant_id == tenant_id]
            if assessment_id:
                results = [c for c in results if c.assessment_id == assessment_id]
            return results

    # =========================================================================
    # 4. Compound Disruption Scenarios
    # =========================================================================

    def save_compound_scenario(self, record: CompoundDisruptionScenarioRecord) -> CompoundDisruptionScenarioRecord:
        with self._lock:
            self._compound_scenarios[record.compound_scenario_id] = record
            return record

    def get_compound_scenario(self, compound_scenario_id: str, tenant_id: str) -> Optional[CompoundDisruptionScenarioRecord]:
        with self._lock:
            rec = self._compound_scenarios.get(compound_scenario_id)
            if rec and rec.tenant_id == tenant_id:
                return rec
            return None

    def list_compound_scenarios(self, tenant_id: str) -> List[CompoundDisruptionScenarioRecord]:
        with self._lock:
            return [cs for cs in self._compound_scenarios.values() if cs.tenant_id == tenant_id]

    # =========================================================================
    # 5. Fallback Comparisons
    # =========================================================================

    def save_fallback_comparison(self, record: FallbackComparisonRecord) -> FallbackComparisonRecord:
        with self._lock:
            self._fallback_comparisons[record.comparison_id] = record
            return record

    def get_fallback_comparison(self, comparison_id: str, tenant_id: str) -> Optional[FallbackComparisonRecord]:
        with self._lock:
            rec = self._fallback_comparisons.get(comparison_id)
            if rec and rec.tenant_id == tenant_id:
                return rec
            return None

    def list_fallback_comparisons(
        self, tenant_id: str, assessment_id: Optional[str] = None
    ) -> List[FallbackComparisonRecord]:
        with self._lock:
            results = [f for f in self._fallback_comparisons.values() if f.tenant_id == tenant_id]
            if assessment_id:
                results = [f for f in results if f.assessment_id == assessment_id]
            return results

    # =========================================================================
    # 6. Remediation Follow-ups
    # =========================================================================

    def save_follow_up(self, record: ImpactFollowUpRecord) -> ImpactFollowUpRecord:
        with self._lock:
            self._follow_ups[record.follow_up_id] = record
            return record

    def get_follow_up(self, follow_up_id: str, tenant_id: str) -> Optional[ImpactFollowUpRecord]:
        with self._lock:
            rec = self._follow_ups.get(follow_up_id)
            if rec and rec.tenant_id == tenant_id:
                return rec
            return None

    def list_follow_ups(
        self,
        tenant_id: str,
        assessment_id: Optional[str] = None,
        destination_workflow: Optional[FollowUpDestinationWorkflow] = None,
        status: Optional[FollowUpStatus] = None,
    ) -> List[ImpactFollowUpRecord]:
        with self._lock:
            results = [fu for fu in self._follow_ups.values() if fu.tenant_id == tenant_id]
            if assessment_id:
                results = [fu for fu in results if fu.assessment_id == assessment_id]
            if destination_workflow:
                results = [fu for fu in results if fu.destination_workflow == destination_workflow]
            if status:
                results = [fu for fu in results if fu.status == status]
            return results


_disruption_impact_repository: Optional[GovernanceDisruptionImpactRepository] = None


def get_governance_disruption_impact_repository() -> GovernanceDisruptionImpactRepository:
    global _disruption_impact_repository
    if _disruption_impact_repository is None:
        _disruption_impact_repository = GovernanceDisruptionImpactRepository()
    return _disruption_impact_repository
