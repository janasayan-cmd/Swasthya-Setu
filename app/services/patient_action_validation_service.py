"""HealthSetu Phase 42 - Patient Action Validation Service.

Validates action state transitions, expiration boundaries, rate limits,
payload invariants, and clinical safety boundaries.

NON-NEGOTIABLE SAFETY PRINCIPLES:
- An expired action must not accept submissions.
- A completed action must not be modified without explicit correction workflow.
- Patient self-service must NEVER directly update authoritative medications, allergies, diagnoses, or dispatch 911.
"""

from __future__ import annotations

import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.core.exceptions import (
    PatientActionAlreadySubmittedException,
    PatientActionAutonomousClinicalProhibitedException,
    PatientActionCancelledException,
    PatientActionCompletedException,
    PatientActionExpiredException,
    PatientActionInvalidStateException,
    PatientActionRateLimitExceededException,
    PatientActionValidationFailedException,
)
from app.schemas.patient_action import ActionStatus, PatientActionRecord


class PatientActionValidationService:
    """Validates operational rules, state transitions, and clinical safety boundaries."""

    def __init__(self) -> None:
        self._user_timestamps: Dict[str, List[float]] = defaultdict(list)

    def check_rate_limit(self, user_id: str) -> None:
        """Enforces sliding-window rate limit on patient action operations."""
        limit = getattr(settings, "PATIENT_ACTION_RATE_LIMIT", 60)
        now = time.time()
        window = 60.0

        timestamps = self._user_timestamps[user_id]
        # Remove expired timestamps
        self._user_timestamps[user_id] = [t for t in timestamps if now - t < window]

        if len(self._user_timestamps[user_id]) >= limit:
            raise PatientActionRateLimitExceededException(
                message=f"Rate limit exceeded ({limit} actions/minute). Please wait before retrying."
            )

        self._user_timestamps[user_id].append(now)

    def validate_action_for_start(self, action: PatientActionRecord) -> None:
        """Validate that an action can be transitioned to STARTED."""
        self._check_expiration(action)

        if action.status in (ActionStatus.EXPIRED,):
            raise PatientActionExpiredException()
        if action.status == ActionStatus.CANCELLED:
            raise PatientActionCancelledException()
        if action.status == ActionStatus.COMPLETED:
            raise PatientActionCompletedException()
        if action.status not in (ActionStatus.CREATED, ActionStatus.AVAILABLE):
            raise PatientActionInvalidStateException(
                message=f"Cannot start action in '{action.status}' state."
            )

    def validate_action_for_submission(self, action: PatientActionRecord) -> None:
        """Validate that an action is in a state ready to accept a submission."""
        self._check_expiration(action)

        if action.status == ActionStatus.EXPIRED:
            raise PatientActionExpiredException()
        if action.status == ActionStatus.CANCELLED:
            raise PatientActionCancelledException()
        if action.status == ActionStatus.COMPLETED:
            raise PatientActionCompletedException(
                message="Cannot submit to an already completed action. Use correction workflow if permitted."
            )
        if action.status == ActionStatus.SUBMITTED:
            raise PatientActionAlreadySubmittedException(
                message="Action already submitted. Use the correction endpoint to submit modifications."
            )
        if action.status not in (ActionStatus.CREATED, ActionStatus.AVAILABLE, ActionStatus.STARTED):
            raise PatientActionInvalidStateException(
                message=f"Action in '{action.status}' state cannot accept submissions."
            )

    def validate_action_for_completion(self, action: PatientActionRecord) -> None:
        """Validate that an action can be marked COMPLETED."""
        if action.status == ActionStatus.COMPLETED:
            return  # Idempotent completion
        if action.status in (ActionStatus.CANCELLED, ActionStatus.EXPIRED):
            raise PatientActionInvalidStateException(
                message=f"Cannot complete action in '{action.status}' state."
            )

    def validate_action_for_cancellation(self, action: PatientActionRecord) -> None:
        """Validate that an action can be cancelled."""
        if action.status in (ActionStatus.COMPLETED, ActionStatus.CANCELLED):
            raise PatientActionInvalidStateException(
                message=f"Cannot cancel action already in '{action.status}' state."
            )

    def validate_action_for_acknowledgement(self, action: PatientActionRecord) -> None:
        """Validate that an action can be acknowledged."""
        self._check_expiration(action)
        if action.status in (ActionStatus.CANCELLED, ActionStatus.EXPIRED, ActionStatus.COMPLETED):
            raise PatientActionInvalidStateException(
                message=f"Cannot acknowledge action in '{action.status}' state."
            )

    def validate_action_for_refusal(self, action: PatientActionRecord) -> None:
        """Validate that an action can be declined/refused by the patient."""
        self._check_expiration(action)
        if action.status in (ActionStatus.CANCELLED, ActionStatus.EXPIRED, ActionStatus.COMPLETED):
            raise PatientActionInvalidStateException(
                message=f"Cannot refuse action in '{action.status}' state."
            )

    def validate_action_for_correction(self, action: PatientActionRecord) -> None:
        """Validate that an action permits a submission correction."""
        if action.status not in (ActionStatus.SUBMITTED, ActionStatus.NEEDS_REVIEW, ActionStatus.COMPLETED):
            raise PatientActionInvalidStateException(
                message="Cannot correct an action that has not yet been submitted."
            )

    def validate_clinical_safety_boundaries(self, payload: Dict[str, Any]) -> None:
        """Ensures patient payload does not attempt direct clinical mutations."""
        # Patient self-service must never contain direct commands to override clinical truth
        prohibited_intent_flags = (
            "direct_prescribe",
            "autonomous_medication_override",
            "autonomous_diagnosis_create",
            "dispatch_emergency_911",
        )
        for flag in prohibited_intent_flags:
            if payload.get(flag) is True:
                raise PatientActionAutonomousClinicalProhibitedException(
                    message=f"Prohibited autonomous clinical action detected: '{flag}'."
                )

    def _check_expiration(self, action: PatientActionRecord) -> None:
        """Internal check if action has passed expiration timestamp."""
        if action.expires_at is not None:
            now = datetime.now(timezone.utc)
            if action.expires_at < now:
                action.status = ActionStatus.EXPIRED
                raise PatientActionExpiredException(
                    message=f"Patient action '{action.id}' expired at {action.expires_at.isoformat()}."
                )
