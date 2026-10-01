"""API Analytics, Usage Governance & Operational Intelligence Endpoints (Phase 28).

Provides:
- Dedicated administrative analytics endpoints under /api/v1/admin/analytics/
- Scoped tenant analytics endpoints under /api/v1/organizations/{organization_id}/analytics
- Scoped facility analytics endpoints under /api/v1/facilities/{facility_id}/analytics
- Operational anomaly lifecycle endpoints (list, acknowledge, resolve)

CRITICAL INVARIANTS:
- ANALYTICS != CLINICAL DECISION
- USAGE DATA != CLINICAL DATA
- METRICS != AUDIT RECORDS
- ANALYTICS != PATIENT PROFILING
- Route templates only in endpoints; NEVER raw patient IDs
- ZERO PHI in analytics responses
- Fail-safe isolation: analytics query or recording failures must never affect clinical safety
"""

from datetime import datetime
from typing import Annotated, Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, Request, status

from app.api.deps import (
    get_analytics_service,
    get_current_user,
)
from app.core.exceptions import (
    AdminAccessDeniedException,
    AdminPermissionRequiredException,
    AnalyticsAccessDeniedException,
    ForbiddenException,
)
from app.core.logging import request_id_ctx_var
from app.core.policies import Permission, ROLE_PERMISSIONS
from app.schemas.analytics import (
    AnalyticsFilterParams,
    AnalyticsOverviewResponse,
    TimeBucket,
)
from app.schemas.anomaly import (
    AnomalyAcknowledgeRequest,
    AnomalyListResponse,
    AnomalyResolveRequest,
    AnomalyStatus,
    UsageAnomaly,
)
from app.schemas.provider_usage import (
    CostMetricsResponse,
    ProviderUsageResponse,
)
from app.schemas.response import StandardSuccessResponse
from app.schemas.usage_metrics import (
    ApiUsageMetricsResponse,
    BackgroundJobAnalyticsResponse,
    ErrorMetricsResponse,
    FeatureUsageResponse,
    LatencyMetricsResponse,
)
from app.schemas.user import AuthenticatedUserContext
from app.services.analytics_service import AnalyticsService

router = APIRouter(tags=["API Analytics & Usage Governance"])


def _req_id(request: Request) -> str:
    """Extract request ID from request state or context variable."""
    return getattr(request.state, "request_id", None) or request_id_ctx_var.get() or "unknown"


def _require_analytics_permission(actor: AuthenticatedUserContext, permission: Permission) -> None:
    """Verify that the actor holds the required permission."""
    role_str = actor.role.value if hasattr(actor.role, "value") else str(actor.role)
    allowed = ROLE_PERMISSIONS.get(role_str, frozenset())
    if permission not in allowed:
        has_admin = any(p.value.startswith("admin:") for p in allowed)
        if not has_admin and permission == Permission.ADMIN_ANALYTICS_VIEW:
            raise AdminAccessDeniedException("Administrative analytics access denied.")
        raise ForbiddenException(f"Missing required permission: {permission.value}")


def _build_filter_params(
    start_time: Optional[datetime],
    end_time: Optional[datetime],
    environment: Optional[str],
    api_version: Optional[str],
    endpoint: Optional[str],
    status: Optional[int],
    feature: Optional[str],
    provider: Optional[str],
    job_type: Optional[str],
    organization_id: Optional[str] = None,
    facility_id: Optional[str] = None,
    time_bucket: TimeBucket = TimeBucket.HOUR,
    offset: int = 0,
    limit: int = 50,
) -> AnalyticsFilterParams:
    """Build and return an AnalyticsFilterParams object."""
    return AnalyticsFilterParams(
        start_time=start_time,
        end_time=end_time,
        environment=environment,
        api_version=api_version,
        endpoint=endpoint,
        status=status,
        feature=feature,
        provider=provider,
        job_type=job_type,
        organization_id=organization_id,
        facility_id=facility_id,
        time_bucket=time_bucket,
        offset=offset,
        limit=limit,
    )


# ===========================================================================
# Admin Analytics Endpoints (/api/v1/admin/analytics/...)
# ===========================================================================

@router.get(
    "/admin/analytics/overview",
    response_model=StandardSuccessResponse[AnalyticsOverviewResponse],
    summary="Get operational analytics overview summary",
)
async def get_analytics_overview(
    request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    analytics_service: Annotated[AnalyticsService, Depends(get_analytics_service)],
    start_time: Optional[datetime] = Query(default=None),
    end_time: Optional[datetime] = Query(default=None),
    environment: Optional[str] = Query(default=None),
    api_version: Optional[str] = Query(default=None),
    endpoint: Optional[str] = Query(default=None),
    status: Optional[int] = Query(default=None),
    feature: Optional[str] = Query(default=None),
    provider: Optional[str] = Query(default=None),
    job_type: Optional[str] = Query(default=None),
) -> StandardSuccessResponse[AnalyticsOverviewResponse]:
    """Top-level operational summary including request volumes, latency percentiles, error rates, and top endpoints."""
    _require_analytics_permission(current_user, Permission.ADMIN_ANALYTICS_VIEW)
    filters = _build_filter_params(
        start_time=start_time,
        end_time=end_time,
        environment=environment,
        api_version=api_version,
        endpoint=endpoint,
        status=status,
        feature=feature,
        provider=provider,
        job_type=job_type,
    )
    result = analytics_service.get_overview(filters=filters, current_user=current_user)
    return StandardSuccessResponse(data=result, request_id=_req_id(request))


@router.get(
    "/admin/analytics/api-usage",
    response_model=StandardSuccessResponse[ApiUsageMetricsResponse],
    summary="Get API usage metrics and time series breakdown",
)
async def get_api_usage_metrics(
    request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    analytics_service: Annotated[AnalyticsService, Depends(get_analytics_service)],
    start_time: Optional[datetime] = Query(default=None),
    end_time: Optional[datetime] = Query(default=None),
    environment: Optional[str] = Query(default=None),
    endpoint: Optional[str] = Query(default=None),
    time_bucket: TimeBucket = Query(default=TimeBucket.HOUR),
) -> StandardSuccessResponse[ApiUsageMetricsResponse]:
    """Retrieve detailed API request volumes, time-bucketed traffic, rate-limit events, and endpoint summaries."""
    _require_analytics_permission(current_user, Permission.ADMIN_ANALYTICS_VIEW)
    filters = _build_filter_params(
        start_time=start_time,
        end_time=end_time,
        environment=environment,
        api_version=None,
        endpoint=endpoint,
        status=None,
        feature=None,
        provider=None,
        job_type=None,
        time_bucket=time_bucket,
    )
    result = analytics_service.get_api_usage_metrics(filters=filters, current_user=current_user)
    return StandardSuccessResponse(data=result, request_id=_req_id(request))


@router.get(
    "/admin/analytics/errors",
    response_model=StandardSuccessResponse[ErrorMetricsResponse],
    summary="Get API error rate metrics and status distribution",
)
async def get_error_metrics(
    request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    analytics_service: Annotated[AnalyticsService, Depends(get_analytics_service)],
    start_time: Optional[datetime] = Query(default=None),
    end_time: Optional[datetime] = Query(default=None),
    environment: Optional[str] = Query(default=None),
    endpoint: Optional[str] = Query(default=None),
) -> StandardSuccessResponse[ErrorMetricsResponse]:
    """Analyze 4xx/5xx error distributions, top failing route templates, and error categories."""
    _require_analytics_permission(current_user, Permission.ADMIN_ANALYTICS_VIEW)
    filters = _build_filter_params(
        start_time=start_time,
        end_time=end_time,
        environment=environment,
        api_version=None,
        endpoint=endpoint,
        status=None,
        feature=None,
        provider=None,
        job_type=None,
    )
    result = analytics_service.get_error_metrics(filters=filters, current_user=current_user)
    return StandardSuccessResponse(data=result, request_id=_req_id(request))


@router.get(
    "/admin/analytics/latency",
    response_model=StandardSuccessResponse[LatencyMetricsResponse],
    summary="Get API latency distribution and percentiles (p50, p90, p95, p99)",
)
async def get_latency_metrics(
    request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    analytics_service: Annotated[AnalyticsService, Depends(get_analytics_service)],
    start_time: Optional[datetime] = Query(default=None),
    end_time: Optional[datetime] = Query(default=None),
    environment: Optional[str] = Query(default=None),
    endpoint: Optional[str] = Query(default=None),
) -> StandardSuccessResponse[LatencyMetricsResponse]:
    """Inspect response latency distribution buckets (<50ms, 50-200ms, >5s) and percentiles."""
    _require_analytics_permission(current_user, Permission.ADMIN_ANALYTICS_VIEW)
    filters = _build_filter_params(
        start_time=start_time,
        end_time=end_time,
        environment=environment,
        api_version=None,
        endpoint=endpoint,
        status=None,
        feature=None,
        provider=None,
        job_type=None,
    )
    result = analytics_service.get_latency_metrics(filters=filters, current_user=current_user)
    return StandardSuccessResponse(data=result, request_id=_req_id(request))


@router.get(
    "/admin/analytics/jobs",
    response_model=StandardSuccessResponse[BackgroundJobAnalyticsResponse],
    summary="Get background job throughput, latency, and failure metrics",
)
async def get_job_analytics(
    request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    analytics_service: Annotated[AnalyticsService, Depends(get_analytics_service)],
    start_time: Optional[datetime] = Query(default=None),
    end_time: Optional[datetime] = Query(default=None),
    job_type: Optional[str] = Query(default=None),
) -> StandardSuccessResponse[BackgroundJobAnalyticsResponse]:
    """Telemetry on asynchronous background worker throughput, retry rates, and execution durations."""
    _require_analytics_permission(current_user, Permission.ADMIN_ANALYTICS_VIEW)
    filters = _build_filter_params(
        start_time=start_time,
        end_time=end_time,
        environment=None,
        api_version=None,
        endpoint=None,
        status=None,
        feature=None,
        provider=None,
        job_type=job_type,
    )
    result = analytics_service.get_job_analytics(filters=filters, current_user=current_user)
    return StandardSuccessResponse(data=result, request_id=_req_id(request))


@router.get(
    "/admin/analytics/providers",
    response_model=StandardSuccessResponse[ProviderUsageResponse],
    summary="Get external provider usage, availability, and error telemetry",
)
async def get_provider_analytics(
    request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    analytics_service: Annotated[AnalyticsService, Depends(get_analytics_service)],
    start_time: Optional[datetime] = Query(default=None),
    end_time: Optional[datetime] = Query(default=None),
    provider: Optional[str] = Query(default=None),
) -> StandardSuccessResponse[ProviderUsageResponse]:
    """Metrics across OCR, AI, Medication terminology, and FHIR integrations (uptime, timeouts, costs)."""
    _require_analytics_permission(current_user, Permission.ADMIN_ANALYTICS_VIEW)
    filters = _build_filter_params(
        start_time=start_time,
        end_time=end_time,
        environment=None,
        api_version=None,
        endpoint=None,
        status=None,
        feature=None,
        provider=provider,
        job_type=None,
    )
    result = analytics_service.get_provider_analytics(filters=filters, current_user=current_user)
    return StandardSuccessResponse(data=result, request_id=_req_id(request))


@router.get(
    "/admin/analytics/features",
    response_model=StandardSuccessResponse[FeatureUsageResponse],
    summary="Get platform feature invocation and adoption analytics",
)
async def get_feature_analytics(
    request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    analytics_service: Annotated[AnalyticsService, Depends(get_analytics_service)],
    start_time: Optional[datetime] = Query(default=None),
    end_time: Optional[datetime] = Query(default=None),
    feature: Optional[str] = Query(default=None),
) -> StandardSuccessResponse[FeatureUsageResponse]:
    """Measure platform feature usage frequency, success/failure counts, and execution durations."""
    _require_analytics_permission(current_user, Permission.ADMIN_ANALYTICS_VIEW)
    filters = _build_filter_params(
        start_time=start_time,
        end_time=end_time,
        environment=None,
        api_version=None,
        endpoint=None,
        status=None,
        feature=feature,
        provider=None,
        job_type=None,
    )
    result = analytics_service.get_feature_usage(filters=filters, current_user=current_user)
    return StandardSuccessResponse(data=result, request_id=_req_id(request))


@router.get(
    "/admin/analytics/anomalies",
    response_model=StandardSuccessResponse[AnomalyListResponse],
    summary="List operational usage anomalies",
)
async def list_usage_anomalies(
    request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    analytics_service: Annotated[AnalyticsService, Depends(get_analytics_service)],
    status: Optional[AnomalyStatus] = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> StandardSuccessResponse[AnomalyListResponse]:
    """Inspect detected operational anomalies (traffic spikes, error surges, provider failures)."""
    _require_analytics_permission(current_user, Permission.ADMIN_ANALYTICS_VIEW)
    result = analytics_service.list_anomalies(
        status=status,
        offset=offset,
        limit=limit,
        current_user=current_user,
    )
    return StandardSuccessResponse(data=result, request_id=_req_id(request))


@router.post(
    "/admin/analytics/anomalies/{anomaly_id}/acknowledge",
    response_model=StandardSuccessResponse[UsageAnomaly],
    summary="Acknowledge an operational usage anomaly",
)
async def acknowledge_usage_anomaly(
    request: Request,
    anomaly_id: str,
    body: AnomalyAcknowledgeRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    analytics_service: Annotated[AnalyticsService, Depends(get_analytics_service)],
) -> StandardSuccessResponse[UsageAnomaly]:
    """Mark an operational anomaly as acknowledged for investigation."""
    _require_analytics_permission(current_user, Permission.ADMIN_ANALYTICS_VIEW)
    updated = analytics_service.acknowledge_anomaly(
        anomaly_id=anomaly_id,
        request=body,
        current_user=current_user,
    )
    return StandardSuccessResponse(data=updated, request_id=_req_id(request))


@router.post(
    "/admin/analytics/anomalies/{anomaly_id}/resolve",
    response_model=StandardSuccessResponse[UsageAnomaly],
    summary="Resolve an operational usage anomaly",
)
async def resolve_usage_anomaly(
    request: Request,
    anomaly_id: str,
    body: AnomalyResolveRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    analytics_service: Annotated[AnalyticsService, Depends(get_analytics_service)],
) -> StandardSuccessResponse[UsageAnomaly]:
    """Mark an operational anomaly as resolved with closing remarks."""
    _require_analytics_permission(current_user, Permission.ADMIN_ANALYTICS_VIEW)
    resolved = analytics_service.resolve_anomaly(
        anomaly_id=anomaly_id,
        request=body,
        current_user=current_user,
    )
    return StandardSuccessResponse(data=resolved, request_id=_req_id(request))


@router.get(
    "/admin/analytics/costs",
    response_model=StandardSuccessResponse[CostMetricsResponse],
    summary="Get cost and resource consumption tracking breakdown",
)
async def get_cost_analytics(
    request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    analytics_service: Annotated[AnalyticsService, Depends(get_analytics_service)],
    start_time: Optional[datetime] = Query(default=None),
    end_time: Optional[datetime] = Query(default=None),
) -> StandardSuccessResponse[CostMetricsResponse]:
    """Operational resource consumption and cost breakdown across AI tokens, OCR pages, and compute."""
    _require_analytics_permission(current_user, Permission.ADMIN_ANALYTICS_VIEW)
    filters = _build_filter_params(
        start_time=start_time,
        end_time=end_time,
        environment=None,
        api_version=None,
        endpoint=None,
        status=None,
        feature=None,
        provider=None,
        job_type=None,
    )
    result = analytics_service.get_cost_analytics(filters=filters, current_user=current_user)
    return StandardSuccessResponse(data=result, request_id=_req_id(request))


# ===========================================================================
# Organization & Facility Scoped Analytics Endpoints
# ===========================================================================

@router.get(
    "/organizations/{organization_id}/analytics",
    response_model=StandardSuccessResponse[AnalyticsOverviewResponse],
    summary="Get organization-scoped operational analytics",
)
async def get_organization_analytics(
    request: Request,
    organization_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    analytics_service: Annotated[AnalyticsService, Depends(get_analytics_service)],
    start_time: Optional[datetime] = Query(default=None),
    end_time: Optional[datetime] = Query(default=None),
) -> StandardSuccessResponse[AnalyticsOverviewResponse]:
    """Retrieve operational analytics aggregated strictly for the specified organization."""
    _require_analytics_permission(current_user, Permission.ORGANIZATION_ANALYTICS_VIEW)
    filters = _build_filter_params(
        start_time=start_time,
        end_time=end_time,
        environment=None,
        api_version=None,
        endpoint=None,
        status=None,
        feature=None,
        provider=None,
        job_type=None,
        organization_id=organization_id,
    )
    result = analytics_service.get_organization_analytics(
        organization_id=organization_id,
        filters=filters,
        current_user=current_user,
    )
    return StandardSuccessResponse(data=result, request_id=_req_id(request))


@router.get(
    "/facilities/{facility_id}/analytics",
    response_model=StandardSuccessResponse[AnalyticsOverviewResponse],
    summary="Get facility-scoped operational analytics",
)
async def get_facility_analytics(
    request: Request,
    facility_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    analytics_service: Annotated[AnalyticsService, Depends(get_analytics_service)],
    start_time: Optional[datetime] = Query(default=None),
    end_time: Optional[datetime] = Query(default=None),
) -> StandardSuccessResponse[AnalyticsOverviewResponse]:
    """Retrieve operational analytics aggregated strictly for the specified facility."""
    _require_analytics_permission(current_user, Permission.FACILITY_ANALYTICS_VIEW)
    filters = _build_filter_params(
        start_time=start_time,
        end_time=end_time,
        environment=None,
        api_version=None,
        endpoint=None,
        status=None,
        feature=None,
        provider=None,
        job_type=None,
        facility_id=facility_id,
    )
    result = analytics_service.get_facility_analytics(
        facility_id=facility_id,
        filters=filters,
        current_user=current_user,
    )
    return StandardSuccessResponse(data=result, request_id=_req_id(request))
