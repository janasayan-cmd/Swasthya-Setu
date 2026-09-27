"""Application middlewares for request tracking, security, and logging."""

import re
import time
import uuid
from typing import Callable
from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import get_settings
from app.core.exceptions import ErrorCode, build_error_response
from app.core.logging import get_logger, request_id_ctx_var
from app.core.metrics import metrics
from app.core.rate_limiter import RateLimitMiddleware
from app.core.security import SECURITY_HEADERS, get_security_headers

logger = get_logger("app.middleware")

# Pattern to validate client-provided request IDs: alphanumeric, hyphen, underscore, 8-64 chars
REQUEST_ID_REGEX = re.compile(r"^[a-zA-Z0-9\-_]{8,64}$")


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Middleware to preserve or generate correlation/request IDs, track operational metrics, and log request lifecycle."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        settings = get_settings()
        header_name = settings.REQUEST_ID_HEADER

        # 1. Check incoming request header
        incoming_id = request.headers.get(header_name)
        if incoming_id and REQUEST_ID_REGEX.match(incoming_id):
            request_id = incoming_id
        else:
            request_id = str(uuid.uuid4())

        # 2. Attach to request state and context var
        request.state.request_id = request_id
        token = request_id_ctx_var.set(request_id)

        metrics.inc_in_progress()
        start_time = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception as exc:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            metrics.dec_in_progress()
            metrics.record_http_request(request.method, request.url.path, 500, duration_ms)
            metrics.record_application_error("UNCAUGHT_EXCEPTION", request.url.path)
            request_id_ctx_var.reset(token)
            # Uncaught exceptions are handled centrally without leaking internals
            from app.core.exceptions import unhandled_exception_handler
            error_response = await unhandled_exception_handler(request, exc)
            error_response.headers[header_name] = request_id
            for hk, hv in SECURITY_HEADERS.items():
                error_response.headers.setdefault(hk, hv)
            return error_response

        metrics.dec_in_progress()
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # 3. Attach request ID to response header
        response.headers[header_name] = request_id

        # 4. Record operational metrics
        if settings.METRICS_ENABLED:
            metrics.record_http_request(request.method, request.url.path, response.status_code, duration_ms)
            if response.status_code == 401:
                metrics.record_auth_failure()
            elif response.status_code == 403:
                metrics.record_authz_denial()

        # 5. Slow Request Detection (Phase 18 TRD Sec 21)
        if settings.OBSERVABILITY_ENABLED and duration_ms >= settings.SLOW_REQUEST_THRESHOLD_MS:
            logger.warning(
                f"SLOW REQUEST: {request.method} {request.url.path} took {duration_ms}ms "
                f"(threshold: {settings.SLOW_REQUEST_THRESHOLD_MS}ms)",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                    "threshold_ms": settings.SLOW_REQUEST_THRESHOLD_MS,
                    "version": settings.APP_VERSION,
                },
            )

        # 6. Structured log for request lifecycle (privacy-conscious: method, path, status, duration only)
        logger.info(
            f"{request.method} {request.url.path} completed with {response.status_code} in {duration_ms}ms",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )

        request_id_ctx_var.reset(token)
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware injecting baseline security headers into every response."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        settings = get_settings()
        if settings.SECURITY_HEADERS_ENABLED:
            headers = get_security_headers(
                is_production=settings.is_production,
                enable_hsts=settings.STRICT_TRANSPORT_SECURITY_ENABLED,
            )
            for header_key, header_val in headers.items():
                response.headers.setdefault(header_key, header_val)
        return response


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Middleware enforcing maximum allowed request payload size."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        settings = get_settings()
        content_length = request.headers.get("content-length")

        if content_length:
            try:
                length = int(content_length)
                if length > settings.MAX_REQUEST_SIZE_BYTES:
                    req_id = getattr(request.state, "request_id", None) or "unknown"
                    return build_error_response(
                        status_code=413,
                        code=ErrorCode.VALIDATION_ERROR.value,
                        message=f"Payload size ({length} bytes) exceeds limit of {settings.MAX_REQUEST_SIZE_BYTES} bytes.",
                        request_id=req_id,
                    )
            except ValueError:
                pass

        return await call_next(request)
