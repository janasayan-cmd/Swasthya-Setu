"""Decision Validation Service (Phase 47).

Enforces:
- Clinical safety boundaries (AI output != clinical decision, suggestion != approval)
- Prevention of autonomous clinical execution (diagnosis, prescription, triage authority)
- Decision state transition validity
- Expiration and supersession checks
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any, Dict, Optional

from app.core.exceptions import (
    AIClinicalActionProhibitedException,
    AutonomousDecisionExecutionProhibitedException,
    DecisionAlreadyReviewedException,
    DecisionAlreadySupersededException,
    DecisionExpiredException,
    DecisionInvalidStateException,
    DecisionNotApprovedException,
)
from app.schemas.decision_review import ReviewAction
from app.schemas.decisions import DecisionRecord, DecisionStatus, DecisionType

logger = logging.getLogger(__name__)


class DecisionValidationService:
    """Validates decision transitions, actor authority, and clinical safety boundaries."""

    @staticmethod
    def validate_safety_boundaries(
        decision_type: DecisionType,
        initiating_actor_role: str,
        attempted_action: str = "EXECUTE",
    ) -> None:
        """Enforce TRD Sec 1 & 16: AI outputs and system suggestions cannot become direct clinical actions."""
        normalized_role = (initiating_actor_role or "").upper()

        # Rule 1: AI cannot directly diagnose, prescribe, triage, or alter clinical truth
        ai_restricted_types = {
            DecisionType.AI_SUMMARY,
            DecisionType.AI_EXTRACTION,
            DecisionType.AI_CLASSIFICATION,
        }
        if normalized_role in {"AI", "AI_AGENT", "BOT", "SYSTEM_AI"} or decision_type in ai_restricted_types:
            if attempted_action in {"AUTONOMOUS_PRESCRIBE", "AUTONOMOUS_DIAGNOSE", "AUTONOMOUS_APPLY"}:
                raise AIClinicalActionProhibitedException(
                    f"AI outputs for {decision_type.value} cannot autonomously execute clinical actions. "
                    "Human clinician review is mandatory."
                )

    @staticmethod
    def validate_review_permission(
        decision: DecisionRecord,
        reviewer_role: str,
        action: ReviewAction,
    ) -> None:
        """Ensure reviewer has clinician authority and decision is eligible for review."""
        normalized_role = (reviewer_role or "").upper()

        if normalized_role not in {"DOCTOR", "CLINICIAN", "CHIEF_MEDICAL_OFFICER", "ADMIN"}:
            raise AutonomousDecisionExecutionProhibitedException(
                f"Role '{reviewer_role}' lacks authority to conduct clinical human oversight review."
            )

        if decision.status == DecisionStatus.SUPERSEDED:
            raise DecisionAlreadySupersededException(
                f"Decision {decision.id} has already been superseded by a newer decision version."
            )

        if decision.expires_at and datetime.now(timezone.utc) > decision.expires_at:
            raise DecisionExpiredException(f"Decision {decision.id} has expired.")

        # Prevent duplicate approval/rejection without modification
        if decision.status in {DecisionStatus.APPROVED, DecisionStatus.REJECTED} and action != ReviewAction.MODIFIED:
            raise DecisionAlreadyReviewedException(
                f"Decision {decision.id} has already been {decision.status.value}."
            )

    @staticmethod
    def validate_application_readiness(
        decision: DecisionRecord,
        actor_role: str,
    ) -> None:
        """Ensure decision is in an approved state and valid for application."""
        if decision.status == DecisionStatus.SUPERSEDED:
            raise DecisionAlreadySupersededException(
                f"Decision {decision.id} has been superseded and cannot be applied."
            )

        if decision.expires_at and datetime.now(timezone.utc) > decision.expires_at:
            raise DecisionExpiredException(f"Decision {decision.id} has expired.")

        if decision.requires_human_oversight and decision.status != DecisionStatus.APPROVED:
            raise DecisionNotApprovedException(
                f"Decision {decision.id} requires human clinical approval prior to application (current status: {decision.status.value})."
            )


decision_validation_service = DecisionValidationService()
