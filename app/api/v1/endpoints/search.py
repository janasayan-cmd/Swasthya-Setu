"""Phase 30 — Authorized Search, Indexing & Clinical Resource Retrieval Endpoints.

INVARIANTS & POLICIES:
- STRICT AUTHORIZATION GATES: Enforced BEFORE query execution.
- PRE-SEARCH SCOPE INJECTION: Org/Facility/Patient isolation.
- NO CLINICAL DECISION MAKING, DIAGNOSIS, OR TRIAGE IN SEARCH.
- SEARCH RELEVANCE ≠ CLINICAL PRIORITY.
- PROVIDER FAILURE ≠ NO RESULTS (explicit error response).
- BOUNDED PAGINATION (page >= 1, page_size <= 100).
- ALLOWLISTED SORTING & FILTERING.
"""

from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, Query, status

from app.api.deps import (
    get_current_user,
    get_search_service,
    require_permission,
)
from app.core.policies import Permission
from app.schemas.user import AuthenticatedUserContext
from app.schemas.search import (
    AutocompleteRequest,
    SearchFilters,
    SearchRequest,
    SearchResourceType,
    SearchSortField,
    SortOrder,
)
from app.schemas.search_result import (
    SearchIndexStatus,
    SearchRebuildRequest,
    SearchResponse,
    SuggestionResponse,
)
from app.services.search_service import SearchService

router = APIRouter(prefix="/search", tags=["Search"])


# ---------------------------------------------------------------------------
# Unified Search Endpoint (Section 8)
# ---------------------------------------------------------------------------

@router.get(
    "",
    response_model=SearchResponse,
    summary="Execute unified authorized search across healthcare resources",
    dependencies=[Depends(require_permission(Permission.SEARCH_EXECUTE))],
)
async def unified_search(
    q: str = Query(..., min_length=2, max_length=200, description="Search query string"),
    resource_type: Optional[SearchResourceType] = Query(None, description="Optional target resource domain"),
    patient_id: Optional[str] = Query(None, description="Filter by authorized patient ID"),
    encounter_id: Optional[str] = Query(None, description="Filter by authorized encounter ID"),
    organization_id: Optional[str] = Query(None, description="Filter by authorized organization ID"),
    facility_id: Optional[str] = Query(None, description="Filter by authorized facility ID"),
    status: Optional[str] = Query(None, description="Filter by resource lifecycle status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size bounded to maximum 100"),
    sort: SearchSortField = Query(SearchSortField.RELEVANCE, description="Allowlisted sort field"),
    sort_order: SortOrder = Query(SortOrder.DESC, description="Sort direction"),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    search_service: SearchService = Depends(get_search_service),
) -> SearchResponse:
    """Execute authorized search query with pre-search boundary injection."""
    filters = SearchFilters(
        patient_id=patient_id,
        encounter_id=encounter_id,
        organization_id=organization_id,
        facility_id=facility_id,
        status=status,
    )
    request = SearchRequest(
        query=q,
        resource_type=resource_type,
        filters=filters,
        page=page,
        page_size=page_size,
        sort=sort,
        sort_order=sort_order,
    )
    return await search_service.execute_search(request=request, user=current_user)


# ---------------------------------------------------------------------------
# Autocomplete / Suggestions Endpoint (Section 28)
# ---------------------------------------------------------------------------

@router.get(
    "/suggestions",
    response_model=SuggestionResponse,
    summary="Retrieve authorized prefix suggestions for autocomplete",
    dependencies=[Depends(require_permission(Permission.SEARCH_EXECUTE))],
)
async def get_suggestions(
    q: str = Query(..., min_length=2, max_length=100, description="Prefix query"),
    resource_type: Optional[SearchResourceType] = Query(None, description="Optional resource filter"),
    limit: int = Query(10, ge=1, le=20, description="Max suggestions"),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    search_service: SearchService = Depends(get_search_service),
) -> SuggestionResponse:
    """Retrieve authorized autocomplete suggestions without information leakage."""
    request = AutocompleteRequest(query=q, resource_type=resource_type, limit=limit)
    return await search_service.get_suggestions(request=request, user=current_user)


# ---------------------------------------------------------------------------
# Resource-Specific Endpoints (Section 9)
# ---------------------------------------------------------------------------

@router.get(
    "/patients",
    response_model=SearchResponse,
    summary="Search patient records with strict identity access controls",
    dependencies=[Depends(require_permission(Permission.SEARCH_PATIENT))],
)
async def search_patients(
    q: str = Query(..., min_length=2, max_length=200),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    search_service: SearchService = Depends(get_search_service),
) -> SearchResponse:
    request = SearchRequest(
        query=q,
        resource_type=SearchResourceType.PATIENT,
        page=page,
        page_size=page_size,
    )
    return await search_service.execute_search(request=request, user=current_user)


@router.get(
    "/documents",
    response_model=SearchResponse,
    summary="Search clinical documents",
    dependencies=[Depends(require_permission(Permission.SEARCH_DOCUMENT))],
)
async def search_documents(
    q: str = Query(..., min_length=2, max_length=200),
    patient_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    search_service: SearchService = Depends(get_search_service),
) -> SearchResponse:
    filters = SearchFilters(patient_id=patient_id) if patient_id else None
    request = SearchRequest(
        query=q,
        resource_type=SearchResourceType.DOCUMENT,
        filters=filters,
        page=page,
        page_size=page_size,
    )
    return await search_service.execute_search(request=request, user=current_user)


@router.get(
    "/medications",
    response_model=SearchResponse,
    summary="Search normalized medications (retrieval only, no safety checks)",
    dependencies=[Depends(require_permission(Permission.SEARCH_EXECUTE))],
)
async def search_medications(
    q: str = Query(..., min_length=2, max_length=200),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    search_service: SearchService = Depends(get_search_service),
) -> SearchResponse:
    request = SearchRequest(
        query=q,
        resource_type=SearchResourceType.MEDICATION,
        page=page,
        page_size=page_size,
    )
    return await search_service.execute_search(request=request, user=current_user)


@router.get(
    "/facilities",
    response_model=SearchResponse,
    summary="Search healthcare facilities",
    dependencies=[Depends(require_permission(Permission.SEARCH_FACILITY))],
)
async def search_facilities(
    q: str = Query(..., min_length=2, max_length=200),
    organization_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    search_service: SearchService = Depends(get_search_service),
) -> SearchResponse:
    filters = SearchFilters(organization_id=organization_id) if organization_id else None
    request = SearchRequest(
        query=q,
        resource_type=SearchResourceType.FACILITY,
        filters=filters,
        page=page,
        page_size=page_size,
    )
    return await search_service.execute_search(request=request, user=current_user)


@router.get(
    "/organizations",
    response_model=SearchResponse,
    summary="Search healthcare organizations",
    dependencies=[Depends(require_permission(Permission.SEARCH_ORGANIZATION))],
)
async def search_organizations(
    q: str = Query(..., min_length=2, max_length=200),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: AuthenticatedUserContext = Depends(get_current_user),
    search_service: SearchService = Depends(get_search_service),
) -> SearchResponse:
    request = SearchRequest(
        query=q,
        resource_type=SearchResourceType.ORGANIZATION,
        page=page,
        page_size=page_size,
    )
    return await search_service.execute_search(request=request, user=current_user)


# ---------------------------------------------------------------------------
# Admin Search Endpoints (Section 50 & 51)
# ---------------------------------------------------------------------------

@router.get(
    "/admin/status",
    response_model=SearchIndexStatus,
    summary="Retrieve operational search index status",
    dependencies=[Depends(require_permission(Permission.ADMIN_SEARCH_VIEW))],
)
async def get_admin_search_status(
    search_service: SearchService = Depends(get_search_service),
) -> SearchIndexStatus:
    return await search_service.get_admin_status()


@router.post(
    "/admin/rebuild",
    summary="Trigger asynchronous index rebuild",
    dependencies=[Depends(require_permission(Permission.ADMIN_SEARCH_MANAGE))],
)
async def trigger_admin_search_rebuild(
    body: SearchRebuildRequest,
    search_service: SearchService = Depends(get_search_service),
):
    return await search_service.trigger_admin_rebuild(resource_type=body.resource_type)
