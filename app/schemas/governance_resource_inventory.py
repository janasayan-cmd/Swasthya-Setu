"""Phase 86: Critical Resource Inventory Schemas.

Defines the inventory structure for resources required by clinical safety governance operations.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

from app.schemas.governance_resource_common import (
    MANDATORY_RESOURCE_DEPENDENCY_DISCLAIMER,
    ResourceCategory,
    ResourceCriticality,
    ResourceLifecycleStatus,
)


class CriticalResourceRecord(BaseModel):
    resource_id: str
    tenant_id: str
    resource_name: str
    category: ResourceCategory
    description: str
    owning_organization: str
    responsible_department: Optional[str] = None
    resource_owner_ref: Optional[str] = None
    criticality: ResourceCriticality = ResourceCriticality.CRITICAL
    associated_governance_capability: Optional[str] = None
    availability_requirement_hours: float = Field(default=99.9, description="Minimum availability percentage")
    recovery_requirement_ref: Optional[str] = None
    dependency_refs: List[str] = Field(default_factory=list)
    alternative_resource_refs: List[str] = Field(default_factory=list)
    external_provider_ref: Optional[str] = None
    source_system_ref: Optional[str] = None
    verification_status: str = "UNVERIFIED"
    last_verified_at: Optional[datetime] = None
    review_cycle_days: int = Field(default=90, ge=1)
    next_review_due: Optional[datetime] = None
    lifecycle_status: ResourceLifecycleStatus = ResourceLifecycleStatus.ACTIVE
    created_by: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    disclaimer: str = Field(default=MANDATORY_RESOURCE_DEPENDENCY_DISCLAIMER)


class CreateResourceRequest(BaseModel):
    resource_name: str
    category: ResourceCategory
    description: str
    owning_organization: str
    responsible_department: Optional[str] = None
    resource_owner_ref: Optional[str] = None
    criticality: ResourceCriticality = ResourceCriticality.CRITICAL
    associated_governance_capability: Optional[str] = None
    availability_requirement_hours: float = Field(default=99.9)
    recovery_requirement_ref: Optional[str] = None
    dependency_refs: List[str] = Field(default_factory=list)
    alternative_resource_refs: List[str] = Field(default_factory=list)
    external_provider_ref: Optional[str] = None
    source_system_ref: Optional[str] = None
    review_cycle_days: int = Field(default=90, ge=1)


class UpdateResourceRequest(BaseModel):
    resource_name: Optional[str] = None
    description: Optional[str] = None
    responsible_department: Optional[str] = None
    resource_owner_ref: Optional[str] = None
    criticality: Optional[ResourceCriticality] = None
    associated_governance_capability: Optional[str] = None
    availability_requirement_hours: Optional[float] = None
    recovery_requirement_ref: Optional[str] = None
    dependency_refs: Optional[List[str]] = None
    alternative_resource_refs: Optional[List[str]] = None
    external_provider_ref: Optional[str] = None
    source_system_ref: Optional[str] = None
    review_cycle_days: Optional[int] = None
    lifecycle_status: Optional[ResourceLifecycleStatus] = None
