"""Phase 79: Cross-Roadmap Dependency Schemas.

Defines schemas and models for:
- Inter-roadmap dependency tracking (shared capabilities, workforce, technology, approvals)
- Cross-roadmap dependency validation (cycle detection, sequencing conflicts)
"""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.governance_strategy_execution_monitoring import (
    CLINICAL_SAFETY_MONITORING_DISCLAIMER,
)


class CrossRoadmapDependencyCategory(str, Enum):
    """Category of dependency relationship spanning multiple roadmaps."""
    SHARED_CAPABILITY = "SHARED_CAPABILITY"
    SHARED_WORKFORCE = "SHARED_WORKFORCE"
    SHARED_TECHNOLOGY = "SHARED_TECHNOLOGY"
    SHARED_APPROVAL = "SHARED_APPROVAL"
    READINESS_REQUIREMENT = "READINESS_REQUIREMENT"
    IMPLEMENTATION_ACTIVITY = "IMPLEMENTATION_ACTIVITY"
    EXTERNAL_SERVICE = "EXTERNAL_SERVICE"


class CrossDependencyStatus(str, Enum):
    """Lifecycle status of a cross-roadmap dependency."""
    IDENTIFIED = "IDENTIFIED"
    CONFIRMED = "CONFIRMED"
    RESOLVED = "RESOLVED"
    CONFLICT_DETECTED = "CONFLICT_DETECTED"
    WAIVED = "WAIVED"


class CrossRoadmapDependencyRecord(BaseModel):
    """Authoritative record for an inter-roadmap dependency."""
    model_config = ConfigDict(extra="forbid")

    dependency_id: str
    tenant_id: str
    source_roadmap_id: str
    target_roadmap_id: str
    source_objective_id: Optional[str] = None
    target_objective_id: Optional[str] = None
    source_milestone_id: Optional[str] = None
    target_milestone_id: Optional[str] = None
    category: CrossRoadmapDependencyCategory
    rationale: str
    planned_dependency_date: str
    status: CrossDependencyStatus
    responsible_owner_id: str
    evidence_references: List[str] = Field(default_factory=list)
    conflict_description: Optional[str] = None
    review_outcome: Optional[str] = None
    disclaimer: str = CLINICAL_SAFETY_MONITORING_DISCLAIMER
    created_at: str
    updated_at: str


class CreateCrossRoadmapDependencyRequest(BaseModel):
    """Request to establish a cross-roadmap dependency."""
    model_config = ConfigDict(extra="forbid")

    source_roadmap_id: str
    target_roadmap_id: str
    source_objective_id: Optional[str] = None
    target_objective_id: Optional[str] = None
    source_milestone_id: Optional[str] = None
    target_milestone_id: Optional[str] = None
    category: CrossRoadmapDependencyCategory
    rationale: str
    planned_dependency_date: str
    responsible_owner_id: str
    evidence_references: Optional[List[str]] = None


class ReviewCrossRoadmapDependencyRequest(BaseModel):
    """Request to review and disposition a cross-roadmap dependency."""
    model_config = ConfigDict(extra="forbid")

    status: CrossDependencyStatus
    review_outcome: str
    conflict_description: Optional[str] = None


class CrossRoadmapValidationResult(BaseModel):
    """Validation report for cross-roadmap dependency integrity and sequencing."""
    model_config = ConfigDict(extra="forbid")

    is_valid: bool
    cycles_detected: List[List[str]] = Field(default_factory=list)
    date_conflicts: List[str] = Field(default_factory=list)
    missing_prerequisites: List[str] = Field(default_factory=list)
    disclaimer: str = CLINICAL_SAFETY_MONITORING_DISCLAIMER
