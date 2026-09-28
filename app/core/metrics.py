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
    clean_path = re.sub(r"/jobs/[^/]+", "/jobs/{job_id}", clean_path)
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

            # Disaster Recovery & Business Continuity telemetry (Phase 19)
            self.recovery_attempts_total: dict[str, int] = defaultdict(int)
            self.recovery_success_total: dict[str, int] = defaultdict(int)
            self.recovery_failure_total: dict[str, int] = defaultdict(int)
            self.recovery_duration_seconds: dict[str, float] = {}
            self.database_restore_duration_seconds: float = 0.0
            self.deployment_rollback_total: int = 0
            self.provider_recovery_total: dict[str, int] = defaultdict(int)

            # Scalability, Performance & High-Availability telemetry (Phase 21)
            self.load_shedding_rejected_total: int = 0
            self.circuit_breaker_trips_total: dict[str, int] = defaultdict(int)
            self.cache_hits_total: dict[str, int] = defaultdict(int)
            self.cache_misses_total: dict[str, int] = defaultdict(int)

            # Asynchronous Workflows & Events (Phase 22)
            self.jobs_created_total: int = 0
            self.jobs_queued_total: int = 0
            self.jobs_completed_total: int = 0
            self.jobs_failed_total: int = 0
            self.jobs_retried_total: int = 0
            self.jobs_cancelled_total: int = 0
            self.events_published_total: int = 0
            self.events_consumed_total: int = 0

            # Phase 24 Data Privacy & Governance telemetry
            self.privacy_policy_evaluations_total: int = 0
            self.privacy_policy_denials_total: int = 0
            self.data_export_requests_total: int = 0
            self.data_export_completed_total: int = 0
            self.data_export_failed_total: int = 0
            self.retention_evaluations_total: int = 0
            self.retention_archives_total: int = 0
            self.retention_deletions_total: int = 0
            self.deidentification_operations_total: int = 0
            self.pseudonymization_operations_total: int = 0

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
    # Disaster Recovery & Business Continuity Telemetry (Phase 19)
    # -------------------------------------------------------------------------

    def record_recovery_attempt(self, subsystem: str = "general") -> None:
        """Record initiation of a disaster recovery or rollback procedure."""
        clean_subsystem = subsystem.lower().strip()
        with self._lock:
            self.recovery_attempts_total[clean_subsystem] += 1

    def record_recovery_result(
        self,
        subsystem: str = "general",
        success: bool = True,
        duration_seconds: float = 0.0,
    ) -> None:
        """Record completion of a disaster recovery procedure."""
        clean_subsystem = subsystem.lower().strip()
        with self._lock:
            if success:
                self.recovery_success_total[clean_subsystem] += 1
            else:
                self.recovery_failure_total[clean_subsystem] += 1
            if duration_seconds > 0:
                self.recovery_duration_seconds[clean_subsystem] = round(duration_seconds, 3)

    def record_database_restore(self, duration_seconds: float) -> None:
        """Record database restoration execution duration."""
        with self._lock:
            self.database_restore_duration_seconds = round(duration_seconds, 3)

    def record_deployment_rollback(self) -> None:
        """Record application deployment rollback event."""
        with self._lock:
            self.deployment_rollback_total += 1

    def record_provider_recovery(self, provider: str) -> None:
        """Record successful external provider recovery and probe validation."""
        clean_provider = provider.lower().strip()
        with self._lock:
            self.provider_recovery_total[clean_provider] += 1

    # -------------------------------------------------------------------------
    # Generic Counter Increment Helper
    # -------------------------------------------------------------------------

    def increment(self, name: str, count: int = 1) -> None:
        """Increment a registered integer counter metric."""
        with self._lock:
            if hasattr(self, name):
                setattr(self, name, getattr(self, name) + count)

    def record_privacy_evaluation(self, allowed: bool) -> None:
        """Record privacy access evaluation and optional denial."""
        with self._lock:
            self.privacy_policy_evaluations_total += 1
            if not allowed:
                self.privacy_policy_denials_total += 1

    def record_data_export(self, status: str) -> None:
        """Record data export request and terminal state."""
        with self._lock:
            self.data_export_requests_total += 1
            if status in ("COMPLETED", "READY"):
                self.data_export_completed_total += 1
            elif status == "FAILED":
                self.data_export_failed_total += 1

    def record_retention_action(self, action: str) -> None:
        """Record retention archival or deletion action."""
        with self._lock:
            self.retention_evaluations_total += 1
            if action == "ARCHIVE":
                self.retention_archives_total += 1
            elif action == "DELETE":
                self.retention_deletions_total += 1

    def record_deidentification(self) -> None:
        """Record batch de-identification operation."""
        with self._lock:
            self.deidentification_operations_total += 1

    def record_pseudonymization(self) -> None:
        """Record cryptographic pseudonymization operation."""
        with self._lock:
            self.pseudonymization_operations_total += 1

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
                "disaster_recovery": {
                    "recovery_attempts_total": sum(self.recovery_attempts_total.values()),
                    "recovery_success_total": sum(self.recovery_success_total.values()),
                    "recovery_failure_total": sum(self.recovery_failure_total.values()),
                    "recovery_duration_seconds": dict(self.recovery_duration_seconds),
                    "database_restore_duration_seconds": self.database_restore_duration_seconds,
                    "deployment_rollback_total": self.deployment_rollback_total,
                    "provider_recovery_total": dict(self.provider_recovery_total),
                },
                "scalability": {
                    "load_shedding_rejected_total": self.load_shedding_rejected_total,
                    "circuit_breaker_trips": dict(self.circuit_breaker_trips_total),
                    "cache_hits": dict(self.cache_hits_total),
                    "cache_misses": dict(self.cache_misses_total),
                },
                "async_workflows": {
                    "jobs_created": self.jobs_created_total,
                    "jobs_queued": self.jobs_queued_total,
                    "jobs_completed": self.jobs_completed_total,
                    "jobs_failed": self.jobs_failed_total,
                    "jobs_retried": self.jobs_retried_total,
                    "jobs_cancelled": self.jobs_cancelled_total,
                    "events_published": self.events_published_total,
                    "events_consumed": self.events_consumed_total,
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

            # Disaster Recovery & Business Continuity (Phase 19)
            lines.extend([
                "# HELP recovery_attempts_total Total disaster recovery attempts initiated",
                "# TYPE recovery_attempts_total counter",
            ])
            for sub, count in sorted(self.recovery_attempts_total.items()):
                lines.append(f'recovery_attempts_total{{subsystem="{sub}"}} {count}')

            lines.extend([
                "# HELP recovery_success_total Total successful disaster recovery procedures",
                "# TYPE recovery_success_total counter",
            ])
            for sub, count in sorted(self.recovery_success_total.items()):
                lines.append(f'recovery_success_total{{subsystem="{sub}"}} {count}')

            lines.extend([
                "# HELP recovery_failure_total Total failed disaster recovery procedures",
                "# TYPE recovery_failure_total counter",
            ])
            for sub, count in sorted(self.recovery_failure_total.items()):
                lines.append(f'recovery_failure_total{{subsystem="{sub}"}} {count}')

            lines.extend([
                "# HELP recovery_duration_seconds Most recent disaster recovery duration in seconds",
                "# TYPE recovery_duration_seconds gauge",
            ])
            for sub, dur in sorted(self.recovery_duration_seconds.items()):
                lines.append(f'recovery_duration_seconds{{subsystem="{sub}"}} {dur}')

            lines.extend([
                "# HELP database_restore_duration_seconds Most recent database restore duration in seconds",
                "# TYPE database_restore_duration_seconds gauge",
                f"database_restore_duration_seconds {self.database_restore_duration_seconds}",
                "# HELP deployment_rollback_total Total deployment rollback actions executed",
                "# TYPE deployment_rollback_total counter",
                f"deployment_rollback_total {self.deployment_rollback_total}",
            ])

            lines.extend([
                "# HELP provider_recovery_total Total external provider recovery validations",
                "# TYPE provider_recovery_total counter",
            ])
            for prov, count in sorted(self.provider_recovery_total.items()):
                lines.append(f'provider_recovery_total{{provider="{prov}"}} {count}')

            # Phase 22 Async Jobs & Events
            lines.extend([
                f"# HELP jobs_created_total Total asynchronous jobs created",
                f"# TYPE jobs_created_total counter",
                f"jobs_created_total {self.jobs_created_total}",
                f"# HELP jobs_completed_total Total asynchronous jobs completed successfully",
                f"# TYPE jobs_completed_total counter",
                f"jobs_completed_total {self.jobs_completed_total}",
                f"# HELP jobs_failed_total Total asynchronous jobs failed permanently",
                f"# TYPE jobs_failed_total counter",
                f"jobs_failed_total {self.jobs_failed_total}",
                f"# HELP jobs_retried_total Total asynchronous jobs scheduled for retry",
                f"# TYPE jobs_retried_total counter",
                f"jobs_retried_total {self.jobs_retried_total}",
                f"# HELP jobs_cancelled_total Total asynchronous jobs cancelled",
                f"# TYPE jobs_cancelled_total counter",
                f"jobs_cancelled_total {self.jobs_cancelled_total}",
                f"# HELP events_published_total Total domain events published",
                f"# TYPE events_published_total counter",
                f"events_published_total {self.events_published_total}",
                f"# HELP events_consumed_total Total domain events consumed",
                f"# TYPE events_consumed_total counter",
                f"events_consumed_total {self.events_consumed_total}",

                # Phase 24 Data Privacy & Governance
                f"# HELP privacy_policy_evaluations_total Total privacy policy access evaluations",
                f"# TYPE privacy_policy_evaluations_total counter",
                f"privacy_policy_evaluations_total {self.privacy_policy_evaluations_total}",
                f"# HELP privacy_policy_denials_total Total access denials under privacy and data governance",
                f"# TYPE privacy_policy_denials_total counter",
                f"privacy_policy_denials_total {self.privacy_policy_denials_total}",
                f"# HELP data_export_requests_total Total patient data export requests initiated",
                f"# TYPE data_export_requests_total counter",
                f"data_export_requests_total {self.data_export_requests_total}",
                f"# HELP data_export_completed_total Total patient data exports successfully generated",
                f"# TYPE data_export_completed_total counter",
                f"data_export_completed_total {self.data_export_completed_total}",
                f"# HELP data_export_failed_total Total patient data export failures",
                f"# TYPE data_export_failed_total counter",
                f"data_export_failed_total {self.data_export_failed_total}",
                f"# HELP retention_evaluations_total Total retention policy evaluations executed",
                f"# TYPE retention_evaluations_total counter",
                f"retention_evaluations_total {self.retention_evaluations_total}",
                f"# HELP retention_archives_total Total resources transitioned to archived state",
                f"# TYPE retention_archives_total counter",
                f"retention_archives_total {self.retention_archives_total}",
                f"# HELP retention_deletions_total Total resources safely deleted under approved policy",
                f"# TYPE retention_deletions_total counter",
                f"retention_deletions_total {self.retention_deletions_total}",
                f"# HELP deidentification_operations_total Total non-production de-identification batches executed",
                f"# TYPE deidentification_operations_total counter",
                f"deidentification_operations_total {self.deidentification_operations_total}",
                f"# HELP pseudonymization_operations_total Total cryptographic pseudonymization operations executed",
                f"# TYPE pseudonymization_operations_total counter",
                f"pseudonymization_operations_total {self.pseudonymization_operations_total}",
            ])

            return "\n".join(lines) + "\n"


# Global singleton collector
metrics = MetricsCollector()


# ---------------------------------------------------------------------------
# Phase 25 Metric Counters (Prometheus-style .labels(...).inc())
# ---------------------------------------------------------------------------

class MetricCounter:
    """Lightweight thread-safe metric counter supporting Prometheus-style labels(...).inc()."""

    def __init__(self, name: str, description: str, label_names: tuple[str, ...] = ()) -> None:
        self.name = name
        self.description = description
        self.label_names = label_names
        self._counts: dict[tuple[str, ...], int] = defaultdict(int)
        self._lock = threading.Lock()

    def labels(self, **kwargs: str) -> _BoundMetricCounter:
        key = tuple(str(kwargs.get(k, "")) for k in self.label_names)
        return _BoundMetricCounter(self, key)

    def inc(self, amount: int = 1) -> None:
        with self._lock:
            self._counts[()] += amount

    def get(self, **kwargs: str) -> int:
        key = tuple(str(kwargs.get(k, "")) for k in self.label_names)
        with self._lock:
            return self._counts.get(key, 0)

    @property
    def total(self) -> int:
        with self._lock:
            return sum(self._counts.values())


class _BoundMetricCounter:
    def __init__(self, parent: MetricCounter, key: tuple[str, ...]) -> None:
        self._parent = parent
        self._key = key

    def inc(self, amount: int = 1) -> None:
        with self._parent._lock:
            self._parent._counts[self._key] += amount


FEATURE_FLAG_EVALUATIONS_COUNTER = MetricCounter(
    "healthsetu_feature_flag_evaluations_total", "Total feature flag evaluations", ("flag_name",)
)
FEATURE_FLAG_ENABLED_COUNTER = MetricCounter(
    "healthsetu_feature_flag_enabled_total", "Total evaluations returning enabled", ("flag_name",)
)
FEATURE_FLAG_DISABLED_COUNTER = MetricCounter(
    "healthsetu_feature_flag_disabled_total", "Total evaluations returning disabled", ("flag_name",)
)
FEATURE_FLAG_EVALUATION_ERRORS_COUNTER = MetricCounter(
    "healthsetu_feature_flag_evaluation_errors_total", "Total feature evaluation errors", ("flag_name",)
)
KILL_SWITCH_ACTIVATIONS_COUNTER = MetricCounter(
    "healthsetu_kill_switch_activations_total", "Total operational kill switch state changes", ("switch_name",)
)
CONFIGURATION_VALIDATION_FAILURES_COUNTER = MetricCounter(
    "healthsetu_configuration_validation_failures_total", "Total configuration validation failures", ("environment", "severity")
)
CONFIGURATION_DRIFT_COUNTER = MetricCounter(
    "healthsetu_configuration_drift_detected_total", "Total configuration drift events detected", ("environment",)
)
CONFIGURATION_CACHE_REFRESHES_COUNTER = MetricCounter(
    "healthsetu_configuration_cache_refreshes_total", "Total configuration cache invalidations or refreshes", ()
)
PROVIDER_CONFIGURATION_ERRORS_COUNTER = MetricCounter(
    "healthsetu_provider_configuration_errors_total", "Total provider configuration errors", ("provider_name",)
)

# ---------------------------------------------------------------------------
# Phase 26: Data Quality & Reconciliation metrics
# ---------------------------------------------------------------------------
DATA_QUALITY_CHECKS_COUNTER = MetricCounter(
    "healthsetu_data_quality_checks_total", "Total data quality checks executed", ("status",)
)
DATA_QUALITY_FINDINGS_CREATED_COUNTER = MetricCounter(
    "healthsetu_data_quality_findings_created_total", "Total data quality findings created", ("finding_type", "severity")
)
DATA_QUALITY_FINDINGS_RESOLVED_COUNTER = MetricCounter(
    "healthsetu_data_quality_findings_resolved_total", "Total data quality findings resolved", ("action",)
)
DUPLICATE_DETECTIONS_COUNTER = MetricCounter(
    "healthsetu_duplicate_detections_total", "Total duplicates detected", ("resource_type",)
)
CONFLICT_DETECTIONS_COUNTER = MetricCounter(
    "healthsetu_conflict_detections_total", "Total clinical conflicts detected", ("concept_type",)
)
RECONCILIATION_OPERATIONS_COUNTER = MetricCounter(
    "healthsetu_reconciliation_operations_total", "Total clinical reconciliation operations", ("scope", "status")
)

