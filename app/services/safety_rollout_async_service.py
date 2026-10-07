"""Phase 57: Safety Rollout Asynchronous Job Orchestrator (Phase 22 Integration).

Orchestrates background processing of long-running rollout verification,
canary progression checks, and observation periods without carrying PHI.
"""

from typing import Any, Dict, Optional

from app.schemas.safety_rollout import (
    AdvanceStageRequest,
    CheckpointStatus,
    RolloutStage,
    SafetyRolloutRecord,
    ValidateStageRequest,
)
from app.services.safety_rollout_service import (
    SafetyRolloutService,
    get_safety_rollout_service,
)


class SafetyRolloutAsyncService:
    """Manages asynchronous rollout task execution."""

    def __init__(self, rollout_service: Optional[SafetyRolloutService] = None) -> None:
        self.rollout_service = rollout_service or get_safety_rollout_service()

    async def execute_background_checkpoint_validation(
        self,
        rollout_id: str,
        checkpoint_id: str,
        observed_state: str,
        status: CheckpointStatus,
        actor_id: str,
        actor_role: str,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute checkpoint validation in background queue."""
        req = ValidateStageRequest(
            checkpoint_id=checkpoint_id,
            observed_state=observed_state,
            status=status,
            evidence_notes=notes,
        )
        cp = self.rollout_service.validate_stage(
            rollout_id=rollout_id,
            request=req,
            actor_id=actor_id,
            actor_role=actor_role,
        )
        return {
            "status": "COMPLETED",
            "rollout_id": rollout_id,
            "checkpoint_id": cp.checkpoint_id,
            "checkpoint_status": cp.status.value,
        }

    async def execute_background_stage_advancement(
        self,
        rollout_id: str,
        target_stage: RolloutStage,
        rationale: str,
        actor_id: str,
        actor_role: str,
    ) -> Dict[str, Any]:
        """Execute stage advancement from background job runner with human supervisor credentials."""
        req = AdvanceStageRequest(
            target_stage=target_stage,
            rationale=rationale,
            is_ai_agent=False,
        )
        rollout = self.rollout_service.advance_stage(
            rollout_id=rollout_id,
            request=req,
            actor_id=actor_id,
            actor_role=actor_role,
        )
        return {
            "status": "COMPLETED",
            "rollout_id": rollout.rollout_id,
            "new_stage": rollout.current_stage.value,
            "lifecycle_state": rollout.lifecycle_state.value,
        }
