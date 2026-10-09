"""Phase 64: Clinical Safety Risk Handoff Escalation Service.

Manages human operational escalation and controlled cancellation.
"""

from typing import Optional
from fastapi import status

from app.core.exceptions import AppException, ErrorCode
from app.schemas.safety_risk_handoff import (
    HandoffHistoryEntry,
    HandoffLifecycleState,
    SafetyRiskHandoffRecord,
)
from app.services.safety_risk_handoff_adapters import DestinationAdapterRegistry
from app.services.safety_risk_handoff_concurrency_service import (
    SafetyRiskHandoffConcurrencyService,
)


class SafetyRiskHandoffEscalationService:
    """Escalates unresolved operational handoffs to human governance."""

    @classmethod
    def escalate(
        cls,
        handoff: SafetyRiskHandoffRecord,
        reason: str,
        actor_id: str,
        actor_role: str,
        severity: str = "HIGH",
    ) -> SafetyRiskHandoffRecord:
        """Escalate an unresolved operational handoff to manual review."""
        prev_state = handoff.state
        handoff.state = HandoffLifecycleState.MANUAL_REVIEW_REQUIRED
        handoff.escalation_reason = reason
        handoff.follow_up_status = f"ESCALATED_{severity}_OPERATIONAL_REVIEW"

        entry = HandoffHistoryEntry(
            from_state=prev_state,
            to_state=HandoffLifecycleState.MANUAL_REVIEW_REQUIRED,
            actor_id=actor_id,
            actor_role=actor_role,
            action="ESCALATE_HANDOFF",
            details={"severity": severity, "reason": reason},
        )
        handoff.history.append(entry)
        SafetyRiskHandoffConcurrencyService.increment_version(handoff)

        return handoff

    @classmethod
    def cancel(
        cls,
        handoff: SafetyRiskHandoffRecord,
        reason: str,
        actor_id: str,
        actor_role: str,
    ) -> SafetyRiskHandoffRecord:
        """Cancel handoff if permitted by destination contract."""
        adapter = DestinationAdapterRegistry.get_adapter(handoff.destination_phase)
        if not adapter.supports_cancellation():
            raise AppException(
                code=ErrorCode.CANCELLATION_NOT_SUPPORTED,
                message=f"Destination '{handoff.destination_phase.value}' does not support workflow cancellation.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        if handoff.state in (HandoffLifecycleState.COMPLETED, HandoffLifecycleState.RECONCILED):
            raise AppException(
                code=ErrorCode.CANCELLATION_NOT_ALLOWED,
                message=f"Handoff '{handoff.handoff_id}' has already been completed or reconciled and cannot be cancelled.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        prev_state = handoff.state
        handoff.state = HandoffLifecycleState.CANCELLED
        handoff.follow_up_status = "HANDOFF_CANCELLED"

        entry = HandoffHistoryEntry(
            from_state=prev_state,
            to_state=HandoffLifecycleState.CANCELLED,
            actor_id=actor_id,
            actor_role=actor_role,
            action="CANCEL_HANDOFF",
            details={"reason": reason},
        )
        handoff.history.append(entry)
        SafetyRiskHandoffConcurrencyService.increment_version(handoff)

        return handoff
