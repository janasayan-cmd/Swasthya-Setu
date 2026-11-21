"""Phase 78: Governance Strategic Milestone and Dependency Schemas.

Defines schemas and models for:
- Strategic roadmap milestones and delivery tracking
- Typed dependencies (sequential, prerequisite, resource, approval, implementation)
- Dependency validation (cycle detection, date conflicts, invalid references)
- Verified milestone completion (not based solely on date passing or unverified owner status)
"""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.governance_strategy_objective import CLINICAL_SAFETY_STRATEGY_DISCLAIMER


class MilestoneStatus(str, Enum):
    """Lifecycle status of a strategic milestone."""
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    DELAYED = "DELAYED"
    BLOCKED = "BLOCKED"
    CANCELLED = "CANCELLED"


class DependencyType(str, Enum):
    """Classification of milestone dependency relationship."""
    SEQUENTIAL = "SEQUENTIAL"
    PREREQUISITE_CAPABILITY = "PREREQUISITE_CAPABILITY"
    RESOURCE_DEPENDENCY = "RESOURCE_DEPENDENCY"
    APPROVAL_DEPENDENCY = "APPROVAL_DEPENDENCY"
    EXTERNAL_INTEGRATION = "EXTERNAL_INTEGRATION"
    GOVERNANCE_DECISION = "GOVERNANCE_DECISION"
    IMPLEMENTATION_DEPENDENCY = "IMPLEMENTATION_DEPENDENCY"


class MilestoneDependency(BaseModel):
    """Dependency relationship between two milestones."""
    model_config = ConfigDict(extra="forbid")

    dependency_id: str
    milestone_id: str
    depends_on_milestone_id: str
    dependency_type: DependencyType
    description: str


class GovernanceStrategyMilestoneRecord(BaseModel):
    """Authoritative record for a strategic roadmap milestone."""
    model_config = ConfigDict(extra="forbid")

    milestone_id: str
    tenant_id: str
    roadmap_id: str
    related_objective_id: Optional[str] = None
    title: str
    description: str
    planned_start_date: str
    planned_completion_date: str
    actual_start_date: Optional[str] = None
    actual_completion_date: Optional[str] = None
    responsible_owner_id: str
    expected_deliverables: List[str] = Field(default_factory=list)
    evidence_requirements: List[str] = Field(default_factory=list)
    completion_evidence_reference: Optional[str] = None
    related_portfolio_id: Optional[str] = None
    related_implementation_id: Optional[str] = None
    status: MilestoneStatus
    delay_reason: Optional[str] = None
    dependencies: List[MilestoneDependency] = Field(default_factory=list)
    verified_by: Optional[str] = None
    verified_at: Optional[str] = None
    disclaimer: str = CLINICAL_SAFETY_STRATEGY_DISCLAIMER
    created_at: str
    updated_at: str


class CreateMilestoneRequest(BaseModel):
    """Request to create a new milestone in a roadmap."""
    model_config = ConfigDict(extra="forbid")

    roadmap_id: str
    related_objective_id: Optional[str] = None
    title: str
    description: str
    planned_start_date: str
    planned_completion_date: str
    responsible_owner_id: str
    expected_deliverables: Optional[List[str]] = None
    evidence_requirements: Optional[List[str]] = None
    related_portfolio_id: Optional[str] = None
    related_implementation_id: Optional[str] = None


class UpdateMilestoneRequest(BaseModel):
    """Request to update an existing milestone."""
    model_config = ConfigDict(extra="forbid")

    title: Optional[str] = None
    description: Optional[str] = None
    planned_start_date: Optional[str] = None
    planned_completion_date: Optional[str] = None
    status: Optional[MilestoneStatus] = None
    delay_reason: Optional[str] = None
    related_portfolio_id: Optional[str] = None
    related_implementation_id: Optional[str] = None


class AddDependencyRequest(BaseModel):
    """Request to establish a dependency between milestones."""
    model_config = ConfigDict(extra="forbid")

    depends_on_milestone_id: str
    dependency_type: DependencyType
    description: str


class SubmitMilestoneCompletionRequest(BaseModel):
    """Request to submit milestone completion with required supporting evidence reference."""
    model_config = ConfigDict(extra="forbid")

    completion_evidence_reference: str = Field(..., description="Reference to authoritative evidence verifying completion")
    actual_completion_date: Optional[str] = None


class VerifyMilestoneCompletionRequest(BaseModel):
    """Request to verify milestone completion by an independent verifier."""
    model_config = ConfigDict(extra="forbid")

    verification_notes: Optional[str] = None


class DependencyValidationResult(BaseModel):
    """Validation report for milestone dependency integrity."""
    model_config = ConfigDict(extra="forbid")

    is_valid: bool
    cycles_detected: List[List[str]] = Field(default_factory=list)
    missing_prerequisites: List[str] = Field(default_factory=list)
    date_conflicts: List[str] = Field(default_factory=list)
    disclaimer: str = CLINICAL_SAFETY_STRATEGY_DISCLAIMER
