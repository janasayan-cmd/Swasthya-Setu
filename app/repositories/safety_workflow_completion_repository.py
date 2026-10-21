"""Phase 65: Safety Workflow Completion Repository.

Thread-safe repository for Phase 65 safety workflow completion coordination records,
evaluations, requirement registers, reviews, authorizations, and closure history.
"""

from datetime import datetime, timezone
import threading
from typing import Dict, List, Optional, Tuple

from app.schemas.safety_workflow_completion import (
    CompletionLifecycleState,
    SafetyWorkflowCompletionRecord,
)


class SafetyWorkflowCompletionRepository:
    """Thread-safe in-memory repository for Phase 65 safety workflow completions."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._completions: Dict[str, SafetyWorkflowCompletionRecord] = {}
        self._idempotency_store: Dict[str, Tuple[str, str, datetime]] = {}

    def save(self, record: SafetyWorkflowCompletionRecord) -> SafetyWorkflowCompletionRecord:
        """Persist or update a completion record."""
        with self._lock:
            record.updated_at = datetime.now(timezone.utc)
            self._completions[record.completion_id] = record
            if record.idempotency_key:
                self._idempotency_store[record.idempotency_key] = (
                    record.completion_id,
                    record.organization_id,
                    datetime.now(timezone.utc),
                )
            return record

    def get(self, completion_id: str) -> Optional[SafetyWorkflowCompletionRecord]:
        """Retrieve completion record by ID."""
        with self._lock:
            return self._completions.get(completion_id)

    def get_by_disposition_id(self, disposition_id: str) -> List[SafetyWorkflowCompletionRecord]:
        """Retrieve completions associated with a given Phase 63 disposition ID."""
        with self._lock:
            return [
                c for c in self._completions.values()
                if c.source_disposition_id == disposition_id
            ]

    def get_by_review_id(self, review_id: str) -> List[SafetyWorkflowCompletionRecord]:
        """Retrieve completions associated with a given Phase 63 review ID."""
        with self._lock:
            return [
                c for c in self._completions.values()
                if c.source_review_id == review_id
            ]

    def get_by_idempotency_key(
        self,
        idempotency_key: str,
        organization_id: Optional[str] = None,
    ) -> Optional[SafetyWorkflowCompletionRecord]:
        """Retrieve existing completion by idempotency key."""
        with self._lock:
            entry = self._idempotency_store.get(idempotency_key)
            if not entry:
                return None
            comp_id, org_id, _ = entry
            if organization_id and org_id != organization_id:
                return None
            return self._completions.get(comp_id)

    def list_completions(
        self,
        organization_id: str,
        facility_id: Optional[str] = None,
        state: Optional[CompletionLifecycleState] = None,
        readiness_state: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[SafetyWorkflowCompletionRecord]:
        """Filter and list completions for a tenant with pagination."""
        with self._lock:
            results = [
                c for c in self._completions.values()
                if c.organization_id == organization_id
                and (facility_id is None or c.facility_id == facility_id)
                and (state is None or c.state == state)
                and (readiness_state is None or c.readiness_state == readiness_state)
            ]
            results.sort(key=lambda x: x.created_at, reverse=True)
            return results[offset : offset + limit]

    def list_pending(
        self,
        organization_id: str,
        facility_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[SafetyWorkflowCompletionRecord]:
        """List workflows with unresolved requirements or handoffs."""
        pending_states = {
            CompletionLifecycleState.CREATED,
            CompletionLifecycleState.VALIDATING,
            CompletionLifecycleState.READINESS_EVALUATION_PENDING,
            CompletionLifecycleState.READINESS_EVALUATING,
            CompletionLifecycleState.NOT_READY,
            CompletionLifecycleState.CLOSURE_PENDING,
        }
        with self._lock:
            results = [
                c for c in self._completions.values()
                if c.organization_id == organization_id
                and (facility_id is None or c.facility_id == facility_id)
                and (
                    c.state in pending_states
                    or c.readiness_state in ("HANDOFFS_PENDING", "OUTCOMES_PENDING", "FOLLOW_UP_PENDING")
                )
            ]
            results.sort(key=lambda x: x.created_at, reverse=True)
            return results[offset : offset + limit]

    def list_blocked(
        self,
        organization_id: str,
        facility_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[SafetyWorkflowCompletionRecord]:
        """List blocked workflows."""
        with self._lock:
            results = [
                c for c in self._completions.values()
                if c.organization_id == organization_id
                and (facility_id is None or c.facility_id == facility_id)
                and (c.state == CompletionLifecycleState.BLOCKED or c.readiness_state == "BLOCKED" or len(c.blockers) > 0)
            ]
            results.sort(key=lambda x: x.created_at, reverse=True)
            return results[offset : offset + limit]

    def list_review_required(
        self,
        organization_id: str,
        facility_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[SafetyWorkflowCompletionRecord]:
        """List workflows awaiting authorized review."""
        review_states = {
            CompletionLifecycleState.READY,
            CompletionLifecycleState.READY_WITH_LIMITATIONS,
            CompletionLifecycleState.REVIEW_PENDING,
            CompletionLifecycleState.REVIEW_IN_PROGRESS,
            CompletionLifecycleState.COMPLETION_AUTHORIZATION_PENDING,
        }
        with self._lock:
            results = [
                c for c in self._completions.values()
                if c.organization_id == organization_id
                and (facility_id is None or c.facility_id == facility_id)
                and (c.state in review_states or c.readiness_state in ("READY", "READY_WITH_LIMITATIONS", "REVIEW_REQUIRED"))
                and c.state != CompletionLifecycleState.CLOSED
            ]
            results.sort(key=lambda x: x.created_at, reverse=True)
            return results[offset : offset + limit]

    def list_reopen_required(
        self,
        organization_id: str,
        facility_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[SafetyWorkflowCompletionRecord]:
        """List workflows requiring reopening or reassessment."""
        reopen_states = {
            CompletionLifecycleState.REOPEN_REQUIRED,
            CompletionLifecycleState.REASSESSMENT_REQUIRED,
            CompletionLifecycleState.STALE,
            CompletionLifecycleState.CONFLICTED,
        }
        with self._lock:
            results = [
                c for c in self._completions.values()
                if c.organization_id == organization_id
                and (facility_id is None or c.facility_id == facility_id)
                and (c.state in reopen_states or c.readiness_state in ("REOPEN_REQUIRED", "REASSESSMENT_REQUIRED", "STALE", "CONFLICTED"))
            ]
            results.sort(key=lambda x: x.created_at, reverse=True)
            return results[offset : offset + limit]

    def clear(self) -> None:
        """Clear all records (used for test isolation)."""
        with self._lock:
            self._completions.clear()
            self._idempotency_store.clear()


# Module-level singleton
_REPO_INSTANCE: Optional[SafetyWorkflowCompletionRepository] = None
_LOCK = threading.Lock()


def get_safety_workflow_completion_repository() -> SafetyWorkflowCompletionRepository:
    """Retrieve or create the singleton instance of SafetyWorkflowCompletionRepository."""
    global _REPO_INSTANCE
    if _REPO_INSTANCE is None:
        with _LOCK:
            if _REPO_INSTANCE is None:
                _REPO_INSTANCE = SafetyWorkflowCompletionRepository()
    return _REPO_INSTANCE
