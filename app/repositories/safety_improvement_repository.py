"""Phase 56: Safety Improvement Repository.

Thread-safe in-memory repository for continuous safety improvement tracking,
proposals, readiness evaluation, and idempotency protection.
"""

from datetime import datetime, timezone
import threading
from typing import Dict, List, Optional, Tuple

from app.schemas.safety_improvement import (
    ImprovementLifecycleState,
    ImprovementPriority,
    ImprovementResponseType,
    SafetyImprovementRecord,
)


class SafetyImprovementRepository:
    """Thread-safe in-memory repository for Phase 56 safety improvements."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._improvements: Dict[str, SafetyImprovementRecord] = {}
        self._eval_to_improvement: Dict[str, str] = {}
        self._idempotency_store: Dict[str, Tuple[str, str, datetime]] = {}

    def save(self, record: SafetyImprovementRecord) -> SafetyImprovementRecord:
        """Insert or update improvement record."""
        with self._lock:
            record.updated_at = datetime.now(timezone.utc)
            self._improvements[record.improvement_id] = record
            self._eval_to_improvement[record.source_evaluation_id] = record.improvement_id
            return record

    def get(self, improvement_id: str) -> Optional[SafetyImprovementRecord]:
        """Fetch improvement by ID."""
        with self._lock:
            return self._improvements.get(improvement_id)

    def get_by_evaluation_id(self, evaluation_id: str) -> Optional[SafetyImprovementRecord]:
        """Fetch improvement by source evaluation ID."""
        with self._lock:
            imp_id = self._eval_to_improvement.get(evaluation_id)
            if imp_id:
                return self._improvements.get(imp_id)
            return None

    def list_improvements(
        self,
        organization_id: Optional[str] = None,
        facility_id: Optional[str] = None,
        lifecycle_state: Optional[ImprovementLifecycleState] = None,
        priority: Optional[ImprovementPriority] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[SafetyImprovementRecord]:
        """List improvements with filter criteria."""
        with self._lock:
            results = list(self._improvements.values())
            if organization_id:
                results = [r for r in results if r.scope.organization_id == organization_id]
            if facility_id:
                results = [r for r in results if r.scope.facility_id == facility_id]
            if lifecycle_state:
                results = [r for r in results if r.lifecycle_state == lifecycle_state]
            if priority:
                results = [r for r in results if r.priority == priority]
            results.sort(key=lambda x: x.updated_at, reverse=True)
            return results[offset : offset + limit]

    def list_pending(self, organization_id: Optional[str] = None) -> List[SafetyImprovementRecord]:
        """List active improvements in non-terminal states."""
        with self._lock:
            pending_states = {
                ImprovementLifecycleState.SIGNAL_IDENTIFIED,
                ImprovementLifecycleState.CLASSIFIED,
                ImprovementLifecycleState.ANALYZING,
                ImprovementLifecycleState.CHANGE_PROPOSED,
                ImprovementLifecycleState.IMPACT_ASSESSED,
                ImprovementLifecycleState.CHANGE_READY,
                ImprovementLifecycleState.GOVERNANCE_ROUTED,
                ImprovementLifecycleState.IMPLEMENTING,
                ImprovementLifecycleState.VALIDATING,
            }
            results = [r for r in self._improvements.values() if r.lifecycle_state in pending_states]
            if organization_id:
                results = [r for r in results if r.scope.organization_id == organization_id]
            results.sort(key=lambda x: x.updated_at, reverse=True)
            return results

    def list_high_priority(self, organization_id: Optional[str] = None) -> List[SafetyImprovementRecord]:
        """List improvements with HIGH or CRITICAL priority."""
        with self._lock:
            results = [
                r for r in self._improvements.values()
                if r.priority in (ImprovementPriority.HIGH, ImprovementPriority.CRITICAL)
            ]
            if organization_id:
                results = [r for r in results if r.scope.organization_id == organization_id]
            results.sort(key=lambda x: x.updated_at, reverse=True)
            return results

    def list_regressions(self, organization_id: Optional[str] = None) -> List[SafetyImprovementRecord]:
        """List improvements triggered by control regression."""
        with self._lock:
            results = [r for r in self._improvements.values() if r.is_regression]
            if organization_id:
                results = [r for r in results if r.scope.organization_id == organization_id]
            results.sort(key=lambda x: x.updated_at, reverse=True)
            return results

    def list_recurring(self, organization_id: Optional[str] = None) -> List[SafetyImprovementRecord]:
        """List recurring failure or recurring reassessment patterns."""
        with self._lock:
            results = [r for r in self._improvements.values() if r.is_recurring]
            if organization_id:
                results = [r for r in results if r.scope.organization_id == organization_id]
            results.sort(key=lambda x: x.updated_at, reverse=True)
            return results

    def list_change_candidates(self, organization_id: Optional[str] = None) -> List[SafetyImprovementRecord]:
        """List opportunities identified for governed change requests."""
        with self._lock:
            results = [
                r for r in self._improvements.values()
                if r.response_type == ImprovementResponseType.CREATE_CHANGE_REQUEST
                or r.change_proposal is not None
            ]
            if organization_id:
                results = [r for r in results if r.scope.organization_id == organization_id]
            results.sort(key=lambda x: x.updated_at, reverse=True)
            return results

    def check_idempotency(self, key: str, payload_hash: str) -> Tuple[bool, Optional[str]]:
        """Verify if key has been consumed."""
        with self._lock:
            if key in self._idempotency_store:
                stored_hash, imp_id, _ = self._idempotency_store[key]
                if stored_hash != payload_hash:
                    return True, None
                return True, imp_id
            return False, None

    def record_idempotency(self, key: str, payload_hash: str, improvement_id: str) -> None:
        """Register idempotency key against an improvement."""
        with self._lock:
            self._idempotency_store[key] = (payload_hash, improvement_id, datetime.now(timezone.utc))

    def clear(self) -> None:
        """Reset repository records for test isolation."""
        with self._lock:
            self._improvements.clear()
            self._eval_to_improvement.clear()
            self._idempotency_store.clear()


# Global singleton
_repository_instance: Optional[SafetyImprovementRepository] = None
_repo_init_lock = threading.Lock()


def get_safety_improvement_repository() -> SafetyImprovementRepository:
    """Retrieve global singleton repository."""
    global _repository_instance
    if _repository_instance is None:
        with _repo_init_lock:
            if _repository_instance is None:
                _repository_instance = SafetyImprovementRepository()
    return _repository_instance
