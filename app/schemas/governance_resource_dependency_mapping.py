"""Phase 86: Capability-to-Resource Dependency Mapping Schemas.

Defines structured mappings between critical governance capabilities and their
required resources, with dependency type classification and approval lifecycle.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

from app.schemas.governance_resource_common import (
    MANDATORY_RESOURCE_DEPENDENCY_DISCLAIMER,
    DependencyMappingStatus,
    DependencyType,
    ResourceCriticality,
)


class CapabilityResourceDependencyRecord(BaseModel):
    dependency_id: str
    tenant_id: str
    governance_capability_ref: str
    responsibility_ref: Optional[str] = None
    resource_id: str
    resource_criticality: ResourceCriticality = ResourceCriticality.CRITICAL
    dependency_type: DependencyType = DependencyType.REQUIRED
    minimum_availability_pct: float = Field(default=99.0)
    required_operating_capacity: Optional[str] = None
    organizational_scope: str = "ORGANIZATION"
    dependency_owner: Optional[str] = None
    evidence_refs: List[str] = Field(default_factory=list)
    status: DependencyMappingStatus = DependencyMappingStatus.DRAFT
    effective_start: Optional[datetime] = None
    effective_end: Optional[datetime] = None
    created_by: str
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    disclaimer: str = Field(default=MANDATORY_RESOURCE_DEPENDENCY_DISCLAIMER)


class CreateDependencyMappingRequest(BaseModel):
    governance_capability_ref: str
    responsibility_ref: Optional[str] = None
    resource_id: str
    resource_criticality: ResourceCriticality = ResourceCriticality.CRITICAL
    dependency_type: DependencyType = DependencyType.REQUIRED
    minimum_availability_pct: float = Field(default=99.0)
    required_operating_capacity: Optional[str] = None
    organizational_scope: str = "ORGANIZATION"
    dependency_owner: Optional[str] = None
    evidence_refs: List[str] = Field(default_factory=list)
    effective_start: Optional[datetime] = None
    effective_end: Optional[datetime] = None


class ApproveDependencyMappingRequest(BaseModel):
    notes: Optional[str] = None


class UpdateDependencyMappingRequest(BaseModel):
    dependency_type: Optional[DependencyType] = None
    minimum_availability_pct: Optional[float] = None
    required_operating_capacity: Optional[str] = None
    dependency_owner: Optional[str] = None
    evidence_refs: Optional[List[str]] = None
    effective_end: Optional[datetime] = None
