"""Phase 55: Action Effectiveness Validation Service.

Validates action eligibility, multi-tenant scope, and prevents client-side result fabrication.
"""

from typing import Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.safety_action_repository import get_safety_action_repository
from app.schemas.action_effectiveness import EffectivenessScope
from app.schemas.safety_action import ActionLifecycleState


_ELIGIBLE_STATES = {
    ActionLifecycleState.COMPLETED,
    ActionLifecycleState.COMPLETION_PENDING,
    ActionLifecycleState.VERIFIED,
    ActionLifecycleState.EFFECTIVENESS_VALIDATION,
    ActionLifecycleState.MONITORING,
    ActionLifecycleState.CLOSED,
}


class ActionEffectivenessValidationService:
    """Service for validating action eligibility and multi-tenant constraints."""

    def __init__(self) -> None:
        self._action_repo = get_safety_action_repository()

    def validate_action_eligibility(
        self,
        action_id: str,
        target_scope: EffectivenessScope,
    ) -> None:
        """Ensure action exists, is in a completed/valid state, and scope aligns."""
        action = self._action_repo.get(action_id)
        if not action:
            raise AppException(
                code=ErrorCode.EFFECTIVENESS_EVALUATION_NOT_FOUND,
                message=f"Referenced safety action '{action_id}' not found.",
                status_code=404,
            )

        # Check tenant scope
        if action.scope.organization_id != target_scope.organization_id:
            raise AppException(
                code=ErrorCode.SCOPE_INVALID,
                message="Organization scope mismatch with referenced safety action.",
                status_code=403,
            )

        # Check action lifecycle state
        if action.lifecycle_state not in _ELIGIBLE_STATES:
            raise AppException(
                code=ErrorCode.ACTION_NOT_ELIGIBLE,
                message=(
                    f"Action '{action_id}' is in state '{action.lifecycle_state.value}'. "
                    "Effectiveness evaluation requires the action to be completed, verified, or pending validation."
                ),
                status_code=400,
            )
