"""API Load Shedding Middleware for HealthSetu (Phase 21).

Enforces Section 37:
- During severe concurrency saturation, sheds non-critical workloads (AI, broad discovery, exports)
- Protects critical clinical operations: Authentication, Emergency Triage, Core EHR, and Audit
- Returns HTTP 503 with Retry-After header and standard error envelope
"""

from __future__ import annotations

import json
import threading
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.metrics import metrics

logger = get_logger("app.core.load_shedding")

# Critical path prefixes that MUST NEVER be shed during load
_CRITICAL_PREFIXES = (
    "/api/v1/health",
    "/api/v1/ready",
    "/api/v1/metrics",
    "/api/v1/auth",
    "/api/v1/triage",
    "/api/v1/patients",
    "/api/v1/clinical-workflow",
    "/api/v1/consents",
)

# Non-critical paths prioritized for shedding during saturation
_SHEDDABLE_PREFIXES = (
    "/api/v1/ai",
    "/api/v1/facilities/discover",
    "/api/v1/interoperability/export",
    "/api/v1/documents",
)


class LoadSheddingController:
    """Tracks concurrency and evaluates shedding decisions."""

    def __init__(self) -> None:
        self._active_requests = 0
        self._lock = threading.Lock()

    @property
    def active_requests(self) -> int:
        with self._lock:
            return self._active_requests

    def inc_request(self) -> int:
        with self._lock:
            self._active_requests += 1
            return self._active_requests

    def dec_request(self) -> None:
        with self._lock:
            if self._active_requests > 0:
                self._active_requests -= 1

    def should_shed(self, path: str) -> bool:
        """Evaluate if the inbound request path should be shed under current load."""
        settings = get_settings()
        if not settings.LOAD_SHEDDING_ENABLED:
            return False

        # Critical paths are never shed
        for prefix in _CRITICAL_PREFIXES:
            if path.startswith(prefix):
                return False

        # Check concurrency threshold
        with self._lock:
            is_saturated = self._active_requests >= settings.LOAD_SHEDDING_MAX_CONCURRENT_REQUESTS

        if not is_saturated:
            return False

        # Shed non-critical paths
        for prefix in _SHEDDABLE_PREFIXES:
            if path.startswith(prefix):
                return True

        return False


# Singleton controller
load_shedding_controller = LoadSheddingController()


class LoadSheddingMiddleware(BaseHTTPMiddleware):
    """Starlette middleware that sheds non-critical traffic under high concurrency."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path

        if load_shedding_controller.should_shed(path):
            logger.warning(
                f"Load shedding active ({load_shedding_controller.active_requests} requests). "
                f"Shedding request to {path}"
            )
            # Record metric counter
            if hasattr(metrics, "load_shedding_rejected_total"):
                metrics.load_shedding_rejected_total += 1

            request_id = request.headers.get("X-Request-ID", "unknown")
            error_payload = {
                "success": False,
                "error": {
                    "code": "LOAD_SHEDDING_ACTIVE",
                    "message": "System is experiencing heavy load. Non-critical request shed to preserve emergency clinical operations.",
                    "request_id": request_id,
                },
            }
            return Response(
                content=json.dumps(error_payload),
                status_code=503,
                media_type="application/json",
                headers={
                    "Retry-After": "5",
                    "X-Request-ID": request_id,
                },
            )

        load_shedding_controller.inc_request()
        try:
            return await call_next(request)
        finally:
            load_shedding_controller.dec_request()
