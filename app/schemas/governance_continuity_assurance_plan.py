"""Phase 81: Continuity Plan Validation Schemas.

Supports controlled validation of Phase 80 continuity plans for completeness,
evidence sufficiency, and criteria fulfillment.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.schemas.governance_continuity_assurance_framework import (
    MANDATORY_GOVERNANCE_CONTINUITY_ASSURANCE_DISCLAIMER,
)


class PlanValidationOutcome(str, Enum):
    VALIDATED = "VALIDATED"
    VALIDATED_WITH_OBSERVATIONS = "VALIDATED_WITH_OBSERVATIONS"
    REQUIRES_REMEDIATION = "REQUIRES_REMEDIATION"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    UNABLE_TO_DETERMINE = "UNABLE_TO_DETERMINE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class PlanValidationReviewStatus(str, Enum):
    DRAFT = "DRAFT"
    UNDER_REVIEW = "UNDER_REVIEW"
    COMPLETED = "COMPLETED"
    SUPERSEDED = "SUPERSEDED"


class EvaluatedCriterionResult(BaseModel):
    criterion_key: str
    criterion_name: str
    is_met: bool
    evidence_reference: Optional[str] = None
    observation_notes: Optional[str] = None


class CreatePlanValidationRequest(BaseModel):
    plan_id: str
    plan_version: int = 1
    framework_version: int = 1
    review_scope: str = "FULL_PLAN_COMPLETENESS"
    custom_criteria_checks: Optional[List[str]] = None
    notes: Optional[str] = None


class ReviewPlanValidationRequest(BaseModel):
    validation_outcome: PlanValidationOutcome
    observations: List[str] = Field(default_factory=list)
    remediation_recommendations: List[str] = Field(default_factory=list)
    limitations: Optional[str] = None


class ContinuityPlanValidationRecord(BaseModel):
    validation_id: str
    plan_id: str
    plan_version: int
    framework_version: int
    review_scope: str
    validation_outcome: PlanValidationOutcome = PlanValidationOutcome.UNABLE_TO_DETERMINE
    review_status: PlanValidationReviewStatus = PlanValidationReviewStatus.DRAFT
    evaluated_criteria: List[EvaluatedCriterionResult] = Field(default_factory=list)
    missing_evidence: List[str] = Field(default_factory=list)
    failed_criteria: List[str] = Field(default_factory=list)
    unverified_criteria: List[str] = Field(default_factory=list)
    observations: List[str] = Field(default_factory=list)
    remediation_recommendations: List[str] = Field(default_factory=list)
    limitations: Optional[str] = None
    evaluated_by: str
    evaluated_at: datetime
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    tenant_id: str = "default"
    disclaimer: str = MANDATORY_GOVERNANCE_CONTINUITY_ASSURANCE_DISCLAIMER
