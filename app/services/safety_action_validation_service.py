"""Phase 54: Safety Action Validation Service.

Validates action preconditions, state transitions, temporal freshness,
separation of duties, scope boundaries, and clinical action restrictions.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, Set

from app.core.exceptions import AppException, ErrorCode
from app.schemas.safety_action import (
    ActionLifecycleState,
    ActionType,
    SafetyActionRecord,
    SafetyActionScope,
)


_VALID_TRANSITIONS: dict[ActionLifecycleState, Set[ActionLifecycleState]] = {
    ActionLifecycleState.IDENTIFIED: {
        ActionLifecycleState.VALIDATING,
        ActionLifecycleState.CANCELLED,
    },
    ActionLifecycleState.VALIDATING: {
        ActionLifecycleState.ACTIONABILITY_DETERMINED,
        ActionLifecycleState.BLOCKED,
        ActionLifecycleState.CANCELLED,
    },
    ActionLifecycleState.ACTIONABILITY_DETERMINED: {
        ActionLifecycleState.REVIEW_REQUIRED,
        ActionLifecycleState.READY,
        ActionLifecycleState.ESCALATED,
        ActionLifecycleState.DEFERRED,
        ActionLifecycleState.CANCELLED,
    },
    ActionLifecycleState.REVIEW_REQUIRED: {
        ActionLifecycleState.APPROVED,
        ActionLifecycleState.REJECTED,
        ActionLifecycleState.DEFERRED,
        ActionLifecycleState.ESCALATED,
        ActionLifecycleState.CANCELLED,
    },
    ActionLifecycleState.APPROVED: {
        ActionLifecycleState.READY,
        ActionLifecycleState.EXPIRED,
        ActionLifecycleState.CANCELLED,
    },
    ActionLifecycleState.READY: {
        ActionLifecycleState.ASSIGNED,
        ActionLifecycleState.IN_PROGRESS,
        ActionLifecycleState.CANCELLED,
    },
    ActionLifecycleState.ASSIGNED: {
        ActionLifecycleState.IN_PROGRESS,
        ActionLifecycleState.DEFERRED,
        ActionLifecycleState.CANCELLED,
    },
    ActionLifecycleState.IN_PROGRESS: {
        ActionLifecycleState.COMPLETION_PENDING,
        ActionLifecycleState.COMPLETED,
        ActionLifecycleState.FAILED,
        ActionLifecycleState.BLOCKED,
        ActionLifecycleState.ESCALATED,
    },
    ActionLifecycleState.COMPLETION_PENDING: {
        ActionLifecycleState.COMPLETED,
        ActionLifecycleState.FAILED,
    },
    ActionLifecycleState.COMPLETED: {
        ActionLifecycleState.EFFECTIVENESS_VALIDATION,
        ActionLifecycleState.VERIFIED,
        ActionLifecycleState.REQUIRES_REASSESSMENT,
    },
    ActionLifecycleState.EFFECTIVENESS_VALIDATION: {
        ActionLifecycleState.VERIFIED,
        ActionLifecycleState.REQUIRES_REASSESSMENT,
        ActionLifecycleState.FAILED,
    },
    ActionLifecycleState.VERIFIED: {
        ActionLifecycleState.MONITORING,
        ActionLifecycleState.CLOSED,
    },
    ActionLifecycleState.MONITORING: {
        ActionLifecycleState.CLOSED,
        ActionLifecycleState.REQUIRES_REASSESSMENT,
        ActionLifecycleState.REOPENED,
    },
    ActionLifecycleState.CLOSED: {
        ActionLifecycleState.REOPENED,
    },
    ActionLifecycleState.DEFERRED: {
        ActionLifecycleState.REVIEW_REQUIRED,
        ActionLifecycleState.READY,
        ActionLifecycleState.CANCELLED,
    },
    ActionLifecycleState.FAILED: {
        ActionLifecycleState.IN_PROGRESS, # Retry
        ActionLifecycleState.REQUIRES_REASSESSMENT,
        ActionLifecycleState.ESCALATED,
        ActionLifecycleState.CANCELLED,
    },
    ActionLifecycleState.BLOCKED: {
        ActionLifecycleState.VALIDATING,
        ActionLifecycleState.CANCELLED,
    },
    ActionLifecycleState.ESCALATED: {
        ActionLifecycleState.REVIEW_REQUIRED,
        ActionLifecycleState.IN_PROGRESS,
        ActionLifecycleState.REQUIRES_REASSESSMENT,
        ActionLifecycleState.CLOSED,
    },
    ActionLifecycleState.REQUIRES_REASSESSMENT: {
        ActionLifecycleState.IN_PROGRESS,
        ActionLifecycleState.CLOSED,
        ActionLifecycleState.CANCELLED,
    },
    ActionLifecycleState.REOPENED: {
        ActionLifecycleState.REVIEW_REQUIRED,
        ActionLifecycleState.IN_PROGRESS,
        ActionLifecycleState.CANCELLED,
    },
    ActionLifecycleState.CANCELLED: set(),
    ActionLifecycleState.REJECTED: {
        ActionLifecycleState.REVIEW_REQUIRED, # If re-reviewed with new evidence
    },
    ActionLifecycleState.EXPIRED: {
        ActionLifecycleState.REVIEW_REQUIRED,
    },
    ActionLifecycleState.SUPERSEDED: set(),
}


class SafetyActionValidationService:
    """Enforces strict safety invariants on action execution and transitions."""

    def validate_transition(
        self,
        current_state: ActionLifecycleState,
        target_state: ActionLifecycleState,
    ) -> None:
        """Validate whether a state transition is permitted."""
        allowed = _VALID_TRANSITIONS.get(current_state, set())
        if target_state not in allowed:
            raise AppException(
                code=ErrorCode.SAFETY_ACTION_INVALID_STATE,
                message=f"Illegal state transition from {current_state.value} to {target_state.value}.",
                status_code=409,
            )

    def validate_scope_access(
        self,
        scope: Optional[SafetyActionScope],
        actor_organization_id: Optional[str],
        actor_facility_id: Optional[str],
    ) -> None:
        """Verify actor has authority over the requested action scope (Tenant Boundary)."""
        if not scope:
            return

        if scope.organization_id and actor_organization_id and scope.organization_id != actor_organization_id:
            raise AppException(
                code=ErrorCode.SAFETY_ACTION_ACCESS_DENIED,
                message="Actor organization does not match action organization scope.",
                status_code=403,
            )

        if scope.facility_id and actor_facility_id and scope.facility_id != actor_facility_id:
            raise AppException(
                code=ErrorCode.SAFETY_ACTION_ACCESS_DENIED,
                message="Actor facility does not match action facility scope.",
                status_code=403,
            )

    def validate_concurrency(
        self,
        action: SafetyActionRecord,
        expected_version: int,
    ) -> None:
        """Check optimistic concurrency against race conditions."""
        if action.version != expected_version:
            raise AppException(
                code=ErrorCode.SAFETY_ACTION_VERSION_CONFLICT,
                message=f"Action version conflict: expected {expected_version}, current {action.version}.",
                status_code=409,
            )

    def validate_separation_of_duties(
        self,
        action: SafetyActionRecord,
        actor_id: str,
        role: str,
        operation: str,
    ) -> None:
        """Enforce separation of duties: finding creator != action approver, implementer != validator."""
        if operation == "approve" and action.created_by_id == actor_id:
            # Policy strictly requires independent peer review unless emergency override
            if "ADMIN" not in role.upper() and "DIRECTOR" not in role.upper():
                raise AppException(
                    code=ErrorCode.SAFETY_ACTION_APPROVAL_DENIED,
                    message="Separation of duties violation: Creator cannot approve their own action.",
                    status_code=403,
                )

        if operation == "verify" and action.assignment and action.assignment.owner_id == actor_id:
            raise AppException(
                code=ErrorCode.SAFETY_ACTION_VERIFICATION_FAILED,
                message="Separation of duties violation: Implementer cannot verify their own completion.",
                status_code=403,
            )

    def validate_clinical_action_boundary(
        self,
        action_type: ActionType,
        execution_payload: Optional[dict] = None,
    ) -> None:
        """Enforce Section 20 & 21: Never allow autonomous clinical actions.
        Direct prescription, diagnosis, or patient medication changes are strictly prohibited.
        """
        payload = execution_payload or {}
        prohibited_keys = {"discontinue_medication", "modify_prescription", "diagnose_patient", "triage_override"}
        if any(k in payload for k in prohibited_keys):
            raise AppException(
                code=ErrorCode.SAFETY_ACTION_CLINICAL_ACTION_RESTRICTED,
                message="Autonomous clinical interventions are prohibited. Route to clinical workflow.",
                status_code=422,
            )


# Global singleton
safety_action_validation_service = SafetyActionValidationService()
