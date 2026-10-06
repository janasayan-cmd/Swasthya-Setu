"""Phase 49: Incident Evidence & Chronological Timeline Schemas.

Defines evidence reference models and reconstructed timeline entries.
Evidence is referenced from source systems without duplicating complete PHI.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


class EvidenceType(str, Enum):
    """Controlled taxonomy of evidence types referenced during safety investigations."""

    DECISION_TRACE = "DECISION_TRACE"
    AUDIT_EVENT = "AUDIT_EVENT"
    VERSION_HISTORY = "VERSION_HISTORY"
    PROVIDER_RESPONSE = "PROVIDER_RESPONSE"
    WORKFLOW_STEP = "WORKFLOW_STEP"
    TASK_RECORD = "TASK_RECORD"
    ALERT_RECORD = "ALERT_RECORD"
    OBSERVABILITY_METRIC = "OBSERVABILITY_METRIC"
    STRUCTURED_LOG = "STRUCTURED_LOG"
    DOCUMENT_REFERENCE = "DOCUMENT_REFERENCE"
    CLINICAL_REPORT = "CLINICAL_REPORT"


class EvidenceReference(BaseModel):
    """Immutable pointer to evidence gathered during an incident investigation."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: f"ev-{uuid.uuid4().hex[:12]}")
    incident_id: str
    evidence_type: EvidenceType
    reference_id: str = Field(description="Foreign identifier in the authoritative subsystem (e.g. decision ID)")
    summary: str = Field(description="Descriptive non-PHI summary of what this evidence shows")
    source_system: str = Field(description="Originating subsystem e.g. decision_service, audit_repository")
    snapshot_hash: Optional[str] = Field(default=None, description="Cryptographic SHA-256 integrity hash")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Safe technical metadata. Must not contain PHI.")
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    recorded_by_id: Optional[str] = None


class EvidenceAttachRequest(BaseModel):
    """Request payload to attach a new evidence pointer to an incident."""

    model_config = ConfigDict(extra="forbid")

    evidence_type: EvidenceType
    reference_id: str
    summary: str
    source_system: str
    snapshot_hash: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class IncidentTimelineEntry(BaseModel):
    """Reconstructed chronological sequence entry for safety investigations."""

    model_config = ConfigDict(extra="ignore")

    entry_id: str = Field(default_factory=lambda: f"tle-{uuid.uuid4().hex[:12]}")
    timestamp: datetime
    event_time_type: str = Field(description="'OCCURRED', 'DETECTED', 'RECORDED', 'TRIAGED', 'CONTAINED', 'RESOLVED', 'CLOSED'")
    title: str
    description: str
    source: str
    evidence_id: Optional[str] = None
