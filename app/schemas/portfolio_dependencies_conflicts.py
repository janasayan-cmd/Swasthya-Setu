"""Phase 75: Cross-Initiative Dependencies, Conflicts & Graph Schemas.

Defines schemas and models for:
- Explicit cross-initiative dependency management
- Dependency graph generation and circular dependency detection
- Conflict detection, human review, and formal disposition
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class DependencyType(str, Enum):
    """Classification of cross-initiative dependency."""
    MUST_COMPLETE_BEFORE = "MUST_COMPLETE_BEFORE"
    MUST_START_BEFORE = "MUST_START_BEFORE"
    SHARED_INFRASTRUCTURE = "SHARED_INFRASTRUCTURE"
    SHARED_OPERATIONAL_RESOURCE = "SHARED_OPERATIONAL_RESOURCE"
    SHARED_TRAINING = "SHARED_TRAINING"
    SHARED_PROCEDURE = "SHARED_PROCEDURE"
    SHARED_SYSTEM_INTEGRATION = "SHARED_SYSTEM_INTEGRATION"
    SHARED_EVIDENCE = "SHARED_EVIDENCE"
    ORGANIZATIONAL_READINESS = "ORGANIZATIONAL_READINESS"
    MUTUAL_EXCLUSION = "MUTUAL_EXCLUSION"
    CONDITIONAL = "CONDITIONAL"


class DependencyStatus(str, Enum):
    """Lifecycle status of a cross-initiative dependency."""
    PROPOSED = "PROPOSED"
    UNDER_REVIEW = "UNDER_REVIEW"
    CONFIRMED = "CONFIRMED"
    ACTIVE = "ACTIVE"
    SATISFIED = "SATISFIED"
    BLOCKED = "BLOCKED"
    DISPUTED = "DISPUTED"
    REMOVED = "REMOVED"
    CANCELLED = "CANCELLED"


class CrossInitiativeDependencyRecord(BaseModel):
    """Authoritative record representing a dependency between two initiatives."""
    model_config = ConfigDict(extra="forbid")

    dependency_id: str
    portfolio_id: str
    tenant_id: str
    source_initiative_id: str = Field(..., description="The dependent initiative")
    target_initiative_id: str = Field(..., description="The prerequisite initiative")
    dependency_type: DependencyType
    description: str
    dependency_owner_id: str
    required_condition: str
    expected_resolution_date: Optional[str] = None
    status: DependencyStatus = DependencyStatus.PROPOSED
    supporting_evidence_reference: Optional[str] = None
    dispute_reason: Optional[str] = None
    verified_by: Optional[str] = None
    verified_at: Optional[str] = None
    created_by: str
    created_at: str
    updated_at: str


class CreateDependencyRequest(BaseModel):
    """Request payload to declare a cross-initiative dependency."""
    model_config = ConfigDict(extra="forbid")

    target_initiative_id: str = Field(..., min_length=2)
    dependency_type: DependencyType
    description: str = Field(..., min_length=5)
    dependency_owner_id: str
    required_condition: str = Field(..., min_length=3)
    expected_resolution_date: Optional[str] = None
    supporting_evidence_reference: Optional[str] = None


class ConfirmDependencyRequest(BaseModel):
    """Request payload to confirm a proposed dependency."""
    model_config = ConfigDict(extra="forbid")

    confirmation_notes: Optional[str] = None


class ResolveDependencyRequest(BaseModel):
    """Request payload to mark a dependency satisfied."""
    model_config = ConfigDict(extra="forbid")

    resolution_evidence: str = Field(..., min_length=3)


class DisputeDependencyRequest(BaseModel):
    """Request payload to dispute a dependency."""
    model_config = ConfigDict(extra="forbid")

    dispute_reason: str = Field(..., min_length=5)


# -----------------------------------------------------------------------------
# Conflicts
# -----------------------------------------------------------------------------


class ConflictClassification(str, Enum):
    """Classification of an observed cross-initiative conflict."""
    OVERLAPPING_SCHEDULE = "OVERLAPPING_SCHEDULE"
    COMPETING_RESOURCE = "COMPETING_RESOURCE"
    CONFLICTING_PROCEDURE = "CONFLICTING_PROCEDURE"
    INCOMPATIBLE_WORKFLOW = "INCOMPATIBLE_WORKFLOW"
    SHARED_INTEGRATION_CONSTRAINT = "SHARED_INTEGRATION_CONSTRAINT"
    TRAINING_COLLISION = "TRAINING_COLLISION"
    INCONSISTENT_BASELINE = "INCONSISTENT_BASELINE"


class ConflictStatus(str, Enum):
    """State of an identified cross-initiative conflict."""
    POTENTIAL_CONFLICT = "POTENTIAL_CONFLICT"
    CONFIRMED_CONFLICT = "CONFIRMED_CONFLICT"
    RESOLVED_CONFLICT = "RESOLVED_CONFLICT"
    ACCEPTED_CONSTRAINT = "ACCEPTED_CONSTRAINT"
    UNABLE_TO_DETERMINE = "UNABLE_TO_DETERMINE"


class PortfolioConflictRecord(BaseModel):
    """Authoritative record representing a conflict between initiatives."""
    model_config = ConfigDict(extra="forbid")

    conflict_id: str
    portfolio_id: str
    tenant_id: str
    initiative_ids: List[str] = Field(default_factory=list)
    classification: ConflictClassification
    description: str
    status: ConflictStatus = ConflictStatus.POTENTIAL_CONFLICT
    detected_by: str = "AUTOMATED_SCAN"
    detected_at: str
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[str] = None
    review_notes: Optional[str] = None
    disposition: Optional[str] = None
    disposed_by: Optional[str] = None
    disposed_at: Optional[str] = None
    disposition_notes: Optional[str] = None
    created_at: str
    updated_at: str


class ReviewConflictRequest(BaseModel):
    """Request payload to record human review of a potential conflict."""
    model_config = ConfigDict(extra="forbid")

    confirmed: bool
    review_notes: str = Field(..., min_length=5)


class DisposeConflictRequest(BaseModel):
    """Request payload to formally dispose a conflict."""
    model_config = ConfigDict(extra="forbid")

    disposition: str = Field(..., description="CONFIRMED_CONFLICT, RESOLVED_CONFLICT, ACCEPTED_CONSTRAINT, or UNABLE_TO_DETERMINE")
    disposition_notes: str = Field(..., min_length=5)


class DependencyGraphResponse(BaseModel):
    """Full graph representation of portfolio initiatives, dependencies, and circular cycles."""
    model_config = ConfigDict(extra="forbid")

    portfolio_id: str
    nodes: List[Dict[str, Any]] = Field(default_factory=list)
    edges: List[Dict[str, Any]] = Field(default_factory=list)
    circular_dependency_detected: bool = False
    circular_paths: List[List[str]] = Field(default_factory=list)
    blocked_initiative_ids: List[str] = Field(default_factory=list)
