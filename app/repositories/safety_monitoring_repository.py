"""Phase 59: Safety Monitoring Repository.

Thread-safe in-memory repository for post-closure surveillance contexts,
signals, thresholds, triggers, and idempotency protection.
"""

from datetime import datetime, timezone
import threading
from typing import Dict, List, Optional, Set, Tuple

from app.schemas.safety_monitoring import (
    MonitoringLifecycleState,
    SafetyMonitoringRecord,
)


class SafetyMonitoringRepository:
    """Thread-safe in-memory repository for Phase 59 safety monitoring."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._monitoring_contexts: Dict[str, SafetyMonitoringRecord] = {}
        self._verification_to_mon: Dict[str, str] = {}
        self._change_to_mon: Dict[str, str] = {}
        self._idempotency_store: Dict[str, Tuple[str, str, datetime]] = {}
        self._seen_signal_keys: Dict[str, Set[str]] = {}

    def save(self, record: SafetyMonitoringRecord) -> SafetyMonitoringRecord:
        """Insert or update monitoring record."""
        with self._lock:
            record.updated_at = datetime.now(timezone.utc)
            self._monitoring_contexts[record.monitoring_id] = record
            self._verification_to_mon[record.verification_id] = record.monitoring_id
            self._change_to_mon[record.change_id] = record.monitoring_id
            return record

    def get(self, monitoring_id: str) -> Optional[SafetyMonitoringRecord]:
        """Fetch monitoring context by ID."""
        with self._lock:
            return self._monitoring_contexts.get(monitoring_id)

    def get_by_verification_id(self, verification_id: str) -> Optional[SafetyMonitoringRecord]:
        """Fetch monitoring context by Phase 58 verification ID."""
        with self._lock:
            m_id = self._verification_to_mon.get(verification_id)
            if m_id:
                return self._monitoring_contexts.get(m_id)
            return None

    def get_by_change_id(self, change_id: str) -> Optional[SafetyMonitoringRecord]:
        """Fetch monitoring context by Phase 51 change ID."""
        with self._lock:
            m_id = self._change_to_mon.get(change_id)
            if m_id:
                return self._monitoring_contexts.get(m_id)
            return None

    def list_monitoring(
        self,
        organization_id: Optional[str] = None,
        facility_id: Optional[str] = None,
        lifecycle_state: Optional[MonitoringLifecycleState] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[SafetyMonitoringRecord]:
        """List monitoring records with filtering and pagination."""
        with self._lock:
            results = list(self._monitoring_contexts.values())
            if organization_id:
                results = [r for r in results if r.scope.organization_id == organization_id]
            if facility_id:
                results = [r for r in results if r.scope.facility_id == facility_id]
            if lifecycle_state:
                results = [r for r in results if r.lifecycle_state == lifecycle_state]
            results.sort(key=lambda x: x.updated_at, reverse=True)
            return results[offset : offset + limit]

    def list_active(self, organization_id: Optional[str] = None) -> List[SafetyMonitoringRecord]:
        """List active surveillance contexts currently in flight."""
        with self._lock:
            active_states = {
                MonitoringLifecycleState.ACTIVE,
                MonitoringLifecycleState.OBSERVING,
                MonitoringLifecycleState.CHECKPOINT_PENDING,
                MonitoringLifecycleState.SIGNAL_DETECTED,
                MonitoringLifecycleState.SIGNAL_VALIDATING,
            }
            results = [
                r for r in self._monitoring_contexts.values()
                if r.lifecycle_state in active_states and not r.is_paused
            ]
            if organization_id:
                results = [r for r in results if r.scope.organization_id == organization_id]
            results.sort(key=lambda x: x.updated_at, reverse=True)
            return results

    def list_review_required(self, organization_id: Optional[str] = None) -> List[SafetyMonitoringRecord]:
        """List surveillance contexts requiring human supervisor review."""
        with self._lock:
            results = [
                r for r in self._monitoring_contexts.values()
                if r.lifecycle_state == MonitoringLifecycleState.REVIEW_REQUIRED
            ]
            if organization_id:
                results = [r for r in results if r.scope.organization_id == organization_id]
            results.sort(key=lambda x: x.updated_at, reverse=True)
            return results

    def list_reopen_required(self, organization_id: Optional[str] = None) -> List[SafetyMonitoringRecord]:
        """List surveillance contexts with active reopen triggers."""
        with self._lock:
            results = [
                r for r in self._monitoring_contexts.values()
                if r.lifecycle_state == MonitoringLifecycleState.REOPEN_REQUIRED
                or any(t.trigger_type == "REOPEN_TRIGGER" and t.status in ("DETECTED", "REVIEW_REQUIRED") for t in r.triggers)
            ]
            if organization_id:
                results = [r for r in results if r.scope.organization_id == organization_id]
            results.sort(key=lambda x: x.updated_at, reverse=True)
            return results

    def list_escalation_required(self, organization_id: Optional[str] = None) -> List[SafetyMonitoringRecord]:
        """List surveillance contexts requiring cross-phase escalation."""
        with self._lock:
            results = [
                r for r in self._monitoring_contexts.values()
                if r.lifecycle_state == MonitoringLifecycleState.ESCALATION_REQUIRED
                or any(t.trigger_type == "ESCALATION_TRIGGER" and t.status in ("DETECTED", "REVIEW_REQUIRED") for t in r.triggers)
            ]
            if organization_id:
                results = [r for r in results if r.scope.organization_id == organization_id]
            results.sort(key=lambda x: x.updated_at, reverse=True)
            return results

    def is_signal_duplicate(self, monitoring_id: str, dedup_key: str) -> bool:
        """Check if deduplication key has been seen for this monitoring context."""
        with self._lock:
            if monitoring_id not in self._seen_signal_keys:
                return False
            return dedup_key in self._seen_signal_keys[monitoring_id]

    def record_signal_dedup(self, monitoring_id: str, dedup_key: str) -> None:
        """Register seen deduplication key."""
        with self._lock:
            if monitoring_id not in self._seen_signal_keys:
                self._seen_signal_keys[monitoring_id] = set()
            self._seen_signal_keys[monitoring_id].add(dedup_key)

    def check_idempotency(self, key: str, payload_hash: str) -> Tuple[bool, Optional[str]]:
        """Verify if key has been consumed and if payload matches."""
        with self._lock:
            if key in self._idempotency_store:
                stored_hash, m_id, _ = self._idempotency_store[key]
                if stored_hash != payload_hash:
                    return True, None  # Conflict
                return True, m_id  # Safe replay
            return False, None

    def record_idempotency(self, key: str, payload_hash: str, monitoring_id: str) -> None:
        """Register idempotency key against a monitoring record."""
        with self._lock:
            self._idempotency_store[key] = (payload_hash, monitoring_id, datetime.now(timezone.utc))

    def clear(self) -> None:
        """Reset repository records for test isolation."""
        with self._lock:
            self._monitoring_contexts.clear()
            self._verification_to_mon.clear()
            self._change_to_mon.clear()
            self._idempotency_store.clear()
            self._seen_signal_keys.clear()


# Global singleton
_repository_instance: Optional[SafetyMonitoringRepository] = None
_repo_init_lock = threading.Lock()


def get_safety_monitoring_repository() -> SafetyMonitoringRepository:
    """Retrieve global singleton repository."""
    global _repository_instance
    if _repository_instance is None:
        with _repo_init_lock:
            if _repository_instance is None:
                _repository_instance = SafetyMonitoringRepository()
    return _repository_instance
