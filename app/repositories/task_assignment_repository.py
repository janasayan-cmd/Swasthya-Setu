"""In-memory thread-safe repository for Task Assignments (Phase 36).

Consumes existing database contracts; does not create competing database schemas or migrations.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional
from app.schemas.task_assignment import TaskAssignmentRecord


class TaskAssignmentRepository:
    """Thread-safe storage for task assignment audit records."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._assignments: Dict[str, TaskAssignmentRecord] = {}
        # Index: task_id -> list of TaskAssignmentRecord
        self._task_assignments: Dict[str, List[TaskAssignmentRecord]] = {}
        self._counter: int = 1

    def _generate_assignment_id(self) -> str:
        today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        record_id = f"ASN-{today_str}-{self._counter:05d}"
        self._counter += 1
        return record_id

    def save(self, record: TaskAssignmentRecord) -> TaskAssignmentRecord:
        """Persist a task assignment record."""
        with self._lock:
            if not record.id:
                record = record.model_copy(update={"id": self._generate_assignment_id()})
            self._assignments[record.id] = record
            if record.task_id not in self._task_assignments:
                self._task_assignments[record.task_id] = []
            self._task_assignments[record.task_id].append(record)
            return record

    def get_by_id(self, record_id: str) -> Optional[TaskAssignmentRecord]:
        """Fetch assignment record by ID."""
        with self._lock:
            return self._assignments.get(record_id)

    def list_by_task_id(self, task_id: str) -> List[TaskAssignmentRecord]:
        """Retrieve assignment history for a task."""
        with self._lock:
            return list(self._task_assignments.get(task_id, []))
