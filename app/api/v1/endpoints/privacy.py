"""Privacy, Retention Lifecycle, and Patient Data Export Endpoints (Phase 24).

Implements RESTful contracts for:
- Patient-initiated and clinician-authorized data exports
- Ephemeral download credentials with bounded TTL
- Public governance and data access policy metadata
- Administrative retention management, holds, and controlled deletion
- Non-production de-identification transformation workflows
"""

from typing import Annotated, Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, Request, status

from app.api.deps import (
    get_current_user,
    get_data_export_service,
    get_deidentification_service,
    get_job_service,
    get_privacy_service,
    get_pseudonymization_service,
    get_retention_service,
)
from app.core.config import get_settings
from app.core.exceptions import (
    ForbiddenException,
    PrivacyPolicyDeniedException,
    UnauthorizedException,
)
from app.core.privacy import DataClassification, DataProcessingPurpose
from app.schemas.auth import UserRole
from app.schemas.data_export import (
    DataExportDownloadResponse,
    DataExportRequest,
    DataExportResponse,
)
from app.schemas.privacy import (
    ControlledDeletionRequest,
    DataAccessPolicyResponse,
    DeletionEligibilityCheck,
    LegalHold,
    LegalHoldCreateRequest,
    PrivacyEvaluationRequest,
    PrivacyEvaluationResponse,
    RetentionPolicy,
)
from app.schemas.user import AuthenticatedUserContext
from app.services.data_export_service import DataExportService
from app.services.deidentification_service import DeidentificationService
from app.services.job_service import JobService
from app.services.privacy_service import PrivacyService
from app.services.pseudonymization_service import PseudonymizationService
from app.services.retention_service import RetentionService

router = APIRouter(tags=["Data Privacy & Governance"])


# ---------------------------------------------------------------------------
# 1. Patient Data Export APIs (TRD Sec 18, 42)
# ---------------------------------------------------------------------------

@router.post(
    "/patients/{patient_id}/data-export",
    response_model=DataExportResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Initiate patient data export",
)
async def request_patient_data_export(
    patient_id: str,
    payload: DataExportRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    export_service: Annotated[DataExportService, Depends(get_data_export_service)],
) -> DataExportResponse:
    """Request an asynchronous data export bundle for a patient.
    
    Access requires either the patient themselves or an authorized clinician with consent.
    """
    return await export_service.initiate_export(
        actor=current_user,
        patient_id=patient_id,
        request=payload,
    )


@router.get(
    "/patients/{patient_id}/data-export/{export_id}",
    response_model=DataExportResponse,
    summary="Get status of patient data export",
)
async def get_patient_data_export_status(
    patient_id: str,
    export_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    export_service: Annotated[DataExportService, Depends(get_data_export_service)],
) -> DataExportResponse:
    """Check progress or retrieval metadata for a previously initiated data export."""
    return await export_service.get_export_status(
        actor=current_user,
        patient_id=patient_id,
        export_id=export_id,
    )


@router.post(
    "/patients/{patient_id}/data-export/{export_id}/download",
    response_model=DataExportDownloadResponse,
    summary="Generate ephemeral download credential for ready export",
)
async def download_patient_data_export(
    patient_id: str,
    export_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    export_service: Annotated[DataExportService, Depends(get_data_export_service)],
) -> DataExportDownloadResponse:
    """Obtain a short-lived download token (never permanent public URL) for ready export."""
    return await export_service.generate_download_token(
        actor=current_user,
        patient_id=patient_id,
        export_id=export_id,
    )


# ---------------------------------------------------------------------------
# 2. Public / Active Governance Policy Metadata (TRD Sec 42)
# ---------------------------------------------------------------------------

@router.get(
    "/privacy/data-access-policy",
    response_model=DataAccessPolicyResponse,
    summary="Retrieve active data access policy and classification framework",
)
async def get_data_access_policy(
    retention_service: Annotated[RetentionService, Depends(get_retention_service)],
) -> DataAccessPolicyResponse:
    """Retrieve metadata describing supported processing purposes, data classifications, and active rules."""
    settings = get_settings()
    return DataAccessPolicyResponse(
        privacy_controls_enabled=settings.PRIVACY_CONTROLS_ENABLED,
        supported_purposes=[p.value for p in DataProcessingPurpose],
        classifications=[c.value for c in DataClassification],
        active_policies_count=len(retention_service.list_policies()),
        active_holds_count=len(retention_service.list_all_holds()),
        governance_framework="HealthSetu Data Governance & Privacy Architecture (Phase 24)",
    )


@router.post(
    "/privacy/evaluate-access",
    response_model=PrivacyEvaluationResponse,
    summary="Evaluate access against privacy policy and purpose",
)
async def evaluate_privacy_access(
    payload: PrivacyEvaluationRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    privacy_service: Annotated[PrivacyService, Depends(get_privacy_service)],
) -> PrivacyEvaluationResponse:
    """Dry-run test whether an operation is permitted under privacy governance and purpose rules."""
    return await privacy_service.evaluate_access(
        actor=current_user,
        resource_type=payload.resource_type,
        resource_id=payload.resource_id,
        purpose=payload.purpose,
        patient_id=payload.patient_id,
    )


# ---------------------------------------------------------------------------
# 3. Administrative Governance & Retention APIs (TRD Sec 42)
# ---------------------------------------------------------------------------

@router.get(
    "/admin/privacy/retention-status",
    summary="Admin view of retention policies, active holds, and lifecycle status",
)
async def get_admin_retention_status(
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    retention_service: Annotated[RetentionService, Depends(get_retention_service)],
) -> Dict[str, Any]:
    """Administrative overview of active policies and legal holds."""
    if current_user.role != UserRole.ADMIN:
        raise ForbiddenException("Administrator privileges required.")

    policies = retention_service.list_policies()
    holds = retention_service.list_all_holds()

    return {
        "active_policies": [p.model_dump() for p in policies],
        "active_holds": [h.model_dump() for h in holds],
        "total_policies": len(policies),
        "total_holds": len(holds),
    }


@router.post(
    "/admin/privacy/retention/run",
    summary="Trigger retention evaluation and cleanup cycle",
)
async def run_retention_cleanup(
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    export_service: Annotated[DataExportService, Depends(get_data_export_service)],
) -> Dict[str, Any]:
    """Execute cleanup cycle to purge expired exports and scratch temporary data."""
    if current_user.role != UserRole.ADMIN:
        raise ForbiddenException("Administrator privileges required.")

    purged = await export_service.purge_expired_exports()
    return {
        "status": "COMPLETED",
        "purged_exports_count": purged,
    }


@router.get(
    "/admin/privacy/jobs/{job_id}",
    summary="Admin view of asynchronous privacy or retention job details",
)
async def get_admin_privacy_job(
    job_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    job_service: Annotated[JobService, Depends(get_job_service)],
) -> Dict[str, Any]:
    """Retrieve detailed execution trace of an asynchronous privacy job."""
    if current_user.role != UserRole.ADMIN:
        raise ForbiddenException("Administrator privileges required.")

    job = await job_service.get_job(job_id=job_id, actor=current_user, is_admin=True)
    return {
        "id": job.id,
        "job_type": job.job_type.value,
        "status": job.status.value,
        "attempt": job.attempt,
        "max_retries": job.max_retries,
        "error_message": job.error_message,
        "created_at": job.created_at.isoformat(),
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }


@router.post(
    "/admin/privacy/holds",
    response_model=LegalHold,
    status_code=status.HTTP_201_CREATED,
    summary="Place legal or organizational hold on a resource",
)
async def create_legal_hold(
    payload: LegalHoldCreateRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    retention_service: Annotated[RetentionService, Depends(get_retention_service)],
) -> LegalHold:
    """Place a preservation hold to forbid resource deletion regardless of retention policies."""
    if current_user.role != UserRole.ADMIN:
        raise ForbiddenException("Administrator privileges required.")

    return await retention_service.place_hold(request=payload, actor_id=current_user.id)


@router.delete(
    "/admin/privacy/holds/{hold_id}",
    summary="Release an active legal hold",
)
async def release_legal_hold(
    hold_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    retention_service: Annotated[RetentionService, Depends(get_retention_service)],
) -> Dict[str, Any]:
    """Release a previously placed legal or organizational hold."""
    if current_user.role != UserRole.ADMIN:
        raise ForbiddenException("Administrator privileges required.")

    released = await retention_service.release_hold(hold_id=hold_id, actor_id=current_user.id)
    return {"released": released, "hold_id": hold_id}


@router.post(
    "/admin/privacy/delete-resource",
    summary="Execute controlled resource deletion (fails closed if held or uncertain)",
)
async def delete_resource_controlled(
    payload: ControlledDeletionRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    retention_service: Annotated[RetentionService, Depends(get_retention_service)],
) -> Dict[str, Any]:
    """Execute controlled deletion following fail-closed hold checks and dependency validation."""
    if current_user.role != UserRole.ADMIN:
        raise ForbiddenException("Administrator privileges required.")

    deleted = await retention_service.execute_deletion(
        resource_type=payload.resource_type,
        resource_id=payload.resource_id,
        actor_id=current_user.id,
        reason=payload.reason,
        force=payload.force,
        patient_id=payload.patient_id,
    )
    return {"deleted": deleted, "resource_id": payload.resource_id}


@router.post(
    "/admin/privacy/deidentify",
    summary="Execute batch de-identification for non-production datasets",
)
async def deidentify_dataset(
    payload: Dict[str, Any],
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    deid_service: Annotated[DeidentificationService, Depends(get_deidentification_service)],
) -> Dict[str, Any]:
    """Transform dataset to redact names, dates, phones, emails, and apply non-legal disclaimer."""
    if current_user.role != UserRole.ADMIN:
        raise ForbiddenException("Administrator privileges required.")

    records = payload.get("records", [])
    reason = payload.get("reason", "Administrative de-identification request")
    transformed = await deid_service.deidentify_patient_dataset(
        records=records,
        actor_id=current_user.id,
        reason=reason,
    )
    return {
        "record_count": len(transformed),
        "records": transformed,
    }
