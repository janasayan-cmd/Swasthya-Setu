"""Phase 64: Clinical Safety Risk Handoff Submission Service.

Coordinates submission of pending handoffs to authoritative destination adapters.
"""

from datetime import datetime, timezone
from typing import Optional
from fastapi import status

from app.core.exceptions import AppException, ErrorCode
from app.schemas.safety_risk_handoff import (
    DestinationAcknowledgement,
    HandoffHistoryEntry,
    HandoffLifecycleState,
    SafetyRiskHandoffRecord,
)
from app.services.safety_risk_handoff_adapters import DestinationAdapterRegistry
from app.services.safety_risk_handoff_concurrency_service import (
    SafetyRiskHandoffConcurrencyService,
)


class SafetyRiskHandoffSubmissionService:
    """Orchestrates transmission to downstream destination adapters and records acknowledgements."""

    @classmethod
    def submit_handoff(
        cls,
        handoff: SafetyRiskHandoffRecord,
        actor_id: str,
        actor_role: str,
    ) -> DestinationAcknowledgement:
        """Transmit handoff and record destination acknowledgement."""
        if handoff.state not in (
            HandoffLifecycleState.READY,
            HandoffLifecycleState.CREATED,
            HandoffLifecycleState.SUBMISSION_PENDING,
            HandoffLifecycleState.RETRY_PENDING,
        ):
            raise AppException(
                code=ErrorCode.INVALID_HANDOFF_STATE,
                message=f"Handoff '{handoff.handoff_id}' in state '{handoff.state.value}' cannot be submitted.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        adapter = DestinationAdapterRegistry.get_adapter(handoff.destination_phase)

        # 1. Validate contract & prerequisites
        adapter.validate_request(handoff)

        # 2. Transition to SUBMISSION_PENDING
        prev_state = handoff.state
        handoff.state = HandoffLifecycleState.SUBMISSION_PENDING
        handoff.submitted_at = datetime.now(timezone.utc)

        # 3. Transmit through destination adapter
        try:
            ack = adapter.submit(handoff)
        except AppException:
            handoff.state = HandoffLifecycleState.DESTINATION_UNAVAILABLE
            raise
        except Exception as e:
            handoff.state = HandoffLifecycleState.RETRY_PENDING
            raise AppException(
                code=ErrorCode.DESTINATION_UNAVAILABLE,
                message=f"Transmission to '{handoff.destination_phase.value}' failed: {e}",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # 4. Record explicit acknowledgement
        handoff.acknowledgement = ack
        handoff.state = HandoffLifecycleState.ACKNOWLEDGED
        handoff.acknowledged_at = ack.acknowledged_at
        handoff.follow_up_status = "ACKNOWLEDGED_BY_DESTINATION"

        entry = HandoffHistoryEntry(
            from_state=prev_state,
            to_state=HandoffLifecycleState.ACKNOWLEDGED,
            actor_id=actor_id,
            actor_role=actor_role,
            action="SUBMIT_AND_ACKNOWLEDGE",
            details={
                "destination_phase": handoff.destination_phase.value,
                "workflow_ref": ack.destination_workflow_ref,
            },
        )
        handoff.history.append(entry)
        SafetyRiskHandoffConcurrencyService.increment_version(handoff)

        return ack
