"""Phase 80: Continuity Testing and Exercise Management Schemas.

Defines schemas and models for:
- Scheduling and recording continuity exercises and simulations
- Tracking tabletop drills, dependency failure simulations, communication tests
- Recording exercise weaknesses and routing follow-ups
"""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.governance_continuity_capability import (
    CLINICAL_SAFETY_CONTINUITY_DISCLAIMER,
)


class ContinuityExerciseType(str, Enum):
    """Classification of governance continuity exercise."""
    TABLETOP_EXERCISE = "TABLETOP_EXERCISE"
    COMMUNICATION_TEST = "COMMUNICATION_TEST"
    PERSONNEL_SUBSTITUTION_TEST = "PERSONNEL_SUBSTITUTION_TEST"
    MANUAL_PROCEDURE_TEST = "MANUAL_PROCEDURE_TEST"
    WORKFLOW_CONTINUITY_SIMULATION = "WORKFLOW_CONTINUITY_SIMULATION"
    DEPENDENCY_FAILURE_SIMULATION = "DEPENDENCY_FAILURE_SIMULATION"
    RECOVERY_COORDINATION_EXERCISE = "RECOVERY_COORDINATION_EXERCISE"
    END_TO_END_GOVERNANCE_EXERCISE = "END_TO_END_GOVERNANCE_EXERCISE"


class ContinuityExerciseStatus(str, Enum):
    """Lifecycle status of a continuity exercise."""
    PLANNED = "PLANNED"
    APPROVED = "APPROVED"
    SCHEDULED = "SCHEDULED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    UNDER_EVALUATION = "UNDER_EVALUATION"
    FOLLOW_UP_REQUIRED = "FOLLOW_UP_REQUIRED"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


class ContinuityExerciseRecord(BaseModel):
    """Authoritative record for a governance continuity exercise."""
    model_config = ConfigDict(extra="forbid")

    exercise_id: str
    tenant_id: str
    title: str
    exercise_type: ContinuityExerciseType
    scope: str
    objectives: str
    applicable_plan_id: str
    plan_version: int
    participating_departments: List[str] = Field(default_factory=list)
    coordinator_id: str
    planned_date: str
    actual_date: Optional[str] = None
    scenario: str
    expected_results: str
    observed_results: str = ""
    status: ContinuityExerciseStatus
    identified_weaknesses: List[str] = Field(default_factory=list)
    corrective_action_references: List[str] = Field(default_factory=list)
    evidence_references: List[str] = Field(default_factory=list)
    disclaimer: str = CLINICAL_SAFETY_CONTINUITY_DISCLAIMER
    created_at: str
    updated_at: str


class CreateExerciseRequest(BaseModel):
    """Request to schedule a continuity exercise."""
    model_config = ConfigDict(extra="forbid")

    title: str
    exercise_type: ContinuityExerciseType
    scope: str
    objectives: str
    applicable_plan_id: str
    plan_version: int = 1
    participating_departments: List[str]
    coordinator_id: str
    planned_date: str
    scenario: str
    expected_results: str


class RecordExerciseExecutionRequest(BaseModel):
    """Request to record completion and observations of a continuity exercise."""
    model_config = ConfigDict(extra="forbid")

    actual_date: str
    observed_results: str
    evidence_references: Optional[List[str]] = None


class SubmitExerciseEvaluationRequest(BaseModel):
    """Request to evaluate exercise results and log identified weaknesses."""
    model_config = ConfigDict(extra="forbid")

    status: ContinuityExerciseStatus
    identified_weaknesses: List[str]
    corrective_action_references: Optional[List[str]] = None
