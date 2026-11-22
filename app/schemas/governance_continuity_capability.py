"""Phase 80: Critical Governance Capability Inventory Schemas.

Defines schemas and models for:
- Controlled inventory of critical clinical safety governance capabilities
- Criticality tiers and continuity attributes
- Human approval workflows and versioning
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

CLINICAL_SAFETY_CONTINUITY_DISCLAIMER = (
    "Governance resilience and continuity assurance records are administrative coordination instruments "
    "and do NOT constitute proof of clinical safety, regulatory compliance, or operational recovery. "
    "Phase 80 does not replace authoritative workflows of Phases 49, 54, 55, 63, 67, 69, 70, 72, 73, 74, 75, 76, 77, 78, or 79."
)


class CapabilityCriticalityTier(str, Enum):
    """Criticality tiers for clinical safety governance capabilities."""
    TIER_1_CRITICAL = "TIER_1_CRITICAL"
    TIER_2_ESSENTIAL = "TIER_2_ESSENTIAL"
    TIER_3_IMPORTANT = "TIER_3_IMPORTANT"
    TIER_4_SUPPORTING = "TIER_4_SUPPORTING"


class CapabilityInventoryStatus(str, Enum):
    """Lifecycle status of a registered governance capability."""
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    ACTIVE = "ACTIVE"
    RETIRED = "RETIRED"


class ClinicalSafetyGovernanceCapabilityRecord(BaseModel):
    """Authoritative record for an inventoried critical governance capability."""
    model_config = ConfigDict(extra="forbid")

    capability_id: str
    tenant_id: str
    name: str
    description: str
    organizational_scope: Dict[str, Any] = Field(default_factory=dict)
    responsible_department: str
    accountable_owner_id: str
    supporting_roles: List[str] = Field(default_factory=list)
    related_workflow: str
    criticality: CapabilityCriticalityTier
    continuity_requirement_id: Optional[str] = None
    required_supporting_systems: List[str] = Field(default_factory=list)
    required_integrations: List[str] = Field(default_factory=list)
    required_information_sources: List[str] = Field(default_factory=list)
    minimum_operational_requirements: str
    max_acceptable_interruption_hours: float
    recovery_priority: int = Field(1, ge=1, le=10)
    status: CapabilityInventoryStatus
    approved_by: Optional[str] = None
    approval_reference: Optional[str] = None
    review_date: str
    version: int = 1
    disclaimer: str = CLINICAL_SAFETY_CONTINUITY_DISCLAIMER
    created_at: str
    updated_at: str


class RegisterCapabilityRequest(BaseModel):
    """Request to register a critical governance capability."""
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    organizational_scope: Optional[Dict[str, Any]] = None
    responsible_department: str
    accountable_owner_id: str
    supporting_roles: Optional[List[str]] = None
    related_workflow: str
    criticality: CapabilityCriticalityTier
    required_supporting_systems: Optional[List[str]] = None
    required_integrations: Optional[List[str]] = None
    required_information_sources: Optional[List[str]] = None
    minimum_operational_requirements: str
    max_acceptable_interruption_hours: float = 4.0
    recovery_priority: int = 1
    review_date: str


class UpdateCapabilityRequest(BaseModel):
    """Request to update draft capability information."""
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = None
    description: Optional[str] = None
    responsible_department: Optional[str] = None
    accountable_owner_id: Optional[str] = None
    supporting_roles: Optional[List[str]] = None
    criticality: Optional[CapabilityCriticalityTier] = None
    minimum_operational_requirements: Optional[str] = None
    max_acceptable_interruption_hours: Optional[float] = None
    recovery_priority: Optional[int] = None
    review_date: Optional[str] = None


class SubmitCapabilityRequest(BaseModel):
    """Request to submit capability for review and approval."""
    model_config = ConfigDict(extra="forbid")

    submission_notes: Optional[str] = None


class ApproveCapabilityRequest(BaseModel):
    """Request to approve capability classification with separation of duties."""
    model_config = ConfigDict(extra="forbid")

    approval_reference: str
    approval_notes: Optional[str] = None
