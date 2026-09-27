"""Patient profile and clinical summary endpoints."""

from typing import Annotated, Any
from fastapi import APIRouter, Depends, Request, status

from app.api.deps import (
    get_audit_service,
    get_authorization_service,
    get_clinical_record_service,
    get_current_user,
    get_patient_service,
    verify_patient_access,
)
from app.core.logging import request_id_ctx_var
from app.schemas.clinical_summary import ClinicalSummaryResponse
from app.schemas.patient import PatientResponse, PatientUpdateRequest
from app.schemas.response import StandardErrorResponse, StandardSuccessResponse
from app.schemas.user import AuthenticatedUserContext
from app.services.audit_service import AuditService
from app.services.authorization_service import AuthorizationService
from app.services.clinical_record_service import ClinicalRecordService
from app.services.patient_service import PatientService

router = APIRouter(prefix="/patients", tags=["Patients"])


def _req_id(request: Request) -> str:
    return getattr(request.state, "request_id", None) or request_id_ctx_var.get() or "unknown"


@router.get(
    "/{patient_id}",
    response_model=StandardSuccessResponse[PatientResponse],
    summary="Get patient profile",
    description="Retrieve patient demographic profile. Subject to ownership and authorization policies.",
    responses={
        401: {"model": StandardErrorResponse, "description": "Authentication required"},
        403: {"model": StandardErrorResponse, "description": "Access denied"},
        404: {"model": StandardErrorResponse, "description": "Patient not found"},
    },
)
async def get_patient_profile(
    request: Request,
    patient_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    patient_service: Annotated[PatientService, Depends(get_patient_service)],
    authz_service: Annotated[AuthorizationService, Depends(get_authorization_service)],
    audit_service: Annotated[AuditService, Depends(get_audit_service)],
) -> StandardSuccessResponse[PatientResponse]:
    """Retrieve patient demographic profile."""
    patient = await verify_patient_access(
        patient_id=patient_id,
        current_user=current_user,
        patient_service=patient_service,
        authz_service=authz_service,
        action="patient_profile:read",
        resource_type="patient_profile",
    )
    await audit_service.record_clinical_record_viewed(
        actor_id=current_user.user_id,
        patient_id=patient_id,
        resource_type="patient",
    )
    return StandardSuccessResponse(data=patient, request_id=_req_id(request))


@router.patch(
    "/{patient_id}",
    response_model=StandardSuccessResponse[PatientResponse],
    summary="Update patient profile",
    description="Update permitted demographic and contact fields for patient. Self-update only.",
    responses={
        401: {"model": StandardErrorResponse, "description": "Authentication required"},
        403: {"model": StandardErrorResponse, "description": "Access denied"},
        404: {"model": StandardErrorResponse, "description": "Patient not found"},
        422: {"model": StandardErrorResponse, "description": "Validation error"},
    },
)
async def update_patient_profile(
    request: Request,
    patient_id: str,
    body: PatientUpdateRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    patient_service: Annotated[PatientService, Depends(get_patient_service)],
    authz_service: Annotated[AuthorizationService, Depends(get_authorization_service)],
    audit_service: Annotated[AuditService, Depends(get_audit_service)],
) -> StandardSuccessResponse[PatientResponse]:
    """Update patient demographic profile."""
    await verify_patient_access(
        patient_id=patient_id,
        current_user=current_user,
        patient_service=patient_service,
        authz_service=authz_service,
        action="patient_profile:update",
        resource_type="patient_profile",
    )
    updated = await patient_service.update_patient(patient_id=patient_id, request=body)
    await audit_service.record_patient_profile_updated(
        actor_id=current_user.user_id,
        patient_id=patient_id,
        updated_fields=list(body.model_dump(exclude_unset=True).keys()),
    )
    return StandardSuccessResponse(data=updated, request_id=_req_id(request))


@router.get(
    "/{patient_id}/clinical-summary",
    response_model=StandardSuccessResponse[ClinicalSummaryResponse],
    summary="Get patient clinical summary",
    description="Assembles a controlled clinical summary including active conditions, allergies, vitals, and encounters.",
    responses={
        401: {"model": StandardErrorResponse, "description": "Authentication required"},
        403: {"model": StandardErrorResponse, "description": "Access denied"},
        404: {"model": StandardErrorResponse, "description": "Patient not found"},
    },
)
async def get_patient_clinical_summary(
    request: Request,
    patient_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    patient_service: Annotated[PatientService, Depends(get_patient_service)],
    clinical_service: Annotated[ClinicalRecordService, Depends(get_clinical_record_service)],
    authz_service: Annotated[AuthorizationService, Depends(get_authorization_service)],
    audit_service: Annotated[AuditService, Depends(get_audit_service)],
) -> StandardSuccessResponse[ClinicalSummaryResponse]:
    """Retrieve assembled clinical summary."""
    patient = await verify_patient_access(
        patient_id=patient_id,
        current_user=current_user,
        patient_service=patient_service,
        authz_service=authz_service,
        action="clinical_summary:read",
        resource_type="clinical_summary",
    )
    summary = await clinical_service.get_clinical_summary(
        patient_id=patient_id,
        patient_profile=patient,
    )
    await audit_service.record_clinical_summary_viewed(
        actor_id=current_user.user_id,
        patient_id=patient_id,
    )
    return StandardSuccessResponse(data=summary, request_id=_req_id(request))


@router.get(
    "/{patient_id}/full-record",
    summary="Get unified longitudinal patient record",
    description="Returns verified medications, allergies, timeline, and demographics with cross-computer persistence and zero dummy data for new users.",
)
async def get_patient_full_record(
    patient_id: str,
    request: Request,
) -> dict[str, Any]:
    """Retrieve full patient record across devices with zero dummy data for new accounts."""
    from app.core.exceptions import NotFoundException
    from app.core.user_profile_store import get_patient_record

    record = get_patient_record(patient_id)
    if not record:
        raise NotFoundException(f"Patient record for '{patient_id}' not found.")
    return {"success": True, "data": record, "request_id": _req_id(request)}


@router.post(
    "/{patient_id}/full-record",
    summary="Sync and update longitudinal patient record",
    description="Updates medications, allergies, timeline events, or demographics, persisting across devices.",
)
async def sync_patient_full_record(
    patient_id: str,
    request: Request,
    body: dict[str, Any],
) -> dict[str, Any]:
    """Update and persist patient medications, timeline, or profile cross-device."""
    from app.core.user_profile_store import get_patient_record, save_patient_record

    clean_id = patient_id.strip().upper()
    existing = get_patient_record(clean_id) or {
        "patient_id": clean_id,
        "name": body.get("name", "Registered Patient"),
        "age": body.get("age", 30),
        "gender": body.get("gender", "Other"),
        "bloodGroup": body.get("bloodGroup", "Not Specified"),
        "city": body.get("city", "Not Specified"),
        "phone": body.get("phone", ""),
        "emergencyContact": body.get("emergencyContact", ""),
        "medications": [],
        "allergies": [],
        "timeline": [],
        "access_requests": [],
    }

    # Merge demographics if provided
    for field in ["name", "age", "gender", "bloodGroup", "city", "phone", "emergencyContact"]:
        if field in body and body[field] is not None:
            existing[field] = body[field]

    # Update medications if provided
    if "medications" in body and isinstance(body["medications"], list):
        existing["medications"] = body["medications"]

    # Update allergies if provided
    if "allergies" in body and isinstance(body["allergies"], list):
        existing["allergies"] = body["allergies"]

    # Update timeline if provided
    if "timeline" in body and isinstance(body["timeline"], list):
        existing["timeline"] = body["timeline"]

    updated = save_patient_record(clean_id, existing)
    return {"success": True, "data": updated, "request_id": _req_id(request)}

