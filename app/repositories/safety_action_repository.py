"""Phase 54: Safety Action Repository.

Manages persistence contract for safety actions, assignment, approval,
history, and escalation records. Adheres to database team boundaries:
- Thread-safe in-memory development implementation
- Fully prepared for SQLAlchemy database models and migrations
"""

from datetime import datetime, timezone
import threading
from typing import Dict, List, Optional

from app.schemas.safety_action import (
    ActionHistoryEntry,
    ActionLifecycleState,
    ActionPriority,
    ActionType,
    SafetyActionRecord,
)


class SafetyActionRepository:
    """Thread-safe in-memory repository for Phase 54 safety action orchestration."""

    def __init__(self) -> None:
        self._actions: Dict[str, SafetyActionRecord] = {}
        self._history: Dict[str, List[ActionHistoryEntry]] = {} # action_id -> list of entries
        self._idempotency_map: Dict[str, str] = {}              # key -> action_id
        self._lock = threading.Lock()

    def reset(self) -> None:
        """Reset repository state for clean test isolation."""
        with self._lock:
            self._actions.clear()
            self._history.clear()
            self._idempotency_map.clear()

    def save_action(self, action: SafetyActionRecord) -> SafetyActionRecord:
        """Upsert a safety action record."""
        with self._lock:
            action.updated_at = datetime.now(timezone.utc)
            self._actions[action.action_id] = action
            if action.idempotency_key:
                self._idempotency_map[action.idempotency_key] = action.action_id
            return action

    def get_action(self, action_id: str) -> Optional[SafetyActionRecord]:
        """Retrieve action by ID."""
        with self._lock:
            return self._actions.get(action_id)

    def get_by_idempotency_key(self, idempotency_key: str) -> Optional[SafetyActionRecord]:
        """Find existing action by idempotency key."""
        with self._lock:
            action_id = self._idempotency_map.get(idempotency_key)
            if action_id:
                return self._actions.get(action_id)
            return None

    def record_history(self, entry: ActionHistoryEntry) -> None:
        """Append an audit history entry for an action transition."""
        with self._lock:
            entries = self._history.setdefault(entry.action_id, [])
            entries.append(entry)

    def get_history(self, action_id: str) -> List[ActionHistoryEntry]:
        """Get history trail for an action, sorted by timestamp ascending."""
        with self._lock:
            entries = self._history.get(action_id, [])
            return list(entries)

    def list_actions(
        self,
        organization_id: Optional[str] = None,
        facility_id: Optional[str] = None,
        lifecycle_state: Optional[ActionLifecycleState] = None,
        action_type: Optional[ActionType] = None,
        priority: Optional[ActionPriority] = None,
        owner_id: Optional[str] = None,
        pending_only: bool = False,
        escalated_only: bool = False,
        overdue_only: bool = False,
        reassessment_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> List[SafetyActionRecord]:
        """List actions matching scope and filter criteria."""
        now = datetime.now(timezone.utc)
        with self._lock:
            results: List[SafetyActionRecord] = []
            for act in self._actions.values():
                if organization_id and act.organization_id and act.organization_id != organization_id:
                    continue
                if facility_id and act.facility_id and act.facility_id != facility_id:
                    continue
                if lifecycle_state and act.lifecycle_state != lifecycle_state:
                    continue
                if action_type and act.action_type != action_type:
                    continue
                if priority and act.priority != priority:
                    continue
                if owner_id and (not act.assignment or act.assignment.owner_id != owner_id):
                    continue

                if pending_only and act.lifecycle_state not in (
                    ActionLifecycleState.REVIEW_REQUIRED,
                    ActionLifecycleState.READY,
                    ActionLifecycleState.ASSIGNED,
                    ActionLifecycleState.IN_PROGRESS,
                    ActionLifecycleState.COMPLETION_PENDING,
                ):
                    continue

                if escalated_only and not act.escalation:
                    continue

                if overdue_only and (not act.due_at or act.due_at > now or act.lifecycle_state == ActionLifecycleState.CLOSED):
                    continue

                if reassessment_only and act.lifecycle_state != ActionLifecycleState.REQUIRES_REASSESSMENT:
                    continue

                results.append(act)

            results.sort(key=lambda r: r.created_at, reverse=True)
            return results[offset : offset + limit]


# Global singleton repository
safety_action_repository = SafetyActionRepository()
