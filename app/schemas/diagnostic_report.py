"""Pydantic schemas for Diagnostic Reports (Phase 34).

SAFETY & ARCHITECTURAL INVARIANTS:
- REPORT CONCLUSION TEXT != STRUCTURED DIAGNOSIS
- DIAGNOSTIC REPORT CONCLUSION TEXT MUST BE TREATED AS SOURCE-PROVIDED CONTENT ONLY
- AI/DOCUMENT EXTRACTION != VERIFIED REPORT
- RADIOLOGY / IMAGING FINDINGS != INDEPENDENT DIAGNOSES
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class DiagnosticReportStatus(str, Enum):
    """Lifecycle status of a diagnostic report."""

    PRELIMINARY = "PRELIMINARY"
    FINAL = "FINAL"
    CORRECTED = "CORRECTED"
    AMENDED = "AMENDED"
    CANCELLED = "CANCELLED"
    UNKNOWN = "UNKNOWN"


class DiagnosticReportCreate(BaseModel):
    """Payload to create or register a diagnostic report."""

    order_id: Optional[str] = Field(default=None, description="Associated order ID")
    patient_id: str = Field(description="Patient identifier")
    encounter_id: Optional[str] = Field(default=None, description="Encounter identifier")
    clinician_id: Optional[str] = Field(default=None, description="Ordering clinician identifier")
    organization_id: Optional[str] = Field(default=None, description="Organization identifier")
    facility_id: Optional[str] = Field(default=None, description="Facility identifier")
    provider_id: str = Field(description="Authoritative diagnostic provider")
    provider_report_id: Optional[str] = Field(default=None, description="External provider report ID")
    status: DiagnosticReportStatus = Field(default=DiagnosticReportStatus.FINAL)
    conclusion_text: Optional[str] = Field(
        default=None,
        description="Source narrative conclusion or impression (CRITICAL: NOT a structured diagnosis)",
    )
    document_id: Optional[str] = Field(default=None, description="Secure document reference (Phase 5)")
    result_ids: List[str] = Field(default_factory=list, description="Associated result references")
    reported_at: Optional[datetime] = None
    notes: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DiagnosticReportRecord(BaseModel):
    """Authoritative diagnostic report entity."""

    model_config = ConfigDict(populate_by_name=True)

    report_id: str = Field(description="Unique internal report identifier")
    report_number: str = Field(description="Human-readable report number (e.g. RPT-20261003-0001)")
    order_id: Optional[str] = None
    patient_id: str
    encounter_id: Optional[str] = None
    clinician_id: Optional[str] = None
    organization_id: Optional[str] = None
    facility_id: Optional[str] = None
    provider_id: str
    provider_report_id: Optional[str] = None
    status: DiagnosticReportStatus = DiagnosticReportStatus.FINAL
    conclusion_text: Optional[str] = None
    document_id: Optional[str] = None
    result_ids: List[str] = Field(default_factory=list)
    reported_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    notes: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DiagnosticReportFilter(BaseModel):
    """Filter options for querying diagnostic reports."""

    patient_id: Optional[str] = None
    order_id: Optional[str] = None
    provider_id: Optional[str] = None
    status: Optional[DiagnosticReportStatus] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=20, ge=1, le=100)


class DiagnosticReportListResponse(BaseModel):
    """Paginated diagnostic reports response."""

    items: List[DiagnosticReportRecord] = Field(default_factory=list)
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    limit: int = Field(ge=1)
