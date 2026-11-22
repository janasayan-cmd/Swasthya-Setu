"""Phase 81: Continuity Capability Coverage Assurance Schemas.

Evaluates coverage of critical governance capabilities against approved
continuity arrangements, identifying uncovered, expired, unapproved, or untested areas.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.schemas.governance_continuity_assurance_framework import (
    MANDATORY_GOVERNANCE_CONTINUITY_ASSURANCE_DISCLAIMER,
)


class CoverageGapType(str, Enum):
    UNCOVERED_CAPABILITY = "UNCOVERED_CAPABILITY"
    EXPIRED_PLAN = "EXPIRED_PLAN"
    UNAPPROVED_PLAN = "UNAPPROVED_PLAN"
    INCOMPLETE_RECOVERY_REQUIREMENTS = "INCOMPLETE_RECOVERY_REQUIREMENTS"
    NO_VALIDATED_PERSONNEL_ALTERNATIVES = "NO_VALIDATED_PERSONNEL_ALTERNATIVES"
    MISSING_COMMUNICATION_ARRANGEMENTS = "MISSING_COMMUNICATION_ARRANGEMENTS"
    UNTESTED_DEPENDENCIES = "UNTESTED_DEPENDENCIES"
    MISSING_RECOVERY_VERIFICATION_CRITERIA = "MISSING_RECOVERY_VERIFICATION_CRITERIA"
    UNRESOLVED_EXERCISE_FINDINGS = "UNRESOLVED_EXERCISE_FINDINGS"


class CapabilityCoverageSummary(BaseModel):
    capability_id: str
    capability_name: str
    criticality_tier: str
    has_active_plan: bool
    plan_id: Optional[str] = None
    plan_version: Optional[int] = None
    identified_gaps: List[CoverageGapType] = Field(default_factory=list)
    recovery_targets_defined: bool = False
    evidence_limitations: Optional[str] = None


class RunCoverageAssessmentRequest(BaseModel):
    scope_level: str = "GLOBAL"  # GLOBAL, FACILITY, DEPARTMENT
    scope_id: Optional[str] = None
    notes: Optional[str] = None


class ContinuityCoverageAssessmentRecord(BaseModel):
    assessment_id: str
    scope_level: str
    scope_id: Optional[str] = None
    assessed_at: datetime
    assessed_by: str
    total_critical_capabilities: int = 0
    covered_capabilities_count: int = 0
    uncovered_capabilities_count: int = 0
    coverage_percentage: float = 0.0
    summaries: List[CapabilityCoverageSummary] = Field(default_factory=list)
    detected_gaps: List[Dict[str, Any]] = Field(default_factory=list)
    limitations: Optional[str] = None
    tenant_id: str = "default"
    disclaimer: str = MANDATORY_GOVERNANCE_CONTINUITY_ASSURANCE_DISCLAIMER
