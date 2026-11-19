"""Phase 67: Governance Escalation Repository.

Thread-safe repository for Phase 67 cross-workflow governance escalations,
exceptions, reviews, decisions, conflicts, resolution requirements, and audit transitions.
"""

from datetime import datetime, timezone
import threading
from typing import Dict, List, Optional, Tuple

from app.schemas.governance_decision_coordination import (
    CrossWorkflowConflictRecord,
    GovernanceDecisionRecord,
    GovernanceReviewRecord,
)
from app.schemas.governance_escalation import (
    EscalationHistoryRecord,
    EscalationLifecycleState,
    GovernanceEscalationRecord,
)
from app.schemas.governance_exception import (
    GovernanceExceptionRecord,
    GovernancePriority,
)
from app.schemas.governance_resolution_requirement import (
    ResolutionRequirementRecord,
)


class GovernanceEscalationRepository:
    """Thread-safe in-memory repository for Phase 67 governance escalation entities."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._escalations: Dict[str, GovernanceEscalationRecord] = {}
        self._exceptions: Dict[str, GovernanceExceptionRecord] = {}
        self._reviews: Dict[str, List[GovernanceReviewRecord]] = {}
        self._decisions: Dict[str, List[GovernanceDecisionRecord]] = {}
        self._conflicts: Dict[str, List[CrossWorkflowConflictRecord]] = {}
        self._requirements: Dict[str, ResolutionRequirementRecord] = {}
        self._history: Dict[str, List[EscalationHistoryRecord]] = {}
        self._idempotency_store: Dict[str, Tuple[str, str, datetime]] = {}

    # -------------------------------------------------------------------------
    # Escalations
    # -------------------------------------------------------------------------

    def save_escalation(self, record: GovernanceEscalationRecord) -> GovernanceEscalationRecord:
        """Persist or update an escalation record."""
        with self._lock:
            record.updated_at = datetime.now(timezone.utc)
            self._escalations[record.escalation_id] = record
            if record.idempotency_key:
                self._idempotency_store[record.idempotency_key] = (
                    record.escalation_id,
                    record.organization_id,
                    datetime.now(timezone.utc),
                )
            return record

    def get_escalation(self, escalation_id: str) -> Optional[GovernanceEscalationRecord]:
        """Retrieve an escalation by its ID."""
        with self._lock:
            return self._escalations.get(escalation_id)

    def list_escalations(
        self,
        organization_id: str,
        facility_id: Optional[str] = None,
        priority: Optional[GovernancePriority] = None,
        state: Optional[EscalationLifecycleState] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[GovernanceEscalationRecord]:
        """List escalations with optional filtering and pagination."""
        with self._lock:
            results = [
                e for e in self._escalations.values()
                if e.organization_id == organization_id
                and (facility_id is None or e.facility_id == facility_id)
                and (priority is None or e.governance_priority == priority)
                and (state is None or e.lifecycle_state == state)
            ]
            results.sort(key=lambda x: x.created_at, reverse=True)
            return results[offset : offset + limit]

    def list_unassigned_escalations(
        self,
        organization_id: str,
        facility_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[GovernanceEscalationRecord]:
        """List escalations requiring an assigned owner."""
        with self._lock:
            results = [
                e for e in self._escalations.values()
                if e.organization_id == organization_id
                and (facility_id is None or e.facility_id == facility_id)
                and (e.assigned_owner_id is None or e.lifecycle_state in {
                    EscalationLifecycleState.DETECTED,
                    EscalationLifecycleState.VALIDATING,
                    EscalationLifecycleState.CLASSIFICATION_PENDING,
                    EscalationLifecycleState.CLASSIFIED,
                    EscalationLifecycleState.ROUTING_PENDING,
                    EscalationLifecycleState.ROUTED,
                    EscalationLifecycleState.OWNERSHIP_PENDING,
                })
                and e.lifecycle_state not in {
                    EscalationLifecycleState.RESOLVED,
                    EscalationLifecycleState.CLOSED,
                    EscalationLifecycleState.CANCELLED,
                    EscalationLifecycleState.SUPERSEDED,
                }
            ]
            results.sort(key=lambda x: x.created_at, reverse=True)
            return results[offset : offset + limit]

    def list_overdue_escalations(
        self,
        organization_id: str,
        facility_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[GovernanceEscalationRecord]:
        """List active escalations that have breached an acknowledgement or review deadline."""
        now = datetime.now(timezone.utc)
        with self._lock:
            results = [
                e for e in self._escalations.values()
                if e.organization_id == organization_id
                and (facility_id is None or e.facility_id == facility_id)
                and (
                    e.is_overdue
                    or (e.acknowledgement_deadline and e.acknowledgement_deadline < now and not e.is_acknowledged)
                    or (e.initial_review_deadline and e.initial_review_deadline < now and e.lifecycle_state in {
                        EscalationLifecycleState.ASSIGNED,
                        EscalationLifecycleState.REVIEW_PENDING,
                    })
                )
                and e.lifecycle_state not in {
                    EscalationLifecycleState.RESOLVED,
                    EscalationLifecycleState.CLOSED,
                    EscalationLifecycleState.CANCELLED,
                    EscalationLifecycleState.SUPERSEDED,
                }
            ]
            results.sort(key=lambda x: x.created_at, reverse=True)
            return results[offset : offset + limit]

    def list_awaiting_acknowledgement(
        self,
        organization_id: str,
        facility_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[GovernanceEscalationRecord]:
        """List assigned escalations pending acknowledgement by their designated owner."""
        with self._lock:
            results = [
                e for e in self._escalations.values()
                if e.organization_id == organization_id
                and (facility_id is None or e.facility_id == facility_id)
                and e.assigned_owner_id is not None
                and not e.is_acknowledged
                and e.lifecycle_state not in {
                    EscalationLifecycleState.RESOLVED,
                    EscalationLifecycleState.CLOSED,
                    EscalationLifecycleState.CANCELLED,
                }
            ]
            results.sort(key=lambda x: x.created_at, reverse=True)
            return results[offset : offset + limit]

    def list_review_required(
        self,
        organization_id: str,
        facility_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[GovernanceEscalationRecord]:
        """List escalations awaiting formal governance review or decision."""
        review_states = {
            EscalationLifecycleState.ACKNOWLEDGED,
            EscalationLifecycleState.REVIEW_PENDING,
            EscalationLifecycleState.REVIEW_IN_PROGRESS,
            EscalationLifecycleState.DECISION_PENDING,
            EscalationLifecycleState.RESOLUTION_REVIEW_PENDING,
        }
        with self._lock:
            results = [
                e for e in self._escalations.values()
                if e.organization_id == organization_id
                and (facility_id is None or e.facility_id == facility_id)
                and e.lifecycle_state in review_states
            ]
            results.sort(key=lambda x: x.created_at, reverse=True)
            return results[offset : offset + limit]

    def list_conflicted(
        self,
        organization_id: str,
        facility_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[GovernanceEscalationRecord]:
        """List escalations currently marked as conflicted or containing active conflicts."""
        with self._lock:
            results = [
                e for e in self._escalations.values()
                if e.organization_id == organization_id
                and (facility_id is None or e.facility_id == facility_id)
                and (e.lifecycle_state == EscalationLifecycleState.CONFLICTED or len(e.conflicting_decision_ids) > 0)
                and e.lifecycle_state not in {
                    EscalationLifecycleState.CLOSED,
                    EscalationLifecycleState.CANCELLED,
                }
            ]
            results.sort(key=lambda x: x.created_at, reverse=True)
            return results[offset : offset + limit]

    # -------------------------------------------------------------------------
    # Exceptions
    # -------------------------------------------------------------------------

    def save_exception(self, record: GovernanceExceptionRecord) -> GovernanceExceptionRecord:
        """Persist or update an ingested governance exception."""
        with self._lock:
            record.updated_at = datetime.now(timezone.utc)
            self._exceptions[record.exception_id] = record
            return record

    def get_exception(self, exception_id: str) -> Optional[GovernanceExceptionRecord]:
        """Retrieve an exception by ID."""
        with self._lock:
            return self._exceptions.get(exception_id)

    def find_existing_exception(
        self, source_phase: str, source_record_id: str, source_version: str
    ) -> Optional[GovernanceExceptionRecord]:
        """Find if a source exception event of identical version was already ingested."""
        with self._lock:
            for ex in self._exceptions.values():
                if (
                    ex.source_phase.value == source_phase
                    and ex.source_record_id == source_record_id
                    and ex.source_version == source_version
                ):
                    return ex
            return None

    def list_exceptions(
        self,
        escalation_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[GovernanceExceptionRecord]:
        """List exceptions filtered by escalation or organization."""
        with self._lock:
            results = [
                ex for ex in self._exceptions.values()
                if (escalation_id is None or ex.escalation_id == escalation_id)
                and (organization_id is None or ex.organization_id == organization_id)
            ]
            results.sort(key=lambda x: x.created_at, reverse=True)
            return results[offset : offset + limit]

    # -------------------------------------------------------------------------
    # Reviews & Decisions
    # -------------------------------------------------------------------------

    def save_review(self, record: GovernanceReviewRecord) -> GovernanceReviewRecord:
        """Save a governance review execution record."""
        with self._lock:
            if record.escalation_id not in self._reviews:
                self._reviews[record.escalation_id] = []
            self._reviews[record.escalation_id].append(record)
            return record

    def list_reviews(self, escalation_id: str) -> List[GovernanceReviewRecord]:
        """List reviews recorded for an escalation."""
        with self._lock:
            return list(self._reviews.get(escalation_id, []))

    def save_decision(self, record: GovernanceDecisionRecord) -> GovernanceDecisionRecord:
        """Save an authorized governance decision."""
        with self._lock:
            if record.escalation_id not in self._decisions:
                self._decisions[record.escalation_id] = []
            self._decisions[record.escalation_id].append(record)
            return record

    def list_decisions(self, escalation_id: str) -> List[GovernanceDecisionRecord]:
        """List decisions recorded for an escalation."""
        with self._lock:
            return list(self._decisions.get(escalation_id, []))

    # -------------------------------------------------------------------------
    # Conflicts
    # -------------------------------------------------------------------------

    def save_conflict(self, record: CrossWorkflowConflictRecord) -> CrossWorkflowConflictRecord:
        """Save a cross-workflow conflict record."""
        with self._lock:
            if record.escalation_id not in self._conflicts:
                self._conflicts[record.escalation_id] = []
            self._conflicts[record.escalation_id].append(record)
            return record

    def list_conflicts(self, escalation_id: str) -> List[CrossWorkflowConflictRecord]:
        """List conflicts captured for an escalation."""
        with self._lock:
            return list(self._conflicts.get(escalation_id, []))

    # -------------------------------------------------------------------------
    # Resolution Requirements
    # -------------------------------------------------------------------------

    def save_requirement(self, record: ResolutionRequirementRecord) -> ResolutionRequirementRecord:
        """Save or update a resolution requirement."""
        with self._lock:
            record.updated_at = datetime.now(timezone.utc)
            self._requirements[record.requirement_id] = record
            return record

    def get_requirement(self, requirement_id: str) -> Optional[ResolutionRequirementRecord]:
        """Retrieve a requirement by ID."""
        with self._lock:
            return self._requirements.get(requirement_id)

    def list_requirements(self, escalation_id: str) -> List[ResolutionRequirementRecord]:
        """List resolution requirements for an escalation."""
        with self._lock:
            results = [
                r for r in self._requirements.values()
                if r.escalation_id == escalation_id
            ]
            results.sort(key=lambda x: x.created_at)
            return results

    # -------------------------------------------------------------------------
    # Audit Transition History
    # -------------------------------------------------------------------------

    def record_history(self, record: EscalationHistoryRecord) -> EscalationHistoryRecord:
        """Record an escalation audit history event."""
        with self._lock:
            if record.escalation_id not in self._history:
                self._history[record.escalation_id] = []
            self._history[record.escalation_id].append(record)
            return record

    def get_history(self, escalation_id: str) -> List[EscalationHistoryRecord]:
        """Retrieve transition audit history for an escalation."""
        with self._lock:
            return list(self._history.get(escalation_id, []))

    # -------------------------------------------------------------------------
    # Idempotency
    # -------------------------------------------------------------------------

    def get_idempotent_id(self, key: str) -> Optional[str]:
        """Check if an idempotency key was previously processed."""
        with self._lock:
            entry = self._idempotency_store.get(key)
            return entry[0] if entry else None

    # -------------------------------------------------------------------------
    # Test Cleanup
    # -------------------------------------------------------------------------

    def clear(self) -> None:
        """Reset all in-memory repository collections."""
        with self._lock:
            self._escalations.clear()
            self._exceptions.clear()
            self._reviews.clear()
            self._decisions.clear()
            self._conflicts.clear()
            self._requirements.clear()
            self._history.clear()
            self._idempotency_store.clear()


# Global singleton instance
_global_governance_escalation_repo = GovernanceEscalationRepository()


def get_governance_escalation_repository() -> GovernanceEscalationRepository:
    """Dependency provider returning the singleton repository instance."""
    return _global_governance_escalation_repo
