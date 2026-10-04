"""Thread-safe in-memory repository for Workflow Step Instances (Phase 37).

Consumes existing database contracts; does not create competing database schemas or migrations.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional
from app.schemas.workflow_step import WorkflowStepRecord


class WorkflowStepRepository:
    """Thread-safe storage and lookup indexing for workflow step runtime instances."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._steps: Dict[str, WorkflowStepRecord] = {}
        # workflow_id -> list of step_instance_ids
        self._workflow_steps: Dict[str, List[str]] = {}
        # related_task_id -> step_instance_id
        self._task_index: Dict[str, str] = {}
        self._counter: int = 1

    def _generate_step_instance_id(self) -> str:
        today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        sid = f"STP-{today_str}-{self._counter:05d}"
        self._counter += 1
        return sid

    def save(self, step: WorkflowStepRecord) -> WorkflowStepRecord:
        """Create or update a step instance record atomically."""
        with self._lock:
            if not step.step_instance_id:
                step = step.model_copy(update={"step_instance_id": self._generate_step_instance_id()})
            step = step.model_copy(update={"updated_at": datetime.now(timezone.utc)})

            self._steps[step.step_instance_id] = step

            # Index by workflow_id
            if step.workflow_id not in self._workflow_steps:
                self._workflow_steps[step.workflow_id] = []
            if step.step_instance_id not in self._workflow_steps[step.workflow_id]:
                self._workflow_steps[step.workflow_id].append(step.step_instance_id)

            # Index by related_task_id if present
            if step.related_task_id:
                self._task_index[step.related_task_id] = step.step_instance_id

            return step

    def get_by_instance_id(self, step_instance_id: str) -> Optional[WorkflowStepRecord]:
        """Fetch step instance by unique runtime ID."""
        with self._lock:
            return self._steps.get(step_instance_id)

    def get_by_workflow_and_step_id(self, workflow_id: str, step_id: str) -> Optional[WorkflowStepRecord]:
        """Fetch step instance by parent workflow ID and definition step ID."""
        with self._lock:
            instance_ids = self._workflow_steps.get(workflow_id, [])
            for iid in instance_ids:
                step = self._steps.get(iid)
                if step and step.step_id == step_id:
                    return step
            return None

    def get_by_task_id(self, task_id: str) -> Optional[WorkflowStepRecord]:
        """Fetch step instance linked to a specific Phase 36 task ID."""
        with self._lock:
            step_instance_id = self._task_index.get(task_id)
            if step_instance_id:
                return self._steps.get(step_instance_id)
            return None

    def list_by_workflow_id(self, workflow_id: str) -> List[WorkflowStepRecord]:
        """List all step instances for a given workflow in order."""
        with self._lock:
            instance_ids = self._workflow_steps.get(workflow_id, [])
            steps = [self._steps[iid] for iid in instance_ids if iid in self._steps]
            steps.sort(key=lambda s: s.order)
            return steps
