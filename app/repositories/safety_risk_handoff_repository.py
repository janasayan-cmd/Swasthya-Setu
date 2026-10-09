"""Phase 64: Safety Risk Handoff Repository.

Thread-safe repository for Phase 64 safety risk handoffs, acknowledgements,
outcomes, and reconciliation records.
"""

from datetime import datetime, timezone
import threading
from typing import Dict, List, Optional, Tuple

from app.schemas.safety_risk_handoff import (
    HandoffDestinationPhase,
    HandoffLifecycleState,
    SafetyRiskHandoffRecord,
)


class SafetyRiskHandoffRepository:
    """Thread-safe in-memory repository for Phase 64 safety risk handoffs."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._handoffs: Dict[str, SafetyRiskHandoffRecord] = {}
        self._idempotency_store: Dict[str, Tuple[str, str, datetime]] = {}

    def save(self, record: SafetyRiskHandoffRecord) -> SafetyRiskHandoffRecord:
        """Persist or update a handoff record."""
        with self._lock:
            record.updated_at = datetime.now(timezone.utc)
            self._handoffs[record.handoff_id] = record
            if record.idempotency_key:
                self._idempotency_store[record.idempotency_key] = (
                    record.handoff_id,
                    record.organization_id,
                    datetime.now(timezone.utc),
                )
            return record

    def get(self, handoff_id: str) -> Optional[SafetyRiskHandoffRecord]:
        """Retrieve handoff record by ID."""
        with self._lock:
            return self._handoffs.get(handoff_id)

    def get_by_disposition_id(self, disposition_id: str) -> List[SafetyRiskHandoffRecord]:
        """Retrieve handoff records associated with a given Phase 63 disposition ID."""
        with self._lock:
            return [
                h for h in self._handoffs.values()
                if h.source_disposition_id == disposition_id
            ]

    def get_by_review_id(self, review_id: str) -> List[SafetyRiskHandoffRecord]:
        """Retrieve handoff records associated with a given Phase 63 review ID."""
        with self._lock:
            return [
                h for h in self._handoffs.values()
                if h.source_review_id == review_id
            ]

    def get_by_idempotency_key(
        self,
        idempotency_key: str,
        organization_id: Optional[str] = None,
    ) -> Optional[SafetyRiskHandoffRecord]:
        """Retrieve existing handoff by idempotency key."""
        with self._lock:
            entry = self._idempotency_store.get(idempotency_key)
            if not entry:
                return None
            hnd_id, org_id, _ = entry
            if organization_id and org_id != organization_id:
                return None
            return self._handoffs.get(hnd_id)

    def list_handoffs(
        self,
        organization_id: str,
        facility_id: Optional[str] = None,
        state: Optional[HandoffLifecycleState] = None,
        destination_phase: Optional[HandoffDestinationPhase] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[SafetyRiskHandoffRecord]:
        """Filter and list handoffs for a tenant with pagination."""
        with self._lock:
            results = [
                h for h in self._handoffs.values()
                if h.organization_id == organization_id
                and (facility_id is None or h.facility_id == facility_id)
                and (state is None or h.state == state)
                and (destination_phase is None or h.destination_phase == destination_phase)
            ]
            results.sort(key=lambda x: x.created_at, reverse=True)
            return results[offset : offset + limit]

    def list_pending(
        self,
        organization_id: str,
        facility_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[SafetyRiskHandoffRecord]:
        """List handoffs pending submission, acknowledgement, or in progress."""
        pending_states = {
            HandoffLifecycleState.CREATED,
            HandoffLifecycleState.VALIDATING,
            HandoffLifecycleState.READY,
            HandoffLifecycleState.SUBMISSION_PENDING,
            HandoffLifecycleState.SUBMITTED,
            HandoffLifecycleState.ACKNOWLEDGED,
            HandoffLifecycleState.IN_PROGRESS,
            HandoffLifecycleState.OUTCOME_PENDING,
        }
        with self._lock:
            results = [
                h for h in self._handoffs.values()
                if h.organization_id == organization_id
                and (facility_id is None or h.facility_id == facility_id)
                and h.state in pending_states
            ]
            results.sort(key=lambda x: x.created_at, reverse=True)
            return results[offset : offset + limit]

    def list_reconciliation_required(
        self,
        organization_id: str,
        facility_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[SafetyRiskHandoffRecord]:
        """List handoffs that require outcome reconciliation or are conflicted."""
        rec_states = {
            HandoffLifecycleState.OUTCOME_RECEIVED,
            HandoffLifecycleState.RECONCILIATION_PENDING,
            HandoffLifecycleState.RECONCILIATION_REQUIRED,
            HandoffLifecycleState.OUTCOME_CONFLICTED,
            HandoffLifecycleState.OUTCOME_STALE,
        }
        with self._lock:
            results = [
                h for h in self._handoffs.values()
                if h.organization_id == organization_id
                and (facility_id is None or h.facility_id == facility_id)
                and h.state in rec_states
            ]
            results.sort(key=lambda x: x.created_at, reverse=True)
            return results[offset : offset + limit]

    def list_retry_exhausted(
        self,
        organization_id: str,
        facility_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[SafetyRiskHandoffRecord]:
        """List handoffs whose bounded retries have been exhausted."""
        with self._lock:
            results = [
                h for h in self._handoffs.values()
                if h.organization_id == organization_id
                and (facility_id is None or h.facility_id == facility_id)
                and h.state == HandoffLifecycleState.RETRY_EXHAUSTED
            ]
            results.sort(key=lambda x: x.created_at, reverse=True)
            return results[offset : offset + limit]

    def list_escalation_required(
        self,
        organization_id: str,
        facility_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[SafetyRiskHandoffRecord]:
        """List handoffs flagged for operational escalation or manual review."""
        esc_states = {
            HandoffLifecycleState.MANUAL_REVIEW_REQUIRED,
            HandoffLifecycleState.BLOCKED,
            HandoffLifecycleState.REJECTED,
            HandoffLifecycleState.RETRY_EXHAUSTED,
            HandoffLifecycleState.OUTCOME_CONFLICTED,
        }
        with self._lock:
            results = [
                h for h in self._handoffs.values()
                if h.organization_id == organization_id
                and (facility_id is None or h.facility_id == facility_id)
                and (h.state in esc_states or h.escalation_reason is not None)
            ]
            results.sort(key=lambda x: x.created_at, reverse=True)
            return results[offset : offset + limit]

    def clear(self) -> None:
        """Clear all handoff records (primarily for test fixture cleanup)."""
        with self._lock:
            self._handoffs.clear()
            self._idempotency_store.clear()


_handoff_repo_instance: Optional[SafetyRiskHandoffRepository] = None


def get_safety_risk_handoff_repository() -> SafetyRiskHandoffRepository:
    global _handoff_repo_instance
    if _handoff_repo_instance is None:
        _handoff_repo_instance = SafetyRiskHandoffRepository()
    return _handoff_repo_instance
