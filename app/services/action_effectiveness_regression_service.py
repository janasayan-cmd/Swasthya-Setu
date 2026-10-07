"""Phase 55: Action Effectiveness Regression Detection Service.

Monitors sustained effectiveness after initial acceptance and detects control regressions.
Preserves both historical acceptance and regressed state.
Enforces the distinction: Regression is a finding, NOT automatically patient harm or an incident.
"""

from datetime import datetime, timezone
from typing import List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.schemas.action_effectiveness import (
    EffectivenessEvaluationRecord,
    EffectivenessLifecycleState,
    EffectivenessState,
    ExpectedVsObservedComparison,
)


class ActionEffectivenessRegressionService:
    """Service for detecting post-acceptance control degradation and regression."""

    def evaluate_regression(
        self,
        evaluation: EffectivenessEvaluationRecord,
        new_comparisons: List[ExpectedVsObservedComparison],
    ) -> bool:
        """Check if newly observed performance fails previously conforming criteria."""
        has_prior_acceptance = evaluation.is_sustained or any(
            r.decision in (HumanReviewOutcome.ACCEPT, HumanReviewOutcome.ACCEPT_WITH_LIMITATIONS)
            for r in evaluation.reviews
        )
        if not has_prior_acceptance and evaluation.lifecycle_state not in (
            EffectivenessLifecycleState.EFFECTIVENESS_ACCEPTED,
            EffectivenessLifecycleState.MONITORING,
            EffectivenessLifecycleState.SUSTAINED_VALIDATION,
            EffectivenessLifecycleState.CLOSED,
        ):
            # Not in sustained monitoring stage
            return False

        # If any criterion was previously conforming and now fails
        has_new_failure = any(not c.is_conforming for c in new_comparisons)
        if has_new_failure:
            evaluation.regression_detected = True
            evaluation.is_sustained = False
            evaluation.effectiveness_state = EffectivenessState.REGRESSED
            evaluation.lifecycle_state = EffectivenessLifecycleState.REGRESSED
            evaluation.version += 1
            evaluation.updated_at = datetime.now(timezone.utc)
            return True

        return False
