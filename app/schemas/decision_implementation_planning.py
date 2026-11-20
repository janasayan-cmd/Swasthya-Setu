"""Phase 73: Implementation Planning & Versioning Schemas.

Defines schemas for:
- Structured implementation plans with work items, milestones, criteria
- Plan review, versioning, change reasons, and approvals
- Readiness evaluation before implementation becomes executable
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class PlanApprovalStatus(str, Enum):
    """Approval lifecycle of an implementation plan."""

    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"


class ImplementationPlanRecord(BaseModel):
    """Domain model representing a versioned implementation plan."""

    model_config = ConfigDict(extra="ignore")

    plan_id: str = Field(default_factory=lambda: f"gdipl-{uuid.uuid4().hex[:12]}")
    implementation_id: str
    version: int = 1

    objectives: List[str] = Field(default_factory=list)
    work_items: List[Dict[str, Any]] = Field(default_factory=list)
    target_dates: Dict[str, Any] = Field(default_factory=dict)

    expected_evidence: List[str] = Field(default_factory=list)
    verification_criteria: List[str] = Field(default_factory=list)
    completion_conditions: List[str] = Field(default_factory=list)

    approval_status: PlanApprovalStatus = PlanApprovalStatus.DRAFT
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    change_reason: Optional[str] = None
    is_active: bool = True

    created_by: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)


# Request Models
class CreatePlanRequest(BaseModel):
    """Request payload to define a structured implementation plan."""

    model_config = ConfigDict(extra="ignore")

    objectives: List[str]
    work_items: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    target_dates: Optional[Dict[str, Any]] = Field(default_factory=dict)
    expected_evidence: Optional[List[str]] = Field(default_factory=list)
    verification_criteria: Optional[List[str]] = Field(default_factory=list)
    completion_conditions: Optional[List[str]] = Field(default_factory=list)
    change_reason: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class UpdatePlanRequest(BaseModel):
    """Request payload to update a draft implementation plan."""

    model_config = ConfigDict(extra="ignore")

    objectives: Optional[List[str]] = None
    work_items: Optional[List[Dict[str, Any]]] = None
    target_dates: Optional[Dict[str, Any]] = None
    expected_evidence: Optional[List[str]] = None
    verification_criteria: Optional[List[str]] = None
    completion_conditions: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None


class SubmitPlanRequest(BaseModel):
    """Request payload to submit a plan for approval."""

    model_config = ConfigDict(extra="ignore")

    submission_notes: Optional[str] = None


class ApprovePlanRequest(BaseModel):
    """Request payload to approve a plan."""

    model_config = ConfigDict(extra="ignore")

    approval_rationale: str
