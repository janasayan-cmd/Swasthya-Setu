"""Phase 81: Continuity Exercise Assurance Service.

Evaluates Phase 80 continuity exercises across 12 exercise types, distinguishing
exercise completion from demonstrated operational effectiveness.
"""

from datetime import datetime
import uuid
from typing import List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_continuity_repository import (
    governance_continuity_repository,
)
from app.repositories.governance_continuity_assurance_repository import (
    governance_continuity_assurance_repository,
)
from app.schemas.governance_continuity_assurance_exercise import (
    ContinuityExerciseAssuranceRecord,
    CreateExerciseAssuranceEvaluationRequest,
    ExerciseCriterionEvaluation,
)


class GovernanceContinuityAssuranceExerciseService:
    """Domain service for assessing continuity exercise effectiveness."""

    def __init__(self, repo=None, phase80_repo=None) -> None:
        self.repo = repo or governance_continuity_assurance_repository
        self.phase80_repo = phase80_repo or governance_continuity_repository

    def create_evaluation(
        self,
        req: CreateExerciseAssuranceEvaluationRequest,
        actor_id: str,
        tenant_id: str = "default",
    ) -> ContinuityExerciseAssuranceRecord:
        exercise = self.phase80_repo.get_exercise(req.exercise_id)
        if not exercise or exercise.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.CONTINUITY_EXERCISE_NOT_FOUND,
                message=f"Phase 80 Continuity Exercise {req.exercise_id} not found",
                status_code=404,
            )

        # Separation of duties: exercise coordinator/lead cannot evaluate exercise effectiveness
        coord_id = getattr(exercise, "coordinator_id", None) or getattr(exercise, "lead_evaluator_id", None)
        if actor_id in (coord_id, getattr(exercise, "created_by", None)):
            raise AppException(
                code=ErrorCode.CONTINUITY_ASSURANCE_SEPARATION_OF_DUTIES_VIOLATION,
                message="Exercise lead/coordinator cannot serve as the independent exercise assurance evaluator",
                status_code=400,
            )

        evaluation_id = f"CEA-{uuid.uuid4().hex[:8].upper()}"

        passed_count = sum(1 for c in req.criteria_evaluations if c.outcome == ExerciseCriterionEvaluation.PASSED)
        failed_count = sum(1 for c in req.criteria_evaluations if c.outcome == ExerciseCriterionEvaluation.FAILED)
        partially_count = sum(1 for c in req.criteria_evaluations if c.outcome == ExerciseCriterionEvaluation.PARTIALLY_DEMONSTRATED)
        untested_count = sum(1 for c in req.criteria_evaluations if c.outcome == ExerciseCriterionEvaluation.NOT_TESTED)
        unable_count = sum(1 for c in req.criteria_evaluations if c.outcome == ExerciseCriterionEvaluation.UNABLE_TO_DETERMINE)

        record = ContinuityExerciseAssuranceRecord(
            evaluation_id=evaluation_id,
            exercise_id=req.exercise_id,
            exercise_type=req.exercise_type,
            plan_id=req.plan_id,
            plan_version=req.plan_version,
            evaluated_by=actor_id,
            evaluator_role=req.evaluator_role,
            evaluated_at=datetime.utcnow(),
            criteria_evaluations=req.criteria_evaluations,
            review_outcome=req.review_outcome,
            passed_count=passed_count,
            failed_count=failed_count,
            partially_demonstrated_count=partially_count,
            untested_count=untested_count,
            unable_to_determine_count=unable_count,
            deviations=req.deviations,
            limitations=req.limitations or "Evaluation reflects controlled exercise conditions, not actual catastrophic disruption.",
            follow_up_requirements=req.follow_up_requirements,
            tenant_id=tenant_id,
        )
        return self.repo.save_exercise_evaluation(record)

    def get_evaluation(self, evaluation_id: str, tenant_id: str = "default") -> ContinuityExerciseAssuranceRecord:
        rec = self.repo.get_exercise_evaluation(evaluation_id, tenant_id)
        if not rec:
            raise AppException(
                code=ErrorCode.EXERCISE_ASSURANCE_NOT_FOUND,
                message=f"Exercise evaluation {evaluation_id} not found",
                status_code=404,
            )
        return rec

    def list_evaluations(
        self,
        tenant_id: str = "default",
        exercise_id: Optional[str] = None,
    ) -> List[ContinuityExerciseAssuranceRecord]:
        return self.repo.list_exercise_evaluations(tenant_id, exercise_id)


# Module-level instance
governance_continuity_assurance_exercise_service = GovernanceContinuityAssuranceExerciseService()
