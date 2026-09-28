"""Workflow Repository (Phase 22).

DATABASE TEAM DEPENDENCY — PHASE 22
===================================
In-memory repository implementing data contracts for multi-step workflows.

Expected PostgreSQL table:
- async_workflows (id, workflow_type, patient_id, initiating_user_id, status,
                   current_step_index, steps, created_at, updated_at, completed_at, metadata)
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.repositories.base import BaseRepository
from app.schemas.workflow import WorkflowRecord, WorkflowStatus


class WorkflowRepository(BaseRepository[Any]):
    """Thread-safe repository managing orchestrated multi-step workflows."""

    def __init__(self, session: Any = None) -> None:
        super().__init__(session=session)
        self._workflows: Dict[str, WorkflowRecord] = {}
        self._lock = asyncio.Lock()

    async def create(self, workflow: WorkflowRecord) -> WorkflowRecord:
        """Persist a new multi-step workflow record."""
        async with self._lock:
            self._workflows[workflow.id] = workflow
            return workflow

    async def get(self, workflow_id: str) -> Optional[WorkflowRecord]:
        """Fetch workflow record by ID."""
        async with self._lock:
            return self._workflows.get(workflow_id)

    async def update(self, workflow: WorkflowRecord) -> WorkflowRecord:
        """Update workflow progress or stage state."""
        async with self._lock:
            workflow.updated_at = datetime.now(timezone.utc)
            self._workflows[workflow.id] = workflow
            return workflow

    async def list_by_patient(self, patient_id: str, limit: int = 50) -> List[WorkflowRecord]:
        """List workflows associated with a patient."""
        async with self._lock:
            matched = [w for w in self._workflows.values() if w.patient_id == patient_id]
            matched.sort(key=lambda w: w.created_at, reverse=True)
            return matched[:limit]
