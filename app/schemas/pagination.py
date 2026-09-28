"""Standard pagination schemas and helpers for HealthSetu (Phase 21).

Enforces bounded query results across collections (Section 11, 12):
- DEFAULT_PAGE_SIZE = 25
- MAX_PAGE_SIZE = 100
- Predictable page, total_count, total_pages, and navigation flags
"""

from __future__ import annotations

import math
from typing import Generic, Sequence, TypeVar
from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class PaginationParams(BaseModel):
    """Standardized pagination query parameters with strict bounds."""
    model_config = ConfigDict(extra="forbid")

    page: int = Field(default=1, ge=1, description="1-indexed page number")
    page_size: int = Field(default=25, ge=1, le=100, description="Items per page (max 100)")

    @property
    def offset(self) -> int:
        """Calculate SQL / collection offset."""
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        """Limit bound equal to page_size."""
        return self.page_size


class PaginatedResponse(BaseModel, Generic[T]):
    """Standardized generic envelope for paginated collection responses."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    items: list[T] = Field(description="Page items collection")
    total_count: int = Field(ge=0, description="Total matching items in collection")
    page: int = Field(ge=1, description="Current page number")
    page_size: int = Field(ge=1, le=100, description="Requested page size")
    total_pages: int = Field(ge=0, description="Total available pages")
    has_next: bool = Field(description="True if subsequent pages exist")
    has_prev: bool = Field(description="True if preceding pages exist")


def create_paginated_response(
    items: Sequence[T],
    total_count: int,
    page: int,
    page_size: int,
) -> PaginatedResponse[T]:
    """Helper to build a validated PaginatedResponse."""
    total_pages = math.ceil(total_count / page_size) if page_size > 0 else 0
    return PaginatedResponse[T](
        items=list(items),
        total_count=total_count,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1 and total_pages > 0,
    )
