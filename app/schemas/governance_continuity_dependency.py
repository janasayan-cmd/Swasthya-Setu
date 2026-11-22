"""Phase 80: Governance Dependency Mapping Schemas.

Defines schemas and models for:
- Personnel, system, information, and external dependencies
- Single point of failure (SPOF) identification
- Unvalidated alternative tracking
"""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.governance_continuity_capability import (
    CLINICAL_SAFETY_CONTINUITY_DISCLAIMER,
)


class ContinuityDependencyType(str, Enum):
    """Classification of critical governance dependency."""
    PERSONNEL = "PERSONNEL"
    SYSTEM = "SYSTEM"
    INFORMATION = "INFORMATION"
    EXTERNAL = "EXTERNAL"


class DependencyCriticality(str, Enum):
    """Criticality ranking of the dependency."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class DependencyStatus(str, Enum):
    """Validation status of the dependency."""
    IDENTIFIED = "IDENTIFIED"
    VALIDATED = "VALIDATED"
    UNVALIDATED = "UNVALIDATED"
    CONFLICT_DETECTED = "CONFLICT_DETECTED"
    WAIVED = "WAIVED"


class GovernanceContinuityDependencyRecord(BaseModel):
    """Authoritative record for an inter-domain governance dependency."""
    model_config = ConfigDict(extra="forbid")

    dependency_id: str
    tenant_id: str
    source_capability_id: str
    dependency_type: ContinuityDependencyType
    target_reference: str
    criticality: DependencyCriticality
    responsible_owner_id: str
    availability_requirements: str
    has_validated_alternative: bool = False
    alternative_arrangement_description: str = ""
    is_single_point_of_failure: bool = False
    last_validation_date: Optional[str] = None
    status: DependencyStatus
    evidence_references: List[str] = Field(default_factory=list)
    disclaimer: str = CLINICAL_SAFETY_CONTINUITY_DISCLAIMER
    created_at: str
    updated_at: str


class CreateDependencyRequest(BaseModel):
    """Request to establish a critical governance dependency."""
    model_config = ConfigDict(extra="forbid")

    source_capability_id: str
    dependency_type: ContinuityDependencyType
    target_reference: str
    criticality: DependencyCriticality = DependencyCriticality.HIGH
    responsible_owner_id: str
    availability_requirements: str = "High availability with real-time failover or tested manual substitute."
    has_validated_alternative: bool = False
    alternative_arrangement_description: Optional[str] = ""
    is_single_point_of_failure: bool = False
    evidence_references: Optional[List[str]] = None


class ValidateDependencyRequest(BaseModel):
    """Request to validate dependency and verify alternative arrangement."""
    model_config = ConfigDict(extra="forbid")

    status: DependencyStatus
    has_validated_alternative: bool
    alternative_arrangement_description: Optional[str] = None
    is_single_point_of_failure: bool
    evidence_reference: str
    validation_notes: Optional[str] = None


class DependencyValidationResult(BaseModel):
    """Report detailing single points of failure and unvalidated dependencies."""
    model_config = ConfigDict(extra="forbid")

    tenant_id: str
    total_dependencies: int
    single_points_of_failure: List[GovernanceContinuityDependencyRecord] = Field(default_factory=list)
    unvalidated_dependencies: List[GovernanceContinuityDependencyRecord] = Field(default_factory=list)
    disclaimer: str = CLINICAL_SAFETY_CONTINUITY_DISCLAIMER
