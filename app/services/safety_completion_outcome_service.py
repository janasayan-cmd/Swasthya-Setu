"""Phase 65: Safety Completion Outcome Service.

Verifies authoritative cross-phase destination outcomes and reconciliation states.
Critical Rule:
Transport-level ACK != Destination Completion.
Generic HTTP 200 SUCCESS != Destination Workflow Completed.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from app.schemas.safety_completion_outcome import (
    CompletionOutcomeReference,
    OutcomeVerificationStatus,
)
from app.schemas.safety_risk_handoff import SafetyRiskHandoffRecord


class SafetyCompletionOutcomeService:
    """Verifies downstream outcomes against authoritative terminal state contracts."""

    # Explicit terminal states recognized across Phase 49-62 destinations
    VALID_TERMINAL_DESTINATION_STATES = {
        "INCIDENT_INVESTIGATED",
        "INCIDENT_RESOLVED",
        "INCIDENT_CLOSED",
        "LEARNING_ACTION_FINALIZED",
        "GOVERNANCE_DECISION_RECORDED",
        "ASSURANCE_REVIEW_COMPLETED",
        "SAFETY_ACTION_IMPLEMENTED",
        "EFFECTIVENESS_EVALUATED",
        "IMPROVEMENT_CHANGE_VERIFIED",
        "MONITORING_REGISTERED",
        "REASSESSMENT_COMPLETED",
        "COMPLETED",
    }

    @staticmethod
    def verify_handoff_outcomes(
        completion_id: str,
        handoffs: List[SafetyRiskHandoffRecord],
    ) -> List[CompletionOutcomeReference]:
        """Examine Phase 64 handoffs and extract verified outcome references."""
        outcome_refs: List[CompletionOutcomeReference] = []

        for handoff in handoffs:
            dest_str = handoff.destination_phase.value if hasattr(handoff.destination_phase, "value") else str(handoff.destination_phase)

            # Check if handoff has outcomes ingested and reconciled
            has_outcomes = len(handoff.outcomes) > 0
            latest_outcome = handoff.outcomes[-1] if has_outcomes else None
            reconciliation = handoff.reconciliation

            dest_status = "UNKNOWN"
            is_terminal = False
            ver_status = OutcomeVerificationStatus.PENDING_DESTINATION
            blockers: List[str] = []

            if latest_outcome:
                dest_status = latest_outcome.get("authoritative_destination_status", "UNKNOWN")
                dest_wf_ref = latest_outcome.get("destination_workflow_ref", handoff.acknowledgement.destination_workflow_ref if handoff.acknowledgement else "unassigned")
                is_terminal = latest_outcome.get("is_terminal", False) or (dest_status in SafetyCompletionOutcomeService.VALID_TERMINAL_DESTINATION_STATES)

                if reconciliation and reconciliation.get("state") == "MATCHED":
                    if is_terminal:
                        ver_status = OutcomeVerificationStatus.VERIFIED_TERMINAL
                    else:
                        ver_status = OutcomeVerificationStatus.PENDING_DESTINATION
                        blockers.append(f"Outcome received from {dest_str} but not yet in terminal state (current: {dest_status}).")
                elif reconciliation and reconciliation.get("state") == "CONFLICTED":
                    ver_status = OutcomeVerificationStatus.CONFLICTED
                    blockers.append(f"Outcome conflict detected in destination {dest_str}.")
                else:
                    ver_status = OutcomeVerificationStatus.PENDING_DESTINATION
            elif handoff.acknowledgement:
                # Only ACK received, NOT completed
                dest_status = handoff.acknowledgement.status
                dest_wf_ref = handoff.acknowledgement.destination_workflow_ref
                ver_status = OutcomeVerificationStatus.PENDING_DESTINATION
                blockers.append(f"Handoff to {dest_str} acknowledged, but terminal outcome is still pending.")
            else:
                dest_wf_ref = "none"
                blockers.append(f"No acknowledgement or outcome received from {dest_str}.")

            outcome_refs.append(
                CompletionOutcomeReference(
                    completion_id=completion_id,
                    originating_handoff_id=handoff.handoff_id,
                    destination_phase=dest_str,
                    destination_workflow_ref=dest_wf_ref,
                    authoritative_destination_status=dest_status,
                    verification_status=ver_status,
                    is_terminal=is_terminal,
                    is_reconciled=bool(reconciliation and reconciliation.get("state") == "MATCHED"),
                    blockers=blockers,
                    provenance="PHASE_64_OUTCOME_SERVICE",
                    verified_at=datetime.now(timezone.utc),
                )
            )

        return outcome_refs
