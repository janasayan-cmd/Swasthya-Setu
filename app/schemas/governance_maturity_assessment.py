"""Phase 77: Clinical Safety Governance Maturity Assessment Schemas.

Defines schemas for scoping, executing, evaluating criteria, aggregating,
and validating clinical safety governance maturity assessments.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.governance_maturity_framework import (
    CLINICAL_SAFETY_DISCLAIMER,
    MaturityDimensionEnum,
    MaturityLevelEnum,
    ScopeTypeEnum,
)


class AssessmentStatus(str, Enum):
    """Lifecycle status of an organizational maturity assessment."""
    DRAFT = "DRAFT"
    IN_PROGRESS = "IN_PROGRESS"
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    SUPERSEDED = "SUPERSEDED"
    ARCHIVED = "ARCHIVED"


class OrganizationalScope(BaseModel):
    """Target organizational boundary for assessment."""
    model_config = ConfigDict(extra="forbid")

    scope_type: ScopeTypeEnum
    scope_id: str
    scope_name: str
    parent_scope_id: Optional[str] = None


class CriterionEvaluationResult(BaseModel):
    """Evaluation result for a specific criterion against verified evidence."""
    model_config = ConfigDict(extra="forbid")

    criterion_id: str
    dimension: MaturityDimensionEnum
    target_level: MaturityLevelEnum
    is_met: bool
    evidence_count: int
    verified_evidence_ids: List[str] = Field(default_factory=list)
    missing_evidence_reasons: List[str] = Field(default_factory=list)
    evaluation_notes: str


class DimensionAssessmentResult(BaseModel):
    """Assessment result for a specific maturity dimension."""
    model_config = ConfigDict(extra="forbid")

    dimension: MaturityDimensionEnum
    achieved_level: MaturityLevelEnum
    criteria_results: List[CriterionEvaluationResult] = Field(default_factory=list)
    strengths: List[str] = Field(default_factory=list)
    vulnerabilities: List[str] = Field(default_factory=list)
    confidence_score: float = Field(1.0, ge=0.0, le=1.0)


class GovernanceMaturityAssessmentRecord(BaseModel):
    """Authoritative record for an organizational maturity assessment."""
    model_config = ConfigDict(extra="forbid")

    assessment_id: str
    tenant_id: str
    framework_id: str
    framework_version: str
    scope: OrganizationalScope
    status: AssessmentStatus
    assessor_id: str
    assessment_date: str
    dimension_results: Dict[str, DimensionAssessmentResult] = Field(default_factory=dict)
    overall_maturity_level: MaturityLevelEnum = MaturityLevelEnum.NOT_ASSESSED
    summary_findings: str = ""
    evidence_coverage_percentage: float = 0.0
    independent_review_id: Optional[str] = None
    disclaimer: str = CLINICAL_SAFETY_DISCLAIMER
    created_at: str
    updated_at: str


class CreateAssessmentRequest(BaseModel):
    """Request to initiate a new maturity assessment."""
    model_config = ConfigDict(extra="forbid")

    framework_id: str
    scope: OrganizationalScope
    assessment_date: Optional[str] = None
    summary_findings: Optional[str] = ""


class EvaluateDimensionRequest(BaseModel):
    """Request to evaluate a dimension based on submitted verified evidence."""
    model_config = ConfigDict(extra="forbid")

    dimension: MaturityDimensionEnum
    strengths: Optional[List[str]] = None
    vulnerabilities: Optional[List[str]] = None
    evaluation_notes: Optional[str] = None


class SubmitAssessmentRequest(BaseModel):
    """Request to submit an assessment for independent review and approval."""
    model_config = ConfigDict(extra="forbid")

    submission_notes: Optional[str] = None


class AggregateMaturityRequest(BaseModel):
    """Request to aggregate maturity across multiple assessed sub-scopes."""
    model_config = ConfigDict(extra="forbid")

    framework_id: str
    parent_scope: OrganizationalScope
    child_assessment_ids: List[str]


class AggregateMaturityResponse(BaseModel):
    """Aggregated maturity summary across multiple organizational boundaries."""
    model_config = ConfigDict(extra="forbid")

    parent_scope: OrganizationalScope
    framework_id: str
    aggregated_level: MaturityLevelEnum
    dimension_levels: Dict[str, MaturityLevelEnum]
    child_assessments_counted: int
    aggregation_methodology: str
    disclaimer: str = CLINICAL_SAFETY_DISCLAIMER
