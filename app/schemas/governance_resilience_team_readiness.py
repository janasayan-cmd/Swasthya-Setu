"""Phase 84: Team Readiness Assessment Schemas.

Evaluates collective organizational team readiness without averaging scores,
ensuring critical role vacancies and missing backup coverage remain explicitly visible.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.schemas.governance_resilience_capability_framework import (
    MANDATORY_RESILIENCE_CAPABILITY_DISCLAIMER,
)


class TeamReadinessOutcome(str, Enum):
    NOT_ASSESSED = "NOT_ASSESSED"
    CRITICAL_ROLES_VACANT = "CRITICAL_ROLES_VACANT"
    BACKUP_COVERAGE_DEFICIT = "BACKUP_COVERAGE_DEFICIT"
    DEMONSTRATION_DEFICIT = "DEMONSTRATION_DEFICIT"
    PARTIALLY_READY = "PARTIALLY_READY"
    READY_SUBJECT_TO_CONDITIONS = "READY_SUBJECT_TO_CONDITIONS"
    VERIFIED_READY = "VERIFIED_READY"


class RoleCoverageItem(BaseModel):
    role_name: str
    primary_user_id: Optional[str] = None
    backup_user_id: Optional[str] = None
    has_verified_evidence: bool = False
    is_vacant: bool = False


class TeamReadinessRecord(BaseModel):
    team_assessment_id: str
    tenant_id: str
    team_name: str
    department_id: Optional[str] = None
    facility_id: Optional[str] = None
    framework_id: str
    framework_version: int = 1
    role_coverage: List[RoleCoverageItem] = Field(default_factory=list)
    critical_vacancies: List[str] = Field(default_factory=list)
    backup_deficits: List[str] = Field(default_factory=list)
    readiness_outcome: TeamReadinessOutcome = TeamReadinessOutcome.NOT_ASSESSED
    conditions_imposed: Optional[str] = None
    limitations: Optional[str] = None
    assessed_by: str
    assessed_at: datetime = Field(default_factory=datetime.utcnow)
    disclaimer: str = Field(default=MANDATORY_RESILIENCE_CAPABILITY_DISCLAIMER)


class AssessTeamReadinessRequest(BaseModel):
    team_name: str
    department_id: Optional[str] = None
    facility_id: Optional[str] = None
    framework_id: str
    framework_version: int = 1
    role_coverage: List[RoleCoverageItem]
    conditions_imposed: Optional[str] = None
    limitations: Optional[str] = None
