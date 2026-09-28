"""Pydantic schemas and dataclasses for Phase 22 — Asynchronous Jobs.

SAFETY & PRIVACY INVARIANTS:
- No raw PHI in job queue payloads or status summaries.
- Only reference identifiers (patient_id, document_id, prescription_id, etc.) are transmitted.
- Job transitions must follow the strict state machine:
  CREATED -> QUEUED -> PROCESSING -> COMPLETED
  PROCESSING -> RETRY_PENDING -> QUEUED -> PROCESSING
  PROCESSING -> FAILED
  QUEUED -> CANCELLED
- FAILED -> COMPLETED directly without re-execution is strictly forbidden.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field
import uuid


class JobStatus(str, Enum):
    """Database-aligned asynchronous job lifecycle states."""

    CREATED = "CREATED"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    RETRY_PENDING = "RETRY_PENDING"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class JobType(str, Enum):
    """Supported asynchronous job types."""

    DOCUMENT_PROCESSING = "DOCUMENT_PROCESSING"
    DOCUMENT_EXTRACTION = "DOCUMENT_EXTRACTION"
    PRESCRIPTION_EXTRACTION = "PRESCRIPTION_EXTRACTION"
    MEDICATION_NORMALIZATION = "MEDICATION_NORMALIZATION"
    MEDICATION_SAFETY_CHECK = "MEDICATION_SAFETY_CHECK"
    DISCHARGE_EXTRACTION = "DISCHARGE_EXTRACTION"
    CARE_PLAN_GENERATION = "CARE_PLAN_GENERATION"
    INTEROPERABILITY_IMPORT = "INTEROPERABILITY_IMPORT"
    INTEROPERABILITY_EXPORT = "INTEROPERABILITY_EXPORT"
    AI_PROCESSING = "AI_PROCESSING"

    # Phase 24: Advanced Data Privacy, Retention & De-identification
    DATA_EXPORT = "DATA_EXPORT"
    RETENTION_EVALUATION = "RETENTION_EVALUATION"
    ARCHIVE_RESOURCE = "ARCHIVE_RESOURCE"
    DELETE_RESOURCE = "DELETE_RESOURCE"
    DELETE_DOCUMENT_OBJECT = "DELETE_DOCUMENT_OBJECT"
    CLEANUP_TEMPORARY_DATA = "CLEANUP_TEMPORARY_DATA"
    PURGE_EXPIRED_EXPORT = "PURGE_EXPIRED_EXPORT"
    DEIDENTIFICATION = "DEIDENTIFICATION"
    PSEUDONYMIZATION = "PSEUDONYMIZATION"


class JobCreate(BaseModel):
    """Payload to request enqueuing an asynchronous job."""

    job_type: JobType
    patient_id: Optional[str] = Field(default=None, description="Patient reference ID")
    resource_type: str = Field(description="Target resource domain (e.g. document, prescription)")
    resource_id: str = Field(description="Unique ID of targeted resource")
    operation_type: str = Field(description="Operation identifier (e.g. extract_text, normalize_rx)")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Execution parameters (zero unmasked PHI)")
    idempotency_key: Optional[str] = Field(default=None, description="Deterministic client idempotency key")
    correlation_id: Optional[str] = Field(default=None, description="Request trace/correlation ID")
    max_retries: int = Field(default=3, ge=0, le=10, description="Max retry attempts for transient errors")


class JobRecord(BaseModel):
    """Internal database and in-memory representation of an asynchronous job."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    job_type: JobType
    status: JobStatus = Field(default=JobStatus.CREATED)
    patient_id: Optional[str] = None
    resource_type: str
    resource_id: str
    operation_type: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    result: Optional[Dict[str, Any]] = None
    initiating_user_id: Optional[str] = None
    idempotency_key: Optional[str] = None
    correlation_id: Optional[str] = None
    attempt: int = 0
    max_retries: int = 3
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    queued_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    error_category: Optional[str] = None
    is_terminal: bool = False


class JobResponse(BaseModel):
    """Public API response representing an asynchronous job."""

    id: str
    job_type: JobType
    status: JobStatus
    patient_id: Optional[str] = None
    resource_type: str
    resource_id: str
    operation_type: str
    attempt: int
    max_retries: int
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    error_category: Optional[str] = None
    result: Optional[Dict[str, Any]] = None


class JobStatusResponse(BaseModel):
    """Lightweight polling endpoint response."""

    job_id: str
    status: JobStatus
    attempt: int
    created_at: datetime
    completed_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    is_terminal: bool


class JobCancelResponse(BaseModel):
    """Response returned upon cancelling a queued job."""

    job_id: str
    status: JobStatus
    message: str


class JobRetryResponse(BaseModel):
    """Response returned upon manually retrying a failed job."""

    job_id: str
    status: JobStatus
    attempt: int
    message: str
