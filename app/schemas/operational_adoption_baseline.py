"""Phase 74: Operational Adoption Baseline Schemas.

Defines schemas and models for:
- Version-controlled operational adoption baselines
- Expected workflow behavior, practices, and readiness requirements
- Baseline submission, review, approval, and supersession tracking
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.governance_change_adoption_registration import OperationalScope


class BaselineApprovalStatus(str, Enum):
    """Approval lifecycle for an operational adoption baseline."""
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    SUPERSEDED = "SUPERSEDED"
    REJECTED = "REJECTED"


class OperationalAdoptionBaselineRecord(BaseModel):
    """Authoritative version-controlled operational baseline."""
    model_config = ConfigDict(extra="forbid")

    baseline_id: str
    registration_id: str
    tenant_id: str
    version: str = Field(..., description="Semantic version string, e.g. 1.0, 1.1")
    previous_version_id: Optional[str] = None
    change_reason: Optional[str] = None

    # Expected practices and criteria
    intended_operational_process: str
    expected_workflow_behavior: str
    required_operational_practices: List[str] = Field(default_factory=list)
    operational_scope: OperationalScope = Field(default_factory=OperationalScope)
    responsible_roles: List[str] = Field(default_factory=list)

    # Readiness & Documentation requirements
    required_training_programmes: List[str] = Field(default_factory=list)
    required_procedural_docs: List[str] = Field(default_factory=list)
    operational_readiness_criteria: List[str] = Field(default_factory=list)
    required_evidence_types: List[str] = Field(default_factory=list)
    monitoring_frequency: str = "WEEKLY"  # DAILY, WEEKLY, BIWEEKLY, MONTHLY, QUARTERLY

    # Known limitations and constraints
    known_limitations: List[str] = Field(default_factory=list)
    system_dependencies: List[str] = Field(default_factory=list)
    approved_exceptions_summary: List[str] = Field(default_factory=list)

    # Lifecycle & Governance
    status: BaselineApprovalStatus = BaselineApprovalStatus.DRAFT
    author_id: str
    submitted_by: Optional[str] = None
    submitted_at: Optional[str] = None
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    approval_authority_role: Optional[str] = None
    rejection_reason: Optional[str] = None
    effective_date: Optional[str] = None
    created_at: str
    updated_at: str


class CreateBaselineRequest(BaseModel):
    """Request payload to create a new baseline (initial or revised version)."""
    model_config = ConfigDict(extra="forbid")

    version: str = Field(..., pattern=r"^\d+\.\d+$", description="Semantic version, e.g. 1.0, 1.1")
    previous_version_id: Optional[str] = None
    change_reason: Optional[str] = None
    intended_operational_process: str = Field(..., min_length=5)
    expected_workflow_behavior: str = Field(..., min_length=5)
    required_operational_practices: List[str] = Field(default_factory=list)
    operational_scope: OperationalScope = Field(default_factory=OperationalScope)
    responsible_roles: List[str] = Field(default_factory=list)
    required_training_programmes: List[str] = Field(default_factory=list)
    required_procedural_docs: List[str] = Field(default_factory=list)
    operational_readiness_criteria: List[str] = Field(default_factory=list)
    required_evidence_types: List[str] = Field(default_factory=list)
    monitoring_frequency: str = Field(default="WEEKLY")
    known_limitations: List[str] = Field(default_factory=list)
    system_dependencies: List[str] = Field(default_factory=list)
    approved_exceptions_summary: List[str] = Field(default_factory=list)


class UpdateBaselineRequest(BaseModel):
    """Request payload to update a baseline draft."""
    model_config = ConfigDict(extra="forbid")

    intended_operational_process: Optional[str] = None
    expected_workflow_behavior: Optional[str] = None
    required_operational_practices: Optional[List[str]] = None
    operational_scope: Optional[OperationalScope] = None
    responsible_roles: Optional[List[str]] = None
    required_training_programmes: Optional[List[str]] = None
    required_procedural_docs: Optional[List[str]] = None
    operational_readiness_criteria: Optional[List[str]] = None
    required_evidence_types: Optional[List[str]] = None
    monitoring_frequency: Optional[str] = None
    known_limitations: Optional[List[str]] = None
    system_dependencies: Optional[List[str]] = None
    approved_exceptions_summary: Optional[List[str]] = None


class SubmitBaselineRequest(BaseModel):
    """Request payload to submit a baseline draft for authoritative governance approval."""
    model_config = ConfigDict(extra="forbid")

    submission_notes: Optional[str] = None


class ApproveBaselineRequest(BaseModel):
    """Request payload to approve a submitted operational adoption baseline."""
    model_config = ConfigDict(extra="forbid")

    effective_date: str = Field(..., description="Effective date ISO timestamp")
    approval_comments: Optional[str] = None
