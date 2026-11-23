"""Phase 86: Resource Dependency Gap Management Schemas.

Defines gap records, remediation assignments, authoritative escalations,
and resolution verification for resource dependency deficits.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

from app.schemas.governance_resource_common import (
    MANDATORY_RESOURCE_DEPENDENCY_DISCLAIMER,
    ResourceGapCategory,
    ResourceGapStatus,
    SPOFSeverity,
)


class ResourceDependencyGapRecord(BaseModel):
    gap_id: str
    tenant_id: str
    governance_capability_ref: Optional[str] = None
    resource_id: Optional[str] = None
    dependency_id: Optional[str] = None
    category: ResourceGapCategory
    severity: SPOFSeverity = SPOFSeverity.HIGH
    status: ResourceGapStatus = ResourceGapStatus.IDENTIFIED
    title: str
    description: str
    identified_at: datetime = Field(default_factory=datetime.utcnow)
    assigned_to: Optional[str] = None
    remediation_proposal: Optional[str] = None
    target_resolution_date: Optional[datetime] = None
    escalated_to_phase: Optional[str] = None
    escalation_reference_id: Optional[str] = None
    resolution_evidence_ref: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolution_verified_by: Optional[str] = None
    created_by: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    disclaimer: str = Field(default=MANDATORY_RESOURCE_DEPENDENCY_DISCLAIMER)


class CreateResourceGapRequest(BaseModel):
    governance_capability_ref: Optional[str] = None
    resource_id: Optional[str] = None
    dependency_id: Optional[str] = None
    category: ResourceGapCategory
    severity: SPOFSeverity = SPOFSeverity.HIGH
    title: str
    description: str
    assigned_to: Optional[str] = None
    remediation_proposal: Optional[str] = None
    target_resolution_date: Optional[datetime] = None


class AssignResourceGapRequest(BaseModel):
    assigned_to: str
    remediation_proposal: Optional[str] = None
    target_resolution_date: Optional[datetime] = None


class EscalateResourceGapRequest(BaseModel):
    escalated_to_phase: str
    escalation_reference_id: str
    escalation_notes: Optional[str] = None


class ResolveResourceGapRequest(BaseModel):
    resolution_notes: str
    resolution_evidence_ref: Optional[str] = None
