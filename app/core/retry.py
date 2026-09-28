"""Selective retry with exponential backoff and jitter for HealthSetu (Phase 21).

Enforces Sections 53, 54, 55:
- Retries transient network glitches and temporary provider 502/503/504/429
- NEVER retries 4xx client errors, auth failures, or clinical validation errors
- Enforces idempotency check: non-idempotent operations are never blindly retried
- Full jitter prevents synchronized retry storms
"""

from __future__ import annotations

import asyncio
import random
from typing import Any, Callable, Coroutine, Sequence, Type, TypeVar
import httpx

from app.core.exceptions import AppException
from app.core.logging import get_logger

logger = get_logger("app.core.retry")
T = TypeVar("T")

# Non-retryable HTTP client status codes
_NON_RETRYABLE_STATUS_CODES = {400, 401, 403, 404, 409, 413, 422}


def is_transient_error(exc: Exception) -> bool:
    """Determine if an exception represents a safe, transient network/service error."""
    # Never retry application logic validation / authorization errors
    if isinstance(exc, AppException):
        if exc.status_code in _NON_RETRYABLE_STATUS_CODES:
            return False
        # 502, 503, 504 or rate limits may be transient
        return exc.status_code in {429, 502, 503, 504}

    if isinstance(exc, (TimeoutError, asyncio.TimeoutError, ConnectionError, ConnectionResetError)):
        return True

    if isinstance(exc, (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout, httpx.NetworkError)):
        return True

    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in {429, 502, 503, 504}

    return False


async def retry_async(
    func: Callable[..., Coroutine[Any, Any, T]],
    *args: Any,
    max_retries: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 5.0,
    jitter: bool = True,
    is_idempotent: bool = True,
    retryable_check: Callable[[Exception], bool] = is_transient_error,
    **kwargs: Any,
) -> T:
    """Execute an async operation with selective exponential backoff.

    Args:
        func: Async function to execute
        max_retries: Maximum additional retry attempts (default 3)
        base_delay: Initial delay in seconds
        max_delay: Maximum delay cap in seconds
        jitter: Apply randomized jitter to avoid thundering herds
        is_idempotent: If False, retries are immediately disallowed to protect clinical data
        retryable_check: Callable that returns True if the exception should be retried
    """
    if not is_idempotent:
        # Non-idempotent operations must only execute once!
        return await func(*args, **kwargs)

    attempt = 0
    while True:
        try:
            return await func(*args, **kwargs)
        except Exception as exc:
            attempt += 1
            if attempt > max_retries or not retryable_check(exc):
                logger.debug(f"Operation failed after attempt {attempt}. Not retrying: {exc}")
                raise

            delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
            if jitter:
                delay = delay * (0.5 + random.random())

            logger.warning(
                f"Transient error ({type(exc).__name__}) on attempt {attempt}/{max_retries}. "
                f"Retrying in {delay:.2f}s..."
            )
            await asyncio.sleep(delay)
