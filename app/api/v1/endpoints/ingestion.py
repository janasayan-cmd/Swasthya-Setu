"""External Clinical Data Ingestion API Endpoints (Phase 45).

SAFETY INVARIANTS:
- IMPORT != VERIFICATION
- IMPORT != CLINICAL TRUTH
- EXTERNAL DATA != HEALTHSETU TRUTH
- AI != INGESTION AUTHORITY
- AI != PATIENT MATCHING AUTHORITY
- NO SILENT CLINICAL OVERWRITE
"""

from __future__ import annotations

from typing import Annotated, Any, Dict, Optional
from fastapi import APIRouter, Depends, Query, Request, status

from app.api.deps import (
    get_audit_service,
    get_current_user,
    get_ingestion_service,
    get_reconciliation_service,
)
from app.core.logging import request_id_ctx_var
from app.schemas.ingestion import (
    ExternalRecordsListResponse,
    IngestionCreateRequest,
    IngestionHistoryResponse,
    IngestionListResponse,
    IngestionRecord,
    IngestionResponse,
    IngestionStatus,
    IngestionStatusResponse,
    ReconciliationResolveAction,
)
from app.schemas.reconciliation import ReconciliationResponse
from app.schemas.response import StandardErrorResponse, StandardSuccessResponse
from app.schemas.user import AuthenticatedUserContext
from app.services.audit_service import AuditService
from app.services.ingestion_service import IngestionService
from app.services.reconciliation_service import ReconciliationService

router = APIRouter(tags=["External Data Ingestion & Clinical Reconciliation"])


def _req_id(request: Request) -> str:
    return getattr(request.state, "request_id", None) or request_id_ctx_var.get() or "unknown"


# ==============================================================================
# INGESTION ENDPOINTS
# ==============================================================================

@router.post(
    "/ingestions",
    status_code=status.HTTP_201_CREATED,
    response_model=StandardSuccessResponse[IngestionResponse],
    summary="Ingest external clinical data",
    description="Receive, validate, resolve identity, and stage external clinical data.",
    responses={
        401: {"model": StandardErrorResponse, "description": "Authentication required"},
        403: {"model": StandardErrorResponse, "description": "Unauthorized or AI attempted ingestion"},
        404: {"model": StandardErrorResponse, "description": "Source not registered"},
        409: {"model": StandardErrorResponse, "description": "Idempotency collision or duplicate"},
        422: {"model": StandardErrorResponse, "description": "Validation error or invalid payload"},
    },
)
async def create_ingestion(
    request: Request,
    body: IngestionCreateRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    ingestion_service: Annotated[IngestionService, Depends(get_ingestion_service)],
) -> StandardSuccessResponse[IngestionResponse]:
    """Submit external clinical data payload for intake and controlled reconciliation."""
    result = await ingestion_service.ingest_clinical_data(
        request=body,
        requester_id=current_user.user_id,
        requester_role=current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role),
        is_ai_agent=getattr(current_user, "is_ai", False),
    )
    return StandardSuccessResponse(
        data=ingestion_service._to_response(result),
        request_id=_req_id(request),
        message="External data ingestion received and staged.",
    )


@router.get(
    "/ingestions",
    response_model=StandardSuccessResponse[IngestionListResponse],
    summary="List ingestion transactions",
    description="List paginated ingestion transactions with filtering.",
)
async def list_ingestions(
    request: Request,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    ingestion_service: Annotated[IngestionService, Depends(get_ingestion_service)],
    source_system: Optional[str] = Query(None, description="Filter by source system ID"),
    patient_id: Optional[str] = Query(None, description="Filter by patient ID"),
    status_filter: Optional[IngestionStatus] = Query(None, alias="status", description="Filter by status"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Page size"),
) -> StandardSuccessResponse[IngestionListResponse]:
    """List external data ingestion transactions."""
    result = await ingestion_service.list_ingestions(
        source_system=source_system,
        patient_id=patient_id,
        status=status_filter,
        page=page,
        size=size,
    )
    return StandardSuccessResponse(
        data=result,
        request_id=_req_id(request),
        message="Ingestion records retrieved successfully.",
    )


@router.get(
    "/ingestions/{ingestion_id}",
    response_model=StandardSuccessResponse[IngestionResponse],
    summary="Get ingestion record by ID",
)
async def get_ingestion(
    request: Request,
    ingestion_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    ingestion_service: Annotated[IngestionService, Depends(get_ingestion_service)],
) -> StandardSuccessResponse[IngestionResponse]:
    """Retrieve full details of an external ingestion record."""
    result = await ingestion_service.get_ingestion(ingestion_id)
    return StandardSuccessResponse(
        data=ingestion_service._to_response(result),
        request_id=_req_id(request),
        message="Ingestion record retrieved.",
    )


@router.get(
    "/ingestions/{ingestion_id}/status",
    response_model=StandardSuccessResponse[IngestionStatusResponse],
    summary="Poll ingestion status",
)
async def get_ingestion_status(
    request: Request,
    ingestion_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    ingestion_service: Annotated[IngestionService, Depends(get_ingestion_service)],
) -> StandardSuccessResponse[IngestionStatusResponse]:
    """Poll lifecycle status of an ingestion transaction."""
    rec = await ingestion_service.get_ingestion(ingestion_id)
    status_resp = IngestionStatusResponse(
        id=rec.id,
        status=rec.status,
        verification_status=rec.verification_status,
        identity_outcome=rec.identity_outcome,
        reconciliation_status=rec.reconciliation_status,
        updated_at=rec.updated_at,
    )
    return StandardSuccessResponse(
        data=status_resp,
        request_id=_req_id(request),
        message="Ingestion status retrieved.",
    )


@router.get(
    "/ingestions/{ingestion_id}/history",
    response_model=StandardSuccessResponse[IngestionHistoryResponse],
    summary="Get ingestion transition history",
)
async def get_ingestion_history(
    request: Request,
    ingestion_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    ingestion_service: Annotated[IngestionService, Depends(get_ingestion_service)],
) -> StandardSuccessResponse[IngestionHistoryResponse]:
    """Retrieve lifecycle history and transition notes for an ingestion."""
    rec = await ingestion_service.get_ingestion(ingestion_id)
    return StandardSuccessResponse(
        data=IngestionHistoryResponse(ingestion_id=rec.id, history=rec.history),
        request_id=_req_id(request),
        message="Ingestion history retrieved.",
    )


@router.post(
    "/ingestions/{ingestion_id}/cancel",
    response_model=StandardSuccessResponse[IngestionResponse],
    summary="Cancel pending ingestion",
)
async def cancel_ingestion(
    request: Request,
    ingestion_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    ingestion_service: Annotated[IngestionService, Depends(get_ingestion_service)],
) -> StandardSuccessResponse[IngestionResponse]:
    """Cancel a pending external ingestion."""
    result = await ingestion_service.cancel_ingestion(
        ingestion_id=ingestion_id,
        actor_id=current_user.user_id,
        actor_role=current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role),
    )
    return StandardSuccessResponse(
        data=ingestion_service._to_response(result),
        request_id=_req_id(request),
        message="Ingestion cancelled successfully.",
    )


# ==============================================================================
# PATIENT-SPECIFIC EXTERNAL RECORDS & IMPORT HISTORY
# ==============================================================================

@router.get(
    "/patients/{patient_id}/external-records",
    response_model=StandardSuccessResponse[ExternalRecordsListResponse],
    summary="List patient external records",
)
async def list_patient_external_records(
    request: Request,
    patient_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    ingestion_service: Annotated[IngestionService, Depends(get_ingestion_service)],
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
) -> StandardSuccessResponse[ExternalRecordsListResponse]:
    """Retrieve staged external records imported for a patient."""
    result = await ingestion_service.list_patient_external_records(
        patient_id=patient_id, page=page, size=size
    )
    return StandardSuccessResponse(
        data=result,
        request_id=_req_id(request),
        message="Patient external records retrieved.",
    )


@router.get(
    "/patients/{patient_id}/import-history",
    response_model=StandardSuccessResponse[ExternalRecordsListResponse],
    summary="Get patient import history",
)
async def get_patient_import_history(
    request: Request,
    patient_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    ingestion_service: Annotated[IngestionService, Depends(get_ingestion_service)],
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
) -> StandardSuccessResponse[ExternalRecordsListResponse]:
    """Retrieve chronological external data import transactions for a patient."""
    result = await ingestion_service.list_patient_external_records(
        patient_id=patient_id, page=page, size=size
    )
    return StandardSuccessResponse(
        data=result,
        request_id=_req_id(request),
        message="Patient import history retrieved.",
    )


# ==============================================================================
# RECONCILIATION RESOLUTION ENDPOINTS
# ==============================================================================

@router.get(
    "/reconciliation/{reconciliation_id}",
    response_model=StandardSuccessResponse[Dict[str, Any]],
    summary="Get reconciliation case details",
)
async def get_reconciliation_case(
    request: Request,
    reconciliation_id: str,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    reconciliation_service: Annotated[ReconciliationService, Depends(get_reconciliation_service)],
) -> StandardSuccessResponse[Dict[str, Any]]:
    """Retrieve details and conflicting items of a clinical reconciliation case."""
    rec = await reconciliation_service.reconciliation_repo.get_by_id(reconciliation_id)
    if not rec:
        return StandardSuccessResponse(
            data={"reconciliation_id": reconciliation_id, "status": "NOT_FOUND"},
            request_id=_req_id(request),
            message="Reconciliation record not found.",
        )
    return StandardSuccessResponse(
        data=rec.model_dump(),
        request_id=_req_id(request),
        message="Reconciliation case details retrieved.",
    )


@router.post(
    "/reconciliation/{reconciliation_id}/resolve",
    response_model=StandardSuccessResponse[Dict[str, Any]],
    summary="Resolve reconciliation conflict",
)
async def resolve_reconciliation_case(
    request: Request,
    reconciliation_id: str,
    body: ReconciliationResolveAction,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    ingestion_service: Annotated[IngestionService, Depends(get_ingestion_service)],
) -> StandardSuccessResponse[Dict[str, Any]]:
    """Clinician manually resolves a clinical reconciliation case."""
    result = await ingestion_service.resolve_reconciliation(
        reconciliation_id=reconciliation_id,
        action=body,
        current_user=current_user,
    )
    return StandardSuccessResponse(
        data=result,
        request_id=_req_id(request),
        message="Clinical reconciliation case resolved successfully.",
    )


# ==============================================================================
# INTERNAL PROCESSING ENDPOINT
# ==============================================================================

@router.post(
    "/internal/ingestion/process",
    response_model=StandardSuccessResponse[IngestionResponse],
    summary="Internal ingestion pipeline process",
)
async def internal_process_ingestion(
    request: Request,
    body: IngestionCreateRequest,
    current_user: Annotated[AuthenticatedUserContext, Depends(get_current_user)],
    ingestion_service: Annotated[IngestionService, Depends(get_ingestion_service)],
) -> StandardSuccessResponse[IngestionResponse]:
    """Internal system/worker trigger to execute synchronous ingestion pipeline."""
    result = await ingestion_service.ingest_clinical_data(
        request=body,
        requester_id=current_user.user_id,
        requester_role=current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role),
        is_ai_agent=getattr(current_user, "is_ai", False),
    )
    return StandardSuccessResponse(
        data=ingestion_service._to_response(result),
        request_id=_req_id(request),
        message="Internal ingestion processed.",
    )
