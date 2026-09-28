"""Medical document management and processing endpoints."""

from typing import Annotated
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Query, Request, UploadFile, status

from app.api.deps import (
    get_audit_service,
    get_authorization_service,
    get_current_user,
    get_document_processing_service,
    get_document_service,
    get_patient_service,
    verify_patient_access,
)
from app.core.exceptions import ValidationException
from app.core.logging import request_id_ctx_var
from app.schemas.auth import UserRole
from app.schemas.document import (
    DocumentDownloadResponse,
    DocumentListResponse,
    DocumentResponse,
    DocumentRetryResponse,
    DocumentSource,
    DocumentType,
    ExtractionResultResponse,
)
from app.schemas.response import StandardErrorResponse, StandardSuccessResponse
from app.schemas.user import AuthenticatedUserContext
from app.services.audit_service import AuditService
from app.services.authorization_service import AuthorizationService
from app.services.document_processing_service import DocumentProcessingService
from app.services.document_service import DocumentService
from app.services.patient_service import PatientService

router = APIRouter(prefix="/patients/{patient_id}/documents", tags=["Medical Documents"])


def _req_id(request: Request) -> str:
    return getattr(request.state, "request_id", None) or request_id_ctx_var.get() or "unknown"


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=StandardSuccessResponse[DocumentResponse],
    summary="Upload medical document",
    description="Upload a medical document (PDF, PNG, JPEG, WEBP). Validates MIME type, file size, signature, and enqueues background OCR processing.",
    responses={
        401: {"model": StandardErrorResponse, "description": "Authentication required"},
        403: {"model": StandardErrorResponse, "description": "Access denied"},
        404: {"model": StandardErrorResponse, "description": "Patient not found"},
        422: {"model": StandardErrorResponse, "description": "Validation error or invalid file"},
    },
)
async def upload_document(
    request: Request,
    patient_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    document_type: DocumentType = Form(default=DocumentType.OTHER_MEDICAL_DOCUMENT),
    source: DocumentSource | None = Form(default=None),
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)] = None,
    patient_service: Annotated[PatientService, Depends(get_patient_service)] = None,
    document_service: Annotated[DocumentService, Depends(get_document_service)] = None,
    doc_processing_service: Annotated[DocumentProcessingService, Depends(get_document_processing_service)] = None,
    authz_service: Annotated[AuthorizationService, Depends(get_authorization_service)] = None,
    audit_service: Annotated[AuditService, Depends(get_audit_service)] = None,
) -> StandardSuccessResponse[DocumentResponse]:
    """Upload and enqueue a medical document."""
    await verify_patient_access(
        patient_id=patient_id,
        current_user=current_user,
        patient_service=patient_service,
        authz_service=authz_service,
        action="document:upload",
        resource_type="document",
    )

    # Establish trusted provenance: do not allow users to claim arbitrary sources
    if current_user.role == UserRole.PATIENT:
        effective_source = DocumentSource.PATIENT_UPLOAD
    elif current_user.role == UserRole.DOCTOR:
        effective_source = source if source in (DocumentSource.DOCTOR_UPLOAD, DocumentSource.CLINIC_UPLOAD) else DocumentSource.DOCTOR_UPLOAD
    else:
        effective_source = DocumentSource.SYSTEM

    file_bytes = await file.read()
    raw_filename = file.filename or "upload.bin"
    content_type = file.content_type or "application/octet-stream"

    doc_record = await document_service.upload_document(
        patient_id=patient_id,
        uploader_id=current_user.user_id,
        file_bytes=file_bytes,
        filename=raw_filename,
        content_type=content_type,
        document_type=document_type,
        source=effective_source,
    )

    # Enqueue background processing job
    await doc_processing_service.enqueue_document(doc_record, actor_id=current_user.user_id)
    background_tasks.add_task(
        doc_processing_service.process_document_job,
        doc_record.id,
        current_user.user_id,
    )

    await audit_service.record_document_uploaded(
        actor_id=current_user.user_id,
        patient_id=patient_id,
        document_id=doc_record.id,
        document_type=doc_record.document_type.value,
        filename=doc_record.filename,
        size_bytes=doc_record.size_bytes,
    )

    response_data = DocumentResponse.model_validate(doc_record)
    return StandardSuccessResponse(data=response_data, request_id=_req_id(request))


@router.get(
    "",
    response_model=StandardSuccessResponse[DocumentListResponse],
    summary="List patient documents",
    description="Retrieve all document metadata records for a patient.",
    responses={
        401: {"model": StandardErrorResponse, "description": "Authentication required"},
        403: {"model": StandardErrorResponse, "description": "Access denied"},
        404: {"model": StandardErrorResponse, "description": "Patient not found"},
    },
)
async def list_documents(
    request: Request,
    patient_id: str,
    include_archived: bool = False,
    limit: Annotated[int, Query(ge=1, le=100, description="Page size limit (max 100)")] = 25,
    offset: Annotated[int, Query(ge=0, description="Page offset")] = 0,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)] = None,
    patient_service: Annotated[PatientService, Depends(get_patient_service)] = None,
    document_service: Annotated[DocumentService, Depends(get_document_service)] = None,
    authz_service: Annotated[AuthorizationService, Depends(get_authorization_service)] = None,
    audit_service: Annotated[AuditService, Depends(get_audit_service)] = None,
) -> StandardSuccessResponse[DocumentListResponse]:
    """List documents for patient with bounded pagination."""
    await verify_patient_access(
        patient_id=patient_id,
        current_user=current_user,
        patient_service=patient_service,
        authz_service=authz_service,
        action="document:read",
        resource_type="document",
    )
    items = await document_service.list_documents(patient_id, include_archived=include_archived)
    await audit_service.record_clinical_record_viewed(
        actor_id=current_user.user_id,
        patient_id=patient_id,
        resource_type="document",
    )
    paginated_items = items[offset : offset + limit]
    return StandardSuccessResponse(
        data=DocumentListResponse(items=paginated_items, total=len(items)),
        request_id=_req_id(request),
    )


@router.get(
    "/{document_id}",
    response_model=StandardSuccessResponse[DocumentResponse],
    summary="Get document metadata",
    description="Retrieve metadata and processing status for a single document.",
    responses={
        401: {"model": StandardErrorResponse, "description": "Authentication required"},
        403: {"model": StandardErrorResponse, "description": "Access denied"},
        404: {"model": StandardErrorResponse, "description": "Document not found"},
    },
)
async def get_document(
    request: Request,
    patient_id: str,
    document_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)] = None,
    patient_service: Annotated[PatientService, Depends(get_patient_service)] = None,
    document_service: Annotated[DocumentService, Depends(get_document_service)] = None,
    authz_service: Annotated[AuthorizationService, Depends(get_authorization_service)] = None,
    audit_service: Annotated[AuditService, Depends(get_audit_service)] = None,
) -> StandardSuccessResponse[DocumentResponse]:
    """Retrieve metadata for a specific document."""
    await verify_patient_access(
        patient_id=patient_id,
        current_user=current_user,
        patient_service=patient_service,
        authz_service=authz_service,
        action="document:read",
        resource_type="document",
        resource_id=document_id,
    )
    doc = await document_service.get_document(patient_id, document_id)
    await audit_service.record_document_viewed(
        actor_id=current_user.user_id,
        patient_id=patient_id,
        document_id=document_id,
    )
    return StandardSuccessResponse(data=doc, request_id=_req_id(request))


@router.get(
    "/{document_id}/download",
    response_model=StandardSuccessResponse[DocumentDownloadResponse],
    summary="Get document download authorization",
    description="Generates a short-lived, controlled download authorization URL after verifying access.",
    responses={
        401: {"model": StandardErrorResponse, "description": "Authentication required"},
        403: {"model": StandardErrorResponse, "description": "Access denied"},
        404: {"model": StandardErrorResponse, "description": "Document not found"},
    },
)
async def get_document_download(
    request: Request,
    patient_id: str,
    document_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)] = None,
    patient_service: Annotated[PatientService, Depends(get_patient_service)] = None,
    document_service: Annotated[DocumentService, Depends(get_document_service)] = None,
    authz_service: Annotated[AuthorizationService, Depends(get_authorization_service)] = None,
    audit_service: Annotated[AuditService, Depends(get_audit_service)] = None,
) -> StandardSuccessResponse[DocumentDownloadResponse]:
    """Generate controlled access download link for an authorized user."""
    await verify_patient_access(
        patient_id=patient_id,
        current_user=current_user,
        patient_service=patient_service,
        authz_service=authz_service,
        action="document:download",
        resource_type="document",
        resource_id=document_id,
    )
    download_info = await document_service.generate_download(patient_id, document_id)
    await audit_service.record_document_download_requested(
        actor_id=current_user.user_id,
        patient_id=patient_id,
        document_id=document_id,
    )
    return StandardSuccessResponse(data=download_info, request_id=_req_id(request))


@router.post(
    "/{document_id}/retry",
    response_model=StandardSuccessResponse[DocumentRetryResponse],
    summary="Retry failed document processing",
    description="Re-enqueues a document that failed processing if within retry limits.",
    responses={
        401: {"model": StandardErrorResponse, "description": "Authentication required"},
        403: {"model": StandardErrorResponse, "description": "Access denied"},
        404: {"model": StandardErrorResponse, "description": "Document not found"},
        422: {"model": StandardErrorResponse, "description": "Document not eligible for retry"},
    },
)
async def retry_document_processing(
    request: Request,
    patient_id: str,
    document_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)] = None,
    patient_service: Annotated[PatientService, Depends(get_patient_service)] = None,
    doc_processing_service: Annotated[DocumentProcessingService, Depends(get_document_processing_service)] = None,
    authz_service: Annotated[AuthorizationService, Depends(get_authorization_service)] = None,
) -> StandardSuccessResponse[DocumentRetryResponse]:
    """Retry failed document processing job."""
    await verify_patient_access(
        patient_id=patient_id,
        current_user=current_user,
        patient_service=patient_service,
        authz_service=authz_service,
        action="document:retry",
        resource_type="document",
        resource_id=document_id,
    )
    result = await doc_processing_service.retry_document_processing(
        patient_id=patient_id,
        document_id=document_id,
        actor_id=current_user.user_id,
    )
    return StandardSuccessResponse(data=result, request_id=_req_id(request))


@router.get(
    "/{document_id}/extraction",
    response_model=StandardSuccessResponse[ExtractionResultResponse],
    summary="Get document extraction result",
    description="Retrieve structured text and layout extraction result. Subject to clinical document authorization.",
    responses={
        401: {"model": StandardErrorResponse, "description": "Authentication required"},
        403: {"model": StandardErrorResponse, "description": "Access denied"},
        404: {"model": StandardErrorResponse, "description": "Extraction result or document not found"},
    },
)
async def get_document_extraction(
    request: Request,
    patient_id: str,
    document_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)] = None,
    patient_service: Annotated[PatientService, Depends(get_patient_service)] = None,
    doc_processing_service: Annotated[DocumentProcessingService, Depends(get_document_processing_service)] = None,
    authz_service: Annotated[AuthorizationService, Depends(get_authorization_service)] = None,
    audit_service: Annotated[AuditService, Depends(get_audit_service)] = None,
) -> StandardSuccessResponse[ExtractionResultResponse]:
    """Retrieve extraction result."""
    await verify_patient_access(
        patient_id=patient_id,
        current_user=current_user,
        patient_service=patient_service,
        authz_service=authz_service,
        action="document_extraction:read",
        resource_type="document_extraction",
        resource_id=document_id,
    )
    result = await doc_processing_service.get_extraction_result(patient_id, document_id)
    await audit_service.record_document_extraction_viewed(
        actor_id=current_user.user_id,
        patient_id=patient_id,
        document_id=document_id,
        extraction_id=result.extraction_id,
    )
    return StandardSuccessResponse(data=result, request_id=_req_id(request))


@router.post(
    "/{document_id}/archive",
    response_model=StandardSuccessResponse[DocumentResponse],
    summary="Archive document",
    description="Soft-delete / archive a document. Preserves audit history and prevents permanent deletion.",
    responses={
        401: {"model": StandardErrorResponse, "description": "Authentication required"},
        403: {"model": StandardErrorResponse, "description": "Access denied"},
        404: {"model": StandardErrorResponse, "description": "Document not found"},
    },
)
async def archive_document(
    request: Request,
    patient_id: str,
    document_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)] = None,
    patient_service: Annotated[PatientService, Depends(get_patient_service)] = None,
    document_service: Annotated[DocumentService, Depends(get_document_service)] = None,
    authz_service: Annotated[AuthorizationService, Depends(get_authorization_service)] = None,
    audit_service: Annotated[AuditService, Depends(get_audit_service)] = None,
) -> StandardSuccessResponse[DocumentResponse]:
    """Archive a medical document."""
    await verify_patient_access(
        patient_id=patient_id,
        current_user=current_user,
        patient_service=patient_service,
        authz_service=authz_service,
        action="document:archive",
        resource_type="document",
        resource_id=document_id,
    )
    result = await document_service.archive_document(patient_id, document_id)
    await audit_service.record_document_archived(
        actor_id=current_user.user_id,
        patient_id=patient_id,
        document_id=document_id,
    )
    return StandardSuccessResponse(data=result, request_id=_req_id(request))
