"""Phase 86: Resource Availability Evidence Schemas.

Defines structures for recording, ingesting, and evaluating resource
availability observations from authoritative monitoring sources.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

from app.schemas.governance_resource_common import (
    MANDATORY_RESOURCE_DEPENDENCY_DISCLAIMER,
    ResourceAvailabilityStatus,
)


class ResourceAvailabilityObservationRecord(BaseModel):
    observation_id: str
    tenant_id: str
    resource_id: str
    source_system: str
    observed_status: ResourceAvailabilityStatus
    observation_timestamp: datetime
    verification_timestamp: Optional[datetime] = None
    data_freshness_minutes: Optional[int] = None
    evidence_ref: Optional[str] = None
    organizational_scope: str = "ORGANIZATION"
    source_reliability: str = "MEDIUM"  # HIGH, MEDIUM, LOW, UNKNOWN
    failure_details: Optional[str] = None
    limitation_details: Optional[str] = None
    recorded_by: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    disclaimer: str = Field(default=MANDATORY_RESOURCE_DEPENDENCY_DISCLAIMER)


class SubmitAvailabilityObservationRequest(BaseModel):
    resource_id: str
    source_system: str
    observed_status: ResourceAvailabilityStatus
    observation_timestamp: Optional[datetime] = None
    source_reliability: str = "MEDIUM"
    evidence_ref: Optional[str] = None
    failure_details: Optional[str] = None
    limitation_details: Optional[str] = None
    organizational_scope: str = "ORGANIZATION"


class ResourceAvailabilitySummary(BaseModel):
    resource_id: str
    resource_name: str
    tenant_id: str
    latest_status: ResourceAvailabilityStatus
    last_observation_at: Optional[datetime] = None
    observation_count: int = 0
    is_stale: bool = False
    conflict_detected: bool = False
    disclaimer: str = Field(default=MANDATORY_RESOURCE_DEPENDENCY_DISCLAIMER)
