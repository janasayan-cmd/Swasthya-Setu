"""Job Repository (Phase 22).

DATABASE TEAM DEPENDENCY — PHASE 22
===================================
In-memory repository implementing the data contract for asynchronous jobs.

Expected PostgreSQL table:
- async_jobs (id, job_type, status, patient_id, resource_type, resource_id,
             operation_type, payload, result, initiating_user_id, idempotency_key,
             correlation_id, attempt, max_retries, created_at, queued_at,
             started_at, completed_at, failed_at, error_message, error_category)
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.repositories.base import BaseRepository
from app.schemas.job import JobRecord, JobStatus, JobType


class JobRepository(BaseRepository[Any]):
    """Thread-safe repository managing asynchronous job state and history."""

    def __init__(self, session: Any = None) -> None:
        super().__init__(session=session)
        self._jobs: Dict[str, JobRecord] = {}
        self._idempotency_index: Dict[str, str] = {}  # idempotency_key -> job_id
        self._lock = asyncio.Lock()

    async def create(self, job: JobRecord) -> JobRecord:
        """Persist a new asynchronous job."""
        async with self._lock:
            self._jobs[job.id] = job
            if job.idempotency_key:
                self._idempotency_index[job.idempotency_key] = job.id
            return job

    async def get(self, job_id: str) -> Optional[JobRecord]:
        """Retrieve job record by ID."""
        async with self._lock:
            return self._jobs.get(job_id)

    async def get_by_idempotency_key(self, idempotency_key: str) -> Optional[JobRecord]:
        """Lookup job by client-supplied idempotency key."""
        async with self._lock:
            job_id = self._idempotency_index.get(idempotency_key)
            if job_id:
                return self._jobs.get(job_id)
            return None

    async def update(self, job: JobRecord) -> JobRecord:
        """Update job lifecycle status, attempts, or outputs."""
        async with self._lock:
            self._jobs[job.id] = job
            return job

    async def list_by_patient(self, patient_id: str, limit: int = 50) -> List[JobRecord]:
        """List jobs associated with a given patient reference."""
        async with self._lock:
            matched = [j for j in self._jobs.values() if j.patient_id == patient_id]
            matched.sort(key=lambda j: j.created_at, reverse=True)
            return matched[:limit]

    async def list_by_status(self, status: JobStatus, limit: int = 50) -> List[JobRecord]:
        """List jobs matching a specific status."""
        async with self._lock:
            matched = [j for j in self._jobs.values() if j.status == status]
            matched.sort(key=lambda j: j.created_at, reverse=True)
            return matched[:limit]
