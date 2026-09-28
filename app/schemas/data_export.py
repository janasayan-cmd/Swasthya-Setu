"""Pydantic schemas and models for Patient Data Export (Phase 24).

Implements strict validation for:
- Export scopes and format types
- Asynchronous export request lifecycle
- Ephemeral download credentials with bounded TTL
- Audit trail serialization
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.core.privacy import DataProcessingPurpose


class ExportScope(str, Enum):
    """Supported export categories for data minimization (TRD Sec 19)."""

    PATIENT_PROFILE = "PATIENT_PROFILE"
    CLINICAL_HISTORY = "CLINICAL_HISTORY"
    ENCOUNTERS = "ENCOUNTERS"
    ALLERGIES = "ALLERGIES"
    VITALS = "VITALS"
    MEDICATIONS = "MEDICATIONS"
    PRESCRIPTIONS = "PRESCRIPTIONS"
    DOCUMENTS = "DOCUMENTS"
    TRIAGE = "TRIAGE"
    CARE_PLANS = "CARE_PLANS"
    TRANSFERS = "TRANSFERS"
    INTEROPERABILITY_DATA = "INTEROPERABILITY_DATA"
    FULL_AUTHORIZED_RECORD = "FULL_AUTHORIZED_RECORD"


class ExportFormat(str, Enum):
    """Serialization formats supported for exported records (TRD Sec 20)."""

    JSON = "JSON"
    CSV = "CSV"
    FHIR = "FHIR"


class ExportStatus(str, Enum):
    """Lifecycle status of an asynchronous patient data export job."""

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    READY = "READY"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"
    PURGED = "PURGED"


class DataExportRequest(BaseModel):
    """Client request payload to initiate an asynchronous data export."""

    scopes: List[ExportScope] = Field(
        default=[ExportScope.FULL_AUTHORIZED_RECORD],
        description="Explicit scopes requested for extraction",
    )
    format: ExportFormat = Field(
        default=ExportFormat.JSON,
        description="Target serialization format (JSON, CSV, FHIR)",
    )
    purpose: DataProcessingPurpose = Field(
        default=DataProcessingPurpose.PATIENT_DATA_EXPORT,
        description="Explicit processing purpose justifying access",
    )


class DataExportRecord(BaseModel):
    """Internal persistence record for an export job."""

    export_id: str
    patient_id: str
    requester_id: str
    status: ExportStatus
    scopes: List[ExportScope]
    format: ExportFormat
    storage_key: Optional[str] = None
    file_size_bytes: Optional[int] = None
    checksum_sha256: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    download_count: int = 0
    error_message: Optional[str] = None


class DataExportResponse(BaseModel):
    """Client-facing status summary for a patient data export."""

    export_id: str
    patient_id: str
    status: ExportStatus
    scopes: List[str]
    format: str
    created_at: datetime
    expires_at: Optional[datetime] = None
    file_size_bytes: Optional[int] = None
    error_message: Optional[str] = None
    download_ready: bool = False


class DataExportDownloadResponse(BaseModel):
    """Secure, short-lived download token response (TRD Sec 21)."""

    token: str
    download_url: str
    expires_in_seconds: int
    filename: str
