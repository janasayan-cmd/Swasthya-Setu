"""Bounded concurrency controls and resource isolation for HealthSetu (Phase 21).

Enforces Sections 19, 21, 26, 27, 28, 48:
- Resource isolation prevents heavy background/AI/OCR jobs from starving clinical endpoints
- Bounded semaphores with acquisition timeouts
- Telemetry instrumentation for queue depth and concurrency
"""

from __future__ import annotations

import asyncio
from typing import Any, Callable, Coroutine, TypeVar

from app.core.config import get_settings
from app.core.exceptions import AppException
from app.core.logging import get_logger

logger = get_logger("app.core.concurrency")
T = TypeVar("T")


class ConcurrencyLimitExceededException(AppException):
    """Raised when an operation cannot acquire a concurrency slot within the timeout."""

    def __init__(self, resource_name: str, message: str | None = None) -> None:
        msg = message or f"Resource limit reached for '{resource_name}'. System is operating under high load."
        super().__init__(
            code="CONCURRENCY_LIMIT_EXCEEDED",
            message=msg,
            status_code=503,
            details={"resource": resource_name},
        )
        self.resource_name = resource_name


class BoundedConcurrencyLimiter:
    """Async semaphore-backed concurrency controller with bounded wait timeout."""

    def __init__(self, name: str, max_concurrency: int, wait_timeout_seconds: float = 10.0) -> None:
        self.name = name
        self.max_concurrency = max_concurrency
        self.wait_timeout = wait_timeout_seconds
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._active_count = 0
        self._lock = asyncio.Lock()

    @property
    def active_count(self) -> int:
        return self._active_count

    @property
    def available_slots(self) -> int:
        return max(0, self.max_concurrency - self._active_count)

    async def run(
        self,
        func: Callable[..., Coroutine[Any, Any, T]],
        *args: Any,
        timeout: float | None = None,
        **kwargs: Any,
    ) -> T:
        """Execute async callable within bounded concurrency slot."""
        wait_time = timeout if timeout is not None else self.wait_timeout
        try:
            acquired = await asyncio.wait_for(self._semaphore.acquire(), timeout=wait_time)
        except asyncio.TimeoutError:
            logger.warning(
                f"Concurrency limit ({self.max_concurrency}) exceeded for '{self.name}'. Timed out after {wait_time}s."
            )
            raise ConcurrencyLimitExceededException(resource_name=self.name)

        async with self._lock:
            self._active_count += 1

        try:
            return await func(*args, **kwargs)
        finally:
            async with self._lock:
                self._active_count = max(0, self._active_count - 1)
            self._semaphore.release()


# ---------------------------------------------------------------------------
# Global Concurrency Limiters for Isolated Workloads
# ---------------------------------------------------------------------------

_LIMITERS: dict[str, BoundedConcurrencyLimiter] = {}


def get_concurrency_limiter(name: str, default_concurrency: int = 5) -> BoundedConcurrencyLimiter:
    """Retrieve or initialize a bounded limiter by name."""
    settings = get_settings()
    if name not in _LIMITERS:
        capacity = default_concurrency
        if name == "ai":
            capacity = settings.AI_MAX_CONCURRENCY
        elif name == "ocr":
            capacity = settings.OCR_MAX_CONCURRENCY
        elif name == "med_safety":
            capacity = settings.MED_SAFETY_MAX_CONCURRENCY
        elif name == "background_worker":
            capacity = settings.BACKGROUND_WORKER_CONCURRENCY

        _LIMITERS[name] = BoundedConcurrencyLimiter(name=name, max_concurrency=capacity)
    return _LIMITERS[name]


def get_all_concurrency_stats() -> dict[str, dict[str, int]]:
    """Return status of all registered concurrency pools."""
    return {
        name: {
            "max_concurrency": limiter.max_concurrency,
            "active_tasks": limiter.active_count,
            "available_slots": limiter.available_slots,
        }
        for name, limiter in _LIMITERS.items()
    }
