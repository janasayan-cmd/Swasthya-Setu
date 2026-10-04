"""In-memory thread-safe repository for Clinical Tasks and Task History (Phase 36).

Consumes existing database contracts; does not create competing database schemas or migrations.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple
from app.schemas.task import TaskFilter, TaskRecord, TaskStatus
from app.schemas.task_history import TaskHistoryAction, TaskHistoryEntry


class TaskRepository:
    """Thread-safe storage for tasks, dependencies, and lifecycle transition history."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._tasks: Dict[str, TaskRecord] = {}
        # Idempotency index by unique idempotency key
        self._idempotency_index: Dict[str, str] = {}
        # Logical identity index: (source_type, source_id, category, patient_id) -> task_id
        self._logical_index: Dict[Tuple[str, str, str, Optional[str]], str] = {}
        # History index: task_id -> list of TaskHistoryEntry
        self._history: Dict[str, List[TaskHistoryEntry]] = {}
        self._counter: int = 1
        self._history_counter: int = 1

    def _generate_task_id(self) -> str:
        today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        task_id = f"TSK-{today_str}-{self._counter:05d}"
        self._counter += 1
        return task_id

    def _generate_history_id(self) -> str:
        today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        hist_id = f"HIST-TSK-{today_str}-{self._history_counter:05d}"
        self._history_counter += 1
        return hist_id

    def save(self, task: TaskRecord) -> TaskRecord:
        """Create or update a task record atomically."""
        with self._lock:
            if not task.id:
                task = task.model_copy(update={"id": self._generate_task_id()})
            task = task.model_copy(update={"updated_at": datetime.now(timezone.utc)})
            self._tasks[task.id] = task

            # Index idempotency
            if task.idempotency_key:
                self._idempotency_index[task.idempotency_key] = task.id

            # Index logical identity
            if task.provenance and task.provenance.source_type and task.provenance.source_id:
                logical_key = (
                    task.provenance.source_type,
                    task.provenance.source_id,
                    task.category.value,
                    task.patient_id,
                )
                self._logical_index[logical_key] = task.id

            return task

    def get_by_id(self, task_id: str) -> Optional[TaskRecord]:
        """Fetch a task by ID."""
        with self._lock:
            return self._tasks.get(task_id)

    def get_by_idempotency_key(self, idempotency_key: str) -> Optional[TaskRecord]:
        """Retrieve task by unique client idempotency key."""
        with self._lock:
            task_id = self._idempotency_index.get(idempotency_key)
            if task_id:
                return self._tasks.get(task_id)
            return None

    def get_by_logical_identity(
        self,
        source_type: str,
        source_id: str,
        category: str,
        patient_id: Optional[str] = None,
    ) -> Optional[TaskRecord]:
        """Retrieve existing task by domain source identity to prevent duplicate work items."""
        with self._lock:
            logical_key = (source_type, source_id, category, patient_id)
            task_id = self._logical_index.get(logical_key)
            if task_id:
                return self._tasks.get(task_id)
            return None

    def add_history(
        self,
        task_id: str,
        action: TaskHistoryAction,
        to_status: str,
        actor_id: str,
        actor_role: str,
        from_status: Optional[str] = None,
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TaskHistoryEntry:
        """Append an audit entry to the task's immutable lifecycle ledger."""
        with self._lock:
            entry = TaskHistoryEntry(
                id=self._generate_history_id(),
                task_id=task_id,
                action=action,
                from_status=from_status,
                to_status=to_status,
                actor_id=actor_id,
                actor_role=actor_role,
                reason=reason,
                metadata=metadata or {},
                timestamp=datetime.now(timezone.utc),
            )
            if task_id not in self._history:
                self._history[task_id] = []
            self._history[task_id].append(entry)
            return entry

    def get_history(self, task_id: str) -> List[TaskHistoryEntry]:
        """Retrieve audit history for a task."""
        with self._lock:
            return list(self._history.get(task_id, []))

    def list_dependents(self, prerequisite_task_id: str) -> List[TaskRecord]:
        """Find tasks that depend on the given task ID."""
        with self._lock:
            return [
                task for task in self._tasks.values()
                if any(dep.depends_on_task_id == prerequisite_task_id for dep in task.dependencies)
            ]

    def list_tasks(
        self,
        filters: TaskFilter,
        allowed_patient_ids: Optional[Set[str]] = None,
        assignee_id: Optional[str] = None,
        team_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        facility_id: Optional[str] = None,
    ) -> Tuple[List[TaskRecord], int]:
        """List tasks with multi-tenant filtering, queue scoping, and pagination."""
        with self._lock:
            results = list(self._tasks.values())
            now = datetime.now(timezone.utc)

            # Multi-tenant scoping
            if organization_id:
                results = [t for t in results if t.organization_id == organization_id or t.organization_id is None]
            if facility_id:
                results = [t for t in results if t.facility_id == facility_id or t.facility_id is None]

            # Patient authorization scoping
            if allowed_patient_ids is not None:
                results = [t for t in results if t.patient_id in allowed_patient_ids]

            # Assignee scoping (e.g. My Tasks)
            if assignee_id:
                results = [t for t in results if t.assignee_id == assignee_id]

            # Team scoping
            if team_id:
                results = [t for t in results if t.team_id == team_id or t.assignee_id == team_id]

            # Query filters
            if filters.status:
                results = [t for t in results if t.status == filters.status]
            if filters.category:
                results = [t for t in results if t.category == filters.category]
            if filters.priority:
                results = [t for t in results if t.priority == filters.priority]
            if filters.assignee_id:
                results = [t for t in results if t.assignee_id == filters.assignee_id]
            if filters.team_id:
                results = [t for t in results if t.team_id == filters.team_id]
            if filters.patient_id:
                results = [t for t in results if t.patient_id == filters.patient_id]
            if filters.facility_id:
                results = [t for t in results if t.facility_id == filters.facility_id]
            if filters.organization_id:
                results = [t for t in results if t.organization_id == filters.organization_id]
            if filters.source_type:
                results = [t for t in results if t.provenance.source_type == filters.source_type]
            if filters.source_id:
                results = [t for t in results if t.provenance.source_id == filters.source_id]
            if filters.verification_required is not None:
                results = [t for t in results if t.verification_required == filters.verification_required]

            if filters.overdue_only:
                terminal = {TaskStatus.COMPLETED, TaskStatus.VERIFIED, TaskStatus.CANCELLED, TaskStatus.REJECTED, TaskStatus.EXPIRED, TaskStatus.FAILED}
                results = [
                    t for t in results
                    if t.due_at and t.due_at < now and t.status not in terminal
                ]

            if filters.created_from:
                results = [t for t in results if t.created_at >= filters.created_from]
            if filters.created_to:
                results = [t for t in results if t.created_at <= filters.created_to]
            if filters.due_from:
                results = [t for t in results if t.due_at and t.due_at >= filters.due_from]
            if filters.due_to:
                results = [t for t in results if t.due_at and t.due_at <= filters.due_to]

            # Priority-aware sorting: URGENT -> HIGH -> NORMAL -> LOW, then due_at ascending, then created_at descending
            priority_rank = {
                TaskStatus.CREATED: 0,
            }
            priority_weight = {
                "URGENT": 4,
                "HIGH": 3,
                "NORMAL": 2,
                "LOW": 1,
            }
            results.sort(
                key=lambda t: (
                    -priority_weight.get(t.priority.value, 0),
                    t.due_at or datetime.max.replace(tzinfo=timezone.utc),
                    -t.created_at.timestamp(),
                )
            )

            total = len(results)
            start_idx = (filters.page - 1) * filters.page_size
            end_idx = start_idx + filters.page_size
            return results[start_idx:end_idx], total
