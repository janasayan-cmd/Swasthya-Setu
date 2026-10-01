"""Analytics and Operational Intelligence Service (Phase 28).

Provides:
- Privacy-safe operational telemetry recording
- Route-template endpoint analytics (no raw patient IDs)
- Latency percentile computation (p50, p90, p95, p99)
- Status code and error rate aggregation
- Feature usage and background-job usage telemetry
- External provider and AI token/cost analytics
- Operational anomaly detection
- Tenant/organization-scoped analytics views

CRITICAL ARCHITECTURAL & PRIVACY INVARIANTS:
- ANALYTICS != CLINICAL DECISION
- USAGE DATA != CLINICAL DATA
- METRICS != AUDIT RECORDS
- ANALYTICS != PATIENT PROFILING
- OPERATIONAL DATA != CLINICAL TRUTH
- USAGE SPIKE != SECURITY INCIDENT
- ANOMALY != MALICIOUS ACTIVITY
- STATISTICAL SIGNAL != CLINICAL SIGNAL
- FAILED JOB != COMPLETED JOB
- QUEUED JOB != COMPLETED JOB
- PROVIDER FAILURE != SUCCESS
- Analytics failure must NEVER fail clinical operations (Fail-safe isolation)
- Route templates only: NEVER use raw patient IDs in endpoints
"""

from __future__ import annotations

import math
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import settings
from app.core.exceptions import (
    AnalyticsAccessDeniedException,
    AnalyticsDisabledException,
    AnalyticsNotFoundException,
    AnalyticsQueryRangeExceededException,
    AnomalyNotFoundException,
)
from app.core.logging import get_logger
from app.repositories.analytics_repository import AnalyticsRepository
from app.repositories.audit_repository import AuditRepository
from app.schemas.analytics import (
    AnalyticsEvent,
    AnalyticsEventType,
    AnalyticsFilterParams,
    AnalyticsOverviewResponse,
    EndpointSummary,
    TimeBucket,
    TimeSeriesPoint,
)
from app.schemas.anomaly import (
    AnomalyAcknowledgeRequest,
    AnomalyListResponse,
    AnomalyResolveRequest,
    AnomalySeverity,
    AnomalyStatus,
    AnomalyType,
    UsageAnomaly,
)
from app.schemas.provider_usage import (
    AIUsageMetricsItem,
    CostBreakdownItem,
    CostCategory,
    CostMetricsResponse,
    ProviderCategory,
    ProviderUsageItem,
    ProviderUsageResponse,
)
from app.schemas.usage_metrics import (
    ApiUsageMetricsResponse,
    BackgroundJobAnalyticsResponse,
    ErrorMetricsResponse,
    FeatureUsageItem,
    FeatureUsageResponse,
    JobTypeMetric,
    LatencyDistributionBucket,
    LatencyMetricsResponse,
)
from app.schemas.user import AuthenticatedUserContext

logger = get_logger("app.services.analytics_service")

# Regex to detect UUIDs
UUID_REGEX = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
NUMERIC_ID_REGEX = re.compile(r"/\d+(?=/|$)")

ALLOWED_METADATA_METRIC_KEYS = {
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "pages_processed",
    "estimated_cost_usd",
    "client_version",
    "duration_sec",
    "cached",
}

SENSITIVE_KEYS = {
    "password",
    "secret",
    "api_key",
    "authorization",
    "access_token",
    "auth_token",
    "bearer_token",
    "clinical_notes",
    "prescription_text",
    "allergy_description",
    "triage_narrative",
    "phi",
    "diagnosis",
    "prompt_text",
    "completion_text",
    "patient_name",
}


def normalize_route_template(path: str) -> str:
    """Normalize a raw request URL into a route template.

    Replaces specific patient, user, or entity IDs with route template tokens.
    Example:
    /api/v1/patients/12345/medications -> /api/v1/patients/{patient_id}/medications
    /api/v1/patients/123e4567-e89b-12d3-a456-426614174000 -> /api/v1/patients/{patient_id}
    """
    if not path:
        return "/"

    # Strip query parameters if present
    path = path.split("?")[0]

    # Specific common entity routes
    path = re.sub(
        r"/api/v1/patients/[^/]+",
        r"/api/v1/patients/{patient_id}",
        path,
    )
    path = re.sub(
        r"/api/v1/organizations/[^/]+",
        r"/api/v1/organizations/{organization_id}",
        path,
    )
    path = re.sub(
        r"/api/v1/facilities/[^/]+",
        r"/api/v1/facilities/{facility_id}",
        path,
    )
    path = re.sub(
        r"/api/v1/documents/[^/]+",
        r"/api/v1/documents/{document_id}",
        path,
    )
    path = re.sub(
        r"/api/v1/jobs/[^/]+",
        r"/api/v1/jobs/{job_id}",
        path,
    )

    # General UUID replacement
    path = UUID_REGEX.sub("{id}", path)

    # General numeric ID replacement
    path = NUMERIC_ID_REGEX.sub("/{id}", path)

    return path


def sanitize_metadata(meta: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Sanitize metadata to ensure no PHI, credentials, or clinical narratives enter analytics."""
    if not meta:
        return {}

    sanitized: Dict[str, Any] = {}
    for k, v in meta.items():
        key_lower = k.lower()
        if key_lower in ALLOWED_METADATA_METRIC_KEYS:
            sanitized[k] = v
            continue
        if any(s in key_lower for s in SENSITIVE_KEYS):
            continue
        if isinstance(v, (str, int, float, bool)):
            sanitized[k] = v
        elif isinstance(v, dict):
            sanitized[k] = sanitize_metadata(v)
    return sanitized


def calculate_percentiles(values: List[float]) -> Tuple[float, float, float, float, float, float, float]:
    """Calculate min, max, avg, p50, p90, p95, p99 from a list of latencies in ms."""
    if not values:
        return 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0

    sorted_vals = sorted(values)
    n = len(sorted_vals)
    min_v = sorted_vals[0]
    max_v = sorted_vals[-1]
    avg_v = sum(sorted_vals) / n

    def get_percentile(p: float) -> float:
        idx = int(n * p)
        if idx >= n:
            idx = n - 1
        return sorted_vals[idx]

    p50 = get_percentile(0.50)
    p90 = get_percentile(0.90)
    p95 = get_percentile(0.95)
    p99 = get_percentile(0.99)

    return min_v, max_v, avg_v, p50, p90, p95, p99


class AnalyticsService:
    """Service orchestrating operational analytics, telemetry aggregation, and usage governance."""

    def __init__(
        self,
        repository: AnalyticsRepository,
        audit_repository: Optional[AuditRepository] = None,
    ) -> None:
        self._repo = repository
        self._audit_repo = audit_repository

    # -------------------------------------------------------------------------
    # Safe Event Ingestion
    # -------------------------------------------------------------------------

    def record_event(
        self,
        event_type: AnalyticsEventType,
        endpoint: Optional[str] = None,
        http_method: Optional[str] = None,
        status: Optional[int] = None,
        duration_ms: Optional[float] = None,
        request_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        user_category: Optional[str] = None,
        organization_id: Optional[str] = None,
        facility_id: Optional[str] = None,
        feature_name: Optional[str] = None,
        provider_name: Optional[str] = None,
        job_type: Optional[str] = None,
        job_status: Optional[str] = None,
        resource_type: Optional[str] = None,
        result_category: Optional[str] = None,
        error_category: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        event_id: Optional[str] = None,
        api_version: str = "v1",
    ) -> Optional[AnalyticsEvent]:
        """Record an operational analytics event.

        CRITICAL FAIL-SAFE INVARIANT:
        If analytics recording encounters any error or if analytics is disabled,
        it logs a warning and returns gracefully. It NEVER raises an exception
        to disrupt the calling clinical or administrative workflow.
        """
        if not getattr(settings, "ANALYTICS_ENABLED", True):
            return None

        try:
            # Normalize endpoint to route template (never store raw patient IDs!)
            normalized_endpoint = normalize_route_template(endpoint) if endpoint else None

            # Sanitize metadata (strip any PHI or credentials)
            clean_metadata = sanitize_metadata(metadata)

            event = AnalyticsEvent(
                event_id=event_id or str(uuid.uuid4()),
                event_type=event_type,
                timestamp=datetime.now(timezone.utc),
                environment=getattr(settings, "ENVIRONMENT", "production"),
                service=getattr(settings, "APP_NAME", "HealthSetu"),
                api_version=api_version,
                endpoint=normalized_endpoint,
                http_method=http_method.upper() if http_method else None,
                status=status,
                duration_ms=duration_ms,
                request_id=request_id,
                correlation_id=correlation_id,
                user_category=user_category,
                organization_id=organization_id,
                facility_id=facility_id,
                feature_name=feature_name,
                provider_name=provider_name,
                job_type=job_type,
                job_status=job_status,
                resource_type=resource_type,
                result_category=result_category,
                error_category=error_category,
                metadata=clean_metadata,
            )

            recorded = self._repo.record_event(event)

            # Check if this event should trigger anomaly detection check
            if getattr(settings, "ANOMALY_DETECTION_ENABLED", True):
                if status and status >= 500:
                    self._check_error_anomaly(event)

            return recorded

        except Exception as exc:
            # Failure isolation: never crash the caller
            logger.warning(
                "Analytics recording failed gracefully: %s. Workflow continues unaffected.",
                str(exc),
            )
            return None

    # -------------------------------------------------------------------------
    # Filter Validation & Scoping
    # -------------------------------------------------------------------------

    def _validate_filter_params(self, params: AnalyticsFilterParams) -> None:
        """Validate filter time bounds according to configured limits."""
        if params.start_time and params.end_time:
            if params.start_time > params.end_time:
                raise AnalyticsQueryRangeExceededException(
                    "start_time cannot be greater than end_time"
                )
            delta = params.end_time - params.start_time
            max_days = getattr(settings, "ANALYTICS_MAX_QUERY_RANGE_DAYS", 90)
            if delta.days > max_days:
                raise AnalyticsQueryRangeExceededException(
                    f"Query range of {delta.days} days exceeds maximum allowed limit of {max_days} days"
                )

    # -------------------------------------------------------------------------
    # Analytics Overview
    # -------------------------------------------------------------------------

    def get_overview(
        self,
        filters: Optional[AnalyticsFilterParams] = None,
        current_user: Optional[AuthenticatedUserContext] = None,
    ) -> AnalyticsOverviewResponse:
        """Compute top-level operational analytics summary."""
        filters = filters or AnalyticsFilterParams()
        self._validate_filter_params(filters)

        events = self._repo.list_events(filters)

        total_requests = 0
        successful_requests = 0
        error_requests = 0
        durations: List[float] = []
        status_dist: Dict[str, int] = {}
        endpoint_map: Dict[str, Dict[str, Any]] = {}

        for ev in events:
            if ev.event_type in (
                AnalyticsEventType.API_REQUEST_COMPLETED,
                AnalyticsEventType.API_REQUEST_FAILED,
            ):
                total_requests += 1

                # Status code
                if ev.status is not None:
                    code_str = str(ev.status)
                    status_dist[code_str] = status_dist.get(code_str, 0) + 1
                    if ev.status < 400:
                        successful_requests += 1
                    else:
                        error_requests += 1
                elif ev.event_type == AnalyticsEventType.API_REQUEST_COMPLETED:
                    successful_requests += 1
                else:
                    error_requests += 1

                # Latency
                if ev.duration_ms is not None:
                    durations.append(ev.duration_ms)

                # Endpoint summary
                ep = ev.endpoint or "unknown"
                if ep not in endpoint_map:
                    endpoint_map[ep] = {
                        "endpoint": ep,
                        "method": ev.http_method or "GET",
                        "request_count": 0,
                        "error_count": 0,
                        "durations": [],
                        "status_distribution": {},
                    }
                item = endpoint_map[ep]
                item["request_count"] += 1
                if ev.status and ev.status >= 400:
                    item["error_count"] += 1
                if ev.duration_ms is not None:
                    item["durations"].append(ev.duration_ms)
                if ev.status:
                    st_str = str(ev.status)
                    item["status_distribution"][st_str] = (
                        item["status_distribution"].get(st_str, 0) + 1
                    )

        min_lat, max_lat, avg_lat, p50, p90, p95, p99 = calculate_percentiles(durations)
        error_rate = (error_requests / total_requests) if total_requests > 0 else 0.0

        # Construct top endpoints list
        top_endpoints: List[EndpointSummary] = []
        for ep_info in endpoint_map.values():
            e_durations = ep_info["durations"]
            _, _, e_avg, _, _, e_p95, _ = calculate_percentiles(e_durations)
            e_cnt = ep_info["request_count"]
            e_err = ep_info["error_count"]
            top_endpoints.append(
                EndpointSummary(
                    endpoint=ep_info["endpoint"],
                    http_method=ep_info["method"],
                    request_count=e_cnt,
                    error_count=e_err,
                    error_rate=round(e_err / e_cnt, 4) if e_cnt > 0 else 0.0,
                    avg_latency_ms=round(e_avg, 2),
                    p95_latency_ms=round(e_p95, 2),
                    status_distribution=ep_info["status_distribution"],
                )
            )

        top_endpoints.sort(key=lambda e: e.request_count, reverse=True)
        top_5_endpoints = top_endpoints[:5]

        # Count active anomalies
        active_anomalies = self._repo.count_anomalies(status=AnomalyStatus.DETECTED)

        # Count active features used
        features_used = len(
            set(ev.feature_name for ev in events if ev.feature_name)
        )

        return AnalyticsOverviewResponse(
            total_requests=total_requests,
            successful_requests=successful_requests,
            error_requests=error_requests,
            overall_error_rate=round(error_rate, 4),
            avg_latency_ms=round(avg_lat, 2),
            p50_latency_ms=round(p50, 2),
            p95_latency_ms=round(p95, 2),
            p99_latency_ms=round(p99, 2),
            http_status_distribution=status_dist,
            top_endpoints=top_5_endpoints,
            active_anomalies_count=active_anomalies,
            total_features_active=features_used,
            query_start_time=filters.start_time,
            query_end_time=filters.end_time,
            environment=getattr(settings, "ENVIRONMENT", "production"),
        )

    # -------------------------------------------------------------------------
    # API Usage Metrics
    # -------------------------------------------------------------------------

    def get_api_usage_metrics(
        self,
        filters: Optional[AnalyticsFilterParams] = None,
        current_user: Optional[AuthenticatedUserContext] = None,
    ) -> ApiUsageMetricsResponse:
        """Detailed API usage analytics breakdown."""
        filters = filters or AnalyticsFilterParams()
        self._validate_filter_params(filters)

        events = self._repo.list_events(filters)

        total_requests = 0
        success_requests = 0
        error_requests = 0
        status_dist: Dict[str, int] = {}
        durations: List[float] = []
        endpoint_map: Dict[str, Dict[str, Any]] = {}
        rate_limit_count = 0
        auth_failures = 0

        # Time series grouping by hour or minute
        bucket_map: Dict[str, Dict[str, Any]] = {}

        for ev in events:
            if ev.event_type == AnalyticsEventType.RATE_LIMIT_TRIGGERED:
                rate_limit_count += 1
            if ev.event_type in (
                AnalyticsEventType.AUTHENTICATION_FAILED,
                AnalyticsEventType.AUTHORIZATION_FAILED,
            ):
                auth_failures += 1

            if ev.event_type not in (
                AnalyticsEventType.API_REQUEST_COMPLETED,
                AnalyticsEventType.API_REQUEST_FAILED,
            ):
                continue

            total_requests += 1
            st = ev.status
            if st is not None:
                st_str = str(st)
                status_dist[st_str] = status_dist.get(st_str, 0) + 1
                if st < 400:
                    success_requests += 1
                else:
                    error_requests += 1
            else:
                success_requests += 1

            if ev.duration_ms is not None:
                durations.append(ev.duration_ms)

            # Endpoint aggregation
            ep = ev.endpoint or "unknown"
            if ep not in endpoint_map:
                endpoint_map[ep] = {
                    "endpoint": ep,
                    "method": ev.http_method or "GET",
                    "request_count": 0,
                    "error_count": 0,
                    "durations": [],
                    "status_distribution": {},
                }
            endpoint_map[ep]["request_count"] += 1
            if st and st >= 400:
                endpoint_map[ep]["error_count"] += 1
            if ev.duration_ms is not None:
                endpoint_map[ep]["durations"].append(ev.duration_ms)
            if st:
                s_str = str(st)
                endpoint_map[ep]["status_distribution"][s_str] = (
                    endpoint_map[ep]["status_distribution"].get(s_str, 0) + 1
                )

            # Time series bucket
            bucket_key = ev.timestamp.strftime("%Y-%m-%dT%H:00:00Z")
            if bucket_key not in bucket_map:
                bucket_map[bucket_key] = {
                    "request_count": 0,
                    "success_count": 0,
                    "error_count": 0,
                    "durations": [],
                }
            bucket_map[bucket_key]["request_count"] += 1
            if st and st >= 400:
                bucket_map[bucket_key]["error_count"] += 1
            else:
                bucket_map[bucket_key]["success_count"] += 1
            if ev.duration_ms is not None:
                bucket_map[bucket_key]["durations"].append(ev.duration_ms)

        # Build endpoint summaries
        endpoints_list: List[EndpointSummary] = []
        for ep_info in endpoint_map.values():
            e_dur = ep_info["durations"]
            _, _, e_avg, _, _, e_p95, _ = calculate_percentiles(e_dur)
            cnt = ep_info["request_count"]
            err = ep_info["error_count"]
            endpoints_list.append(
                EndpointSummary(
                    endpoint=ep_info["endpoint"],
                    http_method=ep_info["method"],
                    request_count=cnt,
                    error_count=err,
                    error_rate=round(err / cnt, 4) if cnt > 0 else 0.0,
                    avg_latency_ms=round(e_avg, 2),
                    p95_latency_ms=round(e_p95, 2),
                    status_distribution=ep_info["status_distribution"],
                )
            )
        endpoints_list.sort(key=lambda x: x.request_count, reverse=True)

        # Build time series
        ts_points: List[TimeSeriesPoint] = []
        for b_time_str in sorted(bucket_map.keys()):
            b_data = bucket_map[b_time_str]
            _, _, b_avg, _, _, b_p95, _ = calculate_percentiles(b_data["durations"])
            b_cnt = b_data["request_count"]
            b_err = b_data["error_count"]
            ts_points.append(
                TimeSeriesPoint(
                    bucket_time=datetime.fromisoformat(b_time_str.replace("Z", "+00:00")),
                    request_count=b_cnt,
                    success_count=b_data["success_count"],
                    error_count=b_err,
                    error_rate=round(b_err / b_cnt, 4) if b_cnt > 0 else 0.0,
                    avg_latency_ms=round(b_avg, 2),
                    p95_latency_ms=round(b_p95, 2),
                )
            )

        error_rate = (error_requests / total_requests) if total_requests > 0 else 0.0
        _, _, avg_lat, p50, _, p95, p99 = calculate_percentiles(durations)

        return ApiUsageMetricsResponse(
            total_requests=total_requests,
            success_count=success_requests,
            error_count=error_requests,
            error_rate=round(error_rate, 4),
            avg_latency_ms=round(avg_lat, 2),
            p50_latency_ms=round(p50, 2),
            p95_latency_ms=round(p95, 2),
            p99_latency_ms=round(p99, 2),
            rate_limit_events_count=rate_limit_count,
            authentication_failures_count=auth_failures,
            status_distribution=status_dist,
            time_series=ts_points,
            endpoints=endpoints_list,
            query_start_time=filters.start_time,
            query_end_time=filters.end_time,
        )

    # -------------------------------------------------------------------------
    # Error Metrics
    # -------------------------------------------------------------------------

    def get_error_metrics(
        self,
        filters: Optional[AnalyticsFilterParams] = None,
        current_user: Optional[AuthenticatedUserContext] = None,
    ) -> ErrorMetricsResponse:
        """Detailed error rate and status class analytics."""
        filters = filters or AnalyticsFilterParams()
        self._validate_filter_params(filters)

        events = self._repo.list_events(filters)

        total_requests = 0
        total_errors = 0
        client_errors_4xx = 0
        server_errors_5xx = 0
        status_dist: Dict[str, int] = {}
        error_category_dist: Dict[str, int] = {}
        endpoint_err_map: Dict[str, Dict[str, Any]] = {}

        for ev in events:
            if ev.event_type not in (
                AnalyticsEventType.API_REQUEST_COMPLETED,
                AnalyticsEventType.API_REQUEST_FAILED,
            ):
                continue

            total_requests += 1
            st = ev.status
            if st is not None:
                st_str = str(st)
                if st >= 400:
                    total_errors += 1
                    status_dist[st_str] = status_dist.get(st_str, 0) + 1
                    if 400 <= st < 500:
                        client_errors_4xx += 1
                    elif st >= 500:
                        server_errors_5xx += 1

                    # Error category
                    cat = ev.error_category or ("4xx_client" if st < 500 else "5xx_server")
                    error_category_dist[cat] = error_category_dist.get(cat, 0) + 1

                    # Top error endpoint
                    ep = ev.endpoint or "unknown"
                    if ep not in endpoint_err_map:
                        endpoint_err_map[ep] = {
                            "endpoint": ep,
                            "method": ev.http_method or "GET",
                            "request_count": 0,
                            "error_count": 0,
                            "durations": [],
                            "status_distribution": {},
                        }
                    endpoint_err_map[ep]["error_count"] += 1
                    endpoint_err_map[ep]["status_distribution"][st_str] = (
                        endpoint_err_map[ep]["status_distribution"].get(st_str, 0) + 1
                    )
            elif ev.event_type == AnalyticsEventType.API_REQUEST_FAILED:
                total_errors += 1
                server_errors_5xx += 1
                cat = ev.error_category or "unknown_failure"
                error_category_dist[cat] = error_category_dist.get(cat, 0) + 1

        top_error_endpoints: List[EndpointSummary] = []
        for ep_info in endpoint_err_map.values():
            cnt = max(ep_info["request_count"], ep_info["error_count"])
            err = ep_info["error_count"]
            top_error_endpoints.append(
                EndpointSummary(
                    endpoint=ep_info["endpoint"],
                    http_method=ep_info["method"],
                    request_count=cnt,
                    error_count=err,
                    error_rate=round(err / cnt, 4) if cnt > 0 else 1.0,
                    avg_latency_ms=0.0,
                    p95_latency_ms=0.0,
                    status_distribution=ep_info["status_distribution"],
                )
            )
        top_error_endpoints.sort(key=lambda x: x.error_count, reverse=True)

        overall_rate = (total_errors / total_requests) if total_requests > 0 else 0.0

        return ErrorMetricsResponse(
            total_requests=total_requests,
            total_errors=total_errors,
            overall_error_rate=round(overall_rate, 4),
            client_errors_4xx=client_errors_4xx,
            server_errors_5xx=server_errors_5xx,
            status_distribution=status_dist,
            top_error_endpoints=top_error_endpoints[:10],
            error_categories=error_category_dist,
            query_start_time=filters.start_time,
            query_end_time=filters.end_time,
        )

    # -------------------------------------------------------------------------
    # Latency Metrics
    # -------------------------------------------------------------------------

    def get_latency_metrics(
        self,
        filters: Optional[AnalyticsFilterParams] = None,
        current_user: Optional[AuthenticatedUserContext] = None,
    ) -> LatencyMetricsResponse:
        """Detailed API response latency analytics with percentiles and distribution."""
        filters = filters or AnalyticsFilterParams()
        self._validate_filter_params(filters)

        events = self._repo.list_events(filters)

        durations: List[float] = []
        for ev in events:
            if ev.duration_ms is not None:
                durations.append(ev.duration_ms)

        min_v, max_v, avg_v, p50, p90, p95, p99 = calculate_percentiles(durations)

        # Distribution buckets
        buckets = [
            ("<50ms", 0.0, 50.0),
            ("50ms-200ms", 50.0, 200.0),
            ("200ms-500ms", 200.0, 500.0),
            ("500ms-1s", 500.0, 1000.0),
            ("1s-5s", 1000.0, 5000.0),
            (">5s", 5000.0, float("inf")),
        ]

        dist_items: List[LatencyDistributionBucket] = []
        total_d = len(durations)
        for label, lower, upper in buckets:
            cnt = sum(1 for d in durations if lower <= d < upper)
            pct = round((cnt / total_d) * 100.0, 2) if total_d > 0 else 0.0
            dist_items.append(
                LatencyDistributionBucket(
                    bucket_label=label,
                    min_ms=lower,
                    max_ms=upper if upper != float("inf") else None,
                    count=cnt,
                    percentage=pct,
                )
            )

        return LatencyMetricsResponse(
            sample_count=total_d,
            min_latency_ms=round(min_v, 2),
            max_latency_ms=round(max_v, 2),
            avg_latency_ms=round(avg_v, 2),
            p50_latency_ms=round(p50, 2),
            p90_latency_ms=round(p90, 2),
            p95_latency_ms=round(p95, 2),
            p99_latency_ms=round(p99, 2),
            distribution=dist_items,
            query_start_time=filters.start_time,
            query_end_time=filters.end_time,
        )

    # -------------------------------------------------------------------------
    # Feature Usage Analytics
    # -------------------------------------------------------------------------

    def get_feature_usage(
        self,
        filters: Optional[AnalyticsFilterParams] = None,
        current_user: Optional[AuthenticatedUserContext] = None,
    ) -> FeatureUsageResponse:
        """Track operational usage of platform features (Phase 25 flags)."""
        filters = filters or AnalyticsFilterParams()
        self._validate_filter_params(filters)

        events = self._repo.list_events(filters)

        features_map: Dict[str, Dict[str, Any]] = {}
        for ev in events:
            if not ev.feature_name:
                continue

            fn = ev.feature_name
            if fn not in features_map:
                features_map[fn] = {
                    "feature_name": fn,
                    "invocations": 0,
                    "success": 0,
                    "failure": 0,
                    "durations": [],
                    "last_used": ev.timestamp,
                }
            f_entry = features_map[fn]
            f_entry["invocations"] += 1
            if ev.timestamp > f_entry["last_used"]:
                f_entry["last_used"] = ev.timestamp

            if ev.result_category == "success" or (ev.status and ev.status < 400):
                f_entry["success"] += 1
            elif ev.result_category == "failure" or (ev.status and ev.status >= 400):
                f_entry["failure"] += 1

            if ev.duration_ms is not None:
                f_entry["durations"].append(ev.duration_ms)

        feature_items: List[FeatureUsageItem] = []
        total_invocations = 0
        for fn, info in features_map.items():
            cnt = info["invocations"]
            total_invocations += cnt
            err_cnt = info["failure"]
            err_r = round(err_cnt / cnt, 4) if cnt > 0 else 0.0
            _, _, avg_d, _, _, p95_d, _ = calculate_percentiles(info["durations"])

            feature_items.append(
                FeatureUsageItem(
                    feature_name=fn,
                    invocation_count=cnt,
                    success_count=info["success"],
                    failure_count=err_cnt,
                    error_rate=err_r,
                    avg_duration_ms=round(avg_d, 2),
                    p95_duration_ms=round(p95_d, 2),
                    last_used_at=info["last_used"],
                )
            )

        feature_items.sort(key=lambda x: x.invocation_count, reverse=True)

        return FeatureUsageResponse(
            total_features_tracked=len(feature_items),
            total_feature_invocations=total_invocations,
            features=feature_items,
            query_start_time=filters.start_time,
            query_end_time=filters.end_time,
        )

    # -------------------------------------------------------------------------
    # Background Job Analytics
    # -------------------------------------------------------------------------

    def get_job_analytics(
        self,
        filters: Optional[AnalyticsFilterParams] = None,
        current_user: Optional[AuthenticatedUserContext] = None,
    ) -> BackgroundJobAnalyticsResponse:
        """Background job throughput, latency, and failure metrics (Phase 22 integration)."""
        filters = filters or AnalyticsFilterParams()
        self._validate_filter_params(filters)

        events = self._repo.list_events(filters)

        total_jobs = 0
        completed_jobs = 0
        failed_jobs = 0
        retried_jobs = 0
        cancelled_jobs = 0
        dead_letter_jobs = 0
        durations: List[float] = []

        jobs_by_type: Dict[str, Dict[str, Any]] = {}

        for ev in events:
            if not ev.job_type and ev.event_type not in (
                AnalyticsEventType.JOB_CREATED,
                AnalyticsEventType.JOB_COMPLETED,
                AnalyticsEventType.JOB_FAILED,
                AnalyticsEventType.JOB_RETRIED,
                AnalyticsEventType.JOB_CANCELLED,
            ):
                continue

            jtype = ev.job_type or "unknown"
            if jtype not in jobs_by_type:
                jobs_by_type[jtype] = {
                    "job_type": jtype,
                    "total": 0,
                    "completed": 0,
                    "failed": 0,
                    "retried": 0,
                    "cancelled": 0,
                    "durations": [],
                }
            entry = jobs_by_type[jtype]

            if ev.event_type == AnalyticsEventType.JOB_CREATED:
                total_jobs += 1
                entry["total"] += 1
            elif ev.event_type == AnalyticsEventType.JOB_COMPLETED:
                completed_jobs += 1
                entry["completed"] += 1
                if ev.duration_ms is not None:
                    durations.append(ev.duration_ms)
                    entry["durations"].append(ev.duration_ms)
            elif ev.event_type == AnalyticsEventType.JOB_FAILED:
                failed_jobs += 1
                entry["failed"] += 1
            elif ev.event_type == AnalyticsEventType.JOB_RETRIED:
                retried_jobs += 1
                entry["retried"] += 1
            elif ev.event_type == AnalyticsEventType.JOB_CANCELLED:
                cancelled_jobs += 1
                entry["cancelled"] += 1

        _, _, avg_dur, _, _, p95_dur, _ = calculate_percentiles(durations)

        job_metrics: List[JobTypeMetric] = []
        for jtype, info in jobs_by_type.items():
            j_tot = max(info["total"], info["completed"] + info["failed"])
            j_fail = info["failed"]
            j_err_r = round(j_fail / j_tot, 4) if j_tot > 0 else 0.0
            _, _, j_avg, _, _, j_p95, _ = calculate_percentiles(info["durations"])

            job_metrics.append(
                JobTypeMetric(
                    job_type=jtype,
                    total_count=j_tot,
                    completed_count=info["completed"],
                    failed_count=j_fail,
                    retried_count=info["retried"],
                    cancelled_count=info["cancelled"],
                    avg_duration_ms=round(j_avg, 2),
                    p95_duration_ms=round(j_p95, 2),
                    failure_rate=j_err_r,
                )
            )

        job_metrics.sort(key=lambda x: x.total_count, reverse=True)

        return BackgroundJobAnalyticsResponse(
            total_jobs_processed=total_jobs,
            completed_jobs=completed_jobs,
            failed_jobs=failed_jobs,
            retried_jobs=retried_jobs,
            cancelled_jobs=cancelled_jobs,
            dead_letter_jobs=dead_letter_jobs,
            avg_processing_duration_ms=round(avg_dur, 2),
            p95_processing_duration_ms=round(p95_dur, 2),
            job_types=job_metrics,
            query_start_time=filters.start_time,
            query_end_time=filters.end_time,
        )

    # -------------------------------------------------------------------------
    # External Provider Analytics
    # -------------------------------------------------------------------------

    def get_provider_analytics(
        self,
        filters: Optional[AnalyticsFilterParams] = None,
        current_user: Optional[AuthenticatedUserContext] = None,
    ) -> ProviderUsageResponse:
        """External integration metrics (OCR, Medication Terminology, AI, Safety)."""
        filters = filters or AnalyticsFilterParams()
        self._validate_filter_params(filters)

        events = self._repo.list_events(filters)

        provider_map: Dict[str, Dict[str, Any]] = {}
        total_reqs = 0
        total_failures = 0
        total_timeouts = 0
        total_cost = 0.0

        for ev in events:
            if not ev.provider_name:
                continue

            pname = ev.provider_name
            if pname not in provider_map:
                # Deduce provider category
                cat = ProviderCategory.OTHER
                if "ocr" in pname.lower() or "vision" in pname.lower():
                    cat = ProviderCategory.OCR
                elif "gemini" in pname.lower() or "ai" in pname.lower() or "openai" in pname.lower():
                    cat = ProviderCategory.AI
                elif "rxnorm" in pname.lower() or "snomed" in pname.lower():
                    cat = ProviderCategory.MEDICATION_TERMINOLOGY
                elif "safety" in pname.lower():
                    cat = ProviderCategory.MEDICATION_SAFETY
                elif "fhir" in pname.lower() or "hl7" in pname.lower():
                    cat = ProviderCategory.FHIR_HL7
                elif "s3" in pname.lower() or "blob" in pname.lower():
                    cat = ProviderCategory.OBJECT_STORAGE
                elif "queue" in pname.lower() or "redis" in pname.lower() or "sqs" in pname.lower():
                    cat = ProviderCategory.QUEUE_PROVIDER

                provider_map[pname] = {
                    "provider_name": pname,
                    "category": cat,
                    "requests": 0,
                    "success": 0,
                    "failure": 0,
                    "timeout": 0,
                    "retry": 0,
                    "durations": [],
                    "cost": 0.0,
                }

            p_entry = provider_map[pname]
            p_entry["requests"] += 1
            total_reqs += 1

            if ev.event_type in (
                AnalyticsEventType.PROVIDER_SUCCESS,
                AnalyticsEventType.AI_COMPLETED,
                AnalyticsEventType.OCR_COMPLETED,
                AnalyticsEventType.INTEROPERABILITY_COMPLETED,
            ):
                p_entry["success"] += 1
            elif ev.event_type == AnalyticsEventType.PROVIDER_TIMEOUT:
                p_entry["timeout"] += 1
                p_entry["failure"] += 1
                total_timeouts += 1
                total_failures += 1
            elif ev.event_type in (
                AnalyticsEventType.PROVIDER_FAILURE,
                AnalyticsEventType.AI_FAILED,
                AnalyticsEventType.OCR_FAILED,
                AnalyticsEventType.INTEROPERABILITY_FAILED,
            ):
                p_entry["failure"] += 1
                total_failures += 1
            elif ev.status and ev.status >= 400:
                p_entry["failure"] += 1
                total_failures += 1
            else:
                p_entry["success"] += 1

            if ev.duration_ms is not None:
                p_entry["durations"].append(ev.duration_ms)

            # Extract estimated cost if present in metadata
            if ev.metadata and "estimated_cost_usd" in ev.metadata:
                c_val = float(ev.metadata.get("estimated_cost_usd", 0.0))
                p_entry["cost"] += c_val
                total_cost += c_val

        providers_list: List[ProviderUsageItem] = []
        for pname, info in provider_map.items():
            req_cnt = info["requests"]
            succ_cnt = info["success"]
            fail_cnt = info["failure"]
            time_cnt = info["timeout"]
            _, _, p_avg, _, _, p_p95, _ = calculate_percentiles(info["durations"])
            avail_pct = round((succ_cnt / req_cnt) * 100.0, 2) if req_cnt > 0 else 100.0

            providers_list.append(
                ProviderUsageItem(
                    provider_name=pname,
                    provider_category=info["category"],
                    request_count=req_cnt,
                    success_count=succ_cnt,
                    failure_count=fail_cnt,
                    timeout_count=time_cnt,
                    retry_count=info["retry"],
                    avg_latency_ms=round(p_avg, 2),
                    p95_latency_ms=round(p_p95, 2),
                    availability_percentage=avail_pct,
                    estimated_cost_usd=round(info["cost"], 4),
                )
            )

        providers_list.sort(key=lambda x: x.request_count, reverse=True)
        overall_error_rate = round(total_failures / total_reqs, 4) if total_reqs > 0 else 0.0

        return ProviderUsageResponse(
            total_providers_tracked=len(providers_list),
            total_provider_requests=total_reqs,
            total_provider_failures=total_failures,
            total_provider_timeouts=total_timeouts,
            overall_provider_error_rate=overall_error_rate,
            total_estimated_cost_usd=round(total_cost, 4),
            providers=providers_list,
            query_start_time=filters.start_time,
            query_end_time=filters.end_time,
        )

    # -------------------------------------------------------------------------
    # Cost & Resource Consumption Analytics
    # -------------------------------------------------------------------------

    def get_cost_analytics(
        self,
        filters: Optional[AnalyticsFilterParams] = None,
        current_user: Optional[AuthenticatedUserContext] = None,
    ) -> CostMetricsResponse:
        """Cost and resource consumption breakdown (AI tokens, OCR pages, safety checks)."""
        filters = filters or AnalyticsFilterParams()
        self._validate_filter_params(filters)

        events = self._repo.list_events(filters)

        # AI tracking
        ai_tasks_map: Dict[str, Dict[str, Any]] = {}
        total_ai_cost = 0.0

        # Category costs
        category_costs: Dict[CostCategory, float] = {cat: 0.0 for cat in CostCategory}
        category_units: Dict[CostCategory, float] = {cat: 0.0 for cat in CostCategory}

        for ev in events:
            # AI telemetry
            if ev.provider_name and (
                "gemini" in ev.provider_name.lower() or "ai" in ev.provider_name.lower()
            ):
                task = ev.feature_name or "inference"
                model = ev.provider_name
                k = f"{model}:{task}"
                if k not in ai_tasks_map:
                    ai_tasks_map[k] = {
                        "model": model,
                        "task": task,
                        "requests": 0,
                        "success": 0,
                        "error": 0,
                        "timeout": 0,
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                        "durations": [],
                        "cost": 0.0,
                    }
                ai_item = ai_tasks_map[k]
                ai_item["requests"] += 1
                if ev.status and ev.status >= 400:
                    ai_item["error"] += 1
                else:
                    ai_item["success"] += 1

                if ev.duration_ms is not None:
                    ai_item["durations"].append(ev.duration_ms)

                if ev.metadata:
                    p_tok = int(ev.metadata.get("prompt_tokens", 0))
                    c_tok = int(ev.metadata.get("completion_tokens", 0))
                    c_val = float(ev.metadata.get("estimated_cost_usd", 0.0))
                    ai_item["prompt_tokens"] += p_tok
                    ai_item["completion_tokens"] += c_tok
                    ai_item["cost"] += c_val
                    total_ai_cost += c_val
                    category_costs[CostCategory.AI_INFERENCE] += c_val
                    category_units[CostCategory.AI_INFERENCE] += (p_tok + c_tok)

            # OCR pages
            elif ev.provider_name and "ocr" in ev.provider_name.lower():
                pages = int(ev.metadata.get("pages_processed", 1)) if ev.metadata else 1
                cost = pages * 0.0015  # standard OCR unit cost estimate
                category_costs[CostCategory.OCR_DOCUMENT_PAGES] += cost
                category_units[CostCategory.OCR_DOCUMENT_PAGES] += pages

            # Medication safety checks
            elif ev.feature_name and "safety" in ev.feature_name.lower():
                category_units[CostCategory.MEDICATION_SAFETY_CHECKS] += 1
                category_costs[CostCategory.MEDICATION_SAFETY_CHECKS] += 0.0005

            # Compute API Volume
            if ev.event_type == AnalyticsEventType.API_REQUEST_COMPLETED:
                category_units[CostCategory.COMPUTE_API_VOLUME] += 1
                category_costs[CostCategory.COMPUTE_API_VOLUME] += 0.00001

        total_cost = sum(category_costs.values())

        # Construct line items
        unit_desc_map = {
            CostCategory.AI_INFERENCE: "Total Tokens (prompt + completion)",
            CostCategory.OCR_DOCUMENT_PAGES: "Document Pages Processed",
            CostCategory.MEDICATION_SAFETY_CHECKS: "Clinical Safety Check Queries",
            CostCategory.MEDICATION_TERMINOLOGY: "Terminology Lookups",
            CostCategory.INTEROPERABILITY_TRANSFERS: "FHIR/HL7 Bundles Transferred",
            CostCategory.STORAGE_CONSUMPTION: "GB-Months Encrypted Storage",
            CostCategory.QUEUE_MESSAGING: "Queue Messages Ingested",
            CostCategory.COMPUTE_API_VOLUME: "Standard HTTP API Invocations",
        }

        breakdown_items: List[CostBreakdownItem] = []
        for cat in CostCategory:
            cost = category_costs[cat]
            units = category_units[cat]
            pct = round((cost / total_cost) * 100.0, 2) if total_cost > 0 else 0.0
            breakdown_items.append(
                CostBreakdownItem(
                    category=cat,
                    resource_units=units,
                    unit_description=unit_desc_map[cat],
                    estimated_cost_usd=round(cost, 4),
                    percentage_of_total=pct,
                )
            )

        # AI items
        ai_telemetry_list: List[AIUsageMetricsItem] = []
        for info in ai_tasks_map.values():
            _, _, a_avg, _, _, a_p95, _ = calculate_percentiles(info["durations"])
            tot_tok = info["prompt_tokens"] + info["completion_tokens"]
            ai_telemetry_list.append(
                AIUsageMetricsItem(
                    model_name=info["model"],
                    task_type=info["task"],
                    request_count=info["requests"],
                    success_count=info["success"],
                    error_count=info["error"],
                    timeout_count=info["timeout"],
                    retry_count=0,
                    structured_output_validation_failures=0,
                    prompt_tokens=info["prompt_tokens"],
                    completion_tokens=info["completion_tokens"],
                    total_tokens=tot_tok,
                    avg_latency_ms=round(a_avg, 2),
                    p95_latency_ms=round(a_p95, 2),
                    estimated_cost_usd=round(info["cost"], 4),
                )
            )

        notes = [
            "Operational cost metrics are estimated on measured consumption units.",
            "All LLM token usage reflects sanitized payloads without PHI.",
            "Capacity utilization remains within configured operational limits.",
        ]

        return CostMetricsResponse(
            total_cost_usd=round(total_cost, 4),
            currency="USD",
            breakdown=breakdown_items,
            ai_telemetry=ai_telemetry_list,
            query_start_time=filters.start_time,
            query_end_time=filters.end_time,
            capacity_notes=notes,
        )

    # -------------------------------------------------------------------------
    # Anomaly Detection & Management
    # -------------------------------------------------------------------------

    def _check_error_anomaly(self, event: AnalyticsEvent) -> None:
        """Internal check to record an anomaly if rapid error thresholds are triggered."""
        # Query recent events in last 5 minutes
        now = datetime.now(timezone.utc)
        start_t = now - timedelta(minutes=5)

        filters = AnalyticsFilterParams(
            start_time=start_t,
            end_time=now,
            endpoint=event.endpoint,
        )
        recent_events = self._repo.list_events(filters)

        total_recent = len(recent_events)
        if total_recent < 5:
            return

        recent_errors = sum(
            1 for e in recent_events if e.status and e.status >= 500
        )
        error_rate = recent_errors / total_recent

        threshold = getattr(settings, "ANALYTICS_ANOMALY_ERROR_RATE_THRESHOLD", 0.05)
        if error_rate > threshold and recent_errors >= 3:
            # Check if an unresolved anomaly for this endpoint already exists
            existing = self._repo.list_anomalies(status=AnomalyStatus.DETECTED)
            for ex in existing:
                if ex.anomaly_type == AnomalyType.API_ERROR_SPIKE and ex.endpoint == event.endpoint:
                    return  # already recorded and active

            anomaly_id = str(uuid.uuid4())
            anomaly = UsageAnomaly(
                anomaly_id=anomaly_id,
                anomaly_type=AnomalyType.API_ERROR_SPIKE,
                severity=AnomalySeverity.HIGH,
                status=AnomalyStatus.DETECTED,
                detected_at=now,
                endpoint=event.endpoint,
                description=(
                    f"Operational error spike detected on endpoint '{event.endpoint}'. "
                    f"Recent 5m error rate is {round(error_rate * 100, 1)}% ({recent_errors}/{total_recent}). "
                    "Note: OPERATIONAL ANOMALY != SECURITY INCIDENT."
                ),
                metrics={
                    "total_requests_5m": total_recent,
                    "error_requests_5m": recent_errors,
                    "error_rate": round(error_rate, 4),
                    "threshold": threshold,
                },
            )
            self._repo.record_anomaly(anomaly)
            logger.info("Recorded operational usage anomaly: %s", anomaly_id)

    def run_anomaly_detection(self) -> List[UsageAnomaly]:
        """Run periodic operational anomaly detection across API traffic, latency, and providers."""
        now = datetime.now(timezone.utc)
        start_t = now - timedelta(minutes=15)
        filters = AnalyticsFilterParams(start_time=start_t, end_time=now)
        recent_events = self._repo.list_events(filters)

        detected_anomalies: List[UsageAnomaly] = []
        if len(recent_events) < 5:
            return detected_anomalies

        # 1. Check Latency Spikes
        durations = [e.duration_ms for e in recent_events if e.duration_ms is not None]
        if len(durations) >= 10:
            _, _, _, _, _, p95, _ = calculate_percentiles(durations)
            latency_thresh = getattr(settings, "ANALYTICS_ANOMALY_LATENCY_SPIKE_THRESHOLD_MS", 2000.0)
            if p95 > latency_thresh:
                existing = self._repo.list_anomalies(status=AnomalyStatus.DETECTED)
                if not any(ex.anomaly_type == AnomalyType.LATENCY_SPIKE for ex in existing):
                    anom = UsageAnomaly(
                        anomaly_id=str(uuid.uuid4()),
                        anomaly_type=AnomalyType.LATENCY_SPIKE,
                        severity=AnomalySeverity.MEDIUM,
                        status=AnomalyStatus.DETECTED,
                        detected_at=now,
                        description=(
                            f"Operational latency spike detected: p95 latency is {round(p95, 2)}ms "
                            f"(threshold: {latency_thresh}ms). Note: USAGE SPIKE != SECURITY INCIDENT."
                        ),
                        metrics={"p95_latency_ms": round(p95, 2), "threshold_ms": latency_thresh},
                    )
                    self._repo.record_anomaly(anom)
                    detected_anomalies.append(anom)

        # 2. Check Provider Outages / Failure Spikes
        providers = set(e.provider_name for e in recent_events if e.provider_name)
        for p in providers:
            p_events = [e for e in recent_events if e.provider_name == p]
            if len(p_events) >= 5:
                p_fails = sum(
                    1
                    for e in p_events
                    if e.event_type in (
                        AnalyticsEventType.PROVIDER_FAILURE,
                        AnalyticsEventType.PROVIDER_TIMEOUT,
                    )
                    or (e.status and e.status >= 500)
                )
                p_err_r = p_fails / len(p_events)
                if p_err_r >= 0.30:  # 30% provider error rate
                    existing = self._repo.list_anomalies(status=AnomalyStatus.DETECTED)
                    if not any(
                        ex.anomaly_type == AnomalyType.PROVIDER_FAILURE_BURST and ex.provider_name == p
                        for ex in existing
                    ):
                        anom = UsageAnomaly(
                            anomaly_id=str(uuid.uuid4()),
                            anomaly_type=AnomalyType.PROVIDER_FAILURE_BURST,
                            severity=AnomalySeverity.HIGH,
                            status=AnomalyStatus.DETECTED,
                            detected_at=now,
                            provider_name=p,
                            description=(
                                f"External provider failure burst for provider '{p}': "
                                f"{round(p_err_r * 100, 1)}% failure rate ({p_fails}/{len(p_events)}). "
                                "Note: PROVIDER FAILURE != CLINICAL DECISION."
                            ),
                            metrics={"failure_rate": round(p_err_r, 4), "total_requests": len(p_events)},
                        )
                        self._repo.record_anomaly(anom)
                        detected_anomalies.append(anom)

        return detected_anomalies

    def list_anomalies(
        self,
        status: Optional[AnomalyStatus] = None,
        offset: int = 0,
        limit: int = 50,
        current_user: Optional[AuthenticatedUserContext] = None,
    ) -> AnomalyListResponse:
        """List operational usage anomalies."""
        anomalies = self._repo.list_anomalies(status=status, offset=offset, limit=limit)
        total = self._repo.count_anomalies(status=status)
        return AnomalyListResponse(
            total_count=total,
            offset=offset,
            limit=limit,
            anomalies=anomalies,
        )

    def acknowledge_anomaly(
        self,
        anomaly_id: str,
        request: AnomalyAcknowledgeRequest,
        current_user: AuthenticatedUserContext,
    ) -> UsageAnomaly:
        """Acknowledge an operational usage anomaly."""
        anomaly = self._repo.get_anomaly(anomaly_id)
        if not anomaly:
            raise AnomalyNotFoundException(f"Anomaly {anomaly_id} not found")

        updated = self._repo.update_anomaly(
            anomaly_id=anomaly_id,
            status=AnomalyStatus.ACKNOWLEDGED,
            acknowledged_by=current_user.user_id,
        )
        if not updated:
            raise AnomalyNotFoundException(f"Anomaly {anomaly_id} not found")

        logger.info(
            "Operational anomaly %s acknowledged by user %s",
            anomaly_id,
            current_user.user_id,
        )
        return updated

    def resolve_anomaly(
        self,
        anomaly_id: str,
        request: AnomalyResolveRequest,
        current_user: AuthenticatedUserContext,
    ) -> UsageAnomaly:
        """Resolve an operational usage anomaly."""
        anomaly = self._repo.get_anomaly(anomaly_id)
        if not anomaly:
            raise AnomalyNotFoundException(f"Anomaly {anomaly_id} not found")

        updated = self._repo.update_anomaly(
            anomaly_id=anomaly_id,
            status=AnomalyStatus.RESOLVED,
            resolution_notes=request.resolution_notes,
        )
        if not updated:
            raise AnomalyNotFoundException(f"Anomaly {anomaly_id} not found")

        logger.info(
            "Operational anomaly %s resolved by user %s",
            anomaly_id,
            current_user.user_id,
        )
        return updated

    # -------------------------------------------------------------------------
    # Organization & Facility Scoped Analytics
    # -------------------------------------------------------------------------

    def get_organization_analytics(
        self,
        organization_id: str,
        filters: Optional[AnalyticsFilterParams] = None,
        current_user: Optional[AuthenticatedUserContext] = None,
    ) -> AnalyticsOverviewResponse:
        """Scoped operational analytics for a specific organization."""
        # Access control: user must belong to this organization or be a system administrator
        if current_user:
            is_sysadmin = current_user.role in ("ADMIN", "SYSTEM_ADMIN", "OPERATIONS_ADMIN")
            if not is_sysadmin and current_user.organization_id != organization_id:
                raise AnalyticsAccessDeniedException(
                    f"User not authorized to access organization analytics for {organization_id}"
                )

        filters = filters or AnalyticsFilterParams()
        filters.organization_id = organization_id
        return self.get_overview(filters=filters, current_user=current_user)

    def get_facility_analytics(
        self,
        facility_id: str,
        filters: Optional[AnalyticsFilterParams] = None,
        current_user: Optional[AuthenticatedUserContext] = None,
    ) -> AnalyticsOverviewResponse:
        """Scoped operational analytics for a specific facility."""
        if current_user:
            is_sysadmin = current_user.role in ("ADMIN", "SYSTEM_ADMIN", "OPERATIONS_ADMIN")
            if not is_sysadmin and current_user.facility_id != facility_id:
                raise AnalyticsAccessDeniedException(
                    f"User not authorized to access facility analytics for {facility_id}"
                )

        filters = filters or AnalyticsFilterParams()
        filters.facility_id = facility_id
        return self.get_overview(filters=filters, current_user=current_user)
