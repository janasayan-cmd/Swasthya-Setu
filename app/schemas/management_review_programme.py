"""Phase 72: Clinical Safety Governance Management Review Programme Schemas.

Defines schemas for:
- Management review programme establishment and governance
- Configurable review categories and frequencies
- Governance programme approvals and version history
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class ReviewProgrammeCategory(str, Enum):
    """Categories of management review programmes."""

    ROUTINE_GOVERNANCE = "ROUTINE_GOVERNANCE"
    CLINICAL_SAFETY_GOVERNANCE = "CLINICAL_SAFETY_GOVERNANCE"
    COMPLIANCE_OVERSIGHT = "COMPLIANCE_OVERSIGHT"
    AUDIT_PERFORMANCE = "AUDIT_PERFORMANCE"
    RISK_AND_EXCEPTION = "RISK_AND_EXCEPTION"
    CORRECTIVE_ACTION = "CORRECTIVE_ACTION"
    POST_INCIDENT_GOVERNANCE = "POST_INCIDENT_GOVERNANCE"
    SPECIAL_MANAGEMENT_REVIEW = "SPECIAL_MANAGEMENT_REVIEW"


class ReviewProgrammeStatus(str, Enum):
    """Lifecycle status of a review programme."""

    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    DEPRECATED = "DEPRECATED"


class ReviewFrequency(str, Enum):
    """Configurable operational frequencies for review meetings."""

    MONTHLY = "MONTHLY"
    QUARTERLY = "QUARTERLY"
    SEMI_ANNUALLY = "SEMI_ANNUALLY"
    ANNUALLY = "ANNUALLY"
    AD_HOC = "AD_HOC"


class ManagementReviewProgrammeRecord(BaseModel):
    """Domain record representing an approved management review programme."""

    model_config = ConfigDict(extra="ignore")

    programme_id: str = Field(default_factory=lambda: f"gmrp-{uuid.uuid4().hex[:12]}")
    name: str
    description: str
    objectives: List[str] = Field(default_factory=list)
    category: ReviewProgrammeCategory = ReviewProgrammeCategory.CLINICAL_SAFETY_GOVERNANCE
    frequency: ReviewFrequency = ReviewFrequency.QUARTERLY
    status: ReviewProgrammeStatus = ReviewProgrammeStatus.DRAFT

    responsible_owner_id: str
    responsible_owner_role: str
    participating_units: List[str] = Field(default_factory=list)
    applicable_domains: List[str] = Field(default_factory=list)

    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    approval_policy_ref: Optional[str] = None

    organization_id: str
    facility_id: Optional[str] = None
    created_by: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CreateReviewProgrammeRequest(BaseModel):
    """Request payload to create a management review programme."""

    model_config = ConfigDict(extra="ignore")

    name: str
    description: str
    objectives: Optional[List[str]] = Field(default_factory=list)
    category: Optional[ReviewProgrammeCategory] = ReviewProgrammeCategory.CLINICAL_SAFETY_GOVERNANCE
    frequency: Optional[ReviewFrequency] = ReviewFrequency.QUARTERLY
    participating_units: Optional[List[str]] = Field(default_factory=list)
    applicable_domains: Optional[List[str]] = Field(default_factory=list)
    facility_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class UpdateReviewProgrammeRequest(BaseModel):
    """Request payload to update review programme details."""

    model_config = ConfigDict(extra="ignore")

    name: Optional[str] = None
    description: Optional[str] = None
    objectives: Optional[List[str]] = None
    frequency: Optional[ReviewFrequency] = None
    participating_units: Optional[List[str]] = None
    applicable_domains: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None


class ApproveReviewProgrammeRequest(BaseModel):
    """Request payload to approve a review programme."""

    model_config = ConfigDict(extra="ignore")

    approval_policy_ref: str
    approval_rationale: Optional[str] = None
