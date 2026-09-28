"""Job Service (Phase 22).

Manages the complete lifecycle, authorization, idempotency, audit trail,
and metrics for asynchronous background jobs.
"""

from __future__ import annotations

from datetime import datetime, timezone
import random
from typing import Any, Dict, List, Optional

from app.core.config import Settings, get_settings
from app.core.exceptions import (
    JobAlreadyCancelledException,
    JobAlreadyCompletedException,
    JobNotAuthorizedException,
    JobNotFoundException,
    ValidationException,
)
from app.core.logging import get_logger
from app.core.metrics import metrics
from app.integrations.queue.base import JobQueueProvider
from app.integrations.queue.provider import get_job_queue_provider
from app.repositories.job_repository import JobRepository
from app.schemas.audit import AuditEventType
from app.schemas.job import JobCreate, JobRecord, JobResponse, JobStatus, JobType
from app.services.audit_service import AuditService
from app.services.base import BaseService
from app.services.idempotency_service import IdempotencyService

logger = get_logger("app.services.job")


class JobService(BaseService[JobRepository]):
    """Orchestrates job creation, authorization, lifecycle transitions, and queuing."""

    def __init__(
        self,
        repository: JobRepository,
        queue_provider: JobQueueProvider,
        idempotency_service: IdempotencyService,
        audit_service: AuditService,
        settings: Settings | None = None,
    ) -> None:
        super().__init__(repository=repository)
        self.job_repo = repository
        self.queue = queue_provider
        self.idempotency = idempotency_service
        self.audit_service = audit_service
        self.settings = settings or get_settings()

    async def enqueue_job(
        self,
        payload: JobCreate,
        actor_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> JobRecord:
        """Create and enqueue a new asynchronous job with idempotency protection."""
        # 1. Idempotency Check
        if payload.idempotency_key:
            can_execute, existing_idempotent = await self.idempotency.acquire_or_replay(
                key=payload.idempotency_key,
                operation_type=payload.operation_type,
                resource_id=payload.resource_id,
            )
            if not can_execute and existing_idempotent and existing_idempotent.result_payload:
                # Find matching job record or construct synthetic completed record
                job_rec = await self.job_repo.get_by_idempotency_key(payload.idempotency_key)
                if job_rec:
                    logger.info(f"Replaying completed job {job_rec.id} for key '{payload.idempotency_key}'.")
                    return job_rec

        # 2. Instantiate Job Record
        now = datetime.now(timezone.utc)
        job = JobRecord(
            job_type=payload.job_type,
            status=JobStatus.CREATED,
            patient_id=payload.patient_id,
            resource_type=payload.resource_type,
            resource_id=payload.resource_id,
            operation_type=payload.operation_type,
            payload=payload.payload,
            initiating_user_id=actor_id,
            idempotency_key=payload.idempotency_key,
            correlation_id=correlation_id or payload.correlation_id,
            max_retries=payload.max_retries,
            created_at=now,
        )

        job = await self.job_repo.create(job)
        metrics.increment("jobs_created_total")

        # 3. Enqueue to provider
        job.status = JobStatus.QUEUED
        job.queued_at = datetime.now(timezone.utc)
        job = await self.job_repo.update(job)

        await self.queue.enqueue(job)

        # 4. Audit
        await self.audit_service.record(
            event_type=AuditEventType.JOB_QUEUED,
            outcome="ALLOW",
            actor_id=actor_id,
            action=f"job:enqueue:{job.job_type.value}",
            resource_type=job.resource_type,
            resource_id=job.resource_id,
            metadata={"job_id": job.id, "job_type": job.job_type.value},
        )

        return job

    async def get_job(
        self,
        job_id: str,
        actor_id: str,
        is_admin: bool = False,
    ) -> JobRecord:
        """Fetch job details with ownership/authorization enforcement."""
        job = await self.job_repo.get(job_id)
        if not job:
            raise JobNotFoundException(job_id=job_id)

        # Authorization: Admins, initiating users, or system can read
        if not is_admin and job.initiating_user_id and job.initiating_user_id != actor_id:
            logger.warning(f"User '{actor_id}' forbidden from inspecting job '{job_id}' owned by '{job.initiating_user_id}'.")
            raise JobNotAuthorizedException()

        return job

    async def cancel_job(
        self,
        job_id: str,
        actor_id: str,
        is_admin: bool = False,
    ) -> JobRecord:
        """Cancel a queued or scheduled job."""
        job = await self.get_job(job_id=job_id, actor_id=actor_id, is_admin=is_admin)

        if job.status == JobStatus.COMPLETED:
            raise JobAlreadyCompletedException(job_id=job_id)

        if job.status == JobStatus.CANCELLED:
            raise JobAlreadyCancelledException(job_id=job_id)

        # Cancel from queue
        await self.queue.cancel(job_id)

        job.status = JobStatus.CANCELLED
        job.is_terminal = True
        job = await self.job_repo.update(job)
        metrics.increment("jobs_cancelled_total")

        await self.audit_service.record(
            event_type=AuditEventType.JOB_CANCELLED,
            outcome="ALLOW",
            actor_id=actor_id,
            action=f"job:cancel:{job.job_type.value}",
            resource_type=job.resource_type,
            resource_id=job.resource_id,
            metadata={"job_id": job.id},
        )

        return job

    async def retry_job(
        self,
        job_id: str,
        actor_id: str,
        is_admin: bool = False,
    ) -> JobRecord:
        """Manually trigger retry of a failed or cancelled job."""
        job = await self.get_job(job_id=job_id, actor_id=actor_id, is_admin=is_admin)

        if job.status not in (JobStatus.FAILED, JobStatus.CANCELLED):
            raise ValidationException(
                f"Cannot retry job in '{job.status.value}' state. Only FAILED or CANCELLED jobs may be retried."
            )

        job.status = JobStatus.QUEUED
        job.queued_at = datetime.now(timezone.utc)
        job.is_terminal = False
        job.error_message = None
        job.error_category = None
        job = await self.job_repo.update(job)

        await self.queue.enqueue(job)
        metrics.increment("jobs_retried_total")

        await self.audit_service.record(
            event_type=AuditEventType.JOB_RETRY_SCHEDULED,
            outcome="ALLOW",
            actor_id=actor_id,
            action=f"job:retry:{job.job_type.value}",
            resource_type=job.resource_type,
            resource_id=job.resource_id,
            metadata={"job_id": job.id, "attempt": job.attempt},
        )

        return job

    async def mark_started(self, job_id: str) -> Optional[JobRecord]:
        """Mark job status PROCESSING upon worker lease."""
        job = await self.job_repo.get(job_id)
        if not job or job.status == JobStatus.CANCELLED:
            return None

        job.status = JobStatus.PROCESSING
        job.started_at = datetime.now(timezone.utc)
        job.attempt += 1
        job = await self.job_repo.update(job)

        await self.audit_service.record(
            event_type=AuditEventType.JOB_STARTED,
            outcome="ALLOW",
            actor_id=job.initiating_user_id,
            action=f"job:start:{job.job_type.value}",
            resource_type=job.resource_type,
            resource_id=job.resource_id,
            metadata={"job_id": job.id, "attempt": job.attempt},
        )
        return job

    async def mark_completed(self, job_id: str, result: Dict[str, Any]) -> JobRecord:
        """Mark job COMPLETED and persist sanitized output."""
        job = await self.job_repo.get(job_id)
        if not job:
            raise JobNotFoundException(job_id=job_id)

        job.status = JobStatus.COMPLETED
        job.completed_at = datetime.now(timezone.utc)
        job.is_terminal = True
        job.result = result
        job = await self.job_repo.update(job)

        # Update idempotency index if key was present
        if job.idempotency_key:
            await self.idempotency.mark_completed(job.idempotency_key, result)

        await self.queue.acknowledge(job_id)
        metrics.increment("jobs_completed_total")

        await self.audit_service.record(
            event_type=AuditEventType.JOB_COMPLETED,
            outcome="ALLOW",
            actor_id=job.initiating_user_id,
            action=f"job:complete:{job.job_type.value}",
            resource_type=job.resource_type,
            resource_id=job.resource_id,
            metadata={"job_id": job.id},
        )
        return job

    async def handle_job_failure(
        self,
        job_id: str,
        error_message: str,
        error_category: str = "TRANSIENT_PROVIDER_ERROR",
        is_transient: bool = True,
    ) -> JobRecord:
        """Handle job failure with bounded exponential retry or dead-letter transition."""
        job = await self.job_repo.get(job_id)
        if not job:
            raise JobNotFoundException(job_id=job_id)

        now = datetime.now(timezone.utc)
        job.error_message = error_message
        job.error_category = error_category

        can_retry = is_transient and (job.attempt < job.max_retries)

        if can_retry:
            # Schedule exponential backoff retry
            base_delay = self.settings.JOB_RETRY_BASE_DELAY_SECONDS
            max_delay = self.settings.JOB_RETRY_MAX_DELAY_SECONDS
            delay = min(max_delay, base_delay * (2 ** (job.attempt - 1)))
            if self.settings.JOB_RETRY_JITTER_ENABLED:
                delay += random.uniform(0.1, 1.0)

            job.status = JobStatus.RETRY_PENDING
            job = await self.job_repo.update(job)

            logger.info(f"Scheduling retry for job {job.id} (attempt {job.attempt}/{job.max_retries}) in {delay:.2f}s.")
            await self.queue.reject(job_id, requeue=False)
            await self.queue.enqueue_delayed(job, delay_seconds=delay)
            metrics.increment("jobs_retried_total")

            await self.audit_service.record(
                event_type=AuditEventType.JOB_RETRY_SCHEDULED,
                outcome="ALLOW",
                actor_id=job.initiating_user_id,
                action=f"job:retry_scheduled:{job.job_type.value}",
                resource_type=job.resource_type,
                resource_id=job.resource_id,
                metadata={"job_id": job.id, "attempt": job.attempt, "delay_seconds": delay},
            )
        else:
            # Permanent failure -> FAILED
            job.status = JobStatus.FAILED
            job.failed_at = now
            job.is_terminal = True
            job = await self.job_repo.update(job)

            if job.idempotency_key:
                await self.idempotency.fail_operation(job.idempotency_key, error_message)

            await self.queue.reject(job_id, requeue=False)
            metrics.increment("jobs_failed_total")

            logger.error(f"Job {job.id} ({job.job_type.value}) permanently FAILED: {error_message}")
            await self.audit_service.record(
                event_type=AuditEventType.JOB_FAILED,
                outcome="DENY",
                actor_id=job.initiating_user_id,
                action=f"job:failed:{job.job_type.value}",
                resource_type=job.resource_type,
                resource_id=job.resource_id,
                metadata={"job_id": job.id, "error_category": error_category},
            )

        return job
