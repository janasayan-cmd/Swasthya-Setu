"""Phase 85: Governance Succession Readiness Schemas.

Coordinates succession pipelines, successor readiness tiers, capability milestones,
and periodic readiness reassessments for critical governance roles.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

from app.schemas.governance_role_coverage_common import (
    SuccessionPlanStatus,
    SuccessionReadinessTier,
    MANDATORY_ROLE_COVERAGE_DISCLAIMER,
)


class SuccessorCandidateItem(BaseModel):
    user_id: str
    user_name: str
    readiness_tier: SuccessionReadinessTier = SuccessionReadinessTier.DEVELOPING
    target_ready_date: Optional[datetime] = None
    capability_gap_refs: List[str] = Field(default_factory=list)
    development_proposal_refs: List[str] = Field(default_factory=list)
    is_nominated_emergency_successor: bool = False
    notes: Optional[str] = None


class SuccessionPlanRecord(BaseModel):
    succession_plan_id: str
    tenant_id: str
    responsibility_id: str
    role_title: str
    status: SuccessionPlanStatus = SuccessionPlanStatus.DRAFT
    candidates: List[SuccessorCandidateItem] = Field(default_factory=list)
    review_cycle_days: int = Field(default=180, ge=1)
    last_reviewed_at: Optional[datetime] = None
    next_review_due: Optional[datetime] = None
    created_by: str
    approved_by: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    disclaimer: str = Field(default=MANDATORY_ROLE_COVERAGE_DISCLAIMER)


class CreateSuccessionPlanRequest(BaseModel):
    responsibility_id: str
    candidates: List[SuccessorCandidateItem] = Field(default_factory=list)
    review_cycle_days: int = Field(default=180, ge=1)


class UpdateSuccessionPlanRequest(BaseModel):
    candidates: Optional[List[SuccessorCandidateItem]] = None
    review_cycle_days: Optional[int] = None


class ApproveSuccessionPlanRequest(BaseModel):
    notes: Optional[str] = None


class ReviewSuccessionPlanRequest(BaseModel):
    review_notes: str
    next_cycle_days: Optional[int] = 180
