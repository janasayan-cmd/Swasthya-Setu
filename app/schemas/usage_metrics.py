"""Usage and Operational Metrics Schemas for HealthSetu (Phase 28).

Provides response models for:
- API endpoint usage statistics
- Error rates and failure categorizations
- Latency percentiles (p50, p90, p95, p99) and distribution buckets
- Feature invocation measurements
- Background job analytics
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.analytics import EndpointSummary, TimeSeriesPoint


class LatencyDistributionBucket(BaseModel):
    """Distribution bucket for request latency."""

    model_config = ConfigDict(extra="ignore")

    bucket_label: str = Field(..., description="E.g. '<50ms', '50ms-200ms', '>5s'")
    min_ms: float = Field(default=0.0)
    max_ms: Optional[float] = Field(default=None)
    count: int = Field(default=0, ge=0)
    percentage: float = Field(default=0.0, ge=0.0, le=100.0)


class LatencyPercentiles(BaseModel):
    """Statistical distribution of request response times."""

    model_config = ConfigDict(extra="ignore")

    p50_ms: float = Field(default=0.0)
    p90_ms: float = Field(default=0.0)
    p95_ms: float = Field(default=0.0)
    p99_ms: float = Field(default=0.0)
    min_ms: float = Field(default=0.0)
    max_ms: float = Field(default=0.0)
    avg_ms: float = Field(default=0.0)


class LatencyMetricsResponse(BaseModel):
    """Platform latency analytics and endpoint response time percentiles."""

    model_config = ConfigDict(extra="ignore")

    sample_count: int = Field(default=0, ge=0)
    min_latency_ms: float = Field(default=0.0)
    max_latency_ms: float = Field(default=0.0)
    avg_latency_ms: float = Field(default=0.0)
    p50_latency_ms: float = Field(default=0.0)
    p90_latency_ms: float = Field(default=0.0)
    p95_latency_ms: float = Field(default=0.0)
    p99_latency_ms: float = Field(default=0.0)
    distribution: List[LatencyDistributionBucket] = Field(default_factory=list)
    overall: Optional[LatencyPercentiles] = None
    by_endpoint: Dict[str, LatencyPercentiles] = Field(default_factory=dict)
    time_series_p95: List[TimeSeriesPoint] = Field(default_factory=list)
    query_start_time: Optional[datetime] = None
    query_end_time: Optional[datetime] = None


class ApiUsageMetricsResponse(BaseModel):
    """Aggregated API request metrics across endpoints and status codes."""

    model_config = ConfigDict(extra="ignore")

    total_requests: int = Field(default=0, ge=0)
    success_count: int = Field(default=0, ge=0)
    error_count: int = Field(default=0, ge=0)
    error_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    avg_latency_ms: float = Field(default=0.0)
    p50_latency_ms: float = Field(default=0.0)
    p95_latency_ms: float = Field(default=0.0)
    p99_latency_ms: float = Field(default=0.0)
    rate_limit_events_count: int = Field(default=0, ge=0)
    authentication_failures_count: int = Field(default=0, ge=0)
    status_distribution: Dict[str, int] = Field(default_factory=dict)
    time_series: List[TimeSeriesPoint] = Field(default_factory=list)
    endpoints: List[EndpointSummary] = Field(default_factory=list)
    query_start_time: Optional[datetime] = None
    query_end_time: Optional[datetime] = None


class ErrorCategoryCount(BaseModel):
    """Count of failures classified by category."""

    model_config = ConfigDict(extra="ignore")

    category: str
    count: int = Field(default=0, ge=0)
    percentage: float = Field(default=0.0, ge=0.0, le=100.0)


class ErrorMetricsResponse(BaseModel):
    """In-depth operational error analysis."""

    model_config = ConfigDict(extra="ignore")

    total_requests: int = Field(default=0, ge=0)
    total_errors: int = Field(default=0, ge=0)
    overall_error_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    client_errors_4xx: int = Field(default=0, ge=0)
    server_errors_5xx: int = Field(default=0, ge=0)
    status_distribution: Dict[str, int] = Field(default_factory=dict)
    top_error_endpoints: List[EndpointSummary] = Field(default_factory=list)
    error_categories: Dict[str, int] = Field(default_factory=dict)
    by_category: List[ErrorCategoryCount] = Field(default_factory=list)
    time_series: List[TimeSeriesPoint] = Field(default_factory=list)
    query_start_time: Optional[datetime] = None
    query_end_time: Optional[datetime] = None


class FeatureUsageItem(BaseModel):
    """Usage measurement for an individual platform capability."""

    model_config = ConfigDict(extra="ignore")

    feature_name: str
    invocation_count: int = Field(default=0, ge=0)
    success_count: int = Field(default=0, ge=0)
    failure_count: int = Field(default=0, ge=0)
    error_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    avg_duration_ms: float = Field(default=0.0)
    p95_duration_ms: float = Field(default=0.0)
    last_used_at: Optional[datetime] = None


class FeatureUsageResponse(BaseModel):
    """Aggregated usage metrics across approved platform features."""

    model_config = ConfigDict(extra="ignore")

    total_features_tracked: int = Field(default=0, ge=0)
    total_feature_invocations: int = Field(default=0, ge=0)
    features: List[FeatureUsageItem] = Field(default_factory=list)
    time_series: List[TimeSeriesPoint] = Field(default_factory=list)
    query_start_time: Optional[datetime] = None
    query_end_time: Optional[datetime] = None


class JobTypeMetric(BaseModel):
    """Analytics for a specific background job type."""

    model_config = ConfigDict(extra="ignore")

    job_type: str
    total_count: int = Field(default=0, ge=0)
    completed_count: int = Field(default=0, ge=0)
    failed_count: int = Field(default=0, ge=0)
    retried_count: int = Field(default=0, ge=0)
    cancelled_count: int = Field(default=0, ge=0)
    avg_duration_ms: float = Field(default=0.0)
    p95_duration_ms: float = Field(default=0.0)
    failure_rate: float = Field(default=0.0, ge=0.0, le=1.0)


class BackgroundJobAnalyticsResponse(BaseModel):
    """Operational metrics for background asynchronous workflows (Phase 22)."""

    model_config = ConfigDict(extra="ignore")

    total_jobs_processed: int = Field(default=0, ge=0)
    completed_jobs: int = Field(default=0, ge=0)
    failed_jobs: int = Field(default=0, ge=0)
    retried_jobs: int = Field(default=0, ge=0)
    cancelled_jobs: int = Field(default=0, ge=0)
    dead_letter_jobs: int = Field(default=0, ge=0)
    avg_processing_duration_ms: float = Field(default=0.0)
    p95_processing_duration_ms: float = Field(default=0.0)
    job_types: List[JobTypeMetric] = Field(default_factory=list)
    time_series: List[TimeSeriesPoint] = Field(default_factory=list)
    query_start_time: Optional[datetime] = None
    query_end_time: Optional[datetime] = None
