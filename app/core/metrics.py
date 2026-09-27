"""Core operational metrics and telemetry instrumentation for HealthSetu (Phase 18).

Provides low-overhead, thread-safe, bounded-cardinality in-memory metrics:
- HTTP request counters, latencies, and in-flight gauges
- Error tracking and status code breakdowns (4xx, 5xx)
- Authentication and authorization failure rates
- Database connectivity and transaction error counters
- External healthcare provider telemetry (OCR, AI, Medication Safety, Interop)
- Background job lifecycle tracking (queued, completed, failed, retried)

CRITICAL PRIVACY BOUNDARY:
- NO patient_id, user_id, or request_id in metric labels.
- Route paths are normalized to eliminate dynamic resource identifiers.
"""

from __future__ import annotations

import math
import re
import threading
import time
from collections import defaultdict
from typing import Any

# Regex to normalize dynamic route IDs and preserve bounded label cardinality
_PATH_PARAM_REGEXES = [
    re.compile(r"/patients/[^/]+"),
    re.compile(r"/documents/[^/]+"),
    re.compile(r"/encounters/[^/]+"),
    re.compile(r"/facilities/[^/]+"),
    re.compile(r"/departments/[^/]+"),
    re.compile(r"/organizations/[^/]+"),
    re.compile(r"/transfers/[^/]+"),
    re.compile(r"/tasks/[^/]+"),
    re.compile(r"/imports/[^/]+"),
    re.compile(r"/exports/[^/]+"),
    re.compile(r"/care-plans/[^/]+"),
    re.compile(r"/clinical-notes/[^/]+"),
    re.compile(r"/medications/[^/]+"),
    re.compile(r"/prescriptions/[^/]+"),
    re.compile(r"/allergies/[^/]+"),
    re.compile(r"/vitals/[^/]+"),
    re.compile(r"/users/[^/]+"),
    # General UUID and alphanumeric ID replacement
    re.compile(r"/[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"),
    re.compile(r"/(?:pat|usr|doc|hosp|rx|imp|exp|task|plan|enc|sess)-[a-zA-Z0-9_\-]+", re.IGNORECASE),
]


def normalize_route_path(path: str) -> str:
    """Normalize raw URL path to a bounded route template to prevent label explosion.

    Example:
        /api/v1/patients/pat-001/medications -> /api/v1/patients/{id}/medications
    """
    clean_path = path.split("?")[0].rstrip("/") or "/"
    # Apply specific resource path mappings
    clean_path = re.sub(r"/patients/[^/]+", "/patients/{patient_id}", clean_path)
    clean_path = re.sub(r"/documents/[^/]+", "/documents/{document_id}", clean_path)
    clean_path = re.sub(r"/facilities/[^/]+", "/facilities/{facility_id}", clean_path)
    clean_path = re.sub(r"/transfers/[^/]+", "/transfers/{transfer_id}", clean_path)
    clean_path = re.sub(r"/tasks/[^/]+", "/tasks/{task_id}", clean_path)
    clean_path = re.sub(r"/imports/[^/]+", "/imports/{import_id}", clean_path)
    clean_path = re.sub(r"/exports/[^/]+", "/exports/{export_id}", clean_path)
    clean_path = re.sub(r"/care-plans/[^/]+", "/care-plans/{care_plan_id}", clean_path)
    clean_path = re.sub(r"/clinical-notes/[^/]+", "/clinical-notes/{note_id}", clean_path)
    clean_path = re.sub(r"/users/[^/]+", "/users/{user_id}", clean_path)

    # Replace any leftover UUIDs or entity tokens
    clean_path = re.sub(
        r"/[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
        "/{id}",
        clean_path,
    )
    clean_path = re.sub(
        r"/(?:pat|usr|doc|hosp|rx|imp|exp|task|plan|enc|sess)-[a-zA-Z0-9_\-]+",
        "/{id}",
        clean_path,
        flags=re.IGNORECASE,
    )
    return clean_path


class MetricsCollector:
    """Thread-safe application metrics registry and aggregator."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._start_time = time.time()
        self.reset()

    def reset(self) -> None:
        """Reset all metrics (primarily for unit test isolation)."""
        with self._lock:
            # Core HTTP metrics
            self.http_requests_total: dict[tuple[str, str, int], int] = defaultdict(int)
            self.http_requests_in_progress: int = 0
            self.http_4xx_total: int = 0
            self.http_5xx_total: int = 0

            # Latency histograms / buckets
            # Track durations in milliseconds: list of recent latencies (capped at 500 samples)
            self._latencies: list[float] = []

            # Application & Security errors
            self.application_errors_total: dict[tuple[str, str], int] = defaultdict(int)
            self.authentication_failures_total: int = 0
            self.authorization_denials_total: int = 0
            self.database_errors_total: int = 0

            # External provider telemetry
            # (provider, outcome) -> count
            self.external_provider_requests_total: dict[tuple[str, str], int] = defaultdict(int)
            self.external_provider_errors_total: dict[str, int] = defaultdict(int)
            self.external_provider_timeouts_total: dict[str, int] = defaultdict(int)
            self._provider_latencies: dict[str, list[float]] = defaultdict(list)

            # Background jobs telemetry
            self.background_job_total: dict[tuple[str, str], int] = defaultdict(int)
            self.background_job_failures_total: dict[str, int] = defaultdict(int)

    # -------------------------------------------------------------------------
    # HTTP Instrumentation
    # -------------------------------------------------------------------------

    def inc_in_progress(self) -> None:
        """Increment gauge of concurrent active HTTP requests."""
        with self._lock:
            self.http_requests_in_progress += 1

    def dec_in_progress(self) -> None:
        """Decrement gauge of concurrent active HTTP requests."""
        with self._lock:
            if self.http_requests_in_progress > 0:
                self.http_requests_in_progress -= 1

    def record_http_request(
        self,
        method: str,
        path: str,
        status_code: int,
        duration_ms: float,
    ) -> None:
        """Record completed HTTP request metrics with normalized route."""
        norm_route = normalize_route_path(path)
        with self._lock:
            self.http_requests_total[(method.upper(), norm_route, status_code)] += 1

            if 400 <= status_code < 500:
                self.http_4xx_total += 1
            elif status_code >= 500:
                self.http_5xx_total += 1

            # Keep rolling window of 1000 latency measurements for p50/p95/p99 calculations
            self._latencies.append(duration_ms)
            if len(self._latencies) > 1000:
                self._latencies.pop(0)

    # -------------------------------------------------------------------------
    # Security & Error Instrumentation
    # -------------------------------------------------------------------------

    def record_auth_failure(self) -> None:
        """Record failed authentication attempt."""
        with self._lock:
            self.authentication_failures_total += 1

    def record_authz_denial(self) -> None:
        """Record authorization / permission / consent denial."""
        with self._lock:
            self.authorization_denials_total += 1

    def record_database_error(self) -> None:
        """Record database connection or query failure."""
        with self._lock:
            self.database_errors_total += 1

    def record_application_error(self, error_code: str, route: str) -> None:
        """Record structured application-level error."""
        norm_route = normalize_route_path(route)
        with self._lock:
            self.application_errors_total[(error_code, norm_route)] += 1

    # -------------------------------------------------------------------------
    # External Provider Telemetry
    # -------------------------------------------------------------------------

    def record_provider_request(
        self,
        provider: str,
        success: bool,
        duration_ms: float = 0.0,
        is_timeout: bool = False,
    ) -> None:
        """Record external healthcare integration provider execution."""
        clean_provider = provider.lower().strip()
        outcome = "success" if success else ("timeout" if is_timeout else "failure")
        with self._lock:
            self.external_provider_requests_total[(clean_provider, outcome)] += 1
            if not success:
                self.external_provider_errors_total[clean_provider] += 1
            if is_timeout:
                self.external_provider_timeouts_total[clean_provider] += 1
            if duration_ms > 0:
                lat_list = self._provider_latencies[clean_provider]
                lat_list.append(duration_ms)
                if len(lat_list) > 200:
                    lat_list.pop(0)

    # -------------------------------------------------------------------------
    # Background Job Telemetry
    # -------------------------------------------------------------------------

    def record_background_job(self, job_type: str, status: str) -> None:
        """Record background asynchronous task state transition."""
        clean_type = job_type.lower().strip()
        clean_status = status.lower().strip()
        with self._lock:
            self.background_job_total[(clean_type, clean_status)] += 1
            if clean_status in ("failed", "failure", "error"):
                self.background_job_failures_total[clean_type] += 1

    # -------------------------------------------------------------------------
    # Aggregations & Reporting
    # -------------------------------------------------------------------------

    def _calculate_percentiles(self, samples: list[float]) -> dict[str, float]:
        """Compute p50, p95, p99 percentiles from a float sample list."""
        if not samples:
            return {"p50": 0.0, "p95": 0.0, "p99": 0.0, "avg": 0.0}
        sorted_samples = sorted(samples)
        n = len(sorted_samples)

        def _p(pct: float) -> float:
            idx = max(0, min(n - 1, math.ceil(pct * n) - 1))
            return round(sorted_samples[idx], 2)

        return {
            "p50": _p(0.50),
            "p95": _p(0.95),
            "p99": _p(0.99),
            "avg": round(sum(sorted_samples) / n, 2),
        }

    def get_summary(self) -> dict[str, Any]:
        """Return structured JSON operational telemetry summary."""
        with self._lock:
            total_reqs = sum(self.http_requests_total.values())
            latency_stats = self._calculate_percentiles(self._latencies)

            provider_summaries: dict[str, Any] = {}
            for prov in set(p for p, _ in self.external_provider_requests_total.keys()):
                prov_lat = self._calculate_percentiles(self._provider_latencies.get(prov, []))
                provider_summaries[prov] = {
                    "total": sum(
                        count
                        for (p, _), count in self.external_provider_requests_total.items()
                        if p == prov
                    ),
                    "errors": self.external_provider_errors_total.get(prov, 0),
                    "timeouts": self.external_provider_timeouts_total.get(prov, 0),
                    "latency_ms": prov_lat,
                }

            return {
                "uptime_seconds": round(time.time() - self._start_time, 1),
                "http": {
                    "total_requests": total_reqs,
                    "in_progress": self.http_requests_in_progress,
                    "status_4xx": self.http_4xx_total,
                    "status_5xx": self.http_5xx_total,
                    "latency_ms": latency_stats,
                },
                "security": {
                    "authentication_failures": self.authentication_failures_total,
                    "authorization_denials": self.authorization_denials_total,
                },
                "database": {
                    "errors_total": self.database_errors_total,
                },
                "external_providers": provider_summaries,
                "background_jobs": {
                    "failures_total": sum(self.background_job_failures_total.values()),
                    "by_type": dict(self.background_job_failures_total),
                },
            }

    def to_prometheus_text(self) -> str:
        """Format metrics in standard Prometheus exposition format."""
        with self._lock:
            lines: list[str] = [
                "# HELP http_requests_total Total HTTP requests processed by HealthSetu backend",
                "# TYPE http_requests_total counter",
            ]
            for (method, route, status_code), count in sorted(self.http_requests_total.items()):
                lines.append(
                    f'http_requests_total{{method="{method}",route="{route}",status_code="{status_code}"}} {count}'
                )

            lines.extend([
                "# HELP http_requests_in_progress Number of active concurrent HTTP requests",
                "# TYPE http_requests_in_progress gauge",
                f"http_requests_in_progress {self.http_requests_in_progress}",
                "# HELP http_4xx_total Total HTTP 4xx client errors",
                "# TYPE http_4xx_total counter",
                f"http_4xx_total {self.http_4xx_total}",
                "# HELP http_5xx_total Total HTTP 5xx server errors",
                "# TYPE http_5xx_total counter",
                f"http_5xx_total {self.http_5xx_total}",
                "# HELP authentication_failures_total Total failed authentication attempts",
                "# TYPE authentication_failures_total counter",
                f"authentication_failures_total {self.authentication_failures_total}",
                "# HELP authorization_denials_total Total authorization and consent access denials",
                "# TYPE authorization_denials_total counter",
                f"authorization_denials_total {self.authorization_denials_total}",
                "# HELP database_errors_total Total database connectivity and transaction errors",
                "# TYPE database_errors_total counter",
                f"database_errors_total {self.database_errors_total}",
            ])

            # External providers
            lines.extend([
                "# HELP external_provider_errors_total Total errors communicating with external healthcare providers",
                "# TYPE external_provider_errors_total counter",
            ])
            for prov, err_count in sorted(self.external_provider_errors_total.items()):
                lines.append(f'external_provider_errors_total{{provider="{prov}"}} {err_count}')

            # Background jobs
            lines.extend([
                "# HELP background_job_failures_total Total background asynchronous processing failures",
                "# TYPE background_job_failures_total counter",
            ])
            for job_type, count in sorted(self.background_job_failures_total.items()):
                lines.append(f'background_job_failures_total{{job_type="{job_type}"}} {count}')

            return "\n".join(lines) + "\n"


# Global singleton collector
metrics = MetricsCollector()
