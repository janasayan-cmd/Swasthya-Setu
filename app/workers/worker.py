"""Async Worker Pool and Execution Loop (Phase 22).

Enforces:
- Bounded concurrency slots.
- Controlled timeout per job execution.
- Transient vs permanent error classification and retry handling.
- Graceful shutdown with drain timeout.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from app.core.config import Settings, get_settings
from app.core.exceptions import AppException
from app.core.logging import get_logger
from app.core.metrics import metrics
from app.integrations.queue.base import JobQueueProvider
from app.schemas.job import JobRecord, JobStatus
from app.services.event_service import EventService
from app.services.job_service import JobService
from app.workers.tasks import get_task_handler

logger = get_logger("app.workers.worker")


class AsyncWorkerPool:
    """Worker pool managing bounded concurrent background job execution."""

    def __init__(
        self,
        job_service: JobService,
        queue_provider: JobQueueProvider,
        event_service: Optional[EventService] = None,
        settings: Optional[Settings] = None,
    ) -> None:
        self.job_service = job_service
        self.queue = queue_provider
        self.event_service = event_service
        self.settings = settings or get_settings()
        self.concurrency = self.settings.WORKER_CONCURRENCY
        self.timeout_seconds = self.settings.JOB_DEFAULT_TIMEOUT_SECONDS
        self._workers: List[asyncio.Task] = []
        self._active_jobs: Dict[str, asyncio.Task] = {}
        self._running = False
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        """Start async worker polling loops."""
        if self._running:
            return
        self._running = True
        logger.info(f"Starting AsyncWorkerPool with {self.concurrency} concurrent worker slots.")

        for i in range(self.concurrency):
            task = asyncio.create_task(self._worker_loop(worker_idx=i))
            self._workers.append(task)

    async def stop(self, timeout: Optional[float] = None) -> None:
        """Gracefully stop worker pool and wait for active jobs to drain."""
        if not self._running:
            return
        self._running = False
        drain_timeout = timeout or self.settings.WORKER_SHUTDOWN_TIMEOUT_SECONDS
        logger.info(f"Initiating graceful worker shutdown (drain timeout: {drain_timeout}s)...")

        # Cancel polling tasks
        for task in self._workers:
            task.cancel()

        # Wait for active in-flight jobs to complete
        if self._active_jobs:
            logger.info(f"Draining {len(self._active_jobs)} in-flight background jobs...")
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self._active_jobs.values(), return_exceptions=True),
                    timeout=drain_timeout,
                )
            except asyncio.TimeoutError:
                logger.warning("Worker drain timeout expired. Forcibly terminating remaining in-flight jobs.")

        self._workers.clear()
        self._active_jobs.clear()
        logger.info("AsyncWorkerPool stopped safely.")

    async def _worker_loop(self, worker_idx: int) -> None:
        """Continuous lease and execution loop for a worker slot."""
        while self._running:
            try:
                job = await self.queue.dequeue(timeout=0.5)
                if not job:
                    await asyncio.sleep(0.05)
                    continue

                # Execute job in slot
                exec_task = asyncio.create_task(self._execute_job(job))
                async with self._lock:
                    self._active_jobs[job.id] = exec_task

                try:
                    await exec_task
                finally:
                    async with self._lock:
                        self._active_jobs.pop(job.id, None)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(f"Worker {worker_idx} encountered unhandled loop error: {exc}")
                await asyncio.sleep(0.5)

    async def _execute_job(self, job: JobRecord) -> None:
        """Execute a single leased job with timeout and error classification."""
        # 1. Mark started
        updated = await self.job_service.mark_started(job.id)
        if not updated:
            # Job was cancelled before lease
            await self.queue.acknowledge(job.id)
            return

        # 2. Resolve task handler
        try:
            handler = get_task_handler(job.job_type)
        except KeyError:
            logger.error(f"No task handler registered for {job.job_type.value}. Marking permanently FAILED.")
            await self.job_service.handle_job_failure(
                job_id=job.id,
                error_message=f"Unsupported job type: {job.job_type.value}",
                error_category="UNSUPPORTED_JOB_TYPE",
                is_transient=False,
            )
            return

        # 3. Execute with bounded timeout
        context = {
            "event_service": self.event_service,
            "job_service": self.job_service,
        }

        try:
            result = await asyncio.wait_for(
                handler(job, context),
                timeout=self.timeout_seconds,
            )
            await self.job_service.mark_completed(job.id, result=result)

        except asyncio.TimeoutError:
            logger.error(f"Job {job.id} timed out after {self.timeout_seconds}s.")
            await self.job_service.handle_job_failure(
                job_id=job.id,
                error_message=f"Execution timed out after {self.timeout_seconds}s.",
                error_category="EXECUTION_TIMEOUT",
                is_transient=True,
            )

        except Exception as exc:
            error_str = str(exc)
            # Classify error: validation/auth errors are permanent, provider/network errors are transient
            is_transient = not any(
                keyword in error_str.lower()
                for keyword in ["validation", "unauthorized", "forbidden", "malformed", "not found"]
            )
            logger.warning(
                f"Job {job.id} failed with error ({'transient' if is_transient else 'permanent'}): {error_str}"
            )
            await self.job_service.handle_job_failure(
                job_id=job.id,
                error_message=error_str,
                error_category="TRANSIENT_PROVIDER_ERROR" if is_transient else "PERMANENT_VALIDATION_ERROR",
                is_transient=is_transient,
            )
