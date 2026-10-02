"""Pydantic schemas for Phase 30 Search Results and Provenance.

CRITICAL PRINCIPLES:
- SEARCH RESULT MINIMIZATION: Only minimum necessary fields to identify the resource.
- NO complete clinical records, unmasked full notes, or complete histories in generic search results.
- SEARCH RESULT ≠ CLINICAL TRUTH
- SEARCH RELEVANCE ≠ CLINICAL PRIORITY
- SEARCH FAILURE ≠ NO RESULTS
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.search import MatchType, SearchResourceType


class SearchResultProvenance(BaseModel):
    """Provenance tracking for retrieved search records."""

    model_config = ConfigDict(extra="ignore")

    source: str = Field(default="healthsetu", description="Originating repository or system")
    source_version: Optional[str] = Field(default=None, description="Schema or entity version")
    source_system: Optional[str] = Field(default=None, description="External system name for interoperability records")
    external_resource_id: Optional[str] = Field(default=None, description="External resource ID if imported")
    source_organization_id: Optional[str] = Field(default=None, description="Owning organization identifier")
    imported_at: Optional[datetime] = Field(default=None, description="Timestamp when record was imported")


class SearchResultItem(BaseModel):
    """Minimized search result item conforming to Section 16 & Section 66."""

    model_config = ConfigDict(extra="ignore")

    resource_type: SearchResourceType = Field(..., description="Domain type of the resource")
    resource_id: str = Field(..., description="Unique identifier of the resource")
    display: str = Field(..., description="Safe, non-sensitive summary display title")
    match_type: MatchType = Field(default=MatchType.EXACT, description="Type of textual or identifier match")
    source: str = Field(default="healthsetu", description="Source of truth origin")
    status: Optional[str] = Field(default=None, description="Source lifecycle state (e.g. ACTIVE, VERIFIED)")
    relevance_score: float = Field(default=1.0, description="Syntactic textual relevance score. NEVER clinical priority.")
    provenance: Optional[SearchResultProvenance] = Field(default=None, description="Data provenance details")


class SearchPagination(BaseModel):
    """Pagination metadata for search responses."""

    page: int = Field(..., ge=1, description="Current page number")
    page_size: int = Field(..., ge=1, description="Page size")
    total: int = Field(..., ge=0, description="Total matching items authorized for actor")
    total_pages: int = Field(..., ge=0, description="Total number of pages")


class SearchResponseData(BaseModel):
    """Payload container for search results."""

    items: List[SearchResultItem] = Field(default_factory=list, description="Retrieved matching items")
    pagination: SearchPagination = Field(..., description="Pagination metadata")


class SearchResponse(BaseModel):
    """Phase 23 compliant unified search response envelope."""

    success: bool = Field(default=True)
    data: SearchResponseData


class SuggestionItem(BaseModel):
    """Minimized suggestion for autocomplete."""

    text: str = Field(..., description="Suggested search term or title")
    resource_type: SearchResourceType = Field(..., description="Associated resource domain")
    resource_id: Optional[str] = Field(default=None, description="Resource identifier if direct match")


class SuggestionResponseData(BaseModel):
    """Payload container for suggestions."""

    suggestions: List[SuggestionItem] = Field(default_factory=list)


class SuggestionResponse(BaseModel):
    """Phase 23 compliant suggestion response envelope."""

    success: bool = Field(default=True)
    data: SuggestionResponseData


class SearchRebuildRequest(BaseModel):
    """Request to initiate background search index rebuild."""

    resource_type: Optional[SearchResourceType] = Field(
        default=None,
        description="Target resource type to rebuild. None rebuilds all authorized indices."
    )
    force_full: bool = Field(default=False, description="Whether to rebuild from scratch")


class SearchIndexStatus(BaseModel):
    """Operational status of search index."""

    provider: str = Field(..., description="Active search provider (e.g. postgres, mock)")
    indexing_enabled: bool = Field(...)
    async_enabled: bool = Field(...)
    total_indexed_records: int = Field(default=0)
    pending_sync_count: int = Field(default=0)
    stale_index_count: int = Field(default=0)
    last_rebuild_at: Optional[datetime] = Field(default=None)
    status: str = Field(default="HEALTHY")
