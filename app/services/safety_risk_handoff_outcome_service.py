"""Phase 64: Clinical Safety Risk Handoff Outcome Service.

Ingests and validates authoritative outcomes reported by downstream destination workflows.
"""

from datetime import datetime, timezone
from typing import Optional
from fastapi import status

from app.core.exceptions import AppException, ErrorCode
from app.schemas.safety_risk_handoff import (
    HandoffHistoryEntry,
    HandoffLifecycleState,
    SafetyRiskHandoffRecord,
)
from app.schemas.safety_risk_handoff_outcome import (
    HandoffOutcomeRecord,
    IngestOutcomeRequest,
)
from app.services.safety_risk_handoff_concurrency_service import (
    SafetyRiskHandoffConcurrencyService,
)


class SafetyRiskHandoffOutcomeService:
    """Ingests, validates, and records outcomes from destination phases."""

    @classmethod
    def ingest_outcome(
        cls,
        handoff: SafetyRiskHandoffRecord,
        request: IngestOutcomeRequest,
        actor_id: str,
        actor_role: str,
    ) -> HandoffOutcomeRecord:
        """Ingest outcome payload into handoff record."""
        if not request.destination_workflow_ref:
            raise AppException(
                code=ErrorCode.OUTCOME_INVALID,
                message="Destination workflow reference is required to ingest outcome.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        if not request.provenance or len(request.provenance.strip()) < 3:
            raise AppException(
                code=ErrorCode.OUTCOME_PROVENANCE_INVALID,
                message="Valid provenance reference is required for destination outcome.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Check for duplicate delivery
        is_duplicate = any(
            o.get("destination_workflow_ref") == request.destination_workflow_ref
            and o.get("outcome_status") == request.outcome_status
            for o in handoff.outcomes
        )

        # Check for conflict with previously ingested outcomes
        is_conflicted = any(
            o.get("outcome_status") != request.outcome_status
            and not is_duplicate
            for o in handoff.outcomes
        )

        outcome_rec = HandoffOutcomeRecord(
            handoff_id=handoff.handoff_id,
            destination_phase=handoff.destination_phase,
            destination_workflow_ref=request.destination_workflow_ref,
            outcome_type=request.outcome_type,
            outcome_status=request.outcome_status,
            revision=request.revision or "v1.0.0",
            provenance=request.provenance,
            is_duplicate=is_duplicate,
            is_conflicted=is_conflicted,
            payload=request.payload or {},
        )

        handoff.outcomes.append(outcome_rec.model_dump())

        prev_state = handoff.state
        if is_conflicted:
            handoff.state = HandoffLifecycleState.OUTCOME_CONFLICTED
            handoff.follow_up_status = "OUTCOME_CONFLICT_INVESTIGATION"
        elif is_duplicate:
            # Duplicate outcome does not re-advance lifecycle
            pass
        else:
            handoff.state = HandoffLifecycleState.OUTCOME_RECEIVED
            handoff.follow_up_status = "OUTCOME_PENDING_RECONCILIATION"

        entry = HandoffHistoryEntry(
            from_state=prev_state,
            to_state=handoff.state,
            actor_id=actor_id,
            actor_role=actor_role,
            action="INGEST_OUTCOME",
            details={
                "outcome_id": outcome_rec.outcome_id,
                "status": request.outcome_status,
                "is_duplicate": is_duplicate,
                "is_conflicted": is_conflicted,
            },
        )
        handoff.history.append(entry)
        SafetyRiskHandoffConcurrencyService.increment_version(handoff)

        return outcome_rec
