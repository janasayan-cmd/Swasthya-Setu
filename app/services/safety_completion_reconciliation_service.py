"""Phase 65: Safety Completion Reconciliation Service.

Reconciles updated destination outcomes and follow-up references.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.schemas.safety_workflow_completion import (
    CompletionLifecycleState,
    SafetyWorkflowCompletionRecord,
)
from app.services.safety_completion_followup_service import SafetyCompletionFollowUpService
from app.services.safety_completion_outcome_service import SafetyCompletionOutcomeService
from app.services.safety_completion_package_service import SafetyCompletionPackageService
from app.services.safety_completion_readiness_service import SafetyCompletionReadinessService
from app.services.safety_completion_requirement_service import SafetyCompletionRequirementService


class SafetyCompletionReconciliationService:
    """Orchestrates reconciliation of updated outcomes and follow-up obligations."""

    @staticmethod
    def reconcile(
        completion: SafetyWorkflowCompletionRecord,
        disposition: Any,
        handoffs: List[Any],
    ) -> SafetyWorkflowCompletionRecord:
        """Refresh outcomes, follow-ups, requirements, and recalculate readiness."""
        # 1. Refresh requirements
        reqs = SafetyCompletionRequirementService.aggregate_requirements(
            completion_id=completion.completion_id,
            disposition=disposition,
            handoffs=handoffs,
            policy_version=completion.applicable_policy_version,
        )
        completion.requirements = [r.model_dump() for r in reqs]

        # 2. Refresh outcomes
        outcomes = SafetyCompletionOutcomeService.verify_handoff_outcomes(
            completion_id=completion.completion_id,
            handoffs=handoffs,
        )
        completion.outcomes = [o.model_dump() for o in outcomes]

        # 3. Refresh follow-ups
        fups = SafetyCompletionFollowUpService.aggregate_follow_ups(
            completion_id=completion.completion_id,
            disposition=disposition,
            handoffs=handoffs,
        )
        completion.follow_ups = [f.model_dump() for f in fups]

        # 4. Recalculate readiness
        readiness = SafetyCompletionReadinessService.evaluate(
            completion_id=completion.completion_id,
            disposition=disposition,
            handoffs=handoffs,
            requirements=reqs,
            outcomes=outcomes,
            follow_ups=fups,
            source_revision=completion.source_revision,
            policy_version=completion.applicable_policy_version,
        )
        completion.readiness_state = readiness.readiness_state.value
        completion.blockers = readiness.blockers
        completion.limitations = readiness.limitations
        completion.evaluated_at = readiness.evaluated_at

        # 5. If not already closed, update lifecycle state
        if completion.state not in (
            CompletionLifecycleState.CLOSED,
            CompletionLifecycleState.POST_CLOSURE_MONITORING,
            CompletionLifecycleState.REOPENED,
        ):
            if readiness.readiness_state.value == "READY":
                completion.state = CompletionLifecycleState.READY
            elif readiness.readiness_state.value == "READY_WITH_LIMITATIONS":
                completion.state = CompletionLifecycleState.READY_WITH_LIMITATIONS
            elif readiness.readiness_state.value == "BLOCKED":
                completion.state = CompletionLifecycleState.BLOCKED
            else:
                completion.state = CompletionLifecycleState.NOT_READY

        # 6. Regenerate package
        pkg = SafetyCompletionPackageService.generate_package(
            completion=completion,
            disposition=disposition,
            handoffs=handoffs,
            readiness=readiness,
        )
        completion.completion_package = pkg.model_dump()
        completion.version += 1
        completion.updated_at = datetime.now(timezone.utc)

        return completion
