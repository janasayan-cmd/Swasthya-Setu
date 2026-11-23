"""Phase 85: Role-Coverage Gap Management and Escalation Schemas.

Coordinates identified coverage gaps, remedial assignments, authoritative escalations
to Phases 54/63/67/72, and resolution verifications.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

from app.schemas.governance_role_coverage_common import (
    CoverageGapCategory,
    CoverageGapStatus,
    DependencyRiskRating,
    MANDATORY_ROLE_COVERAGE_DISCLAIMER,
)


class RoleCoverageGapRecord(BaseModel):
    gap_id: str
    tenant_id: str
    responsibility_id: str
    category: CoverageGapCategory
    severity: DependencyRiskRating = DependencyRiskRating.HIGH
    status: CoverageGapStatus = CoverageGapStatus.IDENTIFIED
    title: str
    description: str
    identified_at: datetime = Field(default_factory=datetime.utcnow)
    assigned_to: Optional[str] = None
    escalated_to_phase: Optional[str] = None
    escalation_reference_id: Optional[str] = None
    remediation_notes: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolution_verified_by: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    disclaimer: str = Field(default=MANDATORY_ROLE_COVERAGE_DISCLAIMER)


class CreateCoverageGapRequest(BaseModel):
    responsibility_id: str
    category: CoverageGapCategory
    severity: DependencyRiskRating = DependencyRiskRating.HIGH
    title: str
    description: str
    assigned_to: Optional[str] = None


class AssignCoverageGapRequest(BaseModel):
    assigned_to: str
    notes: Optional[str] = None


class EscalateCoverageGapRequest(BaseModel):
    escalated_to_phase: str
    escalation_reference_id: str
    escalation_notes: Optional[str] = None


class ResolveCoverageGapRequest(BaseModel):
    remediation_notes: str
    verified_coverage_id: Optional[str] = None
    verified_succession_plan_id: Optional[str] = None
