"""Phase 85: Role-Coverage and Succession Reporting Schemas.

Provides structured executive summaries, bottleneck analysis, verification deficiencies,
and expiring coverage schedule reports.
"""

from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from app.schemas.governance_role_coverage_common import (
    MANDATORY_ROLE_COVERAGE_DISCLAIMER,
)
from app.schemas.governance_role_dependency_analysis import (
    PersonnelConcentrationRecord,
    SinglePersonDependencyRecord,
)
from app.schemas.governance_role_backup_verification import (
    BackupVerificationRecord,
)


class RoleCoverageSummaryReport(BaseModel):
    tenant_id: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    total_critical_responsibilities: int
    tier_distribution: Dict[str, int]
    responsibilities_with_verified_backup: int
    responsibilities_without_verified_backup: int
    overall_coverage_health_percentage: float
    active_coverage_arrangements_count: int
    open_coverage_gaps_count: int
    active_handovers_count: int
    disclaimer: str = Field(default=MANDATORY_ROLE_COVERAGE_DISCLAIMER)


class SinglePersonDependencyReport(BaseModel):
    tenant_id: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    single_person_dependencies: List[SinglePersonDependencyRecord] = Field(default_factory=list)
    key_person_bottlenecks: List[PersonnelConcentrationRecord] = Field(default_factory=list)
    critical_dependencies_count: int
    high_risk_bottlenecks_count: int
    disclaimer: str = Field(default=MANDATORY_ROLE_COVERAGE_DISCLAIMER)


class BackupReadinessDeficienciesReport(BaseModel):
    tenant_id: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    deficient_verifications: List[BackupVerificationRecord] = Field(default_factory=list)
    total_deficient_count: int
    unverified_capability_count: int
    missing_authorization_count: int
    disclaimer: str = Field(default=MANDATORY_ROLE_COVERAGE_DISCLAIMER)


class ExpiringCoverageScheduleItem(BaseModel):
    coverage_id: str
    responsibility_id: str
    backup_user_id: str
    item_type: str
    reference_id: Optional[str] = None
    expires_at: datetime
    days_remaining: int


class ExpiringCoverageScheduleReport(BaseModel):
    tenant_id: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    expiring_items: List[ExpiringCoverageScheduleItem] = Field(default_factory=list)
    total_expiring_soon_count: int
    disclaimer: str = Field(default=MANDATORY_ROLE_COVERAGE_DISCLAIMER)
