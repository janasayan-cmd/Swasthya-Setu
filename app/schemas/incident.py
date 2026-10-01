"""Incident Management Schemas for HealthSetu (Phase 27).

Provides data contracts for:
- Operational incident logging and tracking
- Incident lifecycle transitions: OPEN -> INVESTIGATING -> MITIGATED -> RESOLVED -> CLOSED
- Audit correlation and operator accountability
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
import uuid


class IncidentStatus(str, Enum):
    """Operational incident lifecycle states."""

    OPEN = "OPEN"
    INVESTIGATING = "INVESTIGATING"
    MITIGATED = "MITIGATED"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class IncidentSeverity(str, Enum):
    """Operational impact severity grading."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class IncidentCategory(str, Enum):
    """Categorization of operational failures and outages."""

    API_OUTAGE = "API_OUTAGE"
    DATABASE_FAILURE = "DATABASE_FAILURE"
    QUEUE_FAILURE = "QUEUE_FAILURE"
    OCR_FAILURE = "OCR_FAILURE"
    MEDICATION_PROVIDER_OUTAGE = "MEDICATION_PROVIDER_OUTAGE"
    AI_PROVIDER_OUTAGE = "AI_PROVIDER_OUTAGE"
    INTEROPERABILITY_FAILURE = "INTEROPERABILITY_FAILURE"
    SECURITY_INCIDENT = "SECURITY_INCIDENT"
    DATA_QUALITY_INCIDENT = "DATA_QUALITY_INCIDENT"
    PERFORMANCE_INCIDENT = "PERFORMANCE_INCIDENT"
    DEPLOYMENT_INCIDENT = "DEPLOYMENT_INCIDENT"
    OTHER = "OTHER"


class IncidentCreate(BaseModel):
    """Payload to declare a new operational incident."""

    title: str = Field(..., min_length=3, max_length=200, description="Brief summary of operational incident")
    description: str = Field(..., min_length=5, max_length=4000, description="Detailed technical symptoms and impact")
    category: IncidentCategory = Field(default=IncidentCategory.OTHER, description="Operational failure classification")
    severity: IncidentSeverity = Field(default=IncidentSeverity.MEDIUM, description="Impact severity level")
    correlation_id: Optional[str] = Field(default=None, description="Request ID or trace reference if available")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Operational diagnostics (zero raw PHI/secrets)")


class IncidentUpdate(BaseModel):
    """Payload to update an active operational incident."""

    status: Optional[IncidentStatus] = None
    severity: Optional[IncidentSeverity] = None
    description: Optional[str] = Field(default=None, max_length=4000)
    owner: Optional[str] = Field(default=None, description="Operator user ID assigned to the incident")
    notes: Optional[str] = Field(default=None, max_length=2000, description="Investigation progress note")


class IncidentAcknowledge(BaseModel):
    """Payload to acknowledge an open incident and assign ownership."""

    owner: Optional[str] = Field(default=None, description="Assignee operator ID (defaults to current user)")
    notes: Optional[str] = Field(default=None, description="Initial triage or investigation note")


class IncidentResolve(BaseModel):
    """Payload to resolve an incident with clinical/operational closure notes."""

    resolution_summary: str = Field(..., min_length=5, max_length=2000, description="Summary of root cause and mitigation steps")
    status: IncidentStatus = Field(default=IncidentStatus.RESOLVED, description="Target resolved state (RESOLVED or CLOSED)")


class IncidentRecord(BaseModel):
    """Full operational incident record stored internally and returned to operators."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(default_factory=lambda: f"inc-{uuid.uuid4().hex[:12]}")
    title: str
    description: str
    category: IncidentCategory
    severity: IncidentSeverity
    status: IncidentStatus = Field(default=IncidentStatus.OPEN)
    detected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    owner: Optional[str] = None
    correlation_id: Optional[str] = None
    resolution_summary: Optional[str] = None
    created_by: str
    updated_by: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)


class IncidentListResponse(BaseModel):
    """Paginated response envelope for incident queries."""

    items: List[IncidentRecord]
    total: int
    skip: int
    limit: int
