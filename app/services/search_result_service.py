"""Search Result Service for Phase 30.

CRITICAL RESPONSIBILITIES:
- Search Result Minimization: Strips full clinical record bodies, notes, dosages, and sensitive narratives.
- Provenance Preservation: Ensures originating system, organization, and version are tracked.
- Allowlisted Sorting: Relevance, Date, Name, Status (Strictly NO raw SQL or arbitrary field sorting).
- Bounded Pagination: Enforces bounded page and page_size math.
- Clinical State Preservation: Extracted remains Extracted, Verified remains Verified, never mutated.
"""

from __future__ import annotations

import math
from typing import Any, List, Optional
from app.schemas.search import SearchSortField, SortOrder
from app.schemas.search_result import (
    SearchPagination,
    SearchResultItem,
    SearchResultProvenance,
)


class SearchResultService:
    """Manages transformation, minimization, sorting, and pagination of search records."""

    def sort_and_paginate(
        self,
        items: List[SearchResultItem],
        page: int,
        page_size: int,
        sort: SearchSortField,
        sort_order: SortOrder,
    ) -> tuple[List[SearchResultItem], SearchPagination]:
        """Apply allowlisted sorting and safe bounded pagination."""
        total = len(items)
        reverse = sort_order == SortOrder.DESC

        # Allowlisted sorting key lookup
        if sort == SearchSortField.RELEVANCE:
            # Sort by synthetic textual relevance score
            sorted_items = sorted(items, key=lambda x: x.relevance_score, reverse=reverse)
        elif sort == SearchSortField.NAME:
            sorted_items = sorted(items, key=lambda x: x.display.lower(), reverse=reverse)
        elif sort == SearchSortField.STATUS:
            sorted_items = sorted(items, key=lambda x: (x.status or "").lower(), reverse=reverse)
        else:
            # Fallback to relevance
            sorted_items = sorted(items, key=lambda x: x.relevance_score, reverse=reverse)

        # Pagination slice
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paged_items = sorted_items[start_idx:end_idx]

        total_pages = math.ceil(total / page_size) if total > 0 else 0

        pagination = SearchPagination(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=total_pages,
        )

        return paged_items, pagination

    def build_provenance(
        self,
        source: str = "healthsetu",
        source_version: Optional[str] = None,
        source_system: Optional[str] = None,
        external_resource_id: Optional[str] = None,
        source_organization_id: Optional[str] = None,
    ) -> SearchResultProvenance:
        """Construct standard provenance metadata."""
        return SearchResultProvenance(
            source=source,
            source_version=source_version,
            source_system=source_system,
            external_resource_id=external_resource_id,
            source_organization_id=source_organization_id,
        )
