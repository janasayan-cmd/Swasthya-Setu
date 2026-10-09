"""Phase 64: Clinical Safety Risk Handoff Retry Service.

Manages bounded retry scheduling and failure recovery for handoffs.
Non-Negotiable Invariants:
- RETRY != DUPLICATE AUTHORIZATION
- Do not retry indefinitely.
- Do not retry authorization or contract incompatibilities as transient errors.
"""

from typing import Optional
from fastapi import status

from app.core.exceptions import AppException, ErrorCode
from app.schemas.safety_risk_handoff import (
    HandoffHistoryEntry,
    HandoffLifecycleState,
    SafetyRiskHandoffRecord,
)
from app.services.safety_risk_handoff_concurrency_service import (
    SafetyRiskHandoffConcurrencyService,
)


class SafetyRiskHandoffRetryService:
    """Orchestrates bounded retry execution and prevents runaway replay loops."""

    @classmethod
    def schedule_retry(
        cls,
        handoff: SafetyRiskHandoffRecord,
        reason: str,
        actor_id: str,
        actor_role: str,
    ) -> SafetyRiskHandoffRecord:
        """Evaluate retry eligibility and transition handoff to RETRY_PENDING or RETRY_EXHAUSTED."""
        non_retryable_states = {
            HandoffLifecycleState.COMPLETED,
            HandoffLifecycleState.RECONCILED,
            HandoffLifecycleState.CANCELLED,
            HandoffLifecycleState.SOURCE_SUPERSEDED,
        }
        if handoff.state in non_retryable_states:
            raise AppException(
                code=ErrorCode.RETRY_NOT_ALLOWED,
                message=f"Handoff '{handoff.handoff_id}' in state '{handoff.state.value}' cannot be retried.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        if handoff.retry_count >= handoff.max_retries:
            handoff.state = HandoffLifecycleState.RETRY_EXHAUSTED
            handoff.follow_up_status = "RETRY_LIMIT_EXHAUSTED_MANUAL_INTERVENTION_REQUIRED"
            raise AppException(
                code=ErrorCode.RETRY_EXHAUSTED,
                message=f"Handoff '{handoff.handoff_id}' exceeded maximum retry threshold ({handoff.max_retries}).",
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        prev_state = handoff.state
        handoff.retry_count += 1
        handoff.state = HandoffLifecycleState.RETRY_PENDING
        handoff.follow_up_status = f"RETRY_ATTEMPT_{handoff.retry_count}_QUEUED"

        entry = HandoffHistoryEntry(
            from_state=prev_state,
            to_state=HandoffLifecycleState.RETRY_PENDING,
            actor_id=actor_id,
            actor_role=actor_role,
            action="SCHEDULE_RETRY",
            details={
                "attempt": handoff.retry_count,
                "max_retries": handoff.max_retries,
                "reason": reason,
            },
        )
        handoff.history.append(entry)
        SafetyRiskHandoffConcurrencyService.increment_version(handoff)

        return handoff
