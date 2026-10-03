"""Diagnostic Catalog Endpoints (Phase 34).

Supports querying supported laboratory/diagnostic tests and normalizing raw test names.
"""

from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, Query, status

from app.api.deps import (
    get_current_user,
    get_diagnostic_authorization_service,
    get_diagnostic_catalog_service,
)
from app.schemas.user import AuthenticatedUserContext
from app.schemas.diagnostic_test import (
    DiagnosticTest,
    DiagnosticTestCategory,
    DiagnosticTestSearchFilter,
    DiagnosticTestSearchResult,
    TerminologySystem,
    TestNormalizationRequest,
    TestNormalizationResponse,
)
from app.services.diagnostic_authorization_service import DiagnosticAuthorizationService
from app.services.diagnostic_catalog_service import DiagnosticCatalogService

router = APIRouter(prefix="/diagnostics/catalog", tags=["Diagnostic Catalog"])


@router.get(
    "",
    response_model=DiagnosticTestSearchResult,
    summary="Search diagnostic test catalog",
)
async def search_catalog(
    query: Optional[str] = Query(None, description="Free-text search by name or code"),
    category: Optional[DiagnosticTestCategory] = Query(None, description="Clinical test discipline"),
    specimen_type: Optional[str] = Query(None, description="Filter by specimen type"),
    system: Optional[TerminologySystem] = Query(None, description="Filter by terminology system"),
    is_active: Optional[bool] = Query(True, description="Filter active orderable tests"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    catalog_service: DiagnosticCatalogService = Depends(get_diagnostic_catalog_service),
    auth_service: DiagnosticAuthorizationService = Depends(get_diagnostic_authorization_service),
) -> DiagnosticTestSearchResult:
    """Search and browse diagnostic catalog references."""
    auth_service.authorize_catalog_view(current_user)
    filters = DiagnosticTestSearchFilter(
        query=query,
        category=category,
        specimen_type=specimen_type,
        system=system,
        is_active=is_active,
        page=page,
        limit=limit,
    )
    return catalog_service.search_tests(filters)


@router.get(
    "/{test_id}",
    response_model=DiagnosticTest,
    summary="Get catalog test details",
)
async def get_test_details(
    test_id: str,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    catalog_service: DiagnosticCatalogService = Depends(get_diagnostic_catalog_service),
    auth_service: DiagnosticAuthorizationService = Depends(get_diagnostic_authorization_service),
) -> DiagnosticTest:
    """Fetch test details by test_id."""
    auth_service.authorize_catalog_view(current_user)
    return catalog_service.get_test_by_id(test_id)


@router.post(
    "/normalize",
    response_model=TestNormalizationResponse,
    summary="Normalize raw test string",
)
async def normalize_test_string(
    request: TestNormalizationRequest,
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    catalog_service: DiagnosticCatalogService = Depends(get_diagnostic_catalog_service),
    auth_service: DiagnosticAuthorizationService = Depends(get_diagnostic_authorization_service),
) -> TestNormalizationResponse:
    """Map raw clinical test string to standard catalog concept without autonomous interpretation."""
    auth_service.authorize_catalog_view(current_user)
    return catalog_service.normalize_test(request)
