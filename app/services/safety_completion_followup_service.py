"""Phase 65: Safety Completion Follow-up Obligation Service.

Aggregates, tracks, and reconciles follow-up obligations attached to coordination workflows.
Critical Invariants:
- A waiver is valid ONLY when authorized policy explicitly permits it.
- NO auto-waiver on timeout, failure, or absence of response.
- Follow-up NOT satisfied merely because a request was accepted.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from fastapi import status

from app.core.exceptions import AppException, ErrorCode
from app.schemas.safety_completion_followup import (
    FollowUpObligationRecord,
    FollowUpStatus,
)
from app.schemas.safety_risk_disposition import RiskDispositionRecord
from app.schemas.safety_risk_handoff import SafetyRiskHandoffRecord


class SafetyCompletionFollowUpService:
    """Aggregates and reconciles follow-up obligations across authoritative phases."""

    @staticmethod
    def aggregate_follow_ups(
        completion_id: str,
        disposition: RiskDispositionRecord,
        handoffs: List[SafetyRiskHandoffRecord],
    ) -> List[FollowUpObligationRecord]:
        """Collect follow-up obligations from Phase 63 disposition and Phase 64 handoffs."""
        follow_ups: List[FollowUpObligationRecord] = []

        # Follow-ups defined on handoffs
        for handoff in handoffs:
            if handoff.follow_up_status and handoff.follow_up_status != "NONE":
                dest_str = handoff.destination_phase.value if hasattr(handoff.destination_phase, "value") else str(handoff.destination_phase)
                is_satisfied = handoff.state.value == "COMPLETED"

                follow_ups.append(
                    FollowUpObligationRecord(
                        completion_id=completion_id,
                        originating_phase="PHASE_64",
                        originating_ref=handoff.handoff_id,
                        destination_phase=dest_str,
                        description=f"Follow-up obligation from handoff to {dest_str}: {handoff.follow_up_status}",
                        status=FollowUpStatus.SATISFIED if is_satisfied else FollowUpStatus.PENDING,
                        is_mandatory=True,
                    )
                )

        return follow_ups

    @staticmethod
    def apply_authorized_waiver(
        follow_up: FollowUpObligationRecord,
        waiver_reason: str,
        waived_by: str,
        waiver_policy_reference: str,
        is_policy_permitted: bool,
    ) -> FollowUpObligationRecord:
        """Apply an explicit, policy-permitted waiver to an obligation."""
        if not is_policy_permitted:
            raise AppException(
                code=ErrorCode.COMPLETION_BLOCKED,
                message="Waiver rejected: Authoritative completion policy does not permit waiving this obligation.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        if not waiver_reason or not waiver_reason.strip():
            raise AppException(
                code=ErrorCode.COMPLETION_BLOCKED,
                message="Waiver rejected: Explicit, documented rationale is mandatory.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        follow_up.status = FollowUpStatus.WAIVED_BY_AUTHORIZED_POLICY
        follow_up.waiver_reason = waiver_reason
        follow_up.waived_by = waived_by
        follow_up.waived_at = datetime.now(timezone.utc)
        follow_up.waiver_policy_reference = waiver_policy_reference
        follow_up.updated_at = datetime.now(timezone.utc)
        return follow_up
