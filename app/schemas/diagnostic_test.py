"""Pydantic schemas for Diagnostic Test Catalog (Phase 34).

SAFETY & ARCHITECTURAL INVARIANTS:
- DIAGNOSTIC TEST CATALOG != CLINICAL RECOMMENDATION ENGINE
- TEST CATALOG REFLECTS TERMINOLOGY & SERVICE CAPABILITIES ONLY
- NORMALIZATION != CLINICAL INTERPRETATION
- AMBIGUOUS MATCHES MUST REMAIN AMBIGUOUS (NEVER GUESS)
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class DiagnosticTestCategory(str, Enum):
    """Categorization of diagnostic tests and services."""

    HEMATOLOGY = "HEMATOLOGY"
    BIOCHEMISTRY = "BIOCHEMISTRY"
    MICROBIOLOGY = "MICROBIOLOGY"
    IMMUNOLOGY = "IMMUNOLOGY"
    PATHOLOGY = "PATHOLOGY"
    RADIOLOGY = "RADIOLOGY"
    CARDIOLOGY = "CARDIOLOGY"
    URINALYSIS = "URINALYSIS"
    MOLECULAR = "MOLECULAR"
    OTHER = "OTHER"


class TerminologySystem(str, Enum):
    """Standardized terminology systems."""

    LOINC = "LOINC"
    CPT = "CPT"
    SNOMED_CT = "SNOMED_CT"
    INTERNAL = "INTERNAL"
    LOCAL = "LOCAL"


class DiagnosticTest(BaseModel):
    """Authoritative representation of a catalog test/panel entry."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    test_id: str = Field(description="Internal unique identifier for the diagnostic test")
    code: str = Field(description="Standardized or catalog code (e.g. LOINC 718-7)")
    system: TerminologySystem = Field(default=TerminologySystem.LOINC, description="Terminology system")
    version: Optional[str] = Field(default="1.0", description="Terminology release version")
    name: str = Field(description="Standardized name (e.g. Hemoglobin [Mass/volume] in Blood)")
    raw_name: str = Field(description="Common/clinical name (e.g. Hemoglobin / Hb)")
    category: DiagnosticTestCategory = Field(description="Clinical discipline or lab section")
    specimen_type: Optional[str] = Field(default=None, description="Required specimen type (e.g. BLOOD, SERUM)")
    default_unit: Optional[str] = Field(default=None, description="Standard reporting unit where defined (e.g. g/dL)")
    description: Optional[str] = Field(default=None, description="Service and technical description")
    turn_around_hours: Optional[int] = Field(default=24, ge=0, description="Estimated completion turnaround in hours")
    is_active: bool = Field(default=True, description="Whether test is currently orderable")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Supplementary catalog attributes")


class DiagnosticTestSearchFilter(BaseModel):
    """Filter parameters for querying the diagnostic catalog."""

    query: Optional[str] = Field(default=None, description="Search term for code, name, or raw_name")
    category: Optional[DiagnosticTestCategory] = Field(default=None, description="Filter by test category")
    specimen_type: Optional[str] = Field(default=None, description="Filter by specimen type")
    system: Optional[TerminologySystem] = Field(default=None, description="Filter by terminology system")
    is_active: Optional[bool] = Field(default=True, description="Filter active orderable tests")
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=50, ge=1, le=100)


class DiagnosticTestSearchResult(BaseModel):
    """Paginated catalog search results."""

    items: List[DiagnosticTest] = Field(default_factory=list)
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    limit: int = Field(ge=1)


class TestNormalizationRequest(BaseModel):
    """Request to normalize a raw clinical test name to a standardized catalog concept."""

    __test__ = False

    raw_test_name: str = Field(min_length=1, max_length=255, description="Input raw test string from order/document")
    specimen_type: Optional[str] = Field(default=None, description="Optional specimen hint")


class CandidateMatch(BaseModel):
    """Candidate catalog test match during normalization."""

    test_id: str
    code: str
    system: TerminologySystem
    name: str
    score: float = Field(ge=0.0, le=1.0)


class TestNormalizationResponse(BaseModel):
    """Result of catalog concept normalization."""

    __test__ = False

    raw_test_name: str
    normalized_name: Optional[str] = None
    matched_test_id: Optional[str] = None
    code: Optional[str] = None
    system: Optional[TerminologySystem] = None
    confidence: float = Field(ge=0.0, le=1.0)
    is_ambiguous: bool = Field(default=False, description="True if multiple close concepts match")
    candidate_matches: List[CandidateMatch] = Field(default_factory=list)
