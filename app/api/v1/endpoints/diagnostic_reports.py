"""Diagnostic Reports Endpoints (Phase 34).

Supports publishing and retrieving diagnostic reports across laboratory, radiology,
and pathology findings.
"""

from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, Query, status

from app.api.deps import (
    get_current_user,
    get_diagnostic_report_service,
)
from app.schemas.user import AuthenticatedUserContext
from app.schemas.diagnostic_report import (
    DiagnosticReportCreate,
    DiagnosticReportFilter,
    DiagnosticReportListResponse,
    DiagnosticReportRecord,
    DiagnosticReportStatus,
)
from app.services.diagnostic_report_service import DiagnosticReportService

router = APIRouter(tags=["Diagnostic Reports"])


@router.post(
    "/diagnostic-reports",
    response_model=DiagnosticReportRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Create diagnostic report",
)
async def create_diagnostic_report(
    payload: DiagnosticReportCreate,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    report_service: DiagnosticReportService = Depends(get_diagnostic_report_service),
) -> DiagnosticReportRecord:
    """Register diagnostic report with narrative findings (CRITICAL: conclusion is NOT a diagnosis)."""
    return await report_service.create_report(payload, current_user=current_user)


@router.get(
    "/patients/{patient_id}/diagnostic-reports",
    response_model=DiagnosticReportListResponse,
    summary="List patient diagnostic reports",
)
async def list_patient_diagnostic_reports(
    patient_id: str,
    status_filter: Optional[DiagnosticReportStatus] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    report_service: DiagnosticReportService = Depends(get_diagnostic_report_service),
) -> DiagnosticReportListResponse:
    """Retrieve diagnostic reports for patient with BOLA enforcement."""
    filters = DiagnosticReportFilter(
        patient_id=patient_id,
        status=status_filter,
        page=page,
        limit=limit,
    )
    return await report_service.list_reports(filters, current_user)


@router.get(
    "/patients/{patient_id}/diagnostic-reports/{report_id}",
    response_model=DiagnosticReportRecord,
    summary="Get patient diagnostic report by ID",
)
async def get_patient_diagnostic_report(
    patient_id: str,
    report_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    report_service: DiagnosticReportService = Depends(get_diagnostic_report_service),
) -> DiagnosticReportRecord:
    """Get single diagnostic report for patient."""
    return await report_service.get_report(report_id, current_user)


@router.get(
    "/diagnostic-reports/{report_id}",
    response_model=DiagnosticReportRecord,
    summary="Get diagnostic report by ID",
)
async def get_diagnostic_report(
    report_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    report_service: DiagnosticReportService = Depends(get_diagnostic_report_service),
) -> DiagnosticReportRecord:
    """General retrieval of diagnostic report by ID."""
    return await report_service.get_report(report_id, current_user)
