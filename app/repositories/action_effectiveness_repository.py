"""Phase 55: Action Effectiveness In-Memory Repository.

Stores effectiveness evaluations, criteria, observations, reviews, and idempotency records.
Thread-safe with reentrant locking for high-concurrency assurance pipelines.
"""

from datetime import datetime, timezone
import threading
from typing import Dict, List, Optional, Tuple

from app.schemas.action_effectiveness import (
    EffectivenessEvaluationRecord,
    EffectivenessLifecycleState,
    EffectivenessState,
)


class ActionEffectivenessRepository:
    """Thread-safe in-memory repository for Phase 55 effectiveness evaluations."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._evaluations: Dict[str, EffectivenessEvaluationRecord] = {}
        self._action_to_evaluation: Dict[str, str] = {}
        self._idempotency_store: Dict[str, Tuple[str, str, datetime]] = {}  # key -> (payload_hash, eval_id, created_at)

    def save(self, evaluation: EffectivenessEvaluationRecord) -> EffectivenessEvaluationRecord:
        """Insert or update an evaluation record."""
        with self._lock:
            evaluation.updated_at = datetime.now(timezone.utc)
            self._evaluations[evaluation.evaluation_id] = evaluation
            self._action_to_evaluation[evaluation.action_id] = evaluation.evaluation_id
            return evaluation

    def get(self, evaluation_id: str) -> Optional[EffectivenessEvaluationRecord]:
        """Fetch evaluation by ID."""
        with self._lock:
            return self._evaluations.get(evaluation_id)

    def get_by_action_id(self, action_id: str) -> Optional[EffectivenessEvaluationRecord]:
        """Fetch evaluation for a specific safety action."""
        with self._lock:
            eval_id = self._action_to_evaluation.get(action_id)
            if eval_id:
                return self._evaluations.get(eval_id)
            return None

    def list_evaluations(
        self,
        organization_id: Optional[str] = None,
        facility_id: Optional[str] = None,
        lifecycle_state: Optional[EffectivenessLifecycleState] = None,
        effectiveness_state: Optional[EffectivenessState] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[EffectivenessEvaluationRecord]:
        """List evaluations matching criteria."""
        with self._lock:
            results = list(self._evaluations.values())
            if organization_id:
                results = [e for e in results if e.scope.organization_id == organization_id]
            if facility_id:
                results = [e for e in results if e.scope.facility_id == facility_id]
            if lifecycle_state:
                results = [e for e in results if e.lifecycle_state == lifecycle_state]
            if effectiveness_state:
                results = [e for e in results if e.effectiveness_state == effectiveness_state]
            # Order by updated_at descending
            results.sort(key=lambda x: x.updated_at, reverse=True)
            return results[offset : offset + limit]

    def list_pending(self, organization_id: Optional[str] = None) -> List[EffectivenessEvaluationRecord]:
        """List evaluations currently pending evidence or active observation."""
        with self._lock:
            pending_states = {
                EffectivenessLifecycleState.COMPLETION_RECEIVED,
                EffectivenessLifecycleState.SCOPE_VALIDATION,
                EffectivenessLifecycleState.OBJECTIVE_IDENTIFICATION,
                EffectivenessLifecycleState.CRITERIA_RESOLUTION,
                EffectivenessLifecycleState.WINDOW_DEFINED,
                EffectivenessLifecycleState.EVIDENCE_COLLECTION,
                EffectivenessLifecycleState.EVIDENCE_VALIDATION,
                EffectivenessLifecycleState.COMPARISON,
                EffectivenessLifecycleState.EFFECTIVENESS_ASSESSMENT,
            }
            results = [e for e in self._evaluations.values() if e.lifecycle_state in pending_states]
            if organization_id:
                results = [e for e in results if e.scope.organization_id == organization_id]
            results.sort(key=lambda x: x.updated_at, reverse=True)
            return results

    def list_review_required(self, organization_id: Optional[str] = None) -> List[EffectivenessEvaluationRecord]:
        """List evaluations awaiting human review."""
        with self._lock:
            results = [
                e
                for e in self._evaluations.values()
                if e.lifecycle_state in {
                    EffectivenessLifecycleState.REVIEW_REQUIRED,
                    EffectivenessLifecycleState.HUMAN_REVIEW,
                }
                or e.requires_human_review
            ]
            if organization_id:
                results = [e for e in results if e.scope.organization_id == organization_id]
            results.sort(key=lambda x: x.updated_at, reverse=True)
            return results

    def list_regressions(self, organization_id: Optional[str] = None) -> List[EffectivenessEvaluationRecord]:
        """List evaluations where control regression has been detected."""
        with self._lock:
            results = [
                e
                for e in self._evaluations.values()
                if e.regression_detected
                or e.lifecycle_state == EffectivenessLifecycleState.REGRESSED
                or e.effectiveness_state == EffectivenessState.REGRESSED
            ]
            if organization_id:
                results = [e for e in results if e.scope.organization_id == organization_id]
            results.sort(key=lambda x: x.updated_at, reverse=True)
            return results

    def list_insufficient_evidence(self, organization_id: Optional[str] = None) -> List[EffectivenessEvaluationRecord]:
        """List evaluations blocked by insufficient or missing evidence."""
        with self._lock:
            results = [
                e
                for e in self._evaluations.values()
                if e.lifecycle_state == EffectivenessLifecycleState.INSUFFICIENT_EVIDENCE
                or e.effectiveness_state == EffectivenessState.INSUFFICIENT_EVIDENCE
            ]
            if organization_id:
                results = [e for e in results if e.scope.organization_id == organization_id]
            results.sort(key=lambda x: x.updated_at, reverse=True)
            return results

    def list_failed(self, organization_id: Optional[str] = None) -> List[EffectivenessEvaluationRecord]:
        """List evaluations where action failed to achieve effectiveness objective."""
        with self._lock:
            results = [
                e
                for e in self._evaluations.values()
                if e.lifecycle_state == EffectivenessLifecycleState.FAILED
                or e.effectiveness_state == EffectivenessState.FAILED
            ]
            if organization_id:
                results = [e for e in results if e.scope.organization_id == organization_id]
            results.sort(key=lambda x: x.updated_at, reverse=True)
            return results

    def check_idempotency(self, key: str, payload_hash: str) -> Tuple[bool, Optional[str]]:
        """Verify if idempotency key has been used.
        Returns: (is_duplicate, existing_evaluation_id)
        """
        with self._lock:
            if key in self._idempotency_store:
                stored_hash, eval_id, _ = self._idempotency_store[key]
                if stored_hash != payload_hash:
                    # Conflicting payload with same key
                    return True, None
                return True, eval_id
            return False, None

    def record_idempotency(self, key: str, payload_hash: str, evaluation_id: str) -> None:
        """Register idempotency key against an evaluation."""
        with self._lock:
            self._idempotency_store[key] = (payload_hash, evaluation_id, datetime.now(timezone.utc))

    def clear(self) -> None:
        """Clear all in-memory records (for tests)."""
        with self._lock:
            self._evaluations.clear(
                )
            self._action_to_evaluation.clear()
            self._idempotency_store.clear()


# Global singleton instance
_repository_instance: Optional[ActionEffectivenessRepository] = None
_repo_init_lock = threading.Lock()


def get_action_effectiveness_repository() -> ActionEffectivenessRepository:
    """Retrieve global singleton repository instance."""
    global _repository_instance
    if _repository_instance is None:
        with _repo_init_lock:
            if _repository_instance is None:
                _repository_instance = ActionEffectivenessRepository()
    return _repository_instance
