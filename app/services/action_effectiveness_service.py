"""Phase 55: Primary Action Effectiveness Orchestration Service.

Orchestrates post-action evaluation lifecycle:
- Action eligibility and scope check
- Objective & criteria resolution
- Observation window management
- Evidence collection & sanitization
- Expected-vs-observed comparison
- Policy-driven effectiveness assessment
- Human review gating
- Closed-loop routing (Phases 52, 53, 50, 51, 49, 54)
- Regression detection and sustained monitoring
- Idempotency and concurrency management
"""

from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Dict, List, Optional
import uuid

from app.core.exceptions import AppException, ErrorCode
from app.repositories.action_effectiveness_repository import (
    ActionEffectivenessRepository,
    get_action_effectiveness_repository,
)
from app.repositories.safety_action_repository import get_safety_action_repository
from app.schemas.action_effectiveness import (
    ConfoundingChange,
    CreateEvaluationRequest,
    EffectivenessEvaluationRecord,
    EffectivenessLifecycleState,
    EffectivenessScope,
    EffectivenessState,
    HumanReviewOutcome,
    ObservationWindowType,
    PostActionEvidenceItem,
    SafetyObjective,
)
from app.services.action_effectiveness_assessment_service import ActionEffectivenessAssessmentService
from app.services.action_effectiveness_comparison_service import ActionEffectivenessComparisonService
from app.services.action_effectiveness_criteria_service import ActionEffectivenessCriteriaService
from app.services.action_effectiveness_evidence_service import ActionEffectivenessEvidenceService
from app.services.action_effectiveness_regression_service import ActionEffectivenessRegressionService
from app.services.action_effectiveness_review_service import ActionEffectivenessReviewService
from app.services.action_effectiveness_routing_service import ActionEffectivenessRoutingService
from app.services.action_effectiveness_validation_service import ActionEffectivenessValidationService
from app.services.action_effectiveness_window_service import ActionEffectivenessWindowService


class ActionEffectivenessService:
    """Primary orchestration service for Phase 55 effectiveness evaluations."""

    def __init__(
        self,
        repository: Optional[ActionEffectivenessRepository] = None,
    ) -> None:
        self._repo = repository or get_action_effectiveness_repository()
        self._action_repo = get_safety_action_repository()
        self._criteria_service = ActionEffectivenessCriteriaService()
        self._window_service = ActionEffectivenessWindowService()
        self._evidence_service = ActionEffectivenessEvidenceService()
        self._comparison_service = ActionEffectivenessComparisonService()
        self._assessment_service = ActionEffectivenessAssessmentService()
        self._review_service = ActionEffectivenessReviewService()
        self._regression_service = ActionEffectivenessRegressionService()
        self._routing_service = ActionEffectivenessRoutingService()
        self._validation_service = ActionEffectivenessValidationService()

    def create_evaluation(
        self,
        request: CreateEvaluationRequest,
        actor_id: str,
        actor_role: str,
    ) -> EffectivenessEvaluationRecord:
        """Initialize an effectiveness evaluation for a completed safety action."""
        # 1. Idempotency check
        if request.idempotency_key:
            payload_str = f"{request.action_id}:{request.duration_hours}:{request.min_event_count}"
            p_hash = hashlib.sha256(payload_str.encode()).hexdigest()
            is_dup, existing_id = self._repo.check_idempotency(request.idempotency_key, p_hash)
            if is_dup:
                if existing_id:
                    existing = self._repo.get(existing_id)
                    if existing:
                        return existing
                raise AppException(
                    code=ErrorCode.IDEMPOTENCY_CONFLICT,
                    message="Conflicting idempotency key provided for effectiveness evaluation.",
                    status_code=409,
                )

        # 2. Resolve safety action
        action = self._action_repo.get(request.action_id)
        if not action:
            raise AppException(
                code=ErrorCode.EFFECTIVENESS_EVALUATION_NOT_FOUND,
                message=f"Safety action '{request.action_id}' not found.",
                status_code=404,
            )

        # 3. Scope resolution
        scope = request.scope or EffectivenessScope(
            organization_id=action.scope.organization_id,
            facility_id=action.scope.facility_id,
            department_id=action.scope.department_id,
        )

        # 4. Action eligibility validation
        self._validation_service.validate_action_eligibility(request.action_id, scope)

        # 5. Safety objective resolution & validation
        objective = request.safety_objective or SafetyObjective(
            description=f"Validate effectiveness and eliminate recurrence for {action.action_type.value}",
            target_finding_type=action.finding.source_type.value,
            target_control_id=action.finding.source_id,
            bounded_failure_mode=f"Degradation of {action.action_type.value}",
            is_evidence_testable=True,
        )
        self._criteria_service.validate_safety_objective(objective)

        # 6. Criteria resolution & validation
        criteria = request.criteria or self._criteria_service.resolve_default_criteria(
            objective, action.action_type.value
        )
        self._criteria_service.validate_criteria(criteria)

        # 7. Observation window initialization
        window = self._window_service.initialize_window(
            window_type=request.observation_window_type,
            duration_hours=request.duration_hours,
            min_event_count=request.min_event_count,
        )

        # 8. Construct record
        evaluation = EffectivenessEvaluationRecord(
            evaluation_id=f"eff-{uuid.uuid4().hex[:12]}",
            action_id=request.action_id,
            scope=scope,
            lifecycle_state=EffectivenessLifecycleState.EVIDENCE_COLLECTION,
            effectiveness_state=EffectivenessState.EVIDENCE_PENDING,
            safety_objective=objective,
            criteria=criteria,
            observation_window=window,
            created_by=actor_id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        saved = self._repo.save(evaluation)

        # Record idempotency
        if request.idempotency_key:
            payload_str = f"{request.action_id}:{request.duration_hours}:{request.min_event_count}"
            p_hash = hashlib.sha256(payload_str.encode()).hexdigest()
            self._repo.record_idempotency(request.idempotency_key, p_hash, saved.evaluation_id)

        return saved

    def get_evaluation(self, evaluation_id: str) -> EffectivenessEvaluationRecord:
        """Fetch evaluation record or raise 404."""
        record = self._repo.get(evaluation_id)
        if not record:
            raise AppException(
                code=ErrorCode.EFFECTIVENESS_EVALUATION_NOT_FOUND,
                message=f"Effectiveness evaluation '{evaluation_id}' not found.",
                status_code=404,
            )
        return record

    def collect_evidence(
        self,
        evaluation_id: str,
        evidence_items: List[PostActionEvidenceItem],
        confounding_changes: Optional[List[ConfoundingChange]] = None,
    ) -> EffectivenessEvaluationRecord:
        """Append post-action evidence and confounding factors."""
        evaluation = self.get_evaluation(evaluation_id)

        if evaluation.lifecycle_state in (
            EffectivenessLifecycleState.CLOSED,
            EffectivenessLifecycleState.SUPERSEDED,
        ):
            raise AppException(
                code=ErrorCode.ALREADY_CLOSED,
                message="Cannot add evidence to a closed or superseded evaluation.",
                status_code=400,
            )

        # Validate each item
        for item in evidence_items:
            validated_item = self._evidence_service.validate_and_classify_evidence(
                item=item,
                target_scope=evaluation.scope,
                window_start=evaluation.observation_window.start_time,
            )
            evaluation.evidence_items.append(validated_item)

        if confounding_changes:
            evaluation.confounding_changes.extend(confounding_changes)

        if not evaluation.is_sustained:
            evaluation.lifecycle_state = EffectivenessLifecycleState.EVIDENCE_COLLECTION
        evaluation.version += 1
        return self._repo.save(evaluation)

    def finalize_evaluation(
        self,
        evaluation_id: str,
        reassess_if_needed: bool = True,
    ) -> EffectivenessEvaluationRecord:
        """Execute comparison, determine candidate effectiveness state, and request human review."""
        evaluation = self.get_evaluation(evaluation_id)

        if evaluation.lifecycle_state == EffectivenessLifecycleState.CLOSED:
            raise AppException(
                code=ErrorCode.ALREADY_CLOSED,
                message="Evaluation is already closed.",
                status_code=400,
            )

        # 1. Close observation window
        self._window_service.close_window(evaluation.observation_window)

        # 2. Baseline alignment check
        self._comparison_service.validate_baseline_alignment(evaluation.baseline, evaluation.scope)

        # 3. Detect evidence conflicts
        conflicts = self._evidence_service.detect_evidence_conflicts(evaluation.evidence_items)

        # 4. Execute comparisons
        comparisons = self._comparison_service.execute_comparison(
            criteria=evaluation.criteria,
            evidence_items=evaluation.evidence_items,
            baseline=evaluation.baseline,
            confounding_changes=evaluation.confounding_changes,
        )
        evaluation.comparisons = comparisons

        # 5. Check for regression if evaluation was previously accepted
        has_prior_acceptance = evaluation.is_sustained or any(
            r.decision in (HumanReviewOutcome.ACCEPT, HumanReviewOutcome.ACCEPT_WITH_LIMITATIONS)
            for r in evaluation.reviews
        )
        if has_prior_acceptance or evaluation.lifecycle_state in (
            EffectivenessLifecycleState.EFFECTIVENESS_ACCEPTED,
            EffectivenessLifecycleState.MONITORING,
            EffectivenessLifecycleState.SUSTAINED_VALIDATION,
        ):
            is_regressed = self._regression_service.evaluate_regression(evaluation, comparisons)
            if is_regressed:
                # Route regression feedback
                self._routing_service.route_feedback(evaluation)
                return self._repo.save(evaluation)

        # 6. Policy assessment
        eff_state, life_state, req_review = self._assessment_service.determine_candidate_state(
            comparisons=comparisons,
            evidence_items=evaluation.evidence_items,
            conflicts=conflicts,
        )
        evaluation.effectiveness_state = eff_state
        evaluation.lifecycle_state = life_state
        evaluation.requires_human_review = req_review

        # 7. Route feedback to Phase 52, 53, etc.
        self._routing_service.route_feedback(evaluation)

        evaluation.version += 1
        return self._repo.save(evaluation)

    def submit_review(
        self,
        evaluation_id: str,
        reviewer_id: str,
        reviewer_role: str,
        decision: HumanReviewOutcome,
        rationale: str,
        limitations: Optional[str] = None,
        is_ai_agent: bool = False,
    ) -> EffectivenessEvaluationRecord:
        """Submit human oversight review decision."""
        evaluation = self.get_evaluation(evaluation_id)
        updated = self._review_service.process_review(
            evaluation=evaluation,
            reviewer_id=reviewer_id,
            reviewer_role=reviewer_role,
            decision=decision,
            rationale=rationale,
            limitations=limitations,
            is_ai_agent=is_ai_agent,
        )
        # Update routing based on human decision
        self._routing_service.route_feedback(updated)
        return self._repo.save(updated)

    def accept_evaluation(
        self,
        evaluation_id: str,
        reviewer_id: str,
        reviewer_role: str,
        rationale: str,
        limitations: Optional[str] = None,
    ) -> EffectivenessEvaluationRecord:
        """Convenience method to accept effectiveness evaluation."""
        return self.submit_review(
            evaluation_id=evaluation_id,
            reviewer_id=reviewer_id,
            reviewer_role=reviewer_role,
            decision=HumanReviewOutcome.ACCEPT if not limitations else HumanReviewOutcome.ACCEPT_WITH_LIMITATIONS,
            rationale=rationale,
            limitations=limitations,
            is_ai_agent=False,
        )

    def reject_evaluation(
        self,
        evaluation_id: str,
        reviewer_id: str,
        reviewer_role: str,
        rationale: str,
    ) -> EffectivenessEvaluationRecord:
        """Convenience method to reject effectiveness evaluation."""
        return self.submit_review(
            evaluation_id=evaluation_id,
            reviewer_id=reviewer_id,
            reviewer_role=reviewer_role,
            decision=HumanReviewOutcome.REJECT,
            rationale=rationale,
            is_ai_agent=False,
        )

    def reassess_evaluation(
        self,
        evaluation_id: str,
        actor_id: str,
        reason: str,
        additional_context: Optional[Dict[str, Any]] = None,
    ) -> EffectivenessEvaluationRecord:
        """Request formal reassessment of effectiveness evaluation."""
        evaluation = self.get_evaluation(evaluation_id)
        evaluation.lifecycle_state = EffectivenessLifecycleState.REQUIRES_REASSESSMENT
        evaluation.effectiveness_state = EffectivenessState.REQUIRES_REASSESSMENT
        evaluation.version += 1
        self._routing_service.route_feedback(evaluation)
        return self._repo.save(evaluation)

    def reopen_evaluation(
        self,
        evaluation_id: str,
        actor_id: str,
        reason: str,
        new_evidence: Optional[List[PostActionEvidenceItem]] = None,
    ) -> EffectivenessEvaluationRecord:
        """Reopen evaluation when new evidence arises or regression is observed."""
        evaluation = self.get_evaluation(evaluation_id)
        evaluation.lifecycle_state = EffectivenessLifecycleState.REOPENED
        evaluation.reopened_count += 1
        evaluation.closed_at = None

        if new_evidence:
            for item in new_evidence:
                val_item = self._evidence_service.validate_and_classify_evidence(
                    item, evaluation.scope, evaluation.observation_window.start_time
                )
                evaluation.evidence_items.append(val_item)

        evaluation.version += 1
        return self._repo.save(evaluation)

    def list_evaluations(
        self,
        organization_id: Optional[str] = None,
        facility_id: Optional[str] = None,
        lifecycle_state: Optional[EffectivenessLifecycleState] = None,
        effectiveness_state: Optional[EffectivenessState] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[EffectivenessEvaluationRecord]:
        """Query evaluations with filters."""
        return self._repo.list_evaluations(
            organization_id=organization_id,
            facility_id=facility_id,
            lifecycle_state=lifecycle_state,
            effectiveness_state=effectiveness_state,
            limit=limit,
            offset=offset,
        )

    def list_pending(self, organization_id: Optional[str] = None) -> List[EffectivenessEvaluationRecord]:
        return self._repo.list_pending(organization_id)

    def list_review_required(self, organization_id: Optional[str] = None) -> List[EffectivenessEvaluationRecord]:
        return self._repo.list_review_required(organization_id)

    def list_regressions(self, organization_id: Optional[str] = None) -> List[EffectivenessEvaluationRecord]:
        return self._repo.list_regressions(organization_id)

    def list_insufficient_evidence(self, organization_id: Optional[str] = None) -> List[EffectivenessEvaluationRecord]:
        return self._repo.list_insufficient_evidence(organization_id)

    def list_failed(self, organization_id: Optional[str] = None) -> List[EffectivenessEvaluationRecord]:
        return self._repo.list_failed(organization_id)

    def reanalysis(self, evaluation_ids: Optional[List[str]], reason: str) -> Dict[str, Any]:
        """Batch reanalysis of evaluations."""
        if not reason or len(reason.strip()) < 10:
            raise AppException(
                code=ErrorCode.CRITERIA_MISSING,
                message="Reanalysis reason must be at least 10 characters.",
                status_code=400,
            )
        evals_to_reanalyze = []
        if evaluation_ids:
            for eid in evaluation_ids:
                try:
                    evals_to_reanalyze.append(self.get_evaluation(eid))
                except AppException:
                    pass
        else:
            evals_to_reanalyze = self._repo.list_evaluations(limit=50)

        processed = 0
        for ev in evals_to_reanalyze:
            self.finalize_evaluation(ev.evaluation_id)
            processed += 1

        return {
            "processed_count": processed,
            "reason": reason,
            "status": "COMPLETED",
        }


# Global singleton instance
_service_instance: Optional[ActionEffectivenessService] = None


def get_action_effectiveness_service() -> ActionEffectivenessService:
    """Retrieve global singleton action effectiveness service."""
    global _service_instance
    if _service_instance is None:
        _service_instance = ActionEffectivenessService()
    return _service_instance
