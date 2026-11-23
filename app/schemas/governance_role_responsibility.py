"""Phase 85: Critical Governance Role and Responsibility Schemas.

Defines the inventory of critical clinical safety governance roles, specific responsibilities,
criticality tiers, and continuity requirements.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

from app.schemas.governance_role_coverage_common import (
    CriticalityTier,
    CoverageScope,
    MANDATORY_ROLE_COVERAGE_DISCLAIMER,
)


class CriticalGovernanceResponsibilityRecord(BaseModel):
    responsibility_id: str
    tenant_id: str
    role_title: str
    responsibility_name: str
    description: str
    criticality_tier: CriticalityTier = CriticalityTier.TIER_1_ESSENTIAL
    coverage_scope: CoverageScope = CoverageScope.ORGANIZATION
    max_acceptable_outage_hours: float = Field(default=4.0, ge=0.5)
    primary_owner_id: str
    primary_owner_name: str
    required_capability_framework_id: Optional[str] = None
    required_capability_ids: List[str] = Field(default_factory=list)
    status: str = "ACTIVE"
    review_cycle_days: int = Field(default=90, ge=1)
    last_reviewed_at: Optional[datetime] = None
    next_review_due: Optional[datetime] = None
    created_by: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    disclaimer: str = Field(default=MANDATORY_ROLE_COVERAGE_DISCLAIMER)


class CreateCriticalResponsibilityRequest(BaseModel):
    role_title: str
    responsibility_name: str
    description: str
    criticality_tier: CriticalityTier = CriticalityTier.TIER_1_ESSENTIAL
    coverage_scope: CoverageScope = CoverageScope.ORGANIZATION
    max_acceptable_outage_hours: float = Field(default=4.0, ge=0.5)
    primary_owner_id: str
    primary_owner_name: str
    required_capability_framework_id: Optional[str] = None
    required_capability_ids: List[str] = Field(default_factory=list)
    review_cycle_days: int = Field(default=90, ge=1)


class UpdateCriticalResponsibilityRequest(BaseModel):
    role_title: Optional[str] = None
    responsibility_name: Optional[str] = None
    description: Optional[str] = None
    criticality_tier: Optional[CriticalityTier] = None
    coverage_scope: Optional[CoverageScope] = None
    max_acceptable_outage_hours: Optional[float] = None
    primary_owner_id: Optional[str] = None
    primary_owner_name: Optional[str] = None
    required_capability_framework_id: Optional[str] = None
    required_capability_ids: Optional[List[str]] = None
    review_cycle_days: Optional[int] = None
    status: Optional[str] = None


class ReviewCriticalResponsibilityRequest(BaseModel):
    review_notes: str
    next_review_cycle_days: Optional[int] = 90
