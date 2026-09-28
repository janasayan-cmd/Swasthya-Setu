"""In-memory and factory implementations for JobQueueProvider (Phase 22)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Dict, Optional, Set

from app.core.config import Settings, get_settings
from app.core.exceptions import AppException
from app.core.logging import get_logger
from app.core.metrics import metrics
from app.integrations.queue.base import JobQueueProvider
from app.schemas.job import JobRecord, JobStatus

logger = get_logger("app.integrations.queue")


class InMemoryJobQueueProvider(JobQueueProvider):
    """Thread-safe and task-safe in-memory queue provider for local dev and tests."""

    def __init__(self, max_depth: int = 500) -> None:
        self.max_depth = max_depth
        self._queue: asyncio.Queue[JobRecord] = asyncio.Queue(maxsize=max_depth)
        self._in_flight: Dict[str, JobRecord] = {}
        self._cancelled_ids: Set[str] = set()
        self._lock = asyncio.Lock()
        self._delayed_tasks: Set[asyncio.Task] = set()
        self._closed = False

    async def enqueue(self, job: JobRecord) -> None:
        """Enqueue job immediately into the FIFO queue."""
        if self._closed:
            raise AppException(message="Job queue provider is shut down.", status_code=503)

        if job.id in self._cancelled_ids:
            async with self._lock:
                self._cancelled_ids.discard(job.id)

        try:
            self._queue.put_nowait(job)
            metrics.increment("jobs_queued_total")
        except asyncio.QueueFull:
            logger.error(f"Job queue depth exceeded maximum ({self.max_depth}). Dropping job {job.id}.")
            raise AppException(
                message="Background job queue is full. Try again later.",
                status_code=503,
                code="SERVICE_UNAVAILABLE",
            )

    async def enqueue_delayed(self, job: JobRecord, delay_seconds: float) -> None:
        """Enqueue job after a specified delay."""
        if self._closed:
            return

        async def _delayed_worker():
            try:
                await asyncio.sleep(delay_seconds)
                if not self._closed and job.id not in self._cancelled_ids:
                    await self.enqueue(job)
            except asyncio.CancelledError:
                pass
            finally:
                self._delayed_tasks.discard(task)

        task = asyncio.create_task(_delayed_worker())
        self._delayed_tasks.add(task)

    async def dequeue(self, timeout: float = 1.0) -> Optional[JobRecord]:
        """Lease a job from the queue with timeout."""
        if self._closed:
            return None

        deadline = asyncio.get_event_loop().time() + timeout
        while True:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                return None
            try:
                job = await asyncio.wait_for(self._queue.get(), timeout=min(remaining, 0.5))
                async with self._lock:
                    if job.id in self._cancelled_ids:
                        self._cancelled_ids.discard(job.id)
                        continue
                    self._in_flight[job.id] = job
                return job
            except asyncio.TimeoutError:
                return None

    async def acknowledge(self, job_id: str) -> None:
        """Acknowledge completion and remove from leased set."""
        async with self._lock:
            self._in_flight.pop(job_id, None)

    async def reject(self, job_id: str, requeue: bool = False) -> None:
        """Reject leased job, optionally putting back into queue."""
        async with self._lock:
            job = self._in_flight.pop(job_id, None)
            if requeue and job and not self._closed and job_id not in self._cancelled_ids:
                try:
                    self._queue.put_nowait(job)
                except asyncio.QueueFull:
                    logger.warning(f"Could not requeue rejected job {job_id}: queue full.")

    async def cancel(self, job_id: str) -> bool:
        """Mark job as cancelled so it is skipped upon dequeue."""
        async with self._lock:
            self._cancelled_ids.add(job_id)
            if job_id in self._in_flight:
                return False  # Already in flight
            return True

    def depth(self) -> int:
        """Return number of pending items in queue."""
        return self._queue.qsize()

    async def close(self) -> None:
        """Cancel delayed tasks and shut down."""
        self._closed = True
        for task in list(self._delayed_tasks):
            task.cancel()
        self._delayed_tasks.clear()


_queue_provider_instance: Optional[JobQueueProvider] = None


def get_job_queue_provider(settings: Settings | None = None) -> JobQueueProvider:
    """Singleton factory for job queue provider."""
    global _queue_provider_instance
    if _queue_provider_instance is None:
        cfg = settings or get_settings()
        _queue_provider_instance = InMemoryJobQueueProvider(max_depth=cfg.BACKGROUND_QUEUE_MAX_DEPTH)
    return _queue_provider_instance


def reset_job_queue_provider() -> None:
    """Reset the singleton instance (for testing)."""
    global _queue_provider_instance
    _queue_provider_instance = None
