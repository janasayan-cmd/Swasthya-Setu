"""Analytics and Usage Governance Schemas (Phase 28).

Provides data contracts for:
- Operational analytics events
- Time-bucketed metrics
- Filter specifications with validation
- Overview summary responses

SAFETY & PRIVACY INVARIANTS:
- ANALYTICS != CLINICAL DECISION
- USAGE DATA != CLINICAL DATA
- METRICS != AUDIT RECORDS
- Route templates only (e.g. /api/v1/patients/{patient_id}/medications) — NEVER raw patient IDs
- ZERO PHI (no notes, diagnoses, prescriptions, allergies, or document text)
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
import uuid


class AnalyticsEventType(str, Enum):
    """Operational event types recorded by the analytics pipeline."""

    API_REQUEST_COMPLETED = "API_REQUEST_COMPLETED"
    API_REQUEST_FAILED = "API_REQUEST_FAILED"
    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
    AUTHORIZATION_FAILED = "AUTHORIZATION_FAILED"
    FEATURE_USED = "FEATURE_USED"
    JOB_CREATED = "JOB_CREATED"
    JOB_COMPLETED = "JOB_COMPLETED"
    JOB_FAILED = "JOB_FAILED"
    JOB_RETRIED = "JOB_RETRIED"
    JOB_CANCELLED = "JOB_CANCELLED"
    PROVIDER_REQUEST = "PROVIDER_REQUEST"
    PROVIDER_SUCCESS = "PROVIDER_SUCCESS"
    PROVIDER_FAILURE = "PROVIDER_FAILURE"
    PROVIDER_TIMEOUT = "PROVIDER_TIMEOUT"
    AI_REQUEST = "AI_REQUEST"
    AI_COMPLETED = "AI_COMPLETED"
    AI_FAILED = "AI_FAILED"
    OCR_REQUEST = "OCR_REQUEST"
    OCR_COMPLETED = "OCR_COMPLETED"
    OCR_FAILED = "OCR_FAILED"
    INTEROPERABILITY_REQUEST = "INTEROPERABILITY_REQUEST"
    INTEROPERABILITY_COMPLETED = "INTEROPERABILITY_COMPLETED"
    INTEROPERABILITY_FAILED = "INTEROPERABILITY_FAILED"
    ANOMALY_DETECTED = "ANOMALY_DETECTED"
    RATE_LIMIT_TRIGGERED = "RATE_LIMIT_TRIGGERED"


class TimeBucket(str, Enum):
    """Aggregation temporal resolution."""

    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


class AnalyticsEvent(BaseModel):
    """Raw operational analytics event without raw clinical content."""

    model_config = ConfigDict(extra="ignore", from_attributes=True)

    event_id: str = Field(default_factory=lambda: f"evt-{uuid.uuid4().hex[:12]}")
    event_type: AnalyticsEventType
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    environment: str = Field(default="production")
    service: str = Field(default="healthsetu-backend")
    api_version: str = Field(default="v1")
    endpoint: Optional[str] = Field(default=None, description="Parameterized route template (zero raw IDs)")
    endpoint_template: Optional[str] = None
    http_method: Optional[str] = None
    status: Optional[int] = None
    status_code: Optional[int] = None
    duration_ms: Optional[float] = None
    request_id: Optional[str] = None
    correlation_id: Optional[str] = None
    user_category: Optional[str] = Field(default=None, description="Role or user category (e.g. DOCTOR, PATIENT, ADMIN)")
    organization_id: Optional[str] = None
    facility_id: Optional[str] = None
    feature_name: Optional[str] = None
    provider_name: Optional[str] = None
    job_type: Optional[str] = None
    job_status: Optional[str] = None
    resource_type: Optional[str] = None
    result_category: Optional[str] = None
    error_category: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Safe operational metrics (ZERO PHI/secrets)")

    def model_post_init(self, __context: Any) -> None:
        if self.endpoint and not self.endpoint_template:
            self.endpoint_template = self.endpoint
        elif self.endpoint_template and not self.endpoint:
            self.endpoint = self.endpoint_template
        if self.status is not None and self.status_code is None:
            self.status_code = self.status
        elif self.status_code is not None and self.status is None:
            self.status = self.status_code


class AnalyticsFilterParams(BaseModel):
    """Validated query filter parameters for analytical queries."""

    model_config = ConfigDict(extra="ignore")

    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    environment: Optional[str] = None
    api_version: Optional[str] = None
    endpoint: Optional[str] = None
    status: Optional[int] = None
    status_code: Optional[int] = None
    feature: Optional[str] = None
    feature_name: Optional[str] = None
    provider: Optional[str] = None
    provider_name: Optional[str] = None
    job_type: Optional[str] = None
    organization_id: Optional[str] = None
    facility_id: Optional[str] = None
    event_type: Optional[AnalyticsEventType] = None
    time_bucket: TimeBucket = Field(default=TimeBucket.HOUR)
    bucket: TimeBucket = Field(default=TimeBucket.HOUR)
    offset: int = Field(default=0, ge=0)
    skip: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=100)

    def model_post_init(self, __context: Any) -> None:
        if self.status is not None and self.status_code is None:
            self.status_code = self.status
        elif self.status_code is not None and self.status is None:
            self.status = self.status_code
        if self.feature is not None and self.feature_name is None:
            self.feature_name = self.feature
        elif self.feature_name is not None and self.feature is None:
            self.feature = self.feature_name
        if self.provider is not None and self.provider_name is None:
            self.provider_name = self.provider
        elif self.provider_name is not None and self.provider is None:
            self.provider = self.provider_name
        if self.offset != 0 and self.skip == 0:
            self.skip = self.offset
        elif self.skip != 0 and self.offset == 0:
            self.offset = self.skip


class TimeSeriesPoint(BaseModel):
    """Point in a time-series metric."""

    model_config = ConfigDict(extra="ignore")

    bucket_time: Optional[datetime] = None
    timestamp: Optional[datetime] = None
    request_count: int = Field(default=0, ge=0)
    success_count: int = Field(default=0, ge=0)
    error_count: int = Field(default=0, ge=0)
    error_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    avg_latency_ms: float = Field(default=0.0)
    p95_latency_ms: float = Field(default=0.0)
    value: float = Field(default=0.0)
    count: int = Field(default=1)
    label: Optional[str] = None

    def model_post_init(self, __context: Any) -> None:
        if self.bucket_time and not self.timestamp:
            self.timestamp = self.bucket_time
        elif self.timestamp and not self.bucket_time:
            self.bucket_time = self.timestamp


class EndpointSummary(BaseModel):
    """Summary of traffic for an individual endpoint route."""

    model_config = ConfigDict(extra="ignore")

    endpoint: str = Field(default="")
    endpoint_template: str = Field(default="")
    http_method: str = Field(default="GET")
    request_count: int = Field(default=0, ge=0)
    success_count: int = Field(default=0, ge=0)
    error_count: int = Field(default=0, ge=0)
    error_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    avg_latency_ms: float = Field(default=0.0)
    p50_latency_ms: float = Field(default=0.0)
    p95_latency_ms: float = Field(default=0.0)
    p99_latency_ms: float = Field(default=0.0)
    status_distribution: Dict[str, int] = Field(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        if self.endpoint and not self.endpoint_template:
            self.endpoint_template = self.endpoint
        elif self.endpoint_template and not self.endpoint:
            self.endpoint = self.endpoint_template


class AnalyticsOverviewResponse(BaseModel):
    """High-level operational intelligence summary."""

    model_config = ConfigDict(extra="ignore")

    environment: str = Field(default="production")
    time_window_hours: float = Field(default=24.0)
    total_requests: int = Field(default=0, ge=0)
    successful_requests: int = Field(default=0, ge=0)
    success_count: int = Field(default=0, ge=0)
    error_requests: int = Field(default=0, ge=0)
    error_count: int = Field(default=0, ge=0)
    overall_error_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    error_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    avg_latency_ms: float = Field(default=0.0)
    p50_latency_ms: float = Field(default=0.0)
    p90_latency_ms: float = Field(default=0.0)
    p95_latency_ms: float = Field(default=0.0)
    p99_latency_ms: float = Field(default=0.0)
    http_status_distribution: Dict[str, int] = Field(default_factory=dict)
    active_anomalies_count: int = Field(default=0, ge=0)
    total_features_active: int = Field(default=0, ge=0)
    top_endpoints: List[EndpointSummary] = Field(default_factory=list)
    provider_call_counts: Dict[str, int] = Field(default_factory=dict)
    job_status_counts: Dict[str, int] = Field(default_factory=dict)
    query_start_time: Optional[datetime] = None
    query_end_time: Optional[datetime] = None
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def model_post_init(self, __context: Any) -> None:
        if self.successful_requests and not self.success_count:
            self.success_count = self.successful_requests
        elif self.success_count and not self.successful_requests:
            self.successful_requests = self.success_count
        if self.error_requests and not self.error_count:
            self.error_count = self.error_requests
        elif self.error_count and not self.error_requests:
            self.error_requests = self.error_count
        if self.overall_error_rate and not self.error_rate:
            self.error_rate = self.overall_error_rate
        elif self.error_rate and not self.overall_error_rate:
            self.overall_error_rate = self.error_rate
