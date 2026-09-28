"""Data Quality, Clinical Record Integrity & Reconciliation API Endpoints (Phase 26).

Provides endpoints for:
1. Patient-level data quality checks, findings listing, review, and resolution.
2. Cross-source clinical reconciliation execution, inspection, and authorized resolution.
3. Clinician review queue across assigned patients (/clinicians/me/data-quality/...).
"""

from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends, Query, Request, status

from app.api.deps import (
    get_current_user,
    get_patient_service,
    get_authorization_service,
    verify_patient_access,
    get_data_quality_service,
    get_reconciliation_service,
)
from app.core.exceptions import (
    ForbiddenException,
    DataQualityFindingNotFoundException,
    ReconciliationNotFoundException,
    ResourceVersionConflictException,
)
from app.core.policies import Permission, ROLE_PERMISSIONS
from app.core.logging import request_id_ctx_var
from app.schemas.auth import UserRole
from app.schemas.audit import AuditActor
from app.schemas.response import StandardErrorResponse, StandardSuccessResponse
from app.schemas.user import AuthenticatedUserContext
from app.schemas.data_quality import (
    DataQualityFindingResponse,
    DataQualityFindingListResponse,
    DataQualityFindingStatus,
    DataQualityFindingType,
    DataQualitySeverity,
    DataQualityCheckRequest,
    DataQualityCheckResponse,
    DataQualityReviewRequest,
    DataQualityResolutionRequest,
)
from app.schemas.reconciliation import (
    ReconciliationRequest,
    ReconciliationResponse,
    ReconciliationResolveRequest,
    ReconciliationStatus,
    ReconciliationScope,
)
from app.services.data_quality_service import DataQualityService
from app.services.reconciliation_service import ReconciliationService
from app.services.patient_service import PatientService
from app.services.authorization_service import AuthorizationService

router = APIRouter(tags=["Data Quality & Clinical Reconciliation"])

def _req_id(request: Request) -> str:
    return getattr(request.state, "request_id", None) or request_id_ctx_var.get() or "unknown"

def _to_audit_actor(user: AuthenticatedUserContext) -> AuditActor:
    return AuditActor(
        actor_id=user.user_id,
        role=user.role,
        organization_id=getattr(user, "organization_id", None),
        facility_id=getattr(user, "facility_id", None),
    )

def _require_permission(actor: AuthenticatedUserContext, permission: Permission) -> None:
    role_str = actor.role.value if hasattr(actor.role, "value") else str(actor.role)
    allowed = ROLE_PERMISSIONS.get(role_str, frozenset())
    if permission not in allowed:
        raise ForbiddenException(
            message=f"Actor lacks required permission: '{permission.value}'."
        )

# ---------------------------------------------------------------------------
# Patient Data Quality Endpoints (TRD Sec 18)
# ---------------------------------------------------------------------------

@router.get(
    "/patients/{patient_id}/data-quality",
    response_model=StandardSuccessResponse[DataQualityFindingListResponse],
    summary="List patient data quality findings",
)
async def list_patient_data_quality_findings(
    request: Request,
    patient_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    patient_service: Annotated[PatientService, Depends(get_patient_service)],
    authz_service: Annotated[AuthorizationService, Depends(get_authorization_service)],
    dq_service: Annotated[DataQualityService, Depends(get_data_quality_service)],
    status: Optional[DataQualityFindingStatus] = None,
    finding_type: Optional[DataQualityFindingType] = None,
    severity: Optional[DataQualitySeverity] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
) -> StandardSuccessResponse[DataQualityFindingListResponse]:
    await verify_patient_access(
        patient_id=patient_id,
        current_user=current_user,
        patient_service=patient_service,
        authz_service=authz_service,
        action="data_quality:read",
        resource_type="data_quality",
    )
    result = await dq_service.list_findings(
        patient_id=patient_id,
        status=status,
        finding_type=finding_type,
        severity=severity,
        skip=skip,
        limit=limit,
    )
    return StandardSuccessResponse(data=result, request_id=_req_id(request))


@router.post(
    "/patients/{patient_id}/data-quality/check",
    response_model=StandardSuccessResponse[DataQualityCheckResponse],
    summary="Trigger deterministic data quality check for patient",
)
async def run_patient_data_quality_check(
    request: Request,
    patient_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    patient_service: Annotated[PatientService, Depends(get_patient_service)],
    authz_service: Annotated[AuthorizationService, Depends(get_authorization_service)],
    dq_service: Annotated[DataQualityService, Depends(get_data_quality_service)],
    body: Optional[DataQualityCheckRequest] = None,
) -> StandardSuccessResponse[DataQualityCheckResponse]:
    await verify_patient_access(
        patient_id=patient_id,
        current_user=current_user,
        patient_service=patient_service,
        authz_service=authz_service,
        action="data_quality:check",
        resource_type="data_quality",
    )
    actor = _to_audit_actor(current_user)
    result = await dq_service.run_data_quality_checks(
        patient_id=patient_id,
        request=body,
        actor=actor,
    )
    return StandardSuccessResponse(data=result, request_id=_req_id(request))


@router.get(
    "/patients/{patient_id}/data-quality/{finding_id}",
    response_model=StandardSuccessResponse[DataQualityFindingResponse],
    summary="Get single data quality finding",
)
async def get_patient_data_quality_finding(
    request: Request,
    patient_id: str,
    finding_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    patient_service: Annotated[PatientService, Depends(get_patient_service)],
    authz_service: Annotated[AuthorizationService, Depends(get_authorization_service)],
    dq_service: Annotated[DataQualityService, Depends(get_data_quality_service)],
) -> StandardSuccessResponse[DataQualityFindingResponse]:
    await verify_patient_access(
        patient_id=patient_id,
        current_user=current_user,
        patient_service=patient_service,
        authz_service=authz_service,
        action="data_quality:read",
        resource_type="data_quality",
    )
    actor = _to_audit_actor(current_user)
    finding = await dq_service.get_finding(finding_id=finding_id, actor=actor)
    if finding.patient_id != patient_id:
        raise DataQualityFindingNotFoundException(finding_id)
    return StandardSuccessResponse(data=finding, request_id=_req_id(request))


@router.post(
    "/patients/{patient_id}/data-quality/{finding_id}/review",
    response_model=StandardSuccessResponse[DataQualityFindingResponse],
    summary="Clinician review initiated on data quality finding",
)
async def review_patient_data_quality_finding(
    request: Request,
    patient_id: str,
    finding_id: str,
    body: DataQualityReviewRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    patient_service: Annotated[PatientService, Depends(get_patient_service)],
    authz_service: Annotated[AuthorizationService, Depends(get_authorization_service)],
    dq_service: Annotated[DataQualityService, Depends(get_data_quality_service)],
) -> StandardSuccessResponse[DataQualityFindingResponse]:
    _require_permission(current_user, Permission.DATA_QUALITY_REVIEW)
    await verify_patient_access(
        patient_id=patient_id,
        current_user=current_user,
        patient_service=patient_service,
        authz_service=authz_service,
        action="data_quality:review",
        resource_type="data_quality",
    )
    finding = await dq_service.get_finding(finding_id)
    if finding.patient_id != patient_id:
        raise DataQualityFindingNotFoundException(finding_id)

    actor = _to_audit_actor(current_user)
    updated = await dq_service.review_finding(
        finding_id=finding_id,
        request=body,
        reviewer_id=current_user.user_id,
        actor=actor,
    )
    return StandardSuccessResponse(data=updated, request_id=_req_id(request))


@router.post(
    "/patients/{patient_id}/data-quality/{finding_id}/resolve",
    response_model=StandardSuccessResponse[DataQualityFindingResponse],
    summary="Resolve data quality finding with optimistic concurrency check",
)
async def resolve_patient_data_quality_finding(
    request: Request,
    patient_id: str,
    finding_id: str,
    body: DataQualityResolutionRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    patient_service: Annotated[PatientService, Depends(get_patient_service)],
    authz_service: Annotated[AuthorizationService, Depends(get_authorization_service)],
    dq_service: Annotated[DataQualityService, Depends(get_data_quality_service)],
) -> StandardSuccessResponse[DataQualityFindingResponse]:
    _require_permission(current_user, Permission.DATA_QUALITY_RESOLVE)
    await verify_patient_access(
        patient_id=patient_id,
        current_user=current_user,
        patient_service=patient_service,
        authz_service=authz_service,
        action="data_quality:resolve",
        resource_type="data_quality",
    )
    finding = await dq_service.get_finding(finding_id)
    if finding.patient_id != patient_id:
        raise DataQualityFindingNotFoundException(finding_id)

    actor = _to_audit_actor(current_user)
    resolved = await dq_service.resolve_finding(
        finding_id=finding_id,
        request=body,
        resolver_id=current_user.user_id,
        actor=actor,
    )
    return StandardSuccessResponse(data=resolved, request_id=_req_id(request))


# ---------------------------------------------------------------------------
# Patient Reconciliation Endpoints (TRD Sec 18)
# ---------------------------------------------------------------------------

@router.post(
    "/patients/{patient_id}/data-quality/reconcile",
    response_model=StandardSuccessResponse[ReconciliationResponse],
    summary="Trigger cross-source clinical reconciliation",
)
async def reconcile_patient_clinical_data(
    request: Request,
    patient_id: str,
    body: ReconciliationRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    patient_service: Annotated[PatientService, Depends(get_patient_service)],
    authz_service: Annotated[AuthorizationService, Depends(get_authorization_service)],
    rec_service: Annotated[ReconciliationService, Depends(get_reconciliation_service)],
) -> StandardSuccessResponse[ReconciliationResponse]:
    _require_permission(current_user, Permission.RECONCILIATION_EXECUTE)
    await verify_patient_access(
        patient_id=patient_id,
        current_user=current_user,
        patient_service=patient_service,
        authz_service=authz_service,
        action="reconciliation:execute",
        resource_type="clinical_reconciliation",
    )
    actor = _to_audit_actor(current_user)
    result = await rec_service.reconcile_patient(
        patient_id=patient_id,
        request=body,
        actor=actor,
    )
    return StandardSuccessResponse(data=result, request_id=_req_id(request))


@router.get(
    "/patients/{patient_id}/reconciliation",
    response_model=StandardSuccessResponse[List[ReconciliationResponse]],
    summary="List patient reconciliation records",
)
async def list_patient_reconciliation_records(
    request: Request,
    patient_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    patient_service: Annotated[PatientService, Depends(get_patient_service)],
    authz_service: Annotated[AuthorizationService, Depends(get_authorization_service)],
    rec_service: Annotated[ReconciliationService, Depends(get_reconciliation_service)],
    status: Optional[ReconciliationStatus] = None,
    scope: Optional[ReconciliationScope] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
) -> StandardSuccessResponse[List[ReconciliationResponse]]:
    await verify_patient_access(
        patient_id=patient_id,
        current_user=current_user,
        patient_service=patient_service,
        authz_service=authz_service,
        action="reconciliation:read",
        resource_type="clinical_reconciliation",
    )
    records = await rec_service.list_by_patient(
        patient_id=patient_id,
        status=status,
        scope=scope,
        skip=skip,
        limit=limit,
    )
    return StandardSuccessResponse(data=records, request_id=_req_id(request))


@router.get(
    "/patients/{patient_id}/reconciliation/{reconciliation_id}",
    response_model=StandardSuccessResponse[ReconciliationResponse],
    summary="Get single reconciliation record",
)
async def get_patient_reconciliation_record(
    request: Request,
    patient_id: str,
    reconciliation_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    patient_service: Annotated[PatientService, Depends(get_patient_service)],
    authz_service: Annotated[AuthorizationService, Depends(get_authorization_service)],
    rec_service: Annotated[ReconciliationService, Depends(get_reconciliation_service)],
) -> StandardSuccessResponse[ReconciliationResponse]:
    await verify_patient_access(
        patient_id=patient_id,
        current_user=current_user,
        patient_service=patient_service,
        authz_service=authz_service,
        action="reconciliation:read",
        resource_type="clinical_reconciliation",
    )
    record = await rec_service.get_reconciliation(reconciliation_id)
    if record.patient_id != patient_id:
        raise ReconciliationNotFoundException(reconciliation_id)
    return StandardSuccessResponse(data=record, request_id=_req_id(request))


@router.post(
    "/patients/{patient_id}/reconciliation/{reconciliation_id}/resolve",
    response_model=StandardSuccessResponse[ReconciliationResponse],
    summary="Resolve reconciliation conflict decisions",
)
async def resolve_patient_reconciliation(
    request: Request,
    patient_id: str,
    reconciliation_id: str,
    body: ReconciliationResolveRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    patient_service: Annotated[PatientService, Depends(get_patient_service)],
    authz_service: Annotated[AuthorizationService, Depends(get_authorization_service)],
    rec_service: Annotated[ReconciliationService, Depends(get_reconciliation_service)],
) -> StandardSuccessResponse[ReconciliationResponse]:
    _require_permission(current_user, Permission.RECONCILIATION_RESOLVE)
    await verify_patient_access(
        patient_id=patient_id,
        current_user=current_user,
        patient_service=patient_service,
        authz_service=authz_service,
        action="reconciliation:resolve",
        resource_type="clinical_reconciliation",
    )
    record = await rec_service.get_reconciliation(reconciliation_id)
    if record.patient_id != patient_id:
        raise ReconciliationNotFoundException(reconciliation_id)

    actor = _to_audit_actor(current_user)
    resolved = await rec_service.resolve_reconciliation(
        reconciliation_id=reconciliation_id,
        request=body,
        resolver_id=current_user.user_id,
        actor=actor,
    )
    return StandardSuccessResponse(data=resolved, request_id=_req_id(request))


# ---------------------------------------------------------------------------
# Clinician Review APIs (TRD Sec 19)
# ---------------------------------------------------------------------------

@router.get(
    "/clinicians/me/data-quality/findings",
    response_model=StandardSuccessResponse[List[DataQualityFindingResponse]],
    summary="List pending data quality findings for clinician review queue",
)
async def list_clinician_pending_findings(
    request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    dq_service: Annotated[DataQualityService, Depends(get_data_quality_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
) -> StandardSuccessResponse[List[DataQualityFindingResponse]]:
    _require_permission(current_user, Permission.DATA_QUALITY_REVIEW)
    findings = await dq_service.list_all_pending(skip=skip, limit=limit)
    return StandardSuccessResponse(data=findings, request_id=_req_id(request))


@router.get(
    "/clinicians/me/patients/{patient_id}/data-quality",
    response_model=StandardSuccessResponse[DataQualityFindingListResponse],
    summary="Clinician access patient data quality findings",
)
async def get_clinician_patient_data_quality(
    request: Request,
    patient_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    patient_service: Annotated[PatientService, Depends(get_patient_service)],
    authz_service: Annotated[AuthorizationService, Depends(get_authorization_service)],
    dq_service: Annotated[DataQualityService, Depends(get_data_quality_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
) -> StandardSuccessResponse[DataQualityFindingListResponse]:
    _require_permission(current_user, Permission.DATA_QUALITY_READ)
    await verify_patient_access(
        patient_id=patient_id,
        current_user=current_user,
        patient_service=patient_service,
        authz_service=authz_service,
        action="data_quality:read",
        resource_type="data_quality",
    )
    result = await dq_service.list_findings(
        patient_id=patient_id,
        skip=skip,
        limit=limit,
    )
    return StandardSuccessResponse(data=result, request_id=_req_id(request))


@router.post(
    "/clinicians/me/data-quality/{finding_id}/review",
    response_model=StandardSuccessResponse[DataQualityFindingResponse],
    summary="Clinician review on finding",
)
async def clinician_review_finding(
    request: Request,
    finding_id: str,
    body: DataQualityReviewRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    patient_service: Annotated[PatientService, Depends(get_patient_service)],
    authz_service: Annotated[AuthorizationService, Depends(get_authorization_service)],
    dq_service: Annotated[DataQualityService, Depends(get_data_quality_service)],
) -> StandardSuccessResponse[DataQualityFindingResponse]:
    _require_permission(current_user, Permission.DATA_QUALITY_REVIEW)
    finding = await dq_service.get_finding(finding_id)
    await verify_patient_access(
        patient_id=finding.patient_id,
        current_user=current_user,
        patient_service=patient_service,
        authz_service=authz_service,
        action="data_quality:review",
        resource_type="data_quality",
    )
    actor = _to_audit_actor(current_user)
    updated = await dq_service.review_finding(
        finding_id=finding_id,
        request=body,
        reviewer_id=current_user.user_id,
        actor=actor,
    )
    return StandardSuccessResponse(data=updated, request_id=_req_id(request))


@router.post(
    "/clinicians/me/data-quality/{finding_id}/resolve",
    response_model=StandardSuccessResponse[DataQualityFindingResponse],
    summary="Clinician resolve finding",
)
async def clinician_resolve_finding(
    request: Request,
    finding_id: str,
    body: DataQualityResolutionRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    patient_service: Annotated[PatientService, Depends(get_patient_service)],
    authz_service: Annotated[AuthorizationService, Depends(get_authorization_service)],
    dq_service: Annotated[DataQualityService, Depends(get_data_quality_service)],
) -> StandardSuccessResponse[DataQualityFindingResponse]:
    _require_permission(current_user, Permission.DATA_QUALITY_RESOLVE)
    finding = await dq_service.get_finding(finding_id)
    await verify_patient_access(
        patient_id=finding.patient_id,
        current_user=current_user,
        patient_service=patient_service,
        authz_service=authz_service,
        action="data_quality:resolve",
        resource_type="data_quality",
    )
    actor = _to_audit_actor(current_user)
    resolved = await dq_service.resolve_finding(
        finding_id=finding_id,
        request=body,
        resolver_id=current_user.user_id,
        actor=actor,
    )
    return StandardSuccessResponse(data=resolved, request_id=_req_id(request))
