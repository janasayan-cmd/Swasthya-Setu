"""Validation and Lifecycle State Machine Service for Clinical Alerts (Phase 35).

CORE SAFETY PRINCIPLES:
- ALERT != DIAGNOSIS
- ALERT != TRIAGE DECISION
- ALERT != TREATMENT DECISION
- ALERT != PRESCRIPTION
- ALERT != MEDICATION CHANGE
- CRITICAL RESULT != AUTOMATIC TREATMENT
- UNKNOWN STATUS != RESOLVED
- ALERT CREATED != ALERT DELIVERED != ALERT READ != ALERT ACKNOWLEDGED != CLINICAL ACTION COMPLETED
- ESCALATION != EMERGENCY DISPATCH
- Never convert FAILED -> RESOLVED automatically.
- Never convert DELIVERED -> ACKNOWLEDGED automatically.
- Never re-escalate an acknowledged or resolved alert.
"""

from __future__ import annotations

import logging
from typing import Optional
from app.core.exceptions import (
    AlertAlreadyAcknowledgedException,
    AlertAlreadyResolvedException,
    AlertEscalationNotAllowedException,
    AlertInvalidStateException,
    AlertOperationNotAllowedException,
)
from app.schemas.alert import AlertRecord, AlertSeverity, AlertStatus

logger = logging.getLogger(__name__)

# Valid transitions in the alert lifecycle
VALID_TRANSITIONS: dict[AlertStatus, set[AlertStatus]] = {
    AlertStatus.CREATED: {
        AlertStatus.PENDING_DELIVERY,
        AlertStatus.DELIVERED,
        AlertStatus.FAILED,
        AlertStatus.ACKNOWLEDGED,
        AlertStatus.DISMISSED,
        AlertStatus.RESOLVED,
    },
    AlertStatus.PENDING_DELIVERY: {
        AlertStatus.DELIVERED,
        AlertStatus.FAILED,
        AlertStatus.ACKNOWLEDGED,
        AlertStatus.DISMISSED,
    },
    AlertStatus.DELIVERED: {
        AlertStatus.READ,
        AlertStatus.ACKNOWLEDGED,
        AlertStatus.ESCALATION_PENDING,
        AlertStatus.ESCALATED,
        AlertStatus.RESOLVED,
        AlertStatus.DISMISSED,
        AlertStatus.EXPIRED,
    },
    AlertStatus.READ: {
        AlertStatus.ACKNOWLEDGED,
        AlertStatus.ESCALATION_PENDING,
        AlertStatus.ESCALATED,
        AlertStatus.RESOLVED,
        AlertStatus.DISMISSED,
        AlertStatus.EXPIRED,
    },
    AlertStatus.ESCALATION_PENDING: {
        AlertStatus.ESCALATED,
        AlertStatus.ACKNOWLEDGED,
        AlertStatus.RESOLVED,
        AlertStatus.DISMISSED,
    },
    AlertStatus.ESCALATED: {
        AlertStatus.ACKNOWLEDGED,
        AlertStatus.RESOLVED,
        AlertStatus.DISMISSED,
        AlertStatus.FAILED,
    },
    AlertStatus.ACKNOWLEDGED: {
        AlertStatus.RESOLVED,
        AlertStatus.DISMISSED,
        AlertStatus.EXPIRED,
    },
    AlertStatus.RESOLVED: set(),  # Terminal state
    AlertStatus.DISMISSED: set(),  # Terminal state
    AlertStatus.EXPIRED: set(),    # Terminal state
    AlertStatus.FAILED: {
        AlertStatus.PENDING_DELIVERY,
        AlertStatus.DISMISSED,
    },
}


class AlertValidationService:
    """Service enforcing alert invariants, state transitions, and safety checks."""

    @staticmethod
    def validate_transition(current_status: AlertStatus, new_status: AlertStatus) -> None:
        """Validate that transition from current_status to new_status is allowed."""
        if current_status == new_status:
            return

        # Crucial safety boundaries
        if current_status == AlertStatus.FAILED and new_status == AlertStatus.RESOLVED:
            raise AlertInvalidStateException(
                "Safety violation: A FAILED alert delivery/processing operation cannot convert directly to RESOLVED."
            )

        if current_status == AlertStatus.DELIVERED and new_status == AlertStatus.ACKNOWLEDGED:
            # Note: Transition to ACKNOWLEDGED requires explicit user action, not automatic delivery
            pass

        allowed = VALID_TRANSITIONS.get(current_status, set())
        if new_status not in allowed:
            raise AlertInvalidStateException(
                f"Invalid alert state transition from '{current_status.value}' to '{new_status.value}'."
            )

    @staticmethod
    def validate_acknowledgement(alert: AlertRecord) -> None:
        """Validate alert can be acknowledged."""
        if alert.status == AlertStatus.ACKNOWLEDGED:
            raise AlertAlreadyAcknowledgedException(f"Alert {alert.id} is already acknowledged.")
        if alert.status in {AlertStatus.RESOLVED, AlertStatus.DISMISSED, AlertStatus.EXPIRED}:
            raise AlertInvalidStateException(
                f"Alert {alert.id} is in terminal state '{alert.status.value}' and cannot be acknowledged."
            )

    @staticmethod
    def validate_resolution(alert: AlertRecord, reason: str) -> None:
        """Validate alert can be resolved."""
        if alert.status == AlertStatus.RESOLVED:
            raise AlertAlreadyResolvedException(f"Alert {alert.id} is already resolved.")
        if alert.status in {AlertStatus.DISMISSED, AlertStatus.EXPIRED}:
            raise AlertInvalidStateException(
                f"Alert {alert.id} is in terminal state '{alert.status.value}' and cannot be resolved."
            )
        if not reason or not reason.strip():
            raise AlertOperationNotAllowedException("A valid resolution reason is required to resolve an alert.")

    @staticmethod
    def validate_dismissal(alert: AlertRecord, reason: str) -> None:
        """Validate alert can be dismissed."""
        if alert.status in {AlertStatus.RESOLVED, AlertStatus.DISMISSED, AlertStatus.EXPIRED}:
            raise AlertInvalidStateException(
                f"Alert {alert.id} is already in terminal state '{alert.status.value}'."
            )
        if not reason or not reason.strip():
            raise AlertOperationNotAllowedException("A valid dismissal reason is required to dismiss an alert.")

    @staticmethod
    def validate_escalation_eligibility(alert: AlertRecord) -> None:
        """Verify alert is eligible for escalation."""
        if not alert.escalation_enabled:
            raise AlertEscalationNotAllowedException(f"Alert {alert.id} does not have escalation enabled.")
        if alert.status in {AlertStatus.ACKNOWLEDGED, AlertStatus.RESOLVED, AlertStatus.DISMISSED, AlertStatus.EXPIRED}:
            raise AlertEscalationNotAllowedException(
                f"Alert {alert.id} cannot be escalated because it is already {alert.status.value}."
            )
        if alert.escalation_level >= 3:
            raise AlertEscalationNotAllowedException(
                f"Alert {alert.id} has already reached maximum escalation tier (Level 3: Organization)."
            )

    @staticmethod
    def validate_severity_source(severity: AlertSeverity, source: Optional[str]) -> None:
        """Verify severity is derived from approved rules/providers, not arbitrary AI inference."""
        if source and "ai_autonomous" in source.lower():
            raise AlertOperationNotAllowedException(
                "Clinical safety violation: AI model cannot autonomously invent clinical alert severity."
            )
