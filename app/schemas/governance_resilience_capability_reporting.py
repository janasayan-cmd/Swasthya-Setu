"""Phase 84: Capability Analytics and Management Reporting Schemas.

Supports executive dashboards and compliance monitoring across 6 reports:
capability coverage, role readiness, team readiness, gaps, development, and organizational posture.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.schemas.governance_resilience_capability_framework import (
    MANDATORY_RESILIENCE_CAPABILITY_DISCLAIMER,
)


class CapabilityCoverageReport(BaseModel):
    total_framework_capabilities: int
    by_domain: Dict[str, int]
    by_proficiency_level: Dict[str, int]
    coverage_rate_percent: float
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    disclaimer: str = Field(default=MANDATORY_RESILIENCE_CAPABILITY_DISCLAIMER)


class RoleReadinessReport(BaseModel):
    total_role_requirements: int
    assessed_roles: int
    verified_ready_roles: int
    missing_coverage_roles: int
    role_coverage_percent: float
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    disclaimer: str = Field(default=MANDATORY_RESILIENCE_CAPABILITY_DISCLAIMER)


class TeamReadinessReport(BaseModel):
    total_teams_assessed: int
    verified_ready_teams: int
    teams_with_critical_vacancies: int
    teams_with_backup_deficits: int
    critical_vacant_roles: List[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    disclaimer: str = Field(default=MANDATORY_RESILIENCE_CAPABILITY_DISCLAIMER)


class CapabilityGapsReport(BaseModel):
    total_gaps_detected: int
    validated_gaps: int
    capa_referred_gaps: int
    resolved_gaps: int
    by_category: Dict[str, int]
    by_severity: Dict[str, int]
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    disclaimer: str = Field(default=MANDATORY_RESILIENCE_CAPABILITY_DISCLAIMER)


class DevelopmentProgressReport(BaseModel):
    total_proposals: int
    approved_proposals: int
    in_progress_proposals: int
    completed_proposals: int
    by_intervention_type: Dict[str, int]
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    disclaimer: str = Field(default=MANDATORY_RESILIENCE_CAPABILITY_DISCLAIMER)


class OrganizationalReadinessReport(BaseModel):
    overall_readiness_score: float
    readiness_posture: str
    verified_ready_scopes_count: int
    unresolved_exceptions_count: int
    active_reassessments_count: int
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    disclaimer: str = Field(default=MANDATORY_RESILIENCE_CAPABILITY_DISCLAIMER)
