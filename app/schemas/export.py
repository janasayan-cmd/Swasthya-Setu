"""Pydantic Schemas for Controlled Clinical Exports (Phase 44).

CRITICAL ARCHITECTURAL BOUNDARIES:
- EXPORT != LIVE RECORD (Point-in-time snapshot only)
- READ ACCESS != EXPORT ACCESS
- EXPORT != CLINICAL DECISION OR PRESCRIPTION
- EXPORT MUST NOT EXPOSE PASSWORDS, SECRETS, AUDIT LOGS, OR UNRELATED PATIENT DATA
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ExportFormat(str, Enum):
    """Supported export serialization formats."""

    JSON = "JSON"
    FHIR_BUNDLE = "FHIR_BUNDLE"
    SUMMARY_TEXT = "SUMMARY_TEXT"


class ExportStatus(str, Enum):
    """Lifecycle states of an export job."""

    REQUESTED = "REQUESTED"
    GENERATING = "GENERATING"
    READY = "READY"
    EXPIRED = "EXPIRED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ExportScopeType(str, Enum):
    """Available snapshot resource scopes for export."""

    PATIENT_CLINICAL_SUMMARY = "PATIENT_CLINICAL_SUMMARY"
    MEDICATION_SUMMARY = "MEDICATION_SUMMARY"
    PRESCRIPTION_SUMMARY = "PRESCRIPTION_SUMMARY"
    LABORATORY_RESULT_SUMMARY = "LABORATORY_RESULT_SUMMARY"
    DISCHARGE_SUMMARY = "DISCHARGE_SUMMARY"
    CARE_PLAN_SUMMARY = "CARE_PLAN_SUMMARY"
    CLINICAL_DOCUMENTS = "CLINICAL_DOCUMENTS"
    FHIR_BUNDLE = "FHIR_BUNDLE"


class ExportRequestCreate(BaseModel):
    """Payload to initiate a controlled patient clinical export."""

    model_config = ConfigDict(extra="ignore")

    export_scope: ExportScopeType = Field(
        ...,
        description="Target clinical snapshot scope to export",
    )
    format: ExportFormat = Field(
        default=ExportFormat.JSON,
        description="Target export format",
    )
    purpose: str = Field(
        default="CARE_CONTINUITY",
        description="Clinical or patient justification for export",
    )
    consent_id: Optional[str] = Field(
        None,
        description="Optional active patient consent grant reference",
    )
    idempotency_key: Optional[str] = Field(
        None,
        description="Idempotency key to prevent duplicate export generation",
    )


class ExportSnapshotMetadata(BaseModel):
    """Snapshot provenance metadata captured at export time."""

    model_config = ConfigDict(extra="ignore")

    snapshot_id: str
    patient_id: str
    requester_id: str
    generated_at: datetime
    format: ExportFormat
    record_count: int = 0
    size_bytes: int = 0
    is_live_record: bool = False  # CRITICAL INVARIANT: EXPORT != LIVE RECORD


class ExportResponse(BaseModel):
    """Representation of an authorized clinical export."""

    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: str
    patient_id: str
    requester_id: str
    requester_role: str
    export_scope: ExportScopeType
    format: ExportFormat
    status: ExportStatus
    created_at: datetime
    expires_at: datetime
    completed_at: Optional[datetime] = None
    download_url: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None
    file_size_bytes: Optional[int] = None
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ExportStatusResponse(BaseModel):
    """Minimal status polling response for async export generation."""

    model_config = ConfigDict(extra="ignore")

    export_id: str
    status: ExportStatus
    progress_percentage: int = 0
    expires_at: Optional[datetime] = None
    download_url: Optional[str] = None
    error_message: Optional[str] = None
