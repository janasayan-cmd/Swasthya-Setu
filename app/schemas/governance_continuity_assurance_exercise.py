"""Phase 81: Continuity Exercise Assurance Schemas.

Evaluates Phase 80 continuity exercises across 12 exercise types, distinguishing
exercise completion from demonstrated operational effectiveness.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.schemas.governance_continuity_assurance_framework import (
    MANDATORY_GOVERNANCE_CONTINUITY_ASSURANCE_DISCLAIMER,
)


class ExerciseAssuranceType(str, Enum):
    TABLETOP = "TABLETOP"
    COMMUNICATION = "COMMUNICATION"
    PERSONNEL_SUBSTITUTION = "PERSONNEL_SUBSTITUTION"
    DELEGATED_AUTHORITY = "DELEGATED_AUTHORITY"
    MANUAL_REPORTING = "MANUAL_REPORTING"
    WORKFLOW_CONTINUITY_SIMULATION = "WORKFLOW_CONTINUITY_SIMULATION"
    CRITICAL_DEPENDENCY_FAILURE_SIMULATION = "CRITICAL_DEPENDENCY_FAILURE_SIMULATION"
    EVIDENCE_RECOVERY = "EVIDENCE_RECOVERY"
    GOVERNANCE_DECISION_CONTINUITY = "GOVERNANCE_DECISION_CONTINUITY"
    RECOVERY_COORDINATION = "RECOVERY_COORDINATION"
    CROSS_DEPARTMENT_CONTINUITY = "CROSS_DEPARTMENT_CONTINUITY"
    END_TO_END_CONTINUITY = "END_TO_END_CONTINUITY"


class ExerciseCriterionEvaluation(str, Enum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    PARTIALLY_DEMONSTRATED = "PARTIALLY_DEMONSTRATED"
    NOT_TESTED = "NOT_TESTED"
    UNABLE_TO_DETERMINE = "UNABLE_TO_DETERMINE"


class ExerciseReviewOutcome(str, Enum):
    DEMONSTRATED_EFFECTIVE = "DEMONSTRATED_EFFECTIVE"
    PARTIALLY_EFFECTIVE = "PARTIALLY_EFFECTIVE"
    INEFFECTIVE = "INEFFECTIVE"
    INCONCLUSIVE = "INCONCLUSIVE"


class CriterionEvaluationDetail(BaseModel):
    criterion_id: str
    criterion_name: str
    outcome: ExerciseCriterionEvaluation
    observed_evidence: Optional[str] = None
    notes: Optional[str] = None


class CreateExerciseAssuranceEvaluationRequest(BaseModel):
    exercise_id: str  # References Phase 80 ContinuityExerciseRecord
    exercise_type: ExerciseAssuranceType
    plan_id: str
    plan_version: int = 1
    evaluator_role: str
    criteria_evaluations: List[CriterionEvaluationDetail] = Field(default_factory=list)
    review_outcome: ExerciseReviewOutcome
    deviations: List[str] = Field(default_factory=list)
    limitations: Optional[str] = None
    follow_up_requirements: List[str] = Field(default_factory=list)


class ContinuityExerciseAssuranceRecord(BaseModel):
    evaluation_id: str
    exercise_id: str
    exercise_type: ExerciseAssuranceType
    plan_id: str
    plan_version: int
    evaluated_by: str
    evaluator_role: str
    evaluated_at: datetime
    criteria_evaluations: List[CriterionEvaluationDetail] = Field(default_factory=list)
    review_outcome: ExerciseReviewOutcome
    passed_count: int = 0
    failed_count: int = 0
    partially_demonstrated_count: int = 0
    untested_count: int = 0
    unable_to_determine_count: int = 0
    deviations: List[str] = Field(default_factory=list)
    limitations: Optional[str] = None
    follow_up_requirements: List[str] = Field(default_factory=list)
    tenant_id: str = "default"
    disclaimer: str = MANDATORY_GOVERNANCE_CONTINUITY_ASSURANCE_DISCLAIMER
