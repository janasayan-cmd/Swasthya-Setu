"""Phase 56: Safety Improvement Classification Service.

Interprets post-action effectiveness outcomes and derives policy-driven improvement signals and responses.
Enforces:
- EFFECTIVENESS RESULT != CHANGE REQUEST
- EFFECTIVE_CONTROL does NOT automatically trigger changes
- REGRESSION != CONFIRMED INCIDENT
- Response paths are strictly policy-driven.
"""

from typing import Tuple

from app.core.exceptions import AppException, ErrorCode
from app.schemas.action_effectiveness import (
    EffectivenessEvaluationRecord,
    EffectivenessState,
)
from app.schemas.safety_improvement import (
    ImprovementPriority,
    ImprovementResponseType,
    ImprovementSignalType,
)


class SafetyImprovementClassificationService:
    """Service for classifying continuous improvement signals and responses."""

    def classify_from_evaluation(
        self,
        evaluation: EffectivenessEvaluationRecord,
        prior_recurrence_count: int = 0,
    ) -> Tuple[ImprovementSignalType, ImprovementResponseType, ImprovementPriority, bool, bool]:
        """Derive signal type, response type, priority, is_regression, and is_recurring."""
        eff_state = evaluation.effectiveness_state
        is_regression = evaluation.regression_detected or (eff_state == EffectivenessState.REGRESSED)
        is_recurring = prior_recurrence_count > 1 or (evaluation.reopened_count > 1)

        # 1. Regression takes high precedence
        if is_regression:
            signal = ImprovementSignalType.CONTROL_REGRESSION
            response = ImprovementResponseType.ESCALATE if is_recurring else ImprovementResponseType.REASSESS
            priority = ImprovementPriority.CRITICAL if is_recurring else ImprovementPriority.HIGH
            return signal, response, priority, True, is_recurring

        # 2. Recurring failure
        if is_recurring and eff_state in (
            EffectivenessState.FAILED,
            EffectivenessState.NO_CLEAR_IMPROVEMENT,
            EffectivenessState.DEGRADED,
        ):
            signal = ImprovementSignalType.RECURRING_FAILURE
            response = ImprovementResponseType.REQUEST_RISK_REASSESSMENT
            priority = ImprovementPriority.HIGH
            return signal, response, priority, False, True

        # 3. Effective control -> Continue monitoring or no change
        if eff_state == EffectivenessState.EFFECTIVE_OBSERVED:
            signal = ImprovementSignalType.EFFECTIVE_CONTROL
            response = ImprovementResponseType.CONTINUE_MONITORING if not evaluation.is_sustained else ImprovementResponseType.NO_CHANGE_REQUIRED
            priority = ImprovementPriority.LOW
            return signal, response, priority, False, False

        # 4. Partial effectiveness
        if eff_state == EffectivenessState.PARTIALLY_EFFECTIVE:
            signal = ImprovementSignalType.PARTIAL_EFFECTIVENESS
            response = ImprovementResponseType.CREATE_REVIEW
            priority = ImprovementPriority.MEDIUM
            return signal, response, priority, False, is_recurring

        # 5. No clear improvement or failed
        if eff_state in (EffectivenessState.NO_CLEAR_IMPROVEMENT, EffectivenessState.DEGRADED):
            signal = ImprovementSignalType.NO_CLEAR_IMPROVEMENT
            response = ImprovementResponseType.REASSESS
            priority = ImprovementPriority.MEDIUM
            return signal, response, priority, False, is_recurring

        if eff_state == EffectivenessState.FAILED:
            signal = ImprovementSignalType.INEFFECTIVE_ACTION
            response = ImprovementResponseType.CREATE_CHANGE_REQUEST if is_recurring else ImprovementResponseType.REASSESS
            priority = ImprovementPriority.HIGH
            return signal, response, priority, False, is_recurring

        # 6. Insufficient evidence / Unclear
        if eff_state in (EffectivenessState.INSUFFICIENT_EVIDENCE, EffectivenessState.EVIDENCE_PENDING):
            signal = ImprovementSignalType.EVIDENCE_GAP
            response = ImprovementResponseType.COLLECT_MORE_EVIDENCE
            priority = ImprovementPriority.LOW
            return signal, response, priority, False, False

        # Fallback
        signal = ImprovementSignalType.UNEXPECTED_BEHAVIOR
        response = ImprovementResponseType.COLLECT_MORE_EVIDENCE
        priority = ImprovementPriority.MEDIUM
        return signal, response, priority, False, False

    def validate_classification_policy(
        self,
        signal_type: ImprovementSignalType,
        response_type: ImprovementResponseType,
    ) -> None:
        """Ensure client cannot force arbitrary responses contradicting safety policy."""
        # An effective control cannot directly spawn an unverified change request without evidence
        if signal_type == ImprovementSignalType.EFFECTIVE_CONTROL and response_type == ImprovementResponseType.CREATE_CHANGE_REQUEST:
            raise AppException(
                code=ErrorCode.CHANGE_NOT_ALLOWED,
                message="Effective controls cannot trigger change requests without evidence of degradation or regression.",
                status_code=400,
            )

        # Missing evidence cannot trigger an immediate change request
        if signal_type == ImprovementSignalType.EVIDENCE_GAP and response_type == ImprovementResponseType.CREATE_CHANGE_REQUEST:
            raise AppException(
                code=ErrorCode.EVIDENCE_INSUFFICIENT,
                message="Evidence gaps require evidence collection before proposing safety changes.",
                status_code=400,
            )
