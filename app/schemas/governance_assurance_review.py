"""Phase 77: Governance Assurance Review & Management Package Schemas.

Defines schemas for independent review, conflict of interest checks,
and packaging strategic management review dossiers for Phase 72 referral.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.governance_maturity_framework import CLINICAL_SAFETY_DISCLAIMER


class AssuranceReviewStatus(str, Enum):
    """Status of an independent assessment review."""
    PENDING_REVIEW = "PENDING_REVIEW"
    IN_REVIEW = "IN_REVIEW"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"


class AssuranceReviewRecord(BaseModel):
    """Authoritative record for an independent assessment review."""
    model_config = ConfigDict(extra="forbid")

    review_id: str
    tenant_id: str
    assessment_id: str
    assigned_reviewer_id: str
    assigned_by: str
    assigned_at: str
    status: AssuranceReviewStatus
    conflict_of_interest_cleared: bool
    review_notes: Optional[str] = None
    completed_at: Optional[str] = None
    disclaimer: str = CLINICAL_SAFETY_DISCLAIMER


class AssignReviewerRequest(BaseModel):
    """Request to assign an independent reviewer."""
    model_config = ConfigDict(extra="forbid")

    reviewer_id: str
    conflict_of_interest_cleared: bool = Field(..., description="Must explicitly confirm absence of conflict of interest")


class SubmitReviewDecisionRequest(BaseModel):
    """Request to submit an independent review decision."""
    model_config = ConfigDict(extra="forbid")

    decision: AssuranceReviewStatus
    review_notes: str


class StrategicManagementReviewPackageRecord(BaseModel):
    """Authoritative management dossier for referral to Phase 72 Management Review."""
    model_config = ConfigDict(extra="forbid")

    package_id: str
    tenant_id: str
    title: str
    reporting_period: str
    executive_summary: str
    included_assessment_ids: List[str]
    systemic_gaps: List[Dict[str, Any]] = Field(default_factory=list)
    proposed_improvement_plans: List[Dict[str, Any]] = Field(default_factory=list)
    prepared_by: str
    phase_72_referral_id: Optional[str] = None
    disclaimer: str = CLINICAL_SAFETY_DISCLAIMER
    created_at: str


class PrepareReviewPackageRequest(BaseModel):
    """Request to assemble a strategic management review package."""
    model_config = ConfigDict(extra="forbid")

    title: str
    reporting_period: str
    executive_summary: str
    included_assessment_ids: List[str]


class ReferToPhase72Request(BaseModel):
    """Request to refer a prepared package to Phase 72."""
    model_config = ConfigDict(extra="forbid")

    phase_72_meeting_id: Optional[str] = None
    agenda_item_title: str
    referral_notes: Optional[str] = None
