"""Diagnostic Results Endpoints (Phase 34).

Supports result ingestion, patient factual result access, clinician result review,
version history tracking, and formal clinician verification (Phase 10).
"""

from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status

from app.api.deps import (
    get_current_user,
    get_diagnostic_result_service,
    get_diagnostic_verification_service,
)
from app.schemas.user import AuthenticatedUserContext
from app.schemas.diagnostic_result import (
    DiagnosticResultFilter,
    DiagnosticResultIngest,
    DiagnosticResultListResponse,
    DiagnosticResultRecord,
    ResultStatus,
    ResultVerificationRequest,
    VerificationStatus,
)
from app.services.diagnostic_result_service import DiagnosticResultService
from app.services.diagnostic_verification_service import DiagnosticVerificationService

router = APIRouter(tags=["Diagnostic Results"])


# ---------------------------------------------------------------------------
# Result Ingestion (Section 18 & 37)
# ---------------------------------------------------------------------------

@router.post(
    "/diagnostic-results/ingest",
    response_model=DiagnosticResultRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest diagnostic result",
)
async def ingest_diagnostic_result(
    payload: DiagnosticResultIngest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    result_service: DiagnosticResultService = Depends(get_diagnostic_result_service),
) -> DiagnosticResultRecord:
    """Ingest external laboratory result with normalization, provenance, and critical alerting."""
    return await result_service.ingest_result(payload, actor=current_user)


# ---------------------------------------------------------------------------
# Patient Result Access (Section 29 & 30)
# ---------------------------------------------------------------------------

@router.get(
    "/patients/{patient_id}/diagnostic-results",
    response_model=DiagnosticResultListResponse,
    summary="List patient diagnostic results",
)
async def list_patient_diagnostic_results(
    patient_id: str,
    status_filter: Optional[ResultStatus] = Query(None, alias="status"),
    verification_status: Optional[VerificationStatus] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    result_service: DiagnosticResultService = Depends(get_diagnostic_result_service),
) -> DiagnosticResultListResponse:
    """Retrieve factual diagnostic results for authorized patient."""
    filters = DiagnosticResultFilter(
        patient_id=patient_id,
        status=status_filter,
        verification_status=verification_status,
        page=page,
        limit=limit,
    )
    return await result_service.list_results(filters, current_user)


@router.get(
    "/patients/{patient_id}/diagnostic-results/{result_id}",
    response_model=DiagnosticResultRecord,
    summary="Get patient diagnostic result by ID",
)
async def get_patient_diagnostic_result(
    patient_id: str,
    result_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    result_service: DiagnosticResultService = Depends(get_diagnostic_result_service),
) -> DiagnosticResultRecord:
    """Get single diagnostic result for patient."""
    return await result_service.get_result(result_id, current_user)


# ---------------------------------------------------------------------------
# Clinician Result Review & Verification (Section 28 & Phase 10)
# ---------------------------------------------------------------------------

@router.get(
    "/clinicians/me/diagnostic-results/{result_id}",
    response_model=DiagnosticResultRecord,
    summary="Clinician retrieve diagnostic result",
)
async def clinician_get_diagnostic_result(
    result_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    result_service: DiagnosticResultService = Depends(get_diagnostic_result_service),
) -> DiagnosticResultRecord:
    """Clinician review of result with provenance, units, and ranges."""
    return await result_service.get_result(result_id, current_user)


@router.post(
    "/clinicians/me/diagnostic-results/{result_id}/verify",
    response_model=DiagnosticResultRecord,
    summary="Clinician verify diagnostic result",
)
async def verify_diagnostic_result(
    result_id: str,
    payload: ResultVerificationRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    verification_service: DiagnosticVerificationService = Depends(get_diagnostic_verification_service),
) -> DiagnosticResultRecord:
    """Clinician formally certifies or rejects result (Phase 10 integration)."""
    return await verification_service.verify_result(
        result_id=result_id,
        verification_request=payload,
        clinician=current_user,
    )


# ---------------------------------------------------------------------------
# Generic Result Retrieval & Historical Versioning (Section 26)
# ---------------------------------------------------------------------------

@router.get(
    "/diagnostic-results/{result_id}",
    response_model=DiagnosticResultRecord,
    summary="Get diagnostic result by ID",
)
async def get_diagnostic_result(
    result_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    result_service: DiagnosticResultService = Depends(get_diagnostic_result_service),
) -> DiagnosticResultRecord:
    """General retrieval of diagnostic result."""
    return await result_service.get_result(result_id, current_user)


@router.get(
    "/diagnostic-results/{result_id}/history",
    response_model=List[DiagnosticResultRecord],
    summary="Get result version history",
)
async def get_diagnostic_result_history(
    result_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    result_service: DiagnosticResultService = Depends(get_diagnostic_result_service),
) -> List[DiagnosticResultRecord]:
    """Retrieve complete audit-grade version chain for amended/corrected results."""
    return await result_service.get_version_history(result_id, current_user)
