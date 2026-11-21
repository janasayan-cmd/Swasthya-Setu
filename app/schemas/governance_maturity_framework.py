"""Phase 77: Clinical Safety Governance Maturity Framework Schemas.

Defines the structure, versioning, dimensions, and criteria for assessing
clinical safety governance organizational maturity across 5 defined maturity levels.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


CLINICAL_SAFETY_DISCLAIMER = (
    "Maturity assessment is an internal organizational capability assessment and does NOT constitute "
    "external certification, regulatory accreditation, or proof of clinical safety. "
    "Operational maturity does not equal clinical effectiveness."
)


class MaturityLevelEnum(str, Enum):
    """5-level organizational maturity scale plus non-numerical assessment outcomes."""
    LEVEL_1_INITIAL = "LEVEL_1_INITIAL"
    LEVEL_2_DEVELOPING = "LEVEL_2_DEVELOPING"
    LEVEL_3_DEFINED = "LEVEL_3_DEFINED"
    LEVEL_4_MANAGED = "LEVEL_4_MANAGED"
    LEVEL_5_CONTINUOUSLY_IMPROVING = "LEVEL_5_CONTINUOUSLY_IMPROVING"
    NOT_ASSESSED = "NOT_ASSESSED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    UNABLE_TO_DETERMINE = "UNABLE_TO_DETERMINE"


class MaturityDimensionEnum(str, Enum):
    """Core dimensions of clinical safety governance maturity."""
    LEADERSHIP_ACCOUNTABILITY = "LEADERSHIP_ACCOUNTABILITY"
    CLINICAL_RISK_MANAGEMENT = "CLINICAL_RISK_MANAGEMENT"
    INCIDENT_LEARNING = "INCIDENT_LEARNING"
    DECISION_ASSURANCE = "DECISION_ASSURANCE"
    IMPLEMENTATION_CHANGE_GOVERNANCE = "IMPLEMENTATION_CHANGE_GOVERNANCE"
    EFFECTIVENESS_BENEFITS_ASSURANCE = "EFFECTIVENESS_BENEFITS_ASSURANCE"
    AUDIT_COMPLIANCE_ASSURANCE = "AUDIT_COMPLIANCE_ASSURANCE"
    ORGANIZATIONAL_LEARNING_IMPROVEMENT = "ORGANIZATIONAL_LEARNING_IMPROVEMENT"


class FrameworkStatus(str, Enum):
    """Lifecycle status of a maturity framework definition."""
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    ARCHIVED = "ARCHIVED"


class ScopeTypeEnum(str, Enum):
    """Organizational boundary types for maturity assessment."""
    ORGANIZATION = "ORGANIZATION"
    BUSINESS_UNIT = "BUSINESS_UNIT"
    FACILITY = "FACILITY"
    DEPARTMENT = "DEPARTMENT"
    TEAM = "TEAM"
    WORKFLOW = "WORKFLOW"
    CROSS_FUNCTIONAL = "CROSS_FUNCTIONAL"


class MaturityCriterion(BaseModel):
    """Individual maturity criterion within a dimension and level."""
    model_config = ConfigDict(extra="forbid")

    criterion_id: str
    dimension: MaturityDimensionEnum
    target_level: MaturityLevelEnum
    title: str
    description: str
    required_evidence_types: List[str] = Field(default_factory=list)
    verification_requirements: str
    mandatory: bool = True
    threshold_percentage: float = 100.0


class MaturityDimensionDefinition(BaseModel):
    """Definition of a governance maturity dimension and its criteria."""
    model_config = ConfigDict(extra="forbid")

    dimension: MaturityDimensionEnum
    title: str
    description: str
    weight: float = 1.0
    criteria: List[MaturityCriterion] = Field(default_factory=list)


class GovernanceMaturityFrameworkRecord(BaseModel):
    """Authoritative record for a clinical safety governance maturity framework."""
    model_config = ConfigDict(extra="forbid")

    framework_id: str
    tenant_id: str
    framework_code: str
    name: str
    version: str
    status: FrameworkStatus
    description: str
    dimensions: List[MaturityDimensionDefinition] = Field(default_factory=list)
    author_id: str
    approved_by: Optional[str] = None
    approval_date: Optional[str] = None
    activated_at: Optional[str] = None
    superseded_by_framework_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    disclaimer: str = CLINICAL_SAFETY_DISCLAIMER
    created_at: str
    updated_at: str


class CreateFrameworkRequest(BaseModel):
    """Request to create a new maturity framework in DRAFT status."""
    model_config = ConfigDict(extra="forbid")

    framework_code: str
    name: str
    version: str
    description: str
    dimensions: Optional[List[MaturityDimensionDefinition]] = None
    metadata: Optional[Dict[str, Any]] = None


class AddDimensionRequest(BaseModel):
    """Request to add or update a dimension in a framework."""
    model_config = ConfigDict(extra="forbid")

    dimension: MaturityDimensionEnum
    title: str
    description: str
    weight: float = 1.0
    criteria: Optional[List[MaturityCriterion]] = None


class AddCriterionRequest(BaseModel):
    """Request to add a criterion to a framework dimension."""
    model_config = ConfigDict(extra="forbid")

    criterion_id: str
    dimension: MaturityDimensionEnum
    target_level: MaturityLevelEnum
    title: str
    description: str
    required_evidence_types: List[str] = Field(default_factory=list)
    verification_requirements: str
    mandatory: bool = True
    threshold_percentage: float = 100.0


class ApproveFrameworkRequest(BaseModel):
    """Request to approve a submitted framework."""
    model_config = ConfigDict(extra="forbid")

    approver_notes: Optional[str] = None


class ActivateFrameworkRequest(BaseModel):
    """Request to activate an approved framework (supersedes previous active)."""
    model_config = ConfigDict(extra="forbid")

    activation_notes: Optional[str] = None


class SupersedeFrameworkRequest(BaseModel):
    """Request to supersede an active framework."""
    model_config = ConfigDict(extra="forbid")

    superseding_framework_id: str
    reason: str
