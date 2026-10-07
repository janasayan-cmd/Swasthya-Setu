"""Phase 57: Safety Rollout Stage Service.

Governs controlled progression across stages:
PREPARATION -> CANARY -> LIMITED -> EXPANDED -> FULL.
Enforces checkpoint completion, human oversight authority, and AI boundary constraints.
"""

from datetime import datetime, timezone
from typing import Optional, Tuple

from app.core.exceptions import AppException, ErrorCode
from app.schemas.safety_rollout import (
    RolloutHistoryEntry,
    RolloutLifecycleState,
    RolloutStage,
    SafetyRolloutRecord,
)
from app.services.safety_rollout_verification_service import SafetyRolloutVerificationService


class SafetyRolloutStageService:
    """Orchestrates controlled rollout stage progression."""

    NEXT_STAGE_MAP = {
        RolloutStage.PREPARATION: RolloutStage.CANARY,
        RolloutStage.CANARY: RolloutStage.LIMITED,
        RolloutStage.LIMITED: RolloutStage.EXPANDED,
        RolloutStage.EXPANDED: RolloutStage.FULL,
    }

    STAGE_LIFECYCLE_MAP = {
        RolloutStage.PREPARATION: RolloutLifecycleState.PREPARING,
        RolloutStage.CANARY: RolloutLifecycleState.CANARY,
        RolloutStage.LIMITED: RolloutLifecycleState.LIMITED_ROLLOUT,
        RolloutStage.EXPANDED: RolloutLifecycleState.EXPANDED_ROLLOUT,
        RolloutStage.FULL: RolloutLifecycleState.FULL_ROLLOUT,
    }

    def __init__(self, verification_service: Optional[SafetyRolloutVerificationService] = None) -> None:
        self.verification_service = verification_service or SafetyRolloutVerificationService()

    def advance_stage(
        self,
        rollout: SafetyRolloutRecord,
        target_stage: RolloutStage,
        rationale: str,
        actor_id: str,
        actor_role: str,
        is_ai_agent: bool = False,
    ) -> SafetyRolloutRecord:
        """Advance rollout to next stage after validating checkpoints and governance constraints."""
        # AI Boundary check (TRD Section 31)
        if is_ai_agent or actor_role.upper() in {"AI", "AI_AGENT", "AUTOMATION"}:
            raise AppException(
                code=ErrorCode.STAGE_ADVANCEMENT_DENIED,
                message="AI systems cannot independently authorize or advance safety-critical rollout stages",
                status_code=400,
            )

        if rollout.is_paused or rollout.lifecycle_state == RolloutLifecycleState.PAUSED:
            raise AppException(
                code=ErrorCode.ROLLOUT_PAUSED,
                message="Cannot advance stage while rollout is paused. Resume the rollout first.",
                status_code=400,
            )

        if rollout.is_rolled_back or rollout.lifecycle_state in {
            RolloutLifecycleState.ROLLBACK_REQUIRED,
            RolloutLifecycleState.ROLLING_BACK,
            RolloutLifecycleState.ROLLED_BACK,
        }:
            raise AppException(
                code=ErrorCode.ROLLBACK_REQUIRED,
                message="Cannot advance stage on a rolled back rollout or rollout pending rollback.",
                status_code=400,
            )

        # Validate sequence
        expected_next = self.NEXT_STAGE_MAP.get(rollout.current_stage)
        if not expected_next or target_stage != expected_next:
            raise AppException(
                code=ErrorCode.STAGE_ADVANCEMENT_DENIED,
                message=(
                    f"Invalid stage transition: cannot advance directly from {rollout.current_stage.value} "
                    f"to {target_stage.value}. Expected next stage is {expected_next.value if expected_next else 'NONE'}."
                ),
                status_code=400,
            )

        # Validate that current stage checkpoints are satisfied
        satisfied, blockers = self.verification_service.are_stage_checkpoints_satisfied(
            rollout, rollout.current_stage
        )
        if not satisfied:
            raise AppException(
                code=ErrorCode.VALIDATION_FAILED,
                message=f"Cannot advance to {target_stage.value}. Current stage checkpoints incomplete: {', '.join(blockers)}",
                status_code=400,
            )

        from_stage = rollout.current_stage.value
        from_state = rollout.lifecycle_state.value
        to_stage = target_stage.value
        to_state = self.STAGE_LIFECYCLE_MAP[target_stage].value

        rollout.current_stage = target_stage
        rollout.lifecycle_state = self.STAGE_LIFECYCLE_MAP[target_stage]
        rollout.version += 1

        # Generate checkpoints for new stage
        new_checkpoints = self.verification_service.generate_stage_checkpoints(target_stage)
        rollout.checkpoints.extend(new_checkpoints)

        # Record history
        rollout.history.append(
            RolloutHistoryEntry(
                from_stage=from_stage,
                to_stage=to_stage,
                from_state=from_state,
                to_state=to_state,
                action="ADVANCE_STAGE",
                actor_id=actor_id,
                actor_role=actor_role,
                reason=rationale,
                timestamp=datetime.now(timezone.utc),
            )
        )

        return rollout
