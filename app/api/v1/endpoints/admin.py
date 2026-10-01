"""Administrative, Support Operations & Controlled Backoffice Endpoints (Phase 27).

Provides dedicated APIs under /api/v1/admin/ for authorized internal operators:
- System operational status, in-depth telemetry, and readiness probes
- Background asynchronous job inspection, retry, and cancellation
- External integration monitoring and non-PHI connectivity testing
- Operational incident logging, acknowledgement, progress updates, and resolution
- System-wide data quality aggregated metrics
- Administrative audit log queries
- Security event log inspection
- Operational configuration and feature flag overview
- Privacy-safe patient support lookup with strictly minimized identifiers

INVARIANTS:
- Dedicated /api/v1/admin namespace
- ADMIN ACCESS != CLINICAL AUTHORITY
- SUPPORT ACCESS != UNLIMITED DATA ACCESS
- ADMIN ACTION != CLINICAL DECISION
- DEBUGGING != DIRECT DATABASE MODIFICATION
- OPERATIONAL OVERRIDE != CLINICAL OVERRIDE
- ZERO SECRETS, CREDENTIALS, OR UNPROTECTED PHI EXPOSED
"""

from typing import Annotated, Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, Request, status

from app.api.deps import (
    get_admin_service,
    get_configuration_service,
    get_current_user,
    get_incident_service,
    get_support_service,
)
from app.core.config import settings
from app.core.exceptions import (
    AdminAccessDeniedException,
    AdminPermissionRequiredException,
    ForbiddenException,
)
from app.core.logging import request_id_ctx_var
from app.core.policies import Permission, ROLE_PERMISSIONS
from app.schemas.admin import (
    AdminAuditListResponse,
    AdminDataQualityOverview,
    AdminJobListResponse,
    AdminJobSummary,
    AdminSecurityEventListResponse,
    IntegrationListResponse,
    IntegrationProviderStatus,
    IntegrationTestRequest,
    IntegrationTestResponse,
    JobCancelResponse,
    JobRetryResponse,
    SupportPatientSearchResponse,
    SystemDetailedHealthResponse,
    SystemReadinessResponse,
    SystemStatusResponse,
)
from app.schemas.audit import AuditEventRecord
from app.schemas.incident import (
    IncidentAcknowledge,
    IncidentCategory,
    IncidentCreate,
    IncidentListResponse,
    IncidentRecord,
    IncidentResolve,
    IncidentSeverity,
    IncidentStatus,
    IncidentUpdate,
)
from app.schemas.job import JobStatus, JobType
from app.schemas.response import StandardSuccessResponse
from app.schemas.user import AuthenticatedUserContext
from app.services.admin_service import AdminService
from app.services.configuration_service import ConfigurationService
from app.services.incident_service import IncidentService
from app.services.support_service import SupportService

router = APIRouter(prefix="/admin", tags=["Administration, Support Operations & Backoffice"])


def _req_id(request: Request) -> str:
    """Extract request ID from request state or context variable."""
    return getattr(request.state, "request_id", None) or request_id_ctx_var.get() or "unknown"


def _require_admin_permission(actor: AuthenticatedUserContext, permission: Permission) -> None:
    """Validate that actor possesses required administrative capability permission."""
    role_str = actor.role.value if hasattr(actor.role, "value") else str(actor.role)
    allowed = ROLE_PERMISSIONS.get(role_str, frozenset())
    if permission not in allowed:
        has_any_admin_perm = any(p.value.startswith("admin:") for p in allowed)
        if not has_any_admin_perm:
            raise AdminAccessDeniedException("Administrative access denied. Caller lacks operator authorization.")
        raise AdminPermissionRequiredException(permission.value)


# ---------------------------------------------------------------------------
# System Status, Health & Readiness Endpoints (TRD Sec 9 & 10)
# ---------------------------------------------------------------------------

@router.get(
    "/system/status",
    response_model=StandardSuccessResponse[SystemStatusResponse],
    summary="Get overall system operational status",
)
async def get_system_status(
    request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
) -> StandardSuccessResponse[SystemStatusResponse]:
    """Retrieve composite system operational status across all subsystems and providers."""
    _require_admin_permission(current_user, Permission.ADMIN_SYSTEM_VIEW)
    result = await admin_service.get_system_status(actor=current_user, request_id=_req_id(request))
    return StandardSuccessResponse(data=result, request_id=_req_id(request))


@router.get(
    "/system/health",
    response_model=StandardSuccessResponse[SystemDetailedHealthResponse],
    summary="Get in-depth system operational health and backlog metrics",
)
async def get_system_health(
    request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
) -> StandardSuccessResponse[SystemDetailedHealthResponse]:
    """Retrieve deep operational health telemetry including worker backlog and uptime."""
    _require_admin_permission(current_user, Permission.ADMIN_SYSTEM_VIEW)
    result = await admin_service.get_detailed_health(actor=current_user, request_id=_req_id(request))
    return StandardSuccessResponse(data=result, request_id=_req_id(request))


@router.get(
    "/system/readiness",
    response_model=StandardSuccessResponse[SystemReadinessResponse],
    summary="Get operational readiness probe",
)
async def get_system_readiness(
    request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
) -> StandardSuccessResponse[SystemReadinessResponse]:
    """Inspect core dependency readiness indicating ability to process requests."""
    _require_admin_permission(current_user, Permission.ADMIN_SYSTEM_VIEW)
    result = await admin_service.get_system_readiness(actor=current_user, request_id=_req_id(request))
    return StandardSuccessResponse(data=result, request_id=_req_id(request))


# ---------------------------------------------------------------------------
# Background Job Management Endpoints (TRD Sec 11 & 12)
# ---------------------------------------------------------------------------

@router.get(
    "/jobs",
    response_model=StandardSuccessResponse[AdminJobListResponse],
    summary="List background jobs for administrative inspection",
)
async def list_admin_jobs(
    request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    status: Optional[JobStatus] = None,
    job_type: Optional[JobType] = None,
    patient_id: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
) -> StandardSuccessResponse[AdminJobListResponse]:
    """Inspect asynchronous background jobs with filtering and pagination (PHI-minimized)."""
    _require_admin_permission(current_user, Permission.ADMIN_JOBS_VIEW)
    result = await admin_service.list_jobs(
        skip=skip,
        limit=limit,
        status=status,
        job_type=job_type,
        patient_id=patient_id,
        actor=current_user,
        request_id=_req_id(request),
    )
    return StandardSuccessResponse(data=result, request_id=_req_id(request))


@router.get(
    "/jobs/{job_id}",
    response_model=StandardSuccessResponse[AdminJobSummary],
    summary="Inspect background job details",
)
async def get_admin_job(
    request: Request,
    job_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
) -> StandardSuccessResponse[AdminJobSummary]:
    """Retrieve operational job summary without raw clinical payloads."""
    _require_admin_permission(current_user, Permission.ADMIN_JOBS_VIEW)
    result = await admin_service.get_job(job_id=job_id, actor=current_user, request_id=_req_id(request))
    return StandardSuccessResponse(data=result, request_id=_req_id(request))


@router.post(
    "/jobs/{job_id}/retry",
    response_model=StandardSuccessResponse[JobRetryResponse],
    summary="Idempotently retry a failed background job",
)
async def retry_admin_job(
    request: Request,
    job_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
) -> StandardSuccessResponse[JobRetryResponse]:
    """Queue failed job for idempotent retry. Disallows retry of completed or processing jobs."""
    _require_admin_permission(current_user, Permission.ADMIN_JOBS_MANAGE)
    result = await admin_service.retry_job(job_id=job_id, actor=current_user, request_id=_req_id(request))
    return StandardSuccessResponse(data=result, request_id=_req_id(request))


@router.post(
    "/jobs/{job_id}/cancel",
    response_model=StandardSuccessResponse[JobCancelResponse],
    summary="Cancel an eligible pending or queued job",
)
async def cancel_admin_job(
    request: Request,
    job_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
) -> StandardSuccessResponse[JobCancelResponse]:
    """Cancel a queued background job before execution begins."""
    _require_admin_permission(current_user, Permission.ADMIN_JOBS_MANAGE)
    result = await admin_service.cancel_job(job_id=job_id, actor=current_user, request_id=_req_id(request))
    return StandardSuccessResponse(data=result, request_id=_req_id(request))


# ---------------------------------------------------------------------------
# External Integrations Telemetry & Testing Endpoints (TRD Sec 13 & 14)
# ---------------------------------------------------------------------------

@router.get(
    "/integrations",
    response_model=StandardSuccessResponse[IntegrationListResponse],
    summary="List external integration providers and telemetry",
)
async def list_admin_integrations(
    request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
) -> StandardSuccessResponse[IntegrationListResponse]:
    """Inspect all configured external provider integrations and connectivity status."""
    _require_admin_permission(current_user, Permission.ADMIN_INTEGRATIONS_VIEW)
    result = await admin_service.list_integrations(actor=current_user, request_id=_req_id(request))
    return StandardSuccessResponse(data=result, request_id=_req_id(request))


@router.get(
    "/integrations/{integration_name}",
    response_model=StandardSuccessResponse[IntegrationProviderStatus],
    summary="Inspect specific integration provider status",
)
async def get_admin_integration(
    request: Request,
    integration_name: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
) -> StandardSuccessResponse[IntegrationProviderStatus]:
    """Inspect single external provider telemetry and configuration state."""
    _require_admin_permission(current_user, Permission.ADMIN_INTEGRATIONS_VIEW)
    result = await admin_service.get_integration(
        integration_name=integration_name, actor=current_user, request_id=_req_id(request)
    )
    return StandardSuccessResponse(data=result, request_id=_req_id(request))


@router.post(
    "/integrations/{integration_name}/test",
    response_model=StandardSuccessResponse[IntegrationTestResponse],
    summary="Perform controlled synthetic connectivity test for integration",
)
async def test_admin_integration(
    request: Request,
    integration_name: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    payload: Optional[IntegrationTestRequest] = None,
) -> StandardSuccessResponse[IntegrationTestResponse]:
    """Execute non-PHI synthetic ping against external provider when testing is enabled."""
    _require_admin_permission(current_user, Permission.ADMIN_INTEGRATIONS_VIEW)
    req_payload = payload or IntegrationTestRequest()
    result = await admin_service.test_integration(
        integration_name=integration_name,
        payload=req_payload,
        actor=current_user,
        request_id=_req_id(request),
    )
    return StandardSuccessResponse(data=result, request_id=_req_id(request))


# ---------------------------------------------------------------------------
# Operational Incident Management Endpoints (TRD Sec 15, 16 & 17)
# ---------------------------------------------------------------------------

@router.get(
    "/incidents",
    response_model=StandardSuccessResponse[IncidentListResponse],
    summary="List operational incidents",
)
async def list_admin_incidents(
    request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    incident_service: Annotated[IncidentService, Depends(get_incident_service)],
    status: Optional[IncidentStatus] = None,
    severity: Optional[IncidentSeverity] = None,
    category: Optional[IncidentCategory] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
) -> StandardSuccessResponse[IncidentListResponse]:
    """Query operational incidents with status, severity, and category filtering."""
    _require_admin_permission(current_user, Permission.ADMIN_INCIDENTS_VIEW)
    items, total = await incident_service.list_incidents(
        status=status,
        severity=severity,
        category=category,
        skip=skip,
        limit=limit,
    )
    return StandardSuccessResponse(
        data=IncidentListResponse(items=items, total=total, skip=skip, limit=limit),
        request_id=_req_id(request),
    )


@router.post(
    "/incidents",
    response_model=StandardSuccessResponse[IncidentRecord],
    status_code=status.HTTP_201_CREATED,
    summary="Declare a new operational incident",
)
async def create_admin_incident(
    request: Request,
    payload: IncidentCreate,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    incident_service: Annotated[IncidentService, Depends(get_incident_service)],
) -> StandardSuccessResponse[IncidentRecord]:
    """Declare a new operational incident with severity grading and technical description."""
    _require_admin_permission(current_user, Permission.ADMIN_INCIDENTS_MANAGE)
    incident = await incident_service.create_incident(
        payload=payload,
        actor=current_user,
        request_id=_req_id(request),
    )
    return StandardSuccessResponse(data=incident, request_id=_req_id(request))


@router.get(
    "/incidents/{incident_id}",
    response_model=StandardSuccessResponse[IncidentRecord],
    summary="Get operational incident details",
)
async def get_admin_incident(
    request: Request,
    incident_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    incident_service: Annotated[IncidentService, Depends(get_incident_service)],
) -> StandardSuccessResponse[IncidentRecord]:
    """Retrieve full incident record and investigation log."""
    _require_admin_permission(current_user, Permission.ADMIN_INCIDENTS_VIEW)
    incident = await incident_service.get_incident(incident_id=incident_id)
    return StandardSuccessResponse(data=incident, request_id=_req_id(request))


@router.post(
    "/incidents/{incident_id}/acknowledge",
    response_model=StandardSuccessResponse[IncidentRecord],
    summary="Acknowledge an open operational incident",
)
async def acknowledge_admin_incident(
    request: Request,
    incident_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    incident_service: Annotated[IncidentService, Depends(get_incident_service)],
    payload: Optional[IncidentAcknowledge] = None,
) -> StandardSuccessResponse[IncidentRecord]:
    """Transition incident from OPEN to INVESTIGATING and assign operator ownership."""
    _require_admin_permission(current_user, Permission.ADMIN_INCIDENTS_MANAGE)
    req_payload = payload or IncidentAcknowledge()
    updated = await incident_service.acknowledge_incident(
        incident_id=incident_id,
        payload=req_payload,
        actor=current_user,
        request_id=_req_id(request),
    )
    return StandardSuccessResponse(data=updated, request_id=_req_id(request))


@router.post(
    "/incidents/{incident_id}/update",
    response_model=StandardSuccessResponse[IncidentRecord],
    summary="Update active operational incident",
)
async def update_admin_incident(
    request: Request,
    incident_id: str,
    payload: IncidentUpdate,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    incident_service: Annotated[IncidentService, Depends(get_incident_service)],
) -> StandardSuccessResponse[IncidentRecord]:
    """Update active incident progress notes, severity, or ownership."""
    _require_admin_permission(current_user, Permission.ADMIN_INCIDENTS_MANAGE)
    updated = await incident_service.update_incident(
        incident_id=incident_id,
        payload=payload,
        actor=current_user,
        request_id=_req_id(request),
    )
    return StandardSuccessResponse(data=updated, request_id=_req_id(request))


@router.post(
    "/incidents/{incident_id}/resolve",
    response_model=StandardSuccessResponse[IncidentRecord],
    summary="Resolve or close operational incident",
)
async def resolve_admin_incident(
    request: Request,
    incident_id: str,
    payload: IncidentResolve,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    incident_service: Annotated[IncidentService, Depends(get_incident_service)],
) -> StandardSuccessResponse[IncidentRecord]:
    """Transition operational incident to RESOLVED or CLOSED with mandatory mitigation summary."""
    _require_admin_permission(current_user, Permission.ADMIN_INCIDENTS_MANAGE)
    resolved = await incident_service.resolve_incident(
        incident_id=incident_id,
        payload=payload,
        actor=current_user,
        request_id=_req_id(request),
    )
    return StandardSuccessResponse(data=resolved, request_id=_req_id(request))


# ---------------------------------------------------------------------------
# Audit & Security Events Inspection Endpoints (TRD Sec 22 & 23)
# ---------------------------------------------------------------------------

@router.get(
    "/audit",
    response_model=StandardSuccessResponse[AdminAuditListResponse],
    summary="Query administrative audit trail",
)
async def get_admin_audit(
    request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    event_type: Optional[str] = None,
    actor_id: Optional[str] = None,
    patient_id: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
) -> StandardSuccessResponse[AdminAuditListResponse]:
    """Query immutable audit events. Modifying or deleting audit history is strictly forbidden."""
    _require_admin_permission(current_user, Permission.ADMIN_AUDIT_VIEW)
    items, total = await admin_service.get_audit_records(
        skip=skip,
        limit=limit,
        event_type=event_type,
        actor_id=actor_id,
        patient_id=patient_id,
        actor=current_user,
        request_id=_req_id(request),
    )
    return StandardSuccessResponse(
        data=AdminAuditListResponse(items=items, total=total, skip=skip, limit=limit),
        request_id=_req_id(request),
    )


@router.get(
    "/security-events",
    response_model=StandardSuccessResponse[AdminSecurityEventListResponse],
    summary="Inspect security event audit log",
)
async def get_admin_security_events(
    request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    severity: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
) -> StandardSuccessResponse[AdminSecurityEventListResponse]:
    """Inspect sanitized security audit events (login failures, authorization denials, rate limits)."""
    _require_admin_permission(current_user, Permission.ADMIN_SECURITY_VIEW)
    result = await admin_service.get_security_events(
        skip=skip,
        limit=limit,
        severity=severity,
        actor=current_user,
        request_id=_req_id(request),
    )
    return StandardSuccessResponse(data=result, request_id=_req_id(request))


# ---------------------------------------------------------------------------
# Data Quality & Configuration Inspection Endpoints (TRD Sec 21 & 24)
# ---------------------------------------------------------------------------

@router.get(
    "/data-quality",
    response_model=StandardSuccessResponse[AdminDataQualityOverview],
    summary="Get system-wide data quality overview",
)
async def get_admin_data_quality(
    request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
) -> StandardSuccessResponse[AdminDataQualityOverview]:
    """Inspect platform-level clinical data quality metrics and unresolved reconciliations."""
    _require_admin_permission(current_user, Permission.ADMIN_SYSTEM_VIEW)
    result = await admin_service.get_data_quality_overview(
        actor=current_user, request_id=_req_id(request)
    )
    return StandardSuccessResponse(data=result, request_id=_req_id(request))


@router.get(
    "/configuration",
    response_model=StandardSuccessResponse[Dict[str, Any]],
    summary="Inspect operational configuration and feature flag governance (Phase 25 reuse)",
)
async def get_admin_configuration(
    request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    config_service: Annotated[ConfigurationService, Depends(get_configuration_service)],
) -> StandardSuccessResponse[Dict[str, Any]]:
    """Inspect administrative operational configuration and feature flags without exposing secrets."""
    _require_admin_permission(current_user, Permission.ADMIN_CONFIGURATION_VIEW)
    drift = config_service.detect_drift()
    validation = config_service.validate_configuration()
    data: Dict[str, Any] = {
        "environment": settings.APP_ENV,
        "version": settings.APP_VERSION,
        "is_production": settings.is_production,
        "drift": drift.model_dump(),
        "validation": validation.model_dump(),
        "admin_operations_enabled": settings.ADMIN_OPERATIONS_ENABLED,
        "admin_support_enabled": settings.ADMIN_SUPPORT_ENABLED,
        "admin_job_management_enabled": settings.ADMIN_JOB_MANAGEMENT_ENABLED,
        "admin_incident_management_enabled": settings.ADMIN_INCIDENT_MANAGEMENT_ENABLED,
        "admin_provider_testing_enabled": settings.ADMIN_PROVIDER_TESTING_ENABLED,
    }
    return StandardSuccessResponse(data=data, request_id=_req_id(request))


# ---------------------------------------------------------------------------
# Privacy-Safe Support Lookup (TRD Sec 18, 19 & 20)
# ---------------------------------------------------------------------------

@router.get(
    "/support/patients/search",
    response_model=StandardSuccessResponse[SupportPatientSearchResponse],
    summary="Privacy-safe patient support account lookup",
)
async def search_support_patients(
    request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    support_service: Annotated[SupportService, Depends(get_support_service)],
    query: str = Query(..., min_length=1, max_length=100, description="Patient identifier, phone, or name fragment"),
) -> StandardSuccessResponse[SupportPatientSearchResponse]:
    """Find patient accounts for support troubleshooting with strictly minimized operational fields.
    
    INVARIANT: ZERO clinical notes, diagnoses, medications, allergies, or documents leaked.
    """
    _require_admin_permission(current_user, Permission.ADMIN_SUPPORT_VIEW)
    result = await support_service.search_patient_account(
        query=query, actor=current_user, request_id=_req_id(request)
    )
    return StandardSuccessResponse(data=result, request_id=_req_id(request))
