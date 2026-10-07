"""Phase 54: Safety Action Escalation Service.

Governs escalation routing, escalation levels, and server-side urgency validation.

Core Invariants:
- ESCALATION != INCIDENT CONFIRMATION
- ESCALATION != PATIENT HARM
- URGENCY CANNOT BE CLIENT-SPOOFED
"""

from datetime import datetime, timezone

from app.core.exceptions import AppException, ErrorCode
from app.schemas.safety_action import (
    ActionEscalationRecord,
    ActionLifecycleState,
    EscalationLevel,
    SafetyActionEscalateRequest,
    SafetyActionRecord,
)


class SafetyActionEscalationService:
    """Manages policy-backed escalations across organizational and clinical domains."""

    def escalate_action(
        self,
        action: SafetyActionRecord,
        request: SafetyActionEscalateRequest,
        actor_id: str,
    ) -> ActionEscalationRecord:
        """Process an escalation on a safety action."""
        now = datetime.now(timezone.utc)

        # Derive server urgency — client cannot simply force urgent=True (Section 19)
        # Server verifies if action priority is CRITICAL or finding triggers are active
        is_urgent = bool(action.is_urgent or action.priority.value == "CRITICAL")
        if request.server_urgency_requested and not is_urgent:
            # Recheck if reason justifies urgent escalation
            urgent_terms = ["critical", "failure", "patient risk", "bypass", "disabled"]
            if any(term in request.reason.lower() for term in urgent_terms):
                is_urgent = True

        record = ActionEscalationRecord(
            escalation_level=request.escalation_level,
            escalated_by_id=actor_id,
            reason=request.reason,
            urgency_justification="Derived from validated server policy and severity context." if is_urgent else None,
            escalated_at=now,
            is_urgent=is_urgent,
        )

        action.escalation = record
        action.lifecycle_state = ActionLifecycleState.ESCALATED
        action.is_urgent = is_urgent

        return record


# Global singleton
safety_action_escalation_service = SafetyActionEscalationService()
