"""Phase 77: Governance Strategic Assurance Reporting & Background Job Schemas.

Defines response models for multi-level maturity reports, assurance coverage,
longitudinal trend tracking, and idempotent background scan jobs.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict

from app.schemas.governance_maturity_framework import (
    CLINICAL_SAFETY_DISCLAIMER,
    MaturityDimensionEnum,
    MaturityLevelEnum,
)


class MaturityRadarDimension(BaseModel):
    """Dimension profile score for maturity visualization."""
    model_config = ConfigDict(extra="forbid")

    dimension: MaturityDimensionEnum
    level: MaturityLevelEnum
    numeric_score: float
    confidence: float


class MaturityReportResponse(BaseModel):
    """Detailed maturity report for an assessment or organizational scope."""
    model_config = ConfigDict(extra="forbid")

    tenant_id: str
    assessment_id: Optional[str] = None
    scope_type: str
    scope_name: str
    overall_maturity_level: MaturityLevelEnum
    dimension_scores: List[MaturityRadarDimension]
    evidence_coverage_percentage: float
    disclaimer: str = CLINICAL_SAFETY_DISCLAIMER


class CoverageAnalysisResponse(BaseModel):
    """Assurance coverage breakdown across organizational scopes and evidence."""
    model_config = ConfigDict(extra="forbid")

    tenant_id: str
    total_scopes_defined: int
    scopes_assessed: int
    coverage_ratio: float
    evidence_availability_count: int
    evidence_adequacy_count: int
    scope_breakdown: Dict[str, Any]
    disclaimer: str = CLINICAL_SAFETY_DISCLAIMER


class LongitudinalTrendPoint(BaseModel):
    """Historical assessment data point in a longitudinal trend."""
    model_config = ConfigDict(extra="forbid")

    assessment_id: str
    assessment_date: str
    framework_version: str
    overall_level: MaturityLevelEnum
    comparability_caveat: Optional[str] = None


class LongitudinalTrendReportResponse(BaseModel):
    """Longitudinal trend report preserving methodology/framework comparability."""
    model_config = ConfigDict(extra="forbid")

    tenant_id: str
    scope_id: str
    scope_name: str
    data_points: List[LongitudinalTrendPoint]
    version_transition_detected: bool
    disclaimer: str = CLINICAL_SAFETY_DISCLAIMER


class AssuranceRoutineScanJobResult(BaseModel):
    """Result of an idempotent background assurance maintenance scan."""
    model_config = ConfigDict(extra="forbid")

    scanned_assessments: int
    stale_evidence_flagged: int
    overdue_assessments_flagged: int
    milestone_alerts_generated: int
    status: str
