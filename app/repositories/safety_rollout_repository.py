"""Phase 57: Safety Rollout Repository.

Thread-safe in-memory repository for controlled safety rollout orchestration,
checkpoints, transitions, audit history, and idempotency protection.
"""

from datetime import datetime, timezone
import threading
from typing import Dict, List, Optional, Tuple

from app.schemas.safety_rollout import (
    CheckpointStatus,
    RolloutLifecycleState,
    RolloutStage,
    SafetyRolloutRecord,
)


class SafetyRolloutRepository:
    """Thread-safe in-memory repository for Phase 57 safety rollouts."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._rollouts: Dict[str, SafetyRolloutRecord] = {}
        self._change_to_rollout: Dict[str, str] = {}
        self._idempotency_store: Dict[str, Tuple[str, str, datetime]] = {}

    def save(self, record: SafetyRolloutRecord) -> SafetyRolloutRecord:
        """Insert or update rollout record."""
        with self._lock:
            record.updated_at = datetime.now(timezone.utc)
            self._rollouts[record.rollout_id] = record
            self._change_to_rollout[record.change_id] = record.rollout_id
            return record

    def get(self, rollout_id: str) -> Optional[SafetyRolloutRecord]:
        """Fetch rollout by ID."""
        with self._lock:
            return self._rollouts.get(rollout_id)

    def get_by_change_id(self, change_id: str) -> Optional[SafetyRolloutRecord]:
        """Fetch rollout by source change ID."""
        with self._lock:
            rollout_id = self._change_to_rollout.get(change_id)
            if rollout_id:
                return self._rollouts.get(rollout_id)
            return None

    def list_rollouts(
        self,
        organization_id: Optional[str] = None,
        facility_id: Optional[str] = None,
        stage: Optional[RolloutStage] = None,
        lifecycle_state: Optional[RolloutLifecycleState] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[SafetyRolloutRecord]:
        """List rollouts with filtering and pagination."""
        with self._lock:
            results = list(self._rollouts.values())
            if organization_id:
                results = [r for r in results if r.scope.organization_id == organization_id]
            if facility_id:
                results = [r for r in results if r.scope.facility_id == facility_id]
            if stage:
                results = [r for r in results if r.current_stage == stage]
            if lifecycle_state:
                results = [r for r in results if r.lifecycle_state == lifecycle_state]
            results.sort(key=lambda x: x.updated_at, reverse=True)
            return results[offset : offset + limit]

    def list_pending(self, organization_id: Optional[str] = None) -> List[SafetyRolloutRecord]:
        """List active rollouts currently progressing or pending verification."""
        with self._lock:
            pending_states = {
                RolloutLifecycleState.APPROVED,
                RolloutLifecycleState.READINESS_CHECK,
                RolloutLifecycleState.READY,
                RolloutLifecycleState.PREPARING,
                RolloutLifecycleState.ROLLOUT_AUTHORIZED,
                RolloutLifecycleState.CANARY,
                RolloutLifecycleState.CANARY_VALIDATION,
                RolloutLifecycleState.LIMITED_ROLLOUT,
                RolloutLifecycleState.LIMITED_VALIDATION,
                RolloutLifecycleState.EXPANDED_ROLLOUT,
                RolloutLifecycleState.EXPANDED_VALIDATION,
                RolloutLifecycleState.FULL_ROLLOUT,
                RolloutLifecycleState.POST_DEPLOYMENT_VALIDATION,
                RolloutLifecycleState.ASSURANCE_PENDING,
                RolloutLifecycleState.EFFECTIVENESS_PENDING,
            }
            results = [r for r in self._rollouts.values() if r.lifecycle_state in pending_states]
            if organization_id:
                results = [r for r in results if r.scope.organization_id == organization_id]
            results.sort(key=lambda x: x.updated_at, reverse=True)
            return results

    def list_paused(self, organization_id: Optional[str] = None) -> List[SafetyRolloutRecord]:
        """List paused rollouts."""
        with self._lock:
            results = [
                r for r in self._rollouts.values()
                if r.is_paused or r.lifecycle_state == RolloutLifecycleState.PAUSED
            ]
            if organization_id:
                results = [r for r in results if r.scope.organization_id == organization_id]
            results.sort(key=lambda x: x.updated_at, reverse=True)
            return results

    def list_rollback_required(self, organization_id: Optional[str] = None) -> List[SafetyRolloutRecord]:
        """List rollouts flagged for rollback or in rolled-back status."""
        with self._lock:
            rollback_states = {
                RolloutLifecycleState.ROLLBACK_REQUIRED,
                RolloutLifecycleState.ROLLING_BACK,
                RolloutLifecycleState.ROLLED_BACK,
            }
            results = [
                r for r in self._rollouts.values()
                if r.lifecycle_state in rollback_states or r.is_rolled_back
            ]
            if organization_id:
                results = [r for r in results if r.scope.organization_id == organization_id]
            results.sort(key=lambda x: x.updated_at, reverse=True)
            return results

    def list_validation_failed(self, organization_id: Optional[str] = None) -> List[SafetyRolloutRecord]:
        """List rollouts with failed checkpoints or in blocked/failed states."""
        with self._lock:
            results = [
                r for r in self._rollouts.values()
                if any(cp.status == CheckpointStatus.FAILED for cp in r.checkpoints)
                or r.lifecycle_state in {
                    RolloutLifecycleState.BLOCKED,
                    RolloutLifecycleState.FAILED,
                    RolloutLifecycleState.ROLLBACK_REQUIRED,
                }
            ]
            if organization_id:
                results = [r for r in results if r.scope.organization_id == organization_id]
            results.sort(key=lambda x: x.updated_at, reverse=True)
            return results

    def list_active(self, organization_id: Optional[str] = None) -> List[SafetyRolloutRecord]:
        """List active rollouts in non-terminal, unpaused, non-rollback stages."""
        with self._lock:
            active_stages = {
                RolloutStage.CANARY,
                RolloutStage.LIMITED,
                RolloutStage.EXPANDED,
                RolloutStage.FULL,
            }
            terminal_states = {
                RolloutLifecycleState.COMPLETED,
                RolloutLifecycleState.ROLLED_BACK,
                RolloutLifecycleState.CANCELLED,
                RolloutLifecycleState.REJECTED,
                RolloutLifecycleState.SUPERSEDED,
            }
            results = [
                r for r in self._rollouts.values()
                if r.current_stage in active_stages
                and not r.is_paused
                and not r.is_rolled_back
                and r.lifecycle_state not in terminal_states
            ]
            if organization_id:
                results = [r for r in results if r.scope.organization_id == organization_id]
            results.sort(key=lambda x: x.updated_at, reverse=True)
            return results

    def check_idempotency(self, key: str, payload_hash: str) -> Tuple[bool, Optional[str]]:
        """Verify if key has been consumed and if payload matches."""
        with self._lock:
            if key in self._idempotency_store:
                stored_hash, rollout_id, _ = self._idempotency_store[key]
                if stored_hash != payload_hash:
                    return True, None  # Conflict
                return True, rollout_id  # Safe replay
            return False, None

    def record_idempotency(self, key: str, payload_hash: str, rollout_id: str) -> None:
        """Register idempotency key against a rollout."""
        with self._lock:
            self._idempotency_store[key] = (payload_hash, rollout_id, datetime.now(timezone.utc))

    def clear(self) -> None:
        """Reset repository records for test isolation."""
        with self._lock:
            self._rollouts.clear()
            self._change_to_rollout.clear()
            self._idempotency_store.clear()


# Global singleton
_repository_instance: Optional[SafetyRolloutRepository] = None
_repo_init_lock = threading.Lock()


def get_safety_rollout_repository() -> SafetyRolloutRepository:
    """Retrieve global singleton repository."""
    global _repository_instance
    if _repository_instance is None:
        with _repo_init_lock:
            if _repository_instance is None:
                _repository_instance = SafetyRolloutRepository()
    return _repository_instance
