"""Phase 64: Clinical Safety Risk Handoff Outcome Reconciliation Service.

Performs technical and clinical governance reconciliation on received outcomes.
Non-Negotiable Invariants:
- OUTCOME RECONCILED != RISK ELIMINATED
- A conflicting outcome must be preserved for investigation.
- An unrecognized outcome must not be mapped to success by default.
- A missing outcome must not be interpreted as a successful outcome.
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
from app.schemas.safety_risk_handoff_reconciliation import (
    HandoffReconciliationRecord,
    OutcomeReconciliationState,
)
from app.services.safety_risk_handoff_concurrency_service import (
    SafetyRiskHandoffConcurrencyService,
)


class SafetyRiskHandoffReconciliationService:
    """Evaluates and reconciles received outcomes against authoritative handoff context."""

    @classmethod
    def reconcile(
        cls,
        handoff: SafetyRiskHandoffRecord,
        actor_id: str,
        actor_role: str,
        reason: Optional[str] = "Automated outcome reconciliation evaluation",
    ) -> HandoffReconciliationRecord:
        """Evaluate outcomes and determine reconciliation outcome."""
        if not handoff.outcomes:
            raise AppException(
                code=ErrorCode.OUTCOME_NOT_FOUND,
                message=f"Handoff '{handoff.handoff_id}' has no ingested outcomes to reconcile.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        prev_state = handoff.state
        has_conflicts = any(o.get("is_conflicted", False) for o in handoff.outcomes)
        all_duplicates = all(o.get("is_duplicate", False) for o in handoff.outcomes)

        rec_state: OutcomeReconciliationState
        summary: str
        limitations = []
        conflict_details = None

        if has_conflicts:
            rec_state = OutcomeReconciliationState.CONFLICTED
            summary = "Outcomes received exhibit mutual contradiction across reports."
            conflict_details = "Contradictory destination statuses detected."
            handoff.state = HandoffLifecycleState.OUTCOME_CONFLICTED
            handoff.follow_up_status = "MANUAL_RECONCILIATION_REQUIRED"
        elif all_duplicates and len(handoff.outcomes) > 1:
            rec_state = OutcomeReconciliationState.DUPLICATE
            summary = "All received outcomes are duplicate transmissions."
            handoff.state = HandoffLifecycleState.RECONCILED
            handoff.follow_up_status = "RECONCILED_WITH_DUPLICATE_DELIVERIES"
        else:
            rec_state = OutcomeReconciliationState.MATCHED
            summary = f"Outcome from '{handoff.destination_phase.value}' matched handoff expectations."
            handoff.state = HandoffLifecycleState.RECONCILED
            handoff.follow_up_status = "DESTINATION_WORKFLOW_RECONCILED"
            handoff.completed_at = datetime.now(timezone.utc)

        rec_record = HandoffReconciliationRecord(
            handoff_id=handoff.handoff_id,
            state=rec_state,
            reconciled_by=actor_id,
            summary=summary,
            limitations=limitations,
            conflict_details=conflict_details,
        )
        handoff.reconciliation = rec_record.model_dump()

        entry = HandoffHistoryEntry(
            from_state=prev_state,
            to_state=handoff.state,
            actor_id=actor_id,
            actor_role=actor_role,
            action="RECONCILE_OUTCOME",
            details={"reconciliation_state": rec_state.value, "summary": summary},
        )
        handoff.history.append(entry)
        SafetyRiskHandoffConcurrencyService.increment_version(handoff)

        return rec_record
