"""Phase 80: Governance Disruption Classification Schemas.

Defines schemas and models for:
- Classification and registration of disruptions affecting governance operations
- Linking source incidents and affected capabilities
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.governance_continuity_capability import (
    CLINICAL_SAFETY_CONTINUITY_DISCLAIMER,
)


class DisruptionCategory(str, Enum):
    """Classification of disruptions that impact clinical safety governance operations."""
    TECHNOLOGY_OUTAGE = "TECHNOLOGY_OUTAGE"
    CYBERSECURITY_INCIDENT = "CYBERSECURITY_INCIDENT"
    IDENTITY_AUTHENTICATION_FAILURE = "IDENTITY_AUTHENTICATION_FAILURE"
    COMMUNICATION_FAILURE = "COMMUNICATION_FAILURE"
    WORKFORCE_SHORTAGE = "WORKFORCE_SHORTAGE"
    LOSS_OF_CRITICAL_PERSONNEL = "LOSS_OF_CRITICAL_PERSONNEL"
    FACILITY_DISRUPTION = "FACILITY_DISRUPTION"
    EXTERNAL_SERVICE_OUTAGE = "EXTERNAL_SERVICE_OUTAGE"
    DATA_AVAILABILITY_PROBLEM = "DATA_AVAILABILITY_PROBLEM"
    INTEGRATION_FAILURE = "INTEGRATION_FAILURE"
    PROLONGED_INTERRUPTION = "PROLONGED_INTERRUPTION"
    CONCURRENT_DISRUPTION = "CONCURRENT_DISRUPTION"


class DisruptionStatus(str, Enum):
    """Operational status of an ongoing governance disruption."""
    ACTIVE = "ACTIVE"
    INVESTIGATING = "INVESTIGATING"
    CONTAINED = "CONTAINED"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class GovernanceDisruptionRecord(BaseModel):
    """Authoritative record for an identified disruption affecting clinical safety governance."""
    model_config = ConfigDict(extra="forbid")

    disruption_id: str
    tenant_id: str
    category: DisruptionCategory
    description: str
    affected_organizational_scope: Dict[str, Any] = Field(default_factory=dict)
    affected_capability_ids: List[str] = Field(default_factory=list)
    source_incident_reference: Optional[str] = None
    detection_timestamp: str
    reported_impact: str
    evidence_references: List[str] = Field(default_factory=list)
    status: DisruptionStatus
    responsible_coordinator_id: str
    escalation_destination: str = "PHASE_67_ESCALATION"
    related_plan_id: Optional[str] = None
    recovery_status: str = "NOT_STARTED"
    disclaimer: str = CLINICAL_SAFETY_CONTINUITY_DISCLAIMER
    created_at: str
    updated_at: str


class RegisterDisruptionRequest(BaseModel):
    """Request to register a disruption affecting governance operations."""
    model_config = ConfigDict(extra="forbid")

    category: DisruptionCategory
    description: str
    affected_organizational_scope: Optional[Dict[str, Any]] = None
    affected_capability_ids: List[str]
    source_incident_reference: Optional[str] = None
    detection_timestamp: str
    reported_impact: str
    responsible_coordinator_id: str
    escalation_destination: str = "PHASE_67_ESCALATION"
    related_plan_id: Optional[str] = None
    evidence_references: Optional[List[str]] = None


class UpdateDisruptionRequest(BaseModel):
    """Request to update an active disruption record."""
    model_config = ConfigDict(extra="forbid")

    reported_impact: Optional[str] = None
    status: Optional[DisruptionStatus] = None
    responsible_coordinator_id: Optional[str] = None
    related_plan_id: Optional[str] = None
    recovery_status: Optional[str] = None


class CloseDisruptionRequest(BaseModel):
    """Request to close a disruption with verified resolution evidence."""
    model_config = ConfigDict(extra="forbid")

    resolution_notes: str
    verification_evidence_reference: str
