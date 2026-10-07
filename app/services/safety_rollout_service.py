"""Phase 57: Safety Rollout Core Service.

Authoritative orchestrator for controlled rollout lifecycle, state transitions,
readiness verification, checkpoints, pause/resume, rollback governance, and closed-loop routing.
"""

from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Dict, List, Optional, Tuple

from app.core.exceptions import AppException, ErrorCode
from app.repositories.safety_rollout_repository import (
    SafetyRolloutRepository,
    get_safety_rollout_repository,
)
from app.schemas.safety_rollout import (
    AdvanceStageRequest,
    CheckpointCategory,
    CheckpointStatus,
    CompleteRolloutRequest,
    CreateRolloutRequest,
    PauseRolloutRequest,
    ReanalysisRequest,
    ReassessmentRequest,
    ReopenRolloutRequest,
    ResumeRolloutRequest,
    RollbackRequest,
    RolloutCheckpointsResponse,
    RolloutEvidenceResponse,
    RolloutHistoryEntry,
    RolloutLifecycleState,
    RolloutReadinessResponse,
    RolloutStage,
    RolloutStatusResponse,
    SafetyRolloutRecord,
    StartRolloutRequest,
    ValidateReadinessRequest,
    ValidateRollbackRequest,
    ValidateStageRequest,
    ValidationCheckpoint,
)
from app.services.safety_rollout_deployment_adapter import (
    BaseDeploymentAdapter,
    GovernedDeploymentAdapter,
)
from app.services.safety_rollout_readiness_service import SafetyRolloutReadinessService
from app.services.safety_rollout_routing_service import SafetyRolloutRoutingService
from app.services.safety_rollout_stage_service import SafetyRolloutStageService
from app.services.safety_rollout_verification_service import SafetyRolloutVerificationService


class SafetyRolloutService:
    """Core domain service for Phase 57 clinical safety rollout governance."""

    def __init__(
        self,
        repository: Optional[SafetyRolloutRepository] = None,
        deployment_adapter: Optional[BaseDeploymentAdapter] = None,
        readiness_service: Optional[SafetyRolloutReadinessService] = None,
        verification_service: Optional[SafetyRolloutVerificationService] = None,
        stage_service: Optional[SafetyRolloutStageService] = None,
        routing_service: Optional[SafetyRolloutRoutingService] = None,
    ) -> None:
        self.repository = repository or get_safety_rollout_repository()
        self.deployment_adapter = deployment_adapter or GovernedDeploymentAdapter()
        self.readiness_service = readiness_service or SafetyRolloutReadinessService()
        self.verification_service = (
            verification_service or SafetyRolloutVerificationService(self.deployment_adapter)
        )
        self.stage_service = stage_service or SafetyRolloutStageService(self.verification_service)
        self.routing_service = routing_service or SafetyRolloutRoutingService()

    @staticmethod
    def _compute_hash(data: Dict[str, Any]) -> str:
        serialized = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def create_rollout(
        self, request: CreateRolloutRequest, actor_id: str, actor_role: str
    ) -> SafetyRolloutRecord:
        """Create a new controlled safety rollout from approved Phase 51 change."""
        # 1. Idempotency verification
        if request.idempotency_key:
            payload_hash = self._compute_hash(request.model_dump())
            has_conflict, existing_id = self.repository.check_idempotency(
                request.idempotency_key, payload_hash
            )
            if has_conflict:
                if existing_id:
                    existing = self.repository.get(existing_id)
                    if existing:
                        return existing
                raise AppException(
                    code=ErrorCode.IDEMPOTENCY_CONFLICT,
                    message=f"Idempotency key '{request.idempotency_key}' reused with conflicting payload",
                    status_code=409,
                )

        # 2. Check for existing active rollout for this change
        existing_for_change = self.repository.get_by_change_id(request.change_id)
        if existing_for_change and existing_for_change.lifecycle_state not in {
            RolloutLifecycleState.COMPLETED,
            RolloutLifecycleState.ROLLED_BACK,
            RolloutLifecycleState.CANCELLED,
            RolloutLifecycleState.REJECTED,
        }:
            raise AppException(
                code=ErrorCode.CONCURRENCY_CONFLICT,
                message=f"An active rollout '{existing_for_change.rollout_id}' already exists for change '{request.change_id}'",
                status_code=409,
            )

        now = datetime.now(timezone.utc)
        record = SafetyRolloutRecord(
            change_id=request.change_id,
            change_proposal_id=request.change_proposal_id,
            scope=request.scope,
            approved_version=request.approved_version,
            target_version=request.target_version,
            current_stage=RolloutStage.PREPARATION,
            lifecycle_state=RolloutLifecycleState.APPROVED,
            approval=request.approval,
            dependencies=request.dependencies or [],
            rollback_plan=request.rollback_plan,
            validation_plan=request.validation_plan,
            observation_plan=request.observation_plan,
            created_by=actor_id,
            created_at=now,
            updated_at=now,
        )

        # 3. Initial readiness evaluation
        is_ready, _, _ = self.readiness_service.evaluate_readiness(record)
        if is_ready:
            record.lifecycle_state = RolloutLifecycleState.READY
        else:
            record.lifecycle_state = RolloutLifecycleState.READINESS_CHECK

        # 4. Generate PREPARATION stage checkpoints
        prep_checkpoints = self.verification_service.generate_stage_checkpoints(RolloutStage.PREPARATION)
        record.checkpoints.extend(prep_checkpoints)

        # 5. History entry
        record.history.append(
            RolloutHistoryEntry(
                from_stage=None,
                to_stage=RolloutStage.PREPARATION.value,
                from_state="NONE",
                to_state=record.lifecycle_state.value,
                action="CREATE_ROLLOUT",
                actor_id=actor_id,
                actor_role=actor_role,
                reason="Controlled rollout created for approved change",
                timestamp=now,
            )
        )

        saved = self.repository.save(record)

        if request.idempotency_key:
            self.repository.record_idempotency(
                request.idempotency_key, self._compute_hash(request.model_dump()), saved.rollout_id
            )

        return saved

    def get_rollout(self, rollout_id: str) -> SafetyRolloutRecord:
        """Fetch rollout record or raise 404."""
        record = self.repository.get(rollout_id)
        if not record:
            raise AppException(
                code=ErrorCode.SAFETY_ROLLOUT_NOT_FOUND,
                message=f"Safety rollout '{rollout_id}' not found",
                status_code=404,
            )
        return record

    def get_status(self, rollout_id: str) -> RolloutStatusResponse:
        """Fetch status summary."""
        rollout = self.get_rollout(rollout_id)
        return RolloutStatusResponse(
            rollout_id=rollout.rollout_id,
            change_id=rollout.change_id,
            current_stage=rollout.current_stage,
            lifecycle_state=rollout.lifecycle_state,
            approved_version=rollout.approved_version,
            target_version=rollout.target_version,
            is_paused=rollout.is_paused,
            is_rolled_back=rollout.is_rolled_back,
            version=rollout.version,
            updated_at=rollout.updated_at,
        )

    def get_history(self, rollout_id: str) -> List[RolloutHistoryEntry]:
        """Fetch immutable history audit trail."""
        rollout = self.get_rollout(rollout_id)
        return rollout.history

    def get_readiness(self, rollout_id: str) -> RolloutReadinessResponse:
        """Get current readiness audit assessment."""
        rollout = self.get_rollout(rollout_id)
        _, response, _ = self.readiness_service.evaluate_readiness(rollout)
        return response

    def get_checkpoints(self, rollout_id: str) -> RolloutCheckpointsResponse:
        """Get checkpoints details."""
        rollout = self.get_rollout(rollout_id)
        passed = sum(1 for cp in rollout.checkpoints if cp.status == CheckpointStatus.PASSED)
        failed = sum(1 for cp in rollout.checkpoints if cp.status == CheckpointStatus.FAILED)
        pending = sum(
            1 for cp in rollout.checkpoints if cp.status in (CheckpointStatus.PENDING, CheckpointStatus.BLOCKED)
        )
        return RolloutCheckpointsResponse(
            rollout_id=rollout.rollout_id,
            current_stage=rollout.current_stage,
            checkpoints=rollout.checkpoints,
            passed_count=passed,
            failed_count=failed,
            pending_count=pending,
        )

    def get_evidence(self, rollout_id: str) -> RolloutEvidenceResponse:
        """Get verified safety controls and downstream dispatch evidence."""
        rollout = self.get_rollout(rollout_id)
        return RolloutEvidenceResponse(
            rollout_id=rollout.rollout_id,
            safety_controls_verified=rollout.safety_controls_verified,
            routings=rollout.routings,
        )

    def validate_readiness(
        self, rollout_id: str, request: ValidateReadinessRequest, actor_id: str, actor_role: str
    ) -> RolloutReadinessResponse:
        """Revalidate pre-rollout readiness gates."""
        rollout = self.get_rollout(rollout_id)
        is_ready, response, blockers = self.readiness_service.evaluate_readiness(rollout)

        old_state = rollout.lifecycle_state
        if is_ready:
            rollout.lifecycle_state = RolloutLifecycleState.READY
        else:
            rollout.lifecycle_state = RolloutLifecycleState.BLOCKED

        rollout.history.append(
            RolloutHistoryEntry(
                from_stage=rollout.current_stage.value,
                to_stage=rollout.current_stage.value,
                from_state=old_state.value,
                to_state=rollout.lifecycle_state.value,
                action="VALIDATE_READINESS",
                actor_id=actor_id,
                actor_role=actor_role,
                reason=f"Readiness validation evaluated. Ready={is_ready}. Blockers: {len(blockers)}",
                timestamp=datetime.now(timezone.utc),
            )
        )
        self.repository.save(rollout)
        return response

    def start_rollout(
        self, rollout_id: str, request: StartRolloutRequest, actor_id: str, actor_role: str
    ) -> SafetyRolloutRecord:
        """Start rollout transitioning from READY/PREPARATION to CANARY stage."""
        rollout = self.get_rollout(rollout_id)

        if rollout.is_paused:
            raise AppException(code=ErrorCode.ROLLOUT_PAUSED, message="Cannot start a paused rollout", status_code=400)

        # Pre-rollout readiness revalidation
        is_ready, _, blockers = self.readiness_service.evaluate_readiness(rollout)
        if not is_ready:
            raise AppException(
                code=ErrorCode.READINESS_FAILED,
                message=f"Pre-rollout readiness validation failed: {', '.join(blockers)}",
                status_code=400,
            )

        allowed_start_states = {
            RolloutLifecycleState.READY,
            RolloutLifecycleState.APPROVED,
            RolloutLifecycleState.READINESS_CHECK,
            RolloutLifecycleState.PREPARING,
        }
        if rollout.lifecycle_state not in allowed_start_states:
            raise AppException(
                code=ErrorCode.INVALID_STATE,
                message=f"Rollout must be in READY or APPROVED state to start, currently {rollout.lifecycle_state.value}",
                status_code=400,
            )

        # Deploy canary stage to target infrastructure
        deploy_res = self.deployment_adapter.deploy(
            rollout.rollout_id,
            RolloutStage.CANARY.value,
            rollout.target_version,
            rollout.scope.model_dump(),
        )
        if deploy_res.get("status") == "FAILED":
            rollout.lifecycle_state = RolloutLifecycleState.FAILED
            self.repository.save(rollout)
            raise AppException(
                code=ErrorCode.VALIDATION_FAILED,
                message=f"Deployment infrastructure failed to deploy canary: {deploy_res.get('error')}",
                status_code=400,
            )

        from_state = rollout.lifecycle_state.value
        rollout.current_stage = RolloutStage.CANARY
        rollout.lifecycle_state = RolloutLifecycleState.CANARY
        rollout.version += 1

        # Checkpoints for CANARY
        canary_checkpoints = self.verification_service.generate_stage_checkpoints(RolloutStage.CANARY)
        rollout.checkpoints.extend(canary_checkpoints)

        # Verify initial safety controls
        _, controls = self.verification_service.verify_safety_controls(rollout)
        rollout.safety_controls_verified.extend(controls)

        # Inform Phase 48
        self.routing_service.route_to_phase48_runtime_safety(rollout, "CANARY_STARTED")

        rollout.history.append(
            RolloutHistoryEntry(
                from_stage=RolloutStage.PREPARATION.value,
                to_stage=RolloutStage.CANARY.value,
                from_state=from_state,
                to_state=rollout.lifecycle_state.value,
                action="START_ROLLOUT",
                actor_id=actor_id,
                actor_role=actor_role,
                reason=f"Started canary stage ({request.canary_scope_percentage or 5}% scope)",
                timestamp=datetime.now(timezone.utc),
            )
        )

        return self.repository.save(rollout)

    def advance_stage(
        self, rollout_id: str, request: AdvanceStageRequest, actor_id: str, actor_role: str
    ) -> SafetyRolloutRecord:
        """Advance rollout to next stage with human oversight."""
        rollout = self.get_rollout(rollout_id)
        advanced = self.stage_service.advance_stage(
            rollout=rollout,
            target_stage=request.target_stage,
            rationale=request.rationale,
            actor_id=actor_id,
            actor_role=actor_role,
            is_ai_agent=request.is_ai_agent,
        )

        # Deploy new stage via adapter
        self.deployment_adapter.deploy(
            advanced.rollout_id,
            advanced.current_stage.value,
            advanced.target_version,
            advanced.scope.model_dump(),
        )

        # Route updates
        self.routing_service.route_to_phase48_runtime_safety(
            advanced, f"STAGE_ADVANCED_TO_{advanced.current_stage.value}"
        )

        return self.repository.save(advanced)

    def validate_stage(
        self, rollout_id: str, request: ValidateStageRequest, actor_id: str, actor_role: str
    ) -> ValidationCheckpoint:
        """Submit verification evidence for a stage checkpoint."""
        rollout = self.get_rollout(rollout_id)

        success, cp = self.verification_service.validate_stage_checkpoint(
            rollout=rollout,
            checkpoint_id=request.checkpoint_id,
            observed_state=request.observed_state,
            status=request.status,
            notes=request.evidence_notes,
        )
        if not success or not cp:
            raise AppException(
                code=ErrorCode.SAFETY_ROLLOUT_NOT_FOUND,
                message=f"Checkpoint '{request.checkpoint_id}' not found on rollout '{rollout_id}'",
                status_code=404,
            )

        # If a checkpoint fails, auto-evaluate pause / rollback necessity
        if request.status == CheckpointStatus.FAILED:
            rollout.lifecycle_state = RolloutLifecycleState.FAILED
            self.routing_service.route_to_phase56_feedback(
                rollout,
                failure_reason=f"Checkpoint {cp.checkpoint_id} ({cp.category.value}) failed: {request.observed_state}",
                is_regression=True,
            )

        rollout.history.append(
            RolloutHistoryEntry(
                from_stage=rollout.current_stage.value,
                to_stage=rollout.current_stage.value,
                from_state=rollout.lifecycle_state.value,
                to_state=rollout.lifecycle_state.value,
                action="VALIDATE_STAGE_CHECKPOINT",
                actor_id=actor_id,
                actor_role=actor_role,
                reason=f"Checkpoint {cp.checkpoint_id} set to {request.status.value}",
                timestamp=datetime.now(timezone.utc),
            )
        )

        self.repository.save(rollout)
        return cp

    def pause(
        self, rollout_id: str, request: PauseRolloutRequest, actor_id: str, actor_role: str
    ) -> SafetyRolloutRecord:
        """Pause active rollout."""
        rollout = self.get_rollout(rollout_id)
        if rollout.is_paused:
            return rollout

        old_state = rollout.lifecycle_state.value
        rollout.is_paused = True
        rollout.pause_reason = request.reason
        rollout.lifecycle_state = RolloutLifecycleState.PAUSED
        rollout.version += 1

        self.deployment_adapter.pause(rollout.rollout_id, request.reason)
        self.routing_service.route_to_phase48_runtime_safety(rollout, "ROLLOUT_PAUSED")
        self.routing_service.route_to_phase56_feedback(
            rollout, failure_reason=f"Rollout paused: {request.reason}", is_regression=False
        )

        rollout.history.append(
            RolloutHistoryEntry(
                from_stage=rollout.current_stage.value,
                to_stage=rollout.current_stage.value,
                from_state=old_state,
                to_state=rollout.lifecycle_state.value,
                action="PAUSE_ROLLOUT",
                actor_id=actor_id,
                actor_role=actor_role,
                reason=request.reason,
                timestamp=datetime.now(timezone.utc),
            )
        )

        return self.repository.save(rollout)

    def resume(
        self, rollout_id: str, request: ResumeRolloutRequest, actor_id: str, actor_role: str
    ) -> SafetyRolloutRecord:
        """Resume paused rollout after revalidating readiness."""
        rollout = self.get_rollout(rollout_id)
        if not rollout.is_paused and rollout.lifecycle_state != RolloutLifecycleState.PAUSED:
            return rollout

        # Readiness recheck before resumption
        is_ready, _, blockers = self.readiness_service.evaluate_readiness(rollout)
        if not is_ready:
            raise AppException(
                ErrorCode.READINESS_FAILED,
                f"Cannot resume rollout. Pre-rollout readiness failed: {', '.join(blockers)}",
            )

        old_state = rollout.lifecycle_state.value
        rollout.is_paused = False
        rollout.pause_reason = None
        rollout.lifecycle_state = SafetyRolloutStageService.STAGE_LIFECYCLE_MAP.get(
            rollout.current_stage, RolloutLifecycleState.READY
        )
        rollout.version += 1

        self.routing_service.route_to_phase48_runtime_safety(rollout, "ROLLOUT_RESUMED")

        rollout.history.append(
            RolloutHistoryEntry(
                from_stage=rollout.current_stage.value,
                to_stage=rollout.current_stage.value,
                from_state=old_state,
                to_state=rollout.lifecycle_state.value,
                action="RESUME_ROLLOUT",
                actor_id=actor_id,
                actor_role=actor_role,
                reason=request.rationale,
                timestamp=datetime.now(timezone.utc),
            )
        )

        return self.repository.save(rollout)

    def rollback(
        self, rollout_id: str, request: RollbackRequest, actor_id: str, actor_role: str
    ) -> SafetyRolloutRecord:
        """Initiate rollback of rollout to previous known good version."""
        rollout = self.get_rollout(rollout_id)

        old_state = rollout.lifecycle_state.value
        rollout.is_rolled_back = True
        rollout.rollback_reason = request.reason
        rollout.lifecycle_state = RolloutLifecycleState.ROLLING_BACK
        rollout.version += 1

        # Execute rollback in deployment infrastructure
        self.deployment_adapter.rollback(rollout.rollout_id, request.target_version, request.reason)

        # Add POST_ROLLBACK checkpoint
        rollout.checkpoints.append(
            ValidationCheckpoint(
                category=CheckpointCategory.POST_ROLLBACK,
                stage=rollout.current_stage,
                expected_state=f"ROLLED_BACK_TO_{request.target_version}",
                criteria="Infrastructure restored to target version with safety controls operational",
            )
        )

        # Notify Phase 51 Governance & Phase 56 Improvement Feedback
        self.routing_service.route_to_phase51_governance(
            rollout, "ROLLBACK_INITIATED", {"target_version": request.target_version, "reason": request.reason}
        )
        self.routing_service.route_to_phase56_feedback(
            rollout, failure_reason=f"Rollback initiated: {request.reason}", is_regression=True
        )

        rollout.history.append(
            RolloutHistoryEntry(
                from_stage=rollout.current_stage.value,
                to_stage=rollout.current_stage.value,
                from_state=old_state,
                to_state=rollout.lifecycle_state.value,
                action="ROLLBACK_ROLLOUT",
                actor_id=actor_id,
                actor_role=actor_role,
                reason=request.reason,
                timestamp=datetime.now(timezone.utc),
            )
        )

        return self.repository.save(rollout)

    def validate_rollback(
        self, rollout_id: str, request: ValidateRollbackRequest, actor_id: str, actor_role: str
    ) -> SafetyRolloutRecord:
        """Validate that rollback has successfully restored safety and target version."""
        rollout = self.get_rollout(rollout_id)

        valid, msg = self.verification_service.verify_rollback(
            rollout, request.verified_version, request.safety_controls_intact
        )
        if not valid:
            raise AppException(code=ErrorCode.ROLLBACK_VALIDATION_FAILED, message=msg, status_code=400)

        old_state = rollout.lifecycle_state.value
        rollout.lifecycle_state = RolloutLifecycleState.ROLLED_BACK
        rollout.version += 1

        # Update post-rollback checkpoint
        for cp in rollout.checkpoints:
            if cp.category == CheckpointCategory.POST_ROLLBACK:
                cp.status = CheckpointStatus.PASSED
                cp.observed_state = f"VERIFIED_AT_{request.verified_version}"
                cp.evaluated_at = datetime.now(timezone.utc)
                cp.notes = request.evidence_notes

        # Route to Phase 52
        self.routing_service.route_to_phase52_assurance(
            rollout, {"rollback_verified_version": request.verified_version, "controls_intact": True}
        )

        rollout.history.append(
            RolloutHistoryEntry(
                from_stage=rollout.current_stage.value,
                to_stage=rollout.current_stage.value,
                from_state=old_state,
                to_state=rollout.lifecycle_state.value,
                action="VALIDATE_ROLLBACK",
                actor_id=actor_id,
                actor_role=actor_role,
                reason=f"Rollback validated for version {request.verified_version}",
                timestamp=datetime.now(timezone.utc),
            )
        )

        return self.repository.save(rollout)

    def reassess(
        self, rollout_id: str, request: ReassessmentRequest, actor_id: str, actor_role: str
    ) -> SafetyRolloutRecord:
        """Request formal reassessment of rollout."""
        rollout = self.get_rollout(rollout_id)
        old_state = rollout.lifecycle_state.value
        rollout.lifecycle_state = RolloutLifecycleState.REASSESSMENT_REQUIRED
        rollout.version += 1

        self.routing_service.route_to_phase51_governance(
            rollout, "REASSESSMENT_REQUESTED", {"reason": request.reason}
        )
        self.routing_service.route_to_phase56_feedback(
            rollout, failure_reason=f"Reassessment requested: {request.reason}", is_regression=False
        )

        rollout.history.append(
            RolloutHistoryEntry(
                from_stage=rollout.current_stage.value,
                to_stage=rollout.current_stage.value,
                from_state=old_state,
                to_state=rollout.lifecycle_state.value,
                action="REQUEST_REASSESSMENT",
                actor_id=actor_id,
                actor_role=actor_role,
                reason=request.reason,
                timestamp=datetime.now(timezone.utc),
            )
        )

        return self.repository.save(rollout)

    def complete(
        self, rollout_id: str, request: CompleteRolloutRequest, actor_id: str, actor_role: str
    ) -> SafetyRolloutRecord:
        """Mark rollout completed after observation and verification in FULL stage."""
        rollout = self.get_rollout(rollout_id)

        if rollout.current_stage != RolloutStage.FULL:
            raise AppException(
                code=ErrorCode.STAGE_ADVANCEMENT_DENIED,
                message=f"Rollout must reach FULL stage to complete, currently in {rollout.current_stage.value}",
                status_code=400,
            )

        if rollout.is_paused or rollout.is_rolled_back:
            raise AppException(
                code=ErrorCode.INVALID_STATE,
                message="Cannot complete a rollout that is paused or rolled back",
                status_code=400,
            )

        # Checkpoints check
        satisfied, blockers = self.verification_service.are_stage_checkpoints_satisfied(
            rollout, RolloutStage.FULL
        )
        if not satisfied:
            raise AppException(
                code=ErrorCode.VALIDATION_FAILED,
                message=f"Cannot complete rollout. FULL stage checkpoints incomplete: {', '.join(blockers)}",
                status_code=400,
            )

        old_state = rollout.lifecycle_state.value
        now = datetime.now(timezone.utc)
        rollout.lifecycle_state = RolloutLifecycleState.COMPLETED
        rollout.completed_at = now
        rollout.version += 1

        # Route to Phase 52 (Assurance) & Phase 55 (Effectiveness)
        self.routing_service.route_to_phase52_assurance(
            rollout, {"completed_at": now.isoformat(), "full_rollout_verified": True}
        )
        self.routing_service.route_to_phase55_effectiveness(
            rollout,
            {
                "observation_evidence_id": request.observation_evidence_id,
                "rationale": request.rationale,
                "completed_at": now.isoformat(),
            },
        )

        rollout.history.append(
            RolloutHistoryEntry(
                from_stage=rollout.current_stage.value,
                to_stage=rollout.current_stage.value,
                from_state=old_state,
                to_state=rollout.lifecycle_state.value,
                action="COMPLETE_ROLLOUT",
                actor_id=actor_id,
                actor_role=actor_role,
                reason=request.rationale,
                timestamp=now,
            )
        )

        return self.repository.save(rollout)

    def reopen(
        self, rollout_id: str, request: ReopenRolloutRequest, actor_id: str, actor_role: str
    ) -> SafetyRolloutRecord:
        """Reopen a completed, rolled-back, or cancelled rollout for review."""
        rollout = self.get_rollout(rollout_id)

        if rollout.lifecycle_state not in {
            RolloutLifecycleState.COMPLETED,
            RolloutLifecycleState.ROLLED_BACK,
            RolloutLifecycleState.CANCELLED,
            RolloutLifecycleState.FAILED,
        }:
            raise AppException(
                code=ErrorCode.INVALID_STATE,
                message=f"Cannot reopen rollout in state '{rollout.lifecycle_state.value}'. Only terminal states can be reopened.",
                status_code=400,
            )

        old_state = rollout.lifecycle_state.value
        rollout.lifecycle_state = RolloutLifecycleState.REASSESSMENT_REQUIRED
        rollout.reopened_count += 1
        rollout.version += 1

        self.routing_service.route_to_phase56_feedback(
            rollout, failure_reason=f"Rollout reopened: {request.reason}", is_regression=False
        )

        rollout.history.append(
            RolloutHistoryEntry(
                from_stage=rollout.current_stage.value,
                to_stage=rollout.current_stage.value,
                from_state=old_state,
                to_state=rollout.lifecycle_state.value,
                action="REOPEN_ROLLOUT",
                actor_id=actor_id,
                actor_role=actor_role,
                reason=request.reason,
                timestamp=datetime.now(timezone.utc),
            )
        )

        return self.repository.save(rollout)

    def reanalysis(
        self, request: ReanalysisRequest, actor_id: str, actor_role: str
    ) -> List[RolloutStatusResponse]:
        """Perform batch status and readiness reanalysis on specified or all active rollouts."""
        if request.rollout_ids:
            rollouts = [self.repository.get(rid) for rid in request.rollout_ids if self.repository.get(rid)]
        else:
            rollouts = self.repository.list_active()

        results: List[RolloutStatusResponse] = []
        for r in rollouts:
            if r:
                is_ready, _, _ = self.readiness_service.evaluate_readiness(r)
                if not is_ready and r.lifecycle_state in {
                    RolloutLifecycleState.APPROVED,
                    RolloutLifecycleState.READY,
                }:
                    r.lifecycle_state = RolloutLifecycleState.BLOCKED
                    self.repository.save(r)

                results.append(
                    RolloutStatusResponse(
                        rollout_id=r.rollout_id,
                        change_id=r.change_id,
                        current_stage=r.current_stage,
                        lifecycle_state=r.lifecycle_state,
                        approved_version=r.approved_version,
                        target_version=r.target_version,
                        is_paused=r.is_paused,
                        is_rolled_back=r.is_rolled_back,
                        version=r.version,
                        updated_at=r.updated_at,
                    )
                )

        return results

    # Filtering convenience methods
    def list_rollouts(
        self,
        organization_id: Optional[str] = None,
        facility_id: Optional[str] = None,
        stage: Optional[RolloutStage] = None,
        lifecycle_state: Optional[RolloutLifecycleState] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[SafetyRolloutRecord]:
        return self.repository.list_rollouts(
            organization_id=organization_id,
            facility_id=facility_id,
            stage=stage,
            lifecycle_state=lifecycle_state,
            limit=limit,
            offset=offset,
        )

    def list_pending(self, organization_id: Optional[str] = None) -> List[SafetyRolloutRecord]:
        return self.repository.list_pending(organization_id=organization_id)

    def list_paused(self, organization_id: Optional[str] = None) -> List[SafetyRolloutRecord]:
        return self.repository.list_paused(organization_id=organization_id)

    def list_rollback_required(self, organization_id: Optional[str] = None) -> List[SafetyRolloutRecord]:
        return self.repository.list_rollback_required(organization_id=organization_id)

    def list_validation_failed(self, organization_id: Optional[str] = None) -> List[SafetyRolloutRecord]:
        return self.repository.list_validation_failed(organization_id=organization_id)

    def list_active(self, organization_id: Optional[str] = None) -> List[SafetyRolloutRecord]:
        return self.repository.list_active(organization_id=organization_id)


# Global singleton service
_service_instance: Optional[SafetyRolloutService] = None


def get_safety_rollout_service() -> SafetyRolloutService:
    """Retrieve global singleton service."""
    global _service_instance
    if _service_instance is None:
        _service_instance = SafetyRolloutService()
    return _service_instance
