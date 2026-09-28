"""Domain event schemas and contracts (Phase 22).

INVARIANTS:
- Events represent immutable facts that have ALREADY occurred.
- Events are NOT clinical recommendations or treatment orders.
- Payloads MUST NOT contain unnecessary raw PHI (use reference IDs instead).
- Every event contract is versioned to support safe evolution.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field
import uuid


class DomainEventType(str, Enum):
    """Supported domain event types."""

    PATIENT_DOCUMENT_UPLOADED = "PATIENT_DOCUMENT_UPLOADED"
    DOCUMENT_PROCESSING_COMPLETED = "DOCUMENT_PROCESSING_COMPLETED"
    DOCUMENT_PROCESSING_FAILED = "DOCUMENT_PROCESSING_FAILED"
    PRESCRIPTION_CREATED = "PRESCRIPTION_CREATED"
    MEDICATION_NORMALIZED = "MEDICATION_NORMALIZED"
    MEDICATION_SAFETY_EVALUATION_COMPLETED = "MEDICATION_SAFETY_EVALUATION_COMPLETED"
    DISCHARGE_EXTRACTION_COMPLETED = "DISCHARGE_EXTRACTION_COMPLETED"
    CARE_PLAN_CREATED = "CARE_PLAN_CREATED"
    INTEROPERABILITY_IMPORT_COMPLETED = "INTEROPERABILITY_IMPORT_COMPLETED"
    INTEROPERABILITY_EXPORT_COMPLETED = "INTEROPERABILITY_EXPORT_COMPLETED"


class DomainEvent(BaseModel):
    """Versioned domain event contract transmitted over event buses or stored in outbox."""

    model_config = ConfigDict(frozen=True)

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: DomainEventType
    event_version: str = Field(default="1.0", description="SemVer schema version")
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    producer: str = Field(default="healthsetu-backend")
    correlation_id: Optional[str] = Field(default=None)
    resource_type: str = Field(description="Target resource domain (e.g. document, prescription)")
    resource_id: str = Field(description="Non-PHI identifier of resource")
    patient_id: Optional[str] = Field(default=None, description="Patient reference ID")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Event body (references only, zero raw PHI)")


class OutboxStatus(str, Enum):
    """Transactional outbox event status."""

    PENDING = "PENDING"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"


class OutboxEventRecord(BaseModel):
    """Transactional outbox record ensuring reliable event publishing after DB commit."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event: DomainEvent
    status: OutboxStatus = Field(default=OutboxStatus.PENDING)
    attempts: int = 0
    max_attempts: int = 5
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    published_at: Optional[datetime] = None
    last_error: Optional[str] = None
