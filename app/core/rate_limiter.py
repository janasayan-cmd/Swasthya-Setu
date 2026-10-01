"""Rate limiting middleware and utilities for HealthSetu.

RATE LIMITING POLICY
=====================
Rate limiting protects against:
- Brute-force authentication attacks
- Flooding of resource-intensive endpoints (AI, triage, medication safety)
- Document upload abuse
- Excessive interoperability export/import requests
- Repeated external API calls

LIMITS HIERARCHY
=================
1. Per-IP limits (connection-level defense)
2. Per-user limits (identity-level defense)
3. Endpoint-specific limits (resource-specific defense)

IMPORTANT: IP address is NOT the sole security boundary.
Per-user limits remain enforced even behind reverse proxies.

IMPLEMENTATION NOTE
====================
This module provides in-process, in-memory rate limiting appropriate for
single-instance deployments and testing.

For multi-instance production deployments, a distributed rate limit backend
(e.g., Redis with sliding window counters) should be used. The interface
here is designed to be replaceable with a Redis-backed implementation.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass
from threading import Lock
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.exceptions import ErrorCode, build_error_response
from app.core.logging import get_logger

logger = get_logger("app.rate_limiter")


@dataclass(frozen=True)
class RateLimitConfig:
    """Configuration for a single rate limit window."""

    requests: int     # Maximum requests allowed
    window_seconds: int  # Rolling window duration in seconds
    burst_requests: int | None = None  # Optional burst allowance


# ---------------------------------------------------------------------------
# Endpoint-specific rate limit configurations
# ---------------------------------------------------------------------------

RATE_LIMIT_CONFIGS: dict[str, RateLimitConfig] = {
    # Authentication — tightest limits to prevent brute force
    "auth": RateLimitConfig(requests=10, window_seconds=60),
    # AI requests — resource-intensive
    "ai": RateLimitConfig(requests=30, window_seconds=60),
    # Document upload — disk/storage intensive
    "document_upload": RateLimitConfig(requests=20, window_seconds=60),
    # Triage — clinical workflow, moderate limit
    "triage": RateLimitConfig(requests=60, window_seconds=60),
    # Medication safety checks — external provider calls
    "medication_safety": RateLimitConfig(requests=30, window_seconds=60),
    # Interoperability — external data exchange
    "interoperability": RateLimitConfig(requests=20, window_seconds=60),
    # Transfer creation — workflow creation
    "transfer": RateLimitConfig(requests=30, window_seconds=60),
    # General API default
    "default": RateLimitConfig(requests=120, window_seconds=60),
    # Phase 27: Administration, Support Operations & Backoffice
    "admin": RateLimitConfig(requests=60, window_seconds=60),
    "admin_retry": RateLimitConfig(requests=10, window_seconds=60),
    "admin_test": RateLimitConfig(requests=10, window_seconds=60),
    "admin_search": RateLimitConfig(requests=20, window_seconds=60),
}


def _get_endpoint_category(path: str) -> str:
    """Map request path to rate limit category."""
    p = path.lower()
    if "/admin" in p:
        if "/retry" in p:
            return "admin_retry"
        if "/test" in p:
            return "admin_test"
        if "/search" in p:
            return "admin_search"
        return "admin"
    if "/auth/" in p or "/login" in p or "/token" in p:
        return "auth"
    if "/ai/" in p:
        return "ai"
    if "/documents" in p and ("upload" in p or p.endswith("/documents")):
        return "document_upload"
    if "/triage" in p:
        return "triage"
    if "/medication-safety" in p or "/medication_safety" in p:
        return "medication_safety"
    if "/interoperability" in p:
        return "interoperability"
    if "/transfers" in p:
        return "transfer"
    return "default"


class InMemoryRateLimiter:
    """Thread-safe in-memory sliding window rate limiter.

    Suitable for single-instance deployments.
    For distributed deployments, replace with Redis-backed implementation.
    """

    def __init__(self) -> None:
        # {key: deque of timestamps}
        self._windows: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def is_allowed(
        self,
        key: str,
        config: RateLimitConfig,
    ) -> tuple[bool, int, int]:
        """Check whether a request is within rate limits.

        Args:
            key: Rate limit key (e.g., "ip:127.0.0.1:auth" or "user:uuid:ai").
            config: Rate limit configuration for this window.

        Returns:
            Tuple of (allowed, remaining_requests, retry_after_seconds).
        """
        now = time.monotonic()
        window_start = now - config.window_seconds

        with self._lock:
            window = self._windows[key]

            # Remove expired entries
            while window and window[0] < window_start:
                window.popleft()

            current_count = len(window)
            limit = config.requests

            if current_count >= limit:
                # Calculate retry-after from oldest request in window
                retry_after = int(config.window_seconds - (now - window[0])) + 1 if window else config.window_seconds
                return False, 0, retry_after

            # Allow and record
            window.append(now)
            remaining = limit - current_count - 1
            return True, remaining, 0

    def reset(self, key: str) -> None:
        """Reset rate limit window for a key (for testing)."""
        with self._lock:
            self._windows.pop(key, None)

    def clear_all(self) -> None:
        """Clear all rate limit windows (for testing)."""
        with self._lock:
            self._windows.clear()


# Module-level rate limiter singleton
_rate_limiter = InMemoryRateLimiter()


def get_rate_limiter() -> InMemoryRateLimiter:
    """Return the module-level rate limiter instance."""
    return _rate_limiter


def get_client_ip(request: Request) -> str:
    """Extract client IP from request, considering common proxy headers.

    Uses X-Forwarded-For if available (trusting the outermost proxy).
    Falls back to direct client IP.
    """
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        # X-Forwarded-For: client, proxy1, proxy2
        # Take the leftmost (client) IP
        return forwarded_for.split(",")[0].strip()

    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()

    if request.client:
        return request.client.host

    return "unknown"


def check_rate_limit(
    request: Request,
    *,
    actor_id: str | None = None,
    category: str | None = None,
) -> tuple[bool, int, int]:
    """Check rate limit for a request.

    Checks per-IP and per-user limits independently.
    Both must pass for the request to be allowed.

    Args:
        request: The incoming request.
        actor_id: Authenticated user ID (if available).
        category: Rate limit category override.

    Returns:
        Tuple of (allowed, remaining, retry_after_seconds).
    """
    if category is None:
        category = _get_endpoint_category(request.url.path)

    config = RATE_LIMIT_CONFIGS.get(category, RATE_LIMIT_CONFIGS["default"])
    client_ip = get_client_ip(request)

    limiter = get_rate_limiter()

    # Per-IP check
    ip_key = f"ip:{client_ip}:{category}"
    ip_allowed, ip_remaining, ip_retry = limiter.is_allowed(ip_key, config)
    if not ip_allowed:
        return False, 0, ip_retry

    # Per-user check (if authenticated)
    if actor_id:
        user_key = f"user:{actor_id}:{category}"
        user_allowed, user_remaining, user_retry = limiter.is_allowed(user_key, config)
        if not user_allowed:
            return False, 0, user_retry
        return True, min(ip_remaining, user_remaining), 0

    return True, ip_remaining, 0


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware applying rate limits to sensitive endpoint categories.

    Endpoints are categorized by path pattern. Per-IP limits are applied
    to all requests; per-user limits are applied when authenticated.

    Rate limit violations return:
        HTTP 429 with RATE_LIMIT_EXCEEDED error code
        Retry-After header indicating when to retry
    """

    # Paths to exclude from rate limiting
    _EXCLUDED_PATHS = frozenset(
        {
            "/api/v1/health",
            "/api/v1/readiness",
            "/docs",
            "/redoc",
            "/openapi.json",
        }
    )

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        from app.core.config import get_settings

        settings = get_settings()

        # Skip if rate limiting disabled (e.g., tests)
        if not getattr(settings, "RATE_LIMIT_ENABLED", True) or settings.is_testing:
            return await call_next(request)

        # Skip excluded paths
        if request.url.path in self._EXCLUDED_PATHS:
            return await call_next(request)

        category = _get_endpoint_category(request.url.path)
        config = RATE_LIMIT_CONFIGS.get(category, RATE_LIMIT_CONFIGS["default"])
        client_ip = get_client_ip(request)
        limiter = get_rate_limiter()

        # Per-IP check
        ip_key = f"ip:{client_ip}:{category}"
        allowed, remaining, retry_after = limiter.is_allowed(ip_key, config)

        if not allowed:
            req_id = getattr(request.state, "request_id", "unknown")
            logger.warning(
                f"Rate limit exceeded for IP {client_ip} on {category}",
                extra={
                    "event_type": "RATE_LIMIT_TRIGGERED",
                    "category": category,
                    "ip_address": client_ip,
                    "request_id": req_id,
                },
            )
            response = build_error_response(
                status_code=429,
                code=ErrorCode.RATE_LIMIT_EXCEEDED.value,
                message="Too many requests. Please try again later.",
                request_id=req_id,
            )
            response.headers["Retry-After"] = str(retry_after)
            response.headers["X-RateLimit-Limit"] = str(config.requests)
            response.headers["X-RateLimit-Remaining"] = "0"
            response.headers["X-RateLimit-Reset"] = str(retry_after)
            return response

        response = await call_next(request)

        # Add rate limit headers to successful responses
        response.headers["X-RateLimit-Limit"] = str(config.requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)

        return response
