"""Phase 85: Single-Person Dependency and Concentration Analysis Schemas.

Detects critical governance single points of failure, key-person bottlenecks,
and personnel concentration risks across critical responsibilities.
"""

from typing import List, Optional
from pydantic import BaseModel, Field

from app.schemas.governance_role_coverage_common import (
    DependencyRiskRating,
    MANDATORY_ROLE_COVERAGE_DISCLAIMER,
)


class SinglePersonDependencyRecord(BaseModel):
    dependency_id: str
    tenant_id: str
    responsibility_id: str
    role_title: str
    primary_owner_id: str
    verified_backups_count: int
    is_single_person_dependent: bool
    risk_rating: DependencyRiskRating
    vulnerabilities: List[str] = Field(default_factory=list)
    disclaimer: str = Field(default=MANDATORY_ROLE_COVERAGE_DISCLAIMER)


class PersonnelConcentrationRecord(BaseModel):
    concentration_id: str
    tenant_id: str
    user_id: str
    user_name: str
    tier1_primary_roles_count: int
    tier1_backup_roles_count: int
    total_critical_roles_covered: int
    associated_responsibility_ids: List[str] = Field(default_factory=list)
    risk_rating: DependencyRiskRating
    is_bottleneck: bool
    disclaimer: str = Field(default=MANDATORY_ROLE_COVERAGE_DISCLAIMER)


class RunDependencyAnalysisRequest(BaseModel):
    include_tier2: bool = True
    bottleneck_threshold: int = Field(default=3, ge=1)
