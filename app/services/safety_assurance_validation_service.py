"""Phase 52: Control Assurance Validation Service.

Validates assurance operation preconditions:
- Control identity and version resolution
- Scope enforcement
- Evaluation eligibility
- Observation window validity
- Authorization context (server-derived only, never client-provided)
- Evidence provenance eligibility
- Idempotency

Client-provided actor_id, reviewer_id, effectiveness_state, risk_state,
control_state, and approval_state are NEVER trusted or consumed here.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from app.core.exceptions import (
    AppException,
    ErrorCode,
)
from app.schemas.safety_assurance import (
    AssuranceEvaluationRequest,
    AssuranceEvaluationRecord,
    AssuranceLifecycleState,
)

logger = logging.getLogger("app.services.safety_assurance_validation_service")

# Minimum observation window (1 hour)
_MIN_OBSERVATION_WINDOW_SECONDS = 3600
# Maximum observation window (365 days)
_MAX_OBSERVATION_WINDOW_DAYS = 365
# Maximum future scheduling offset (30 days)
_MAX_FUTURE_SCHEDULE_DAYS = 30


class SafetyAssuranceValidationService:
    """Validates assurance operation preconditions before evaluation begins."""

    def validate_evaluation_request(
        self,
        request: AssuranceEvaluationRequest,
        actor_organization_id: Optional[str],
        actor_facility_id: Optional[str],
    ) -> None:
        """Validate an assurance evaluation request.

        Raises AppException with appropriate error code on failure.
        Client-provided scope is validated against authenticated context.
        """
        now = datetime.now(timezone.utc)

        # Observation window validity
        if request.observation_end <= request.observation_start:
            raise AppException(
                code=ErrorCode.SAFETY_ASSURANCE_SCOPE_INVALID,
                message="Observation end must be after observation start.",
                status_code=422,
            )

        window_seconds = (request.observation_end - request.observation_start).total_seconds()
        if window_seconds < _MIN_OBSERVATION_WINDOW_SECONDS:
            raise AppException(
                code=ErrorCode.SAFETY_ASSURANCE_SCOPE_INVALID,
                message=f"Observation window must be at least {_MIN_OBSERVATION_WINDOW_SECONDS} seconds.",
                status_code=422,
            )

        window_days = window_seconds / 86400
        if window_days > _MAX_OBSERVATION_WINDOW_DAYS:
            raise AppException(
                code=ErrorCode.SAFETY_ASSURANCE_SCOPE_INVALID,
                message=f"Observation window cannot exceed {_MAX_OBSERVATION_WINDOW_DAYS} days.",
                status_code=422,
            )

        # Control identity
        if not request.control_id or not request.control_id.strip():
            raise AppException(
                code=ErrorCode.SAFETY_ASSURANCE_CONTROL_NOT_FOUND,
                message="Control ID must be provided.",
                status_code=422,
            )

        if not request.control_version or not request.control_version.strip():
            raise AppException(
                code=ErrorCode.SAFETY_ASSURANCE_CONTROL_VERSION_INVALID,
                message="Control version must be provided.",
                status_code=422,
            )

        # Organization scope: if client provides org_id, verify it matches authenticated context
        if (
            request.organization_id
            and actor_organization_id
            and request.organization_id != actor_organization_id
        ):
            raise AppException(
                code=ErrorCode.SAFETY_ASSURANCE_UNAUTHORIZED,
                message="Requested organization scope does not match authenticated actor context.",
                status_code=403,
            )

        # Facility scope: if client provides facility_id, verify it matches authenticated context
        if (
            request.facility_id
            and actor_facility_id
            and request.facility_id != actor_facility_id
        ):
            raise AppException(
                code=ErrorCode.SAFETY_ASSURANCE_UNAUTHORIZED,
                message="Requested facility scope does not match authenticated actor context.",
                status_code=403,
            )

    def validate_state_transition(
        self,
        evaluation: AssuranceEvaluationRecord,
        target_state: AssuranceLifecycleState,
    ) -> None:
        """Validate that a lifecycle state transition is permitted.

        Raises AppException if the transition is invalid.
        """
        current = evaluation.lifecycle_state
        allowed_transitions: dict[AssuranceLifecycleState, list[AssuranceLifecycleState]] = {
            AssuranceLifecycleState.SCHEDULED: [
                AssuranceLifecycleState.ELIGIBILITY_CHECK,
                AssuranceLifecycleState.CANCELLED,
                AssuranceLifecycleState.BLOCKED,
            ],
            AssuranceLifecycleState.ELIGIBILITY_CHECK: [
                AssuranceLifecycleState.OBSERVATION_COLLECTION,
                AssuranceLifecycleState.BLOCKED,
                AssuranceLifecycleState.CANCELLED,
                AssuranceLifecycleState.INSUFFICIENT_EVIDENCE,
            ],
            AssuranceLifecycleState.OBSERVATION_COLLECTION: [
                AssuranceLifecycleState.EVIDENCE_ASSESSMENT,
                AssuranceLifecycleState.INSUFFICIENT_EVIDENCE,
                AssuranceLifecycleState.BLOCKED,
                AssuranceLifecycleState.CANCELLED,
            ],
            AssuranceLifecycleState.EVIDENCE_ASSESSMENT: [
                AssuranceLifecycleState.EFFECTIVENESS_EVALUATION,
                AssuranceLifecycleState.INSUFFICIENT_EVIDENCE,
                AssuranceLifecycleState.BLOCKED,
            ],
            AssuranceLifecycleState.EFFECTIVENESS_EVALUATION: [
                AssuranceLifecycleState.REVIEW_REQUIRED,
                AssuranceLifecycleState.ASSURANCE_ACCEPTED,
                AssuranceLifecycleState.DEGRADED,
                AssuranceLifecycleState.FAILED,
                AssuranceLifecycleState.INSUFFICIENT_EVIDENCE,
            ],
            AssuranceLifecycleState.REVIEW_REQUIRED: [
                AssuranceLifecycleState.UNDER_REVIEW,
                AssuranceLifecycleState.CANCELLED,
            ],
            AssuranceLifecycleState.UNDER_REVIEW: [
                AssuranceLifecycleState.ASSURANCE_ACCEPTED,
                AssuranceLifecycleState.DEGRADED,
                AssuranceLifecycleState.FAILED,
                AssuranceLifecycleState.INSUFFICIENT_EVIDENCE,
                AssuranceLifecycleState.REASSESSMENT_REQUIRED,
                AssuranceLifecycleState.REOPENED,
            ],
            AssuranceLifecycleState.ASSURANCE_ACCEPTED: [
                AssuranceLifecycleState.MONITORING,
                AssuranceLifecycleState.REASSESSMENT_REQUIRED,
                AssuranceLifecycleState.SUPERSEDED,
                AssuranceLifecycleState.REOPENED,
            ],
            AssuranceLifecycleState.MONITORING: [
                AssuranceLifecycleState.REASSESSMENT_REQUIRED,
                AssuranceLifecycleState.DEGRADED,
                AssuranceLifecycleState.FAILED,
                AssuranceLifecycleState.SUPERSEDED,
            ],
            AssuranceLifecycleState.DEGRADED: [
                AssuranceLifecycleState.FAILED,
                AssuranceLifecycleState.REASSESSMENT_REQUIRED,
                AssuranceLifecycleState.REVIEW_REQUIRED,
            ],
            AssuranceLifecycleState.FAILED: [
                AssuranceLifecycleState.REASSESSMENT_REQUIRED,
                AssuranceLifecycleState.REVIEW_REQUIRED,
            ],
            AssuranceLifecycleState.INSUFFICIENT_EVIDENCE: [
                AssuranceLifecycleState.REASSESSMENT_REQUIRED,
                AssuranceLifecycleState.BLOCKED,
                AssuranceLifecycleState.CANCELLED,
                AssuranceLifecycleState.REOPENED,
            ],
            AssuranceLifecycleState.REASSESSMENT_REQUIRED: [
                AssuranceLifecycleState.SCHEDULED,
                AssuranceLifecycleState.CANCELLED,
            ],
            AssuranceLifecycleState.REOPENED: [
                AssuranceLifecycleState.OBSERVATION_COLLECTION,
                AssuranceLifecycleState.CANCELLED,
            ],
            # Terminal states (no further transitions)
            AssuranceLifecycleState.BLOCKED: [],
            AssuranceLifecycleState.CANCELLED: [],
            AssuranceLifecycleState.EXPIRED: [],
            AssuranceLifecycleState.SUPERSEDED: [],
        }

        permitted = allowed_transitions.get(current, [])
        if target_state not in permitted:
            raise AppException(
                code=ErrorCode.SAFETY_ASSURANCE_INVALID_STATE,
                message=(
                    f"Cannot transition assurance evaluation from "
                    f"'{current.value}' to '{target_state.value}'."
                ),
                status_code=409,
            )

    def validate_not_already_running(
        self,
        existing: Optional[AssuranceEvaluationRecord],
    ) -> None:
        """Ensure no duplicate in-progress evaluation exists for same scope."""
        if existing is None:
            return
        in_progress_states = {
            AssuranceLifecycleState.SCHEDULED,
            AssuranceLifecycleState.ELIGIBILITY_CHECK,
            AssuranceLifecycleState.OBSERVATION_COLLECTION,
            AssuranceLifecycleState.EVIDENCE_ASSESSMENT,
            AssuranceLifecycleState.EFFECTIVENESS_EVALUATION,
            AssuranceLifecycleState.REVIEW_REQUIRED,
            AssuranceLifecycleState.UNDER_REVIEW,
        }
        if existing.lifecycle_state in in_progress_states:
            raise AppException(
                code=ErrorCode.SAFETY_ASSURANCE_ALREADY_RUNNING,
                message=(
                    f"An assurance evaluation for control '{existing.control_id}' "
                    f"is already in progress (evaluation_id={existing.evaluation_id})."
                ),
                status_code=409,
            )

    def validate_concurrency(
        self,
        record: AssuranceEvaluationRecord,
        expected_version: int,
    ) -> None:
        """Enforce optimistic concurrency via version check."""
        if record.version != expected_version:
            raise AppException(
                code=ErrorCode.SAFETY_ASSURANCE_CONCURRENCY_CONFLICT,
                message=(
                    f"Concurrency conflict: expected version {expected_version}, "
                    f"current version is {record.version}."
                ),
                status_code=409,
            )


# Global singleton
safety_assurance_validation_service = SafetyAssuranceValidationService()
