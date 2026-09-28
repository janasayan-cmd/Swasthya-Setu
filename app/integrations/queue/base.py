"""Abstract base class for asynchronous job queue providers (Phase 22).

Enables swapping queue brokers (in-memory, Redis, SQS, RabbitMQ)
without impacting domain services or task workers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from app.schemas.job import JobRecord


class JobQueueProvider(ABC):
    """Abstract interface for queuing and leasing asynchronous jobs."""

    @abstractmethod
    async def enqueue(self, job: JobRecord) -> None:
        """Enqueue a job for immediate worker leasing."""
        pass

    @abstractmethod
    async def enqueue_delayed(self, job: JobRecord, delay_seconds: float) -> None:
        """Enqueue a job to become visible after delay_seconds (e.g. for retries)."""
        pass

    @abstractmethod
    async def dequeue(self, timeout: float = 1.0) -> Optional[JobRecord]:
        """Lease next available job, blocking up to timeout seconds."""
        pass

    @abstractmethod
    async def acknowledge(self, job_id: str) -> None:
        """Confirm successful completion of leased job."""
        pass

    @abstractmethod
    async def reject(self, job_id: str, requeue: bool = False) -> None:
        """Reject leased job on error, optionally requeueing."""
        pass

    @abstractmethod
    async def cancel(self, job_id: str) -> bool:
        """Remove queued job prior to worker leasing."""
        pass

    @abstractmethod
    def depth(self) -> int:
        """Current number of pending queued jobs."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close provider connections and release resources."""
        pass
