"""
Phase 88: Clinical Safety Governance Resilience Response Strategy Repository.

Thread-safe in-memory persistence for:
- Response strategies
- Candidate recovery options
- Feasibility assessments
- Recovery priority evaluations and sequences
- Recovery option comparisons and trade-offs
- Recovery resource allocation plans
- Recovery recommendations and management decisions
- Continuity handoffs (Phase 80)
- Recovery execution tracking records
"""

import threading
from typing import Dict, List, Optional

from app.schemas.governance_response_common import (
    ContinuityHandoffStatus,
    ExecutionTrackingStatus,
    RecommendationLifecycleStatus,
    RecoveryFeasibilityOutcome,
    ResponseStrategyCategory,
    StrategyReviewStatus,
)
from app.schemas.governance_response_strategy import ResponseStrategyRecord
from app.schemas.governance_recovery_option import (
    CandidateRecoveryOptionRecord,
    FeasibilityAssessmentRecord,
)
from app.schemas.governance_recovery_priority import (
    RecoveryPriorityEvaluationRecord,
    RecoverySequenceRecord,
)
from app.schemas.governance_recovery_comparison import RecoveryComparisonRecord
from app.schemas.governance_recovery_resource_planning import RecoveryResourcePlanRecord
from app.schemas.governance_recovery_recommendation import (
    ContinuityHandoffRecord,
    RecoveryRecommendationRecord,
)
from app.schemas.governance_recovery_execution import RecoveryExecutionTrackingRecord


class GovernanceResponseStrategyRepository:
    """Thread-safe in-memory repository for Phase 88 response strategy optimization data."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._strategies: Dict[str, ResponseStrategyRecord] = {}
        self._options: Dict[str, CandidateRecoveryOptionRecord] = {}
        self._feasibility_assessments: Dict[str, FeasibilityAssessmentRecord] = {}
        self._priorities: Dict[str, RecoveryPriorityEvaluationRecord] = {}
        self._sequences: Dict[str, RecoverySequenceRecord] = {}
        self._comparisons: Dict[str, RecoveryComparisonRecord] = {}
        self._resource_plans: Dict[str, RecoveryResourcePlanRecord] = {}
        self._recommendations: Dict[str, RecoveryRecommendationRecord] = {}
        self._handoffs: Dict[str, ContinuityHandoffRecord] = {}
        self._executions: Dict[str, RecoveryExecutionTrackingRecord] = {}

    def clear(self) -> None:
        with self._lock:
            self._strategies.clear()
            self._options.clear()
            self._feasibility_assessments.clear()
            self._priorities.clear()
            self._sequences.clear()
            self._comparisons.clear()
            self._resource_plans.clear()
            self._recommendations.clear()
            self._handoffs.clear()
            self._executions.clear()

    # =========================================================================
    # 1. Strategies
    # =========================================================================

    def save_strategy(self, record: ResponseStrategyRecord) -> ResponseStrategyRecord:
        with self._lock:
            self._strategies[record.strategy_id] = record
            return record

    def create_strategy(self, record: ResponseStrategyRecord) -> ResponseStrategyRecord:
        return self.save_strategy(record)

    def update_strategy(self, record: ResponseStrategyRecord) -> ResponseStrategyRecord:
        return self.save_strategy(record)

    def get_strategy(self, strategy_id: str, tenant_id: str) -> Optional[ResponseStrategyRecord]:
        with self._lock:
            rec = self._strategies.get(strategy_id)
            if rec and rec.tenant_id == tenant_id:
                return rec
            return None

    def list_strategies(
        self,
        tenant_id: str,
        category: Optional[ResponseStrategyCategory] = None,
        review_status: Optional[StrategyReviewStatus] = None,
        status: Optional[StrategyReviewStatus] = None,
        scenario_ref: Optional[str] = None,
        scenario_id: Optional[str] = None,
        capability_ref: Optional[str] = None,
    ) -> List[ResponseStrategyRecord]:
        with self._lock:
            results = [s for s in self._strategies.values() if s.tenant_id == tenant_id]
            if category:
                results = [s for s in results if s.category == category]
            effective_status = status or review_status
            if effective_status:
                results = [s for s in results if s.review_status == effective_status]
            eff_scenario = scenario_id or scenario_ref
            if eff_scenario:
                results = [s for s in results if eff_scenario in s.applicable_scenario_ids]
            if capability_ref:
                results = [s for s in results if capability_ref in s.affected_capability_refs]
            return results

    # =========================================================================
    # 2. Candidate Recovery Options
    # =========================================================================

    def save_option(self, record: CandidateRecoveryOptionRecord) -> CandidateRecoveryOptionRecord:
        with self._lock:
            self._options[record.option_id] = record
            return record

    def create_option(self, record: CandidateRecoveryOptionRecord) -> CandidateRecoveryOptionRecord:
        return self.save_option(record)

    def update_option(self, record: CandidateRecoveryOptionRecord) -> CandidateRecoveryOptionRecord:
        return self.save_option(record)

    def get_option(self, option_id: str, tenant_id: str) -> Optional[CandidateRecoveryOptionRecord]:
        with self._lock:
            rec = self._options.get(option_id)
            if rec and rec.tenant_id == tenant_id:
                return rec
            return None

    def list_options(
        self,
        tenant_id: str,
        scenario_id: Optional[str] = None,
        scenario_ref: Optional[str] = None,
        strategy_ref: Optional[str] = None,
        capability_ref: Optional[str] = None,
        feasibility_outcome: Optional[RecoveryFeasibilityOutcome] = None,
    ) -> List[CandidateRecoveryOptionRecord]:
        with self._lock:
            results = [o for o in self._options.values() if o.tenant_id == tenant_id]
            eff_scen = scenario_id or scenario_ref
            if eff_scen:
                results = [o for o in results if o.scenario_id == eff_scen]
            if strategy_ref:
                results = [o for o in results if o.strategy_id == strategy_ref]
            if capability_ref:
                results = [o for o in results if capability_ref in o.target_capability_refs]
            if feasibility_outcome:
                results = [o for o in results if o.feasibility_outcome == feasibility_outcome]
            return results

    # =========================================================================
    # 3. Feasibility Assessments
    # =========================================================================

    def save_feasibility_assessment(self, record: FeasibilityAssessmentRecord) -> FeasibilityAssessmentRecord:
        with self._lock:
            self._feasibility_assessments[record.assessment_id] = record
            return record

    def create_feasibility_assessment(self, record: FeasibilityAssessmentRecord) -> FeasibilityAssessmentRecord:
        return self.save_feasibility_assessment(record)

    def get_feasibility_assessment(self, assessment_id: str, tenant_id: str) -> Optional[FeasibilityAssessmentRecord]:
        with self._lock:
            rec = self._feasibility_assessments.get(assessment_id)
            if rec and rec.tenant_id == tenant_id:
                return rec
            return None

    def list_feasibility_assessments(
        self,
        tenant_id: str,
        option_id: Optional[str] = None,
        option_ref: Optional[str] = None,
        outcome: Optional[RecoveryFeasibilityOutcome] = None,
    ) -> List[FeasibilityAssessmentRecord]:
        with self._lock:
            results = [fa for fa in self._feasibility_assessments.values() if fa.tenant_id == tenant_id]
            eff_opt = option_id or option_ref
            if eff_opt:
                results = [fa for fa in results if fa.option_id == eff_opt]
            if outcome:
                results = [fa for fa in results if fa.feasibility_outcome == outcome]
            return results

    # =========================================================================
    # 4. Priorities and Sequences
    # =========================================================================

    def save_priority_evaluation(self, record: RecoveryPriorityEvaluationRecord) -> RecoveryPriorityEvaluationRecord:
        with self._lock:
            self._priorities[record.priority_evaluation_id] = record
            return record

    def create_priority_evaluation(self, record: RecoveryPriorityEvaluationRecord) -> RecoveryPriorityEvaluationRecord:
        return self.save_priority_evaluation(record)

    def get_priority_evaluation(self, priority_evaluation_id: str, tenant_id: str) -> Optional[RecoveryPriorityEvaluationRecord]:
        with self._lock:
            rec = self._priorities.get(priority_evaluation_id)
            if rec and rec.tenant_id == tenant_id:
                return rec
            return None

    def list_priority_evaluations(
        self,
        tenant_id: str,
        scenario_id: Optional[str] = None,
        scenario_ref: Optional[str] = None,
    ) -> List[RecoveryPriorityEvaluationRecord]:
        with self._lock:
            results = [p for p in self._priorities.values() if p.tenant_id == tenant_id]
            eff_scen = scenario_id or scenario_ref
            if eff_scen:
                results = [p for p in results if p.scenario_id == eff_scen]
            return results

    def save_sequence(self, record: RecoverySequenceRecord) -> RecoverySequenceRecord:
        with self._lock:
            self._sequences[record.sequence_id] = record
            return record

    def create_recovery_sequence(self, record: RecoverySequenceRecord) -> RecoverySequenceRecord:
        return self.save_sequence(record)

    def get_sequence(self, sequence_id: str, tenant_id: str) -> Optional[RecoverySequenceRecord]:
        with self._lock:
            rec = self._sequences.get(sequence_id)
            if rec and rec.tenant_id == tenant_id:
                return rec
            return None

    def get_recovery_sequence(self, sequence_id: str, tenant_id: str) -> Optional[RecoverySequenceRecord]:
        return self.get_sequence(sequence_id, tenant_id)

    def list_recovery_sequences(
        self,
        tenant_id: str,
        priority_evaluation_ref: Optional[str] = None,
    ) -> List[RecoverySequenceRecord]:
        with self._lock:
            return [s for s in self._sequences.values() if s.tenant_id == tenant_id]

    # =========================================================================
    # 5. Comparisons
    # =========================================================================

    def save_comparison(self, record: RecoveryComparisonRecord) -> RecoveryComparisonRecord:
        with self._lock:
            self._comparisons[record.comparison_id] = record
            return record

    def create_comparison(self, record: RecoveryComparisonRecord) -> RecoveryComparisonRecord:
        return self.save_comparison(record)

    def get_comparison(self, comparison_id: str, tenant_id: str) -> Optional[RecoveryComparisonRecord]:
        with self._lock:
            rec = self._comparisons.get(comparison_id)
            if rec and rec.tenant_id == tenant_id:
                return rec
            return None

    def list_comparisons(
        self,
        tenant_id: str,
        scenario_ref: Optional[str] = None,
        strategy_ref: Optional[str] = None,
    ) -> List[RecoveryComparisonRecord]:
        with self._lock:
            return [c for c in self._comparisons.values() if c.tenant_id == tenant_id]

    # =========================================================================
    # 6. Resource Plans
    # =========================================================================

    def save_resource_plan(self, record: RecoveryResourcePlanRecord) -> RecoveryResourcePlanRecord:
        with self._lock:
            self._resource_plans[record.plan_id] = record
            return record

    def create_resource_plan(self, record: RecoveryResourcePlanRecord) -> RecoveryResourcePlanRecord:
        return self.save_resource_plan(record)

    def get_resource_plan(self, plan_id: str, tenant_id: str) -> Optional[RecoveryResourcePlanRecord]:
        with self._lock:
            rec = self._resource_plans.get(plan_id)
            if rec and rec.tenant_id == tenant_id:
                return rec
            return None

    def list_resource_plans(
        self,
        tenant_id: str,
        option_id: Optional[str] = None,
        option_ref: Optional[str] = None,
        scenario_ref: Optional[str] = None,
    ) -> List[RecoveryResourcePlanRecord]:
        with self._lock:
            results = [rp for rp in self._resource_plans.values() if rp.tenant_id == tenant_id]
            eff_opt = option_id or option_ref
            if eff_opt:
                results = [rp for rp in results if rp.option_id == eff_opt]
            return results

    # =========================================================================
    # 7. Recommendations
    # =========================================================================

    def save_recommendation(self, record: RecoveryRecommendationRecord) -> RecoveryRecommendationRecord:
        with self._lock:
            self._recommendations[record.recommendation_id] = record
            return record

    def create_recommendation(self, record: RecoveryRecommendationRecord) -> RecoveryRecommendationRecord:
        return self.save_recommendation(record)

    def update_recommendation(self, record: RecoveryRecommendationRecord) -> RecoveryRecommendationRecord:
        return self.save_recommendation(record)

    def get_recommendation(self, recommendation_id: str, tenant_id: str) -> Optional[RecoveryRecommendationRecord]:
        with self._lock:
            rec = self._recommendations.get(recommendation_id)
            if rec and rec.tenant_id == tenant_id:
                return rec
            return None

    def list_recommendations(
        self,
        tenant_id: str,
        status: Optional[RecommendationLifecycleStatus] = None,
        scenario_ref: Optional[str] = None,
    ) -> List[RecoveryRecommendationRecord]:
        with self._lock:
            results = [r for r in self._recommendations.values() if r.tenant_id == tenant_id]
            if status:
                results = [r for r in results if r.lifecycle_status == status]
            return results

    # =========================================================================
    # 8. Continuity Handoffs (Phase 80)
    # =========================================================================

    def save_handoff(self, record: ContinuityHandoffRecord) -> ContinuityHandoffRecord:
        with self._lock:
            self._handoffs[record.handoff_id] = record
            return record

    def create_continuity_handoff(self, record: ContinuityHandoffRecord) -> ContinuityHandoffRecord:
        return self.save_handoff(record)

    def update_continuity_handoff(self, record: ContinuityHandoffRecord) -> ContinuityHandoffRecord:
        return self.save_handoff(record)

    def get_handoff(self, handoff_id: str, tenant_id: str) -> Optional[ContinuityHandoffRecord]:
        with self._lock:
            rec = self._handoffs.get(handoff_id)
            if rec and rec.tenant_id == tenant_id:
                return rec
            return None

    def get_continuity_handoff(self, handoff_id: str, tenant_id: str) -> Optional[ContinuityHandoffRecord]:
        return self.get_handoff(handoff_id, tenant_id)

    def list_handoffs(
        self,
        tenant_id: str,
        recommendation_ref: Optional[str] = None,
        status: Optional[ContinuityHandoffStatus] = None,
    ) -> List[ContinuityHandoffRecord]:
        with self._lock:
            results = [h for h in self._handoffs.values() if h.tenant_id == tenant_id]
            if recommendation_ref:
                results = [h for h in results if h.recommendation_id == recommendation_ref]
            if status:
                results = [h for h in results if h.status == status]
            return results

    def list_continuity_handoffs(
        self,
        tenant_id: str,
        recommendation_ref: Optional[str] = None,
        status: Optional[ContinuityHandoffStatus] = None,
    ) -> List[ContinuityHandoffRecord]:
        return self.list_handoffs(tenant_id, recommendation_ref, status)

    # =========================================================================
    # 9. Recovery Execution Tracking
    # =========================================================================

    def save_execution(self, record: RecoveryExecutionTrackingRecord) -> RecoveryExecutionTrackingRecord:
        with self._lock:
            self._executions[record.execution_id] = record
            return record

    def create_execution_tracking(self, record: RecoveryExecutionTrackingRecord) -> RecoveryExecutionTrackingRecord:
        return self.save_execution(record)

    def update_execution_tracking(self, record: RecoveryExecutionTrackingRecord) -> RecoveryExecutionTrackingRecord:
        return self.save_execution(record)

    def get_execution(self, execution_id: str, tenant_id: str) -> Optional[RecoveryExecutionTrackingRecord]:
        with self._lock:
            rec = self._executions.get(execution_id)
            if rec and rec.tenant_id == tenant_id:
                return rec
            return None

    def get_execution_tracking(self, execution_id: str, tenant_id: str) -> Optional[RecoveryExecutionTrackingRecord]:
        return self.get_execution(execution_id, tenant_id)

    def list_executions(
        self,
        tenant_id: str,
        status: Optional[ExecutionTrackingStatus] = None,
        recommendation_ref: Optional[str] = None,
    ) -> List[RecoveryExecutionTrackingRecord]:
        with self._lock:
            results = [e for e in self._executions.values() if e.tenant_id == tenant_id]
            if status:
                results = [e for e in results if e.status == status]
            return results

    def list_execution_trackings(
        self,
        tenant_id: str,
        status: Optional[ExecutionTrackingStatus] = None,
        recommendation_ref: Optional[str] = None,
    ) -> List[RecoveryExecutionTrackingRecord]:
        return self.list_executions(tenant_id, status, recommendation_ref)


_response_strategy_repository: Optional[GovernanceResponseStrategyRepository] = None


def get_governance_response_strategy_repository() -> GovernanceResponseStrategyRepository:
    global _response_strategy_repository
    if _response_strategy_repository is None:
        _response_strategy_repository = GovernanceResponseStrategyRepository()
    return _response_strategy_repository
