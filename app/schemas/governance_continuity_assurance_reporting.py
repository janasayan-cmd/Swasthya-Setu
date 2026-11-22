"""Phase 81: Continuity Assurance Scoring and Strategic Resilience Reporting Schemas.

Defines configurable assurance analytics, explainable scoring outcomes,
and specifications for 14 strategic resilience reports.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.schemas.governance_continuity_assurance_framework import (
    MANDATORY_GOVERNANCE_CONTINUITY_ASSURANCE_DISCLAIMER,
)


class OverallAssuranceOutcome(str, Enum):
    SATISFACTORY = "SATISFACTORY"
    SATISFACTORY_WITH_OBSERVATIONS = "SATISFACTORY_WITH_OBSERVATIONS"
    IMPROVEMENT_REQUIRED = "IMPROVEMENT_REQUIRED"
    UNSATISFACTORY = "UNSATISFACTORY"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    UNABLE_TO_DETERMINE = "UNABLE_TO_DETERMINE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ReportType(str, Enum):
    GOVERNANCE_CONTINUITY_OVERVIEW = "GOVERNANCE_CONTINUITY_OVERVIEW"
    CRITICAL_CAPABILITY_COVERAGE = "CRITICAL_CAPABILITY_COVERAGE"
    PLAN_VALIDATION_RESULTS = "PLAN_VALIDATION_RESULTS"
    CONTINUITY_EXERCISE_PERFORMANCE = "CONTINUITY_EXERCISE_PERFORMANCE"
    SCENARIO_COVERAGE_MATRIX = "SCENARIO_COVERAGE_MATRIX"
    PERSONNEL_READINESS_ASSESSMENT = "PERSONNEL_READINESS_ASSESSMENT"
    DEPENDENCY_RESILIENCE_ASSESSMENT = "DEPENDENCY_RESILIENCE_ASSESSMENT"
    RECOVERY_TARGET_PERFORMANCE = "RECOVERY_TARGET_PERFORMANCE"
    DECISION_RECONCILIATION_INTEGRITY = "DECISION_RECONCILIATION_INTEGRITY"
    INDEPENDENT_VALIDATION_FINDINGS = "INDEPENDENT_VALIDATION_FINDINGS"
    RECURRING_CONTINUITY_WEAKNESSES = "RECURRING_CONTINUITY_WEAKNESSES"
    CORRECTIVE_ACTION_FOLLOW_UP = "CORRECTIVE_ACTION_FOLLOW_UP"
    CONTINUITY_ASSURANCE_TREND_ANALYSIS = "CONTINUITY_ASSURANCE_TREND_ANALYSIS"
    ORGANIZATIONAL_RESILIENCE_ASSURANCE = "ORGANIZATIONAL_RESILIENCE_ASSURANCE"


class GenerateReportRequest(BaseModel):
    report_type: ReportType
    organizational_scope: str = "GLOBAL"
    reporting_period: str = "CURRENT"
    framework_version: int = 1


class ContinuityAssuranceReportRecord(BaseModel):
    report_id: str
    report_type: ReportType
    organizational_scope: str
    reporting_period: str
    framework_version: int
    generated_at: datetime
    generated_by: str
    overall_outcome: OverallAssuranceOutcome
    summary_indicators: Dict[str, Any] = Field(default_factory=dict)
    detailed_sections: List[Dict[str, Any]] = Field(default_factory=list)
    source_record_references: List[str] = Field(default_factory=list)
    calculation_methodology: str
    data_freshness_timestamp: datetime
    known_limitations: Optional[str] = None
    disclaimer: str = MANDATORY_GOVERNANCE_CONTINUITY_ASSURANCE_DISCLAIMER


class RoutineScanResult(BaseModel):
    scanned_at: datetime
    overdue_plan_validations: int = 0
    overdue_exercises: int = 0
    stale_evidence_count: int = 0
    unreconciled_decisions_count: int = 0
    active_findings_count: int = 0
    scan_notes: str
    disclaimer: str = MANDATORY_GOVERNANCE_CONTINUITY_ASSURANCE_DISCLAIMER
