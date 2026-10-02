"""Pydantic schemas for Phase 30 — Authorized Search, Indexing & Clinical Resource Retrieval.

CRITICAL CLINICAL SAFETY PRINCIPLES:
- SEARCH ≠ CLINICAL DECISION
- SEARCH ≠ DIAGNOSIS
- SEARCH ≠ TRIAGE
- SEARCH ≠ MEDICATION SAFETY
- SEARCH ≠ PATIENT MATCHING
- SEARCH RELEVANCE ≠ CLINICAL PRIORITY
- SEARCH RESULT ≠ CLINICAL TRUTH
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class SearchResourceType(str, Enum):
    """Allowed resource types for HealthSetu search."""

    PATIENT = "patient"
    ENCOUNTER = "encounter"
    DOCUMENT = "document"
    PRESCRIPTION = "prescription"
    MEDICATION = "medication"
    CARE_PLAN = "care_plan"
    DISCHARGE = "discharge"
    CLINICAL_NOTE = "clinical_note"
    ORGANIZATION = "organization"
    FACILITY = "facility"
    CLINICIAN = "clinician"
    TRANSFER = "transfer"


class MatchType(str, Enum):
    """Matching strategy executed during retrieval."""

    EXACT = "EXACT"
    IDENTIFIER = "IDENTIFIER"
    PREFIX = "PREFIX"
    CONTAINS = "CONTAINS"
    FULL_TEXT = "FULL_TEXT"


class SearchSortField(str, Enum):
    """Allowlisted sorting criteria. Raw SQL expressions are strictly prohibited."""

    RELEVANCE = "relevance"
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"
    NAME = "name"
    DATE = "date"
    STATUS = "status"


class SortOrder(str, Enum):
    """Sorting direction."""

    ASC = "asc"
    DESC = "desc"


class SearchFilters(BaseModel):
    """Strictly allowlisted filter parameters for search queries."""

    model_config = ConfigDict(extra="forbid")

    patient_id: Optional[str] = Field(default=None, description="Filter by authorized patient ID")
    encounter_id: Optional[str] = Field(default=None, description="Filter by authorized encounter ID")
    organization_id: Optional[str] = Field(default=None, description="Filter by authorized organization ID")
    facility_id: Optional[str] = Field(default=None, description="Filter by authorized facility ID")
    clinician_id: Optional[str] = Field(default=None, description="Filter by authorized clinician ID")
    status: Optional[str] = Field(default=None, description="Filter by resource lifecycle status (e.g. ACTIVE, VERIFIED)")
    document_type: Optional[str] = Field(default=None, description="Filter for clinical documents")
    from_date: Optional[datetime] = Field(default=None, description="Filter records on or after date")
    to_date: Optional[datetime] = Field(default=None, description="Filter records on or before date")

    @field_validator("to_date")
    @classmethod
    def validate_date_range(cls, v: Optional[datetime], info: Any) -> Optional[datetime]:
        from_val = info.data.get("from_date")
        if v and from_val and v < from_val:
            raise ValueError("to_date must be greater than or equal to from_date")
        return v


class SearchRequest(BaseModel):
    """Validated search request specification."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(..., min_length=2, max_length=200, description="Normalized search term or identifier")
    resource_type: Optional[SearchResourceType] = Field(
        default=None,
        description="Target resource type. If omitted, searches across user's authorized domains."
    )
    filters: Optional[SearchFilters] = Field(default=None, description="Validated filter criteria")
    page: int = Field(default=1, ge=1, description="Page index (1-based)")
    page_size: int = Field(default=20, ge=1, le=100, description="Page size bounded to maximum 100")
    sort: SearchSortField = Field(default=SearchSortField.RELEVANCE, description="Allowlisted sort field")
    sort_order: SortOrder = Field(default=SortOrder.DESC, description="Sort direction")


class AutocompleteRequest(BaseModel):
    """Query parameter validation for suggestions / autocomplete."""

    query: str = Field(..., min_length=2, max_length=100, description="Suggestion query prefix")
    resource_type: Optional[SearchResourceType] = Field(default=None, description="Scope suggestion to specific resource")
    limit: int = Field(default=10, ge=1, le=20, description="Max suggestions to return")
