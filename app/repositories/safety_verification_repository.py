"""Phase 58: Safety Verification Repository.

Thread-safe in-memory repository for change verification records, evidence consolidation,
closure tracking, post-closure monitoring, and idempotency protection.
"""

from datetime import datetime, timezone
import threading
from typing import Dict, List, Optional, Tuple

from app.schemas.safety_verification import (
    SafetyVerificationRecord,
    VerificationLifecycleState,
)


class SafetyVerificationRepository:
    """Thread-safe in-memory repository for Phase 58 safety verifications."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._verifications: Dict[str, SafetyVerificationRecord] = {}
        self._rollout_to_verification: Dict[str, str] = {}
        self._change_to_verification: Dict[str, str] = {}
        self._idempotency_store: Dict[str, Tuple[str, str, datetime]] = {}

    def save(self, record: SafetyVerificationRecord) -> SafetyVerificationRecord:
        """Insert or update verification record."""
        with self._lock:
            record.updated_at = datetime.now(timezone.utc)
            self._verifications[record.verification_id] = record
            self._rollout_to_verification[record.rollout_id] = record.verification_id
            self._change_to_verification[record.change_id] = record.verification_id
            return record

    def get(self, verification_id: str) -> Optional[SafetyVerificationRecord]:
        """Fetch verification by ID."""
        with self._lock:
            return self._verifications.get(verification_id)

    def get_by_rollout_id(self, rollout_id: str) -> Optional[SafetyVerificationRecord]:
        """Fetch verification by Phase 57 rollout ID."""
        with self._lock:
            v_id = self._rollout_to_verification.get(rollout_id)
            if v_id:
                return self._verifications.get(v_id)
            return None

    def get_by_change_id(self, change_id: str) -> Optional[SafetyVerificationRecord]:
        """Fetch verification by Phase 51 change ID."""
        with self._lock:
            v_id = self._change_to_verification.get(change_id)
            if v_id:
                return self._verifications.get(v_id)
            return None

    def list_verifications(
        self,
        organization_id: Optional[str] = None,
        facility_id: Optional[str] = None,
        verification_status: Optional[VerificationLifecycleState] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[SafetyVerificationRecord]:
        """List verifications with filtering and pagination."""
        with self._lock:
            results = list(self._verifications.values())
            if organization_id:
                results = [r for r in results if r.scope.organization_id == organization_id]
            if facility_id:
                results = [r for r in results if r.scope.facility_id == facility_id]
            if verification_status:
                results = [r for r in results if r.verification_status == verification_status]
            results.sort(key=lambda x: x.updated_at, reverse=True)
            return results[offset : offset + limit]

    def list_pending(self, organization_id: Optional[str] = None) -> List[SafetyVerificationRecord]:
        """List verifications in progress or pending evidence collection."""
        with self._lock:
            pending_states = {
                VerificationLifecycleState.PENDING,
                VerificationLifecycleState.COLLECTING_EVIDENCE,
                VerificationLifecycleState.EVIDENCE_INCOMPLETE,
                VerificationLifecycleState.VERIFICATION_IN_PROGRESS,
            }
            results = [r for r in self._verifications.values() if r.verification_status in pending_states]
            if organization_id:
                results = [r for r in results if r.scope.organization_id == organization_id]
            results.sort(key=lambda x: x.updated_at, reverse=True)
            return results

    def list_review_required(self, organization_id: Optional[str] = None) -> List[SafetyVerificationRecord]:
        """List verifications requiring human supervisor review."""
        with self._lock:
            results = [
                r for r in self._verifications.values()
                if r.verification_status == VerificationLifecycleState.HUMAN_REVIEW_REQUIRED
            ]
            if organization_id:
                results = [r for r in results if r.scope.organization_id == organization_id]
            results.sort(key=lambda x: x.updated_at, reverse=True)
            return results

    def list_closure_pending(self, organization_id: Optional[str] = None) -> List[SafetyVerificationRecord]:
        """List verifications verified and awaiting controlled closure."""
        with self._lock:
            closure_states = {
                VerificationLifecycleState.CLOSURE_PENDING,
                VerificationLifecycleState.VERIFIED,
                VerificationLifecycleState.CONDITIONALLY_VERIFIED,
            }
            results = [
                r for r in self._verifications.values()
                if (r.verification_status in closure_states or r.closure_eligible)
                and r.verification_status != VerificationLifecycleState.CLOSED
            ]
            if organization_id:
                results = [r for r in results if r.scope.organization_id == organization_id]
            results.sort(key=lambda x: x.updated_at, reverse=True)
            return results

    def list_reopened(self, organization_id: Optional[str] = None) -> List[SafetyVerificationRecord]:
        """List verifications reopened for reinvestigation or reassessment."""
        with self._lock:
            reopened_states = {
                VerificationLifecycleState.REOPENED,
                VerificationLifecycleState.REOPEN_REQUIRED,
            }
            results = [
                r for r in self._verifications.values()
                if r.verification_status in reopened_states or len(r.reopen_history) > 0
            ]
            if organization_id:
                results = [r for r in results if r.scope.organization_id == organization_id]
            results.sort(key=lambda x: x.updated_at, reverse=True)
            return results

    def check_idempotency(self, key: str, payload_hash: str) -> Tuple[bool, Optional[str]]:
        """Verify if key has been consumed and if payload matches."""
        with self._lock:
            if key in self._idempotency_store:
                stored_hash, v_id, _ = self._idempotency_store[key]
                if stored_hash != payload_hash:
                    return True, None  # Conflict
                return True, v_id  # Safe replay
            return False, None

    def record_idempotency(self, key: str, payload_hash: str, verification_id: str) -> None:
        """Register idempotency key against a verification."""
        with self._lock:
            self._idempotency_store[key] = (payload_hash, verification_id, datetime.now(timezone.utc))

    def clear(self) -> None:
        """Reset repository records for test isolation."""
        with self._lock:
            self._verifications.clear()
            self._rollout_to_verification.clear()
            self._change_to_verification.clear()
            self._idempotency_store.clear()


# Global singleton
_repository_instance: Optional[SafetyVerificationRepository] = None
_repo_init_lock = threading.Lock()


def get_safety_verification_repository() -> SafetyVerificationRepository:
    """Retrieve global singleton repository."""
    global _repository_instance
    if _repository_instance is None:
        with _repo_init_lock:
            if _repository_instance is None:
                _repository_instance = SafetyVerificationRepository()
    return _repository_instance
