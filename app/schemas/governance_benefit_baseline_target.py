"""Phase 76: Benefit Baseline and Target Management Schemas.

Defines schemas and models for:
- Version-controlled benefit baselines and targets
- Explicit approval workflows and separation of duties enforcement
- Prevention of silent metric comparability overwrites
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class BaselineStatus(str, Enum):
    """Lifecycle status of a benefit baseline."""
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    SUPERSEDED = "SUPERSEDED"
    REJECTED = "REJECTED"


class TargetStatus(str, Enum):
    """Lifecycle status of a benefit target."""
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    SUPERSEDED = "SUPERSEDED"
    REJECTED = "REJECTED"


class BenefitBaselineRecord(BaseModel):
    """Authoritative record for a benefit realization baseline."""
    model_config = ConfigDict(extra="forbid")

    baseline_id: str
    benefit_id: str
    tenant_id: str
    version: int = 1
    measurement_definition: str
    baseline_value: Optional[float] = None
    qualitative_state: Optional[str] = None
    unit: str
    measurement_period: str
    source_system: str
    data_collection_method: str
    data_quality_requirements: List[str] = Field(default_factory=list)
    organizational_scope: Dict[str, Any] = Field(default_factory=dict)
    status: BaselineStatus = BaselineStatus.DRAFT
    created_by: str
    created_at: str
    submitted_by: Optional[str] = None
    submitted_at: Optional[str] = None
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    approval_reference: Optional[str] = None
    approval_notes: Optional[str] = None
    change_reason: Optional[str] = None


class CreateBaselineRequest(BaseModel):
    """Request payload to establish a measurable benefit baseline."""
    model_config = ConfigDict(extra="forbid")

    measurement_definition: str = Field(..., min_length=3)
    baseline_value: Optional[float] = None
    qualitative_state: Optional[str] = None
    unit: str = Field(..., min_length=1)
    measurement_period: str = Field(..., min_length=2)
    source_system: str = Field(..., min_length=2)
    data_collection_method: str = Field(..., min_length=3)
    data_quality_requirements: List[str] = Field(default_factory=list)
    organizational_scope: Dict[str, Any] = Field(default_factory=dict)
    change_reason: Optional[str] = None


class SubmitBaselineRequest(BaseModel):
    """Request payload to submit a baseline for governance approval."""
    model_config = ConfigDict(extra="forbid")

    submission_notes: Optional[str] = None


class ApproveBaselineRequest(BaseModel):
    """Request payload to approve a baseline (Separation of duties enforced)."""
    model_config = ConfigDict(extra="forbid")

    approval_reference: str = Field(..., min_length=3)
    approval_notes: Optional[str] = None


class BenefitTargetRecord(BaseModel):
    """Authoritative record for an expected benefit realization target."""
    model_config = ConfigDict(extra="forbid")

    target_id: str
    benefit_id: str
    tenant_id: str
    version: int = 1
    target_value: Optional[float] = None
    target_condition: Optional[str] = None
    target_measurement_date: str
    unit: str
    measurement_method: str
    required_evidence: List[str] = Field(default_factory=list)
    organizational_scope: Dict[str, Any] = Field(default_factory=dict)
    status: TargetStatus = TargetStatus.DRAFT
    created_by: str
    created_at: str
    submitted_by: Optional[str] = None
    submitted_at: Optional[str] = None
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    approval_reference: Optional[str] = None
    approval_notes: Optional[str] = None
    review_date: Optional[str] = None
    change_reason: Optional[str] = None


class CreateTargetRequest(BaseModel):
    """Request payload to establish an approved benefit target."""
    model_config = ConfigDict(extra="forbid")

    target_value: Optional[float] = None
    target_condition: Optional[str] = None
    target_measurement_date: str
    unit: str = Field(..., min_length=1)
    measurement_method: str = Field(..., min_length=3)
    required_evidence: List[str] = Field(default_factory=list)
    organizational_scope: Dict[str, Any] = Field(default_factory=dict)
    review_date: Optional[str] = None
    change_reason: Optional[str] = None


class SubmitTargetRequest(BaseModel):
    """Request payload to submit a target for governance approval."""
    model_config = ConfigDict(extra="forbid")

    submission_notes: Optional[str] = None


class ApproveTargetRequest(BaseModel):
    """Request payload to approve a target (Separation of duties enforced)."""
    model_config = ConfigDict(extra="forbid")

    approval_reference: str = Field(..., min_length=3)
    approval_notes: Optional[str] = None
