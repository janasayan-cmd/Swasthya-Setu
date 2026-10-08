"""Phase 60: Safety Triage Repository.

Thread-safe repository for safety triage contexts, classification,
severity evaluations, and governed routing history.
"""

from datetime import datetime, timezone
import threading
from typing import Dict, List, Optional, Set, Tuple

from app.schemas.safety_triage import (
    EscalationRoutingPriority,
    GovernedSignalSeverity,
    RoutingDestination,
    SafetyTriageRecord,
    TriageLifecycleState,
)


class SafetyTriageRepository:
    """Thread-safe in-memory repository for Phase 60 safety triage records."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._triage_records: Dict[str, SafetyTriageRecord] = {}
        self._signal_to_triage: Dict[str, str] = {}
        self._idempotency_store: Dict[str, Tuple[str, str, datetime]] = {}

    def save(self, record: SafetyTriageRecord) -> SafetyTriageRecord:
        """Persist or update triage record."""
        with self._lock:
            record.updated_at = datetime.now(timezone.utc)
            self._triage_records[record.triage_id] = record
            self._signal_to_triage[record.primary_signal_id] = record.triage_id
            for s in record.signals:
                self._signal_to_triage[s.signal_id] = record.triage_id
            return record

    def get(self, triage_id: str) -> Optional[SafetyTriageRecord]:
        """Retrieve triage record by ID."""
        with self._lock:
            return self._triage_records.get(triage_id)

    def get_by_signal_id(self, signal_id: str) -> Optional[SafetyTriageRecord]:
        """Retrieve triage record associated with a signal ID."""
        with self._lock:
            triage_id = self._signal_to_triage.get(signal_id)
            if triage_id:
                return self._triage_records.get(triage_id)
            return None

    def list_triage(
        self,
        organization_id: Optional[str] = None,
        facility_id: Optional[str] = None,
        lifecycle_state: Optional[TriageLifecycleState] = None,
        severity: Optional[GovernedSignalSeverity] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[SafetyTriageRecord]:
        """Query triage records with multi-tenant filtering."""
        with self._lock:
            results = list(self._triage_records.values())

            if organization_id:
                results = [r for r in results if r.organization_id == organization_id]
            if facility_id:
                results = [r for r in results if r.scope.facility_id == facility_id]
            if lifecycle_state:
                results = [r for r in results if r.lifecycle_state == lifecycle_state]
            if severity:
                results = [r for r in results if r.governed_severity == severity]

            results.sort(key=lambda x: x.updated_at, reverse=True)
            return results[offset : offset + limit]

    def list_review_required(self, organization_id: Optional[str] = None) -> List[SafetyTriageRecord]:
        """List triage records requiring human review."""
        with self._lock:
            results = [
                r for r in self._triage_records.values()
                if r.requires_human_review or r.lifecycle_state == TriageLifecycleState.REVIEW_REQUIRED
            ]
            if organization_id:
                results = [r for r in results if r.organization_id == organization_id]
            results.sort(key=lambda x: x.updated_at, reverse=True)
            return results

    def list_high_priority(self, organization_id: Optional[str] = None) -> List[SafetyTriageRecord]:
        """List high-priority or urgent triage records."""
        with self._lock:
            high_priorities = {
                EscalationRoutingPriority.HIGH_PRIORITY_REVIEW,
                EscalationRoutingPriority.URGENT_GOVERNANCE_REVIEW,
                EscalationRoutingPriority.CRITICAL_ESCALATION,
            }
            results = [
                r for r in self._triage_records.values()
                if r.priority in high_priorities or r.governed_severity in (GovernedSignalSeverity.HIGH, GovernedSignalSeverity.CRITICAL)
            ]
            if organization_id:
                results = [r for r in results if r.organization_id == organization_id]
            results.sort(key=lambda x: x.updated_at, reverse=True)
            return results

    def list_escalation_required(self, organization_id: Optional[str] = None) -> List[SafetyTriageRecord]:
        """List triage records requiring escalation."""
        with self._lock:
            results = [
                r for r in self._triage_records.values()
                if r.is_escalated or r.lifecycle_state == TriageLifecycleState.ESCALATION_REQUIRED
            ]
            if organization_id:
                results = [r for r in results if r.organization_id == organization_id]
            results.sort(key=lambda x: x.updated_at, reverse=True)
            return results

    def list_reopen_required(self, organization_id: Optional[str] = None) -> List[SafetyTriageRecord]:
        """List triage records requiring Phase 58 reopen review."""
        with self._lock:
            results = [
                r for r in self._triage_records.values()
                if r.reopen_triggered
                or r.lifecycle_state == TriageLifecycleState.REOPEN_REQUIRED
                or any(d.destination == RoutingDestination.PHASE_58_REOPEN_REVIEW for d in r.routing_decisions)
            ]
            if organization_id:
                results = [r for r in results if r.organization_id == organization_id]
            results.sort(key=lambda x: x.updated_at, reverse=True)
            return results

    def list_incident_routing_required(self, organization_id: Optional[str] = None) -> List[SafetyTriageRecord]:
        """List triage records requiring Phase 49 incident routing."""
        with self._lock:
            results = [
                r for r in self._triage_records.values()
                if r.lifecycle_state == TriageLifecycleState.INCIDENT_ROUTING_REQUIRED
                or any(d.destination == RoutingDestination.PHASE_49_INCIDENT_ROUTING for d in r.routing_decisions)
            ]
            if organization_id:
                results = [r for r in results if r.organization_id == organization_id]
            results.sort(key=lambda x: x.updated_at, reverse=True)
            return results

    def list_governance_routing_required(self, organization_id: Optional[str] = None) -> List[SafetyTriageRecord]:
        """List triage records requiring Phase 51 governance routing."""
        with self._lock:
            results = [
                r for r in self._triage_records.values()
                if r.lifecycle_state == TriageLifecycleState.GOVERNANCE_ROUTING_REQUIRED
                or any(d.destination == RoutingDestination.PHASE_51_GOVERNANCE_REVIEW for d in r.routing_decisions)
            ]
            if organization_id:
                results = [r for r in results if r.organization_id == organization_id]
            results.sort(key=lambda x: x.updated_at, reverse=True)
            return results

    def check_idempotency(self, key: str, payload_hash: str) -> Tuple[bool, Optional[str]]:
        """Verify if key has been consumed and if payload matches."""
        with self._lock:
            if key in self._idempotency_store:
                stored_hash, t_id, _ = self._idempotency_store[key]
                if stored_hash != payload_hash:
                    return True, None  # Conflict
                return True, t_id  # Safe replay
            return False, None

    def record_idempotency(self, key: str, payload_hash: str, triage_id: str) -> None:
        """Register idempotency key against a triage record."""
        with self._lock:
            self._idempotency_store[key] = (payload_hash, triage_id, datetime.now(timezone.utc))

    def clear(self) -> None:
        """Reset repository records for test isolation."""
        with self._lock:
            self._triage_records.clear()
            self._signal_to_triage.clear()
            self._idempotency_store.clear()


# Global singleton
_repository_instance: Optional[SafetyTriageRepository] = None
_repo_init_lock = threading.Lock()


def get_safety_triage_repository() -> SafetyTriageRepository:
    """Retrieve global singleton repository."""
    global _repository_instance
    if _repository_instance is None:
        with _repo_init_lock:
            if _repository_instance is None:
                _repository_instance = SafetyTriageRepository()
    return _repository_instance
