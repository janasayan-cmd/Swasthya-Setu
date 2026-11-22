"""Phase 80: Continuity Testing and Exercise Management Service.

Schedules, executes, and evaluates continuity exercises (tabletop, simulation, drills).
"""

from datetime import datetime, timezone
import uuid
from typing import List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_continuity_repository import (
    GovernanceContinuityRepository,
    get_governance_continuity_repository,
)
from app.schemas.governance_continuity_exercises import (
    ContinuityExerciseRecord,
    ContinuityExerciseStatus,
    ContinuityExerciseType,
    CreateExerciseRequest,
    RecordExerciseExecutionRequest,
    SubmitExerciseEvaluationRequest,
)
from app.schemas.governance_continuity_capability import (
    CLINICAL_SAFETY_CONTINUITY_DISCLAIMER,
)


def _get_utc_now_str() -> str:
    return datetime.now(timezone.utc).isoformat()


class GovernanceContinuityExercisesService:
    """Manages continuity exercises, scenario execution, weakness identification, and evaluations."""

    def __init__(
        self,
        repository: Optional[GovernanceContinuityRepository] = None,
    ) -> None:
        self.repository = repository or get_governance_continuity_repository()

    def create_exercise(
        self,
        tenant_id: str,
        author_id: str,
        request: CreateExerciseRequest,
    ) -> ContinuityExerciseRecord:
        ex_id = f"GCE-{uuid.uuid4().hex[:8].upper()}"
        now_str = _get_utc_now_str()

        record = ContinuityExerciseRecord(
            exercise_id=ex_id,
            tenant_id=tenant_id,
            title=request.title,
            exercise_type=request.exercise_type,
            scope=request.scope,
            objectives=request.objectives,
            applicable_plan_id=request.applicable_plan_id,
            plan_version=request.plan_version,
            participating_departments=request.participating_departments,
            coordinator_id=request.coordinator_id,
            planned_date=request.planned_date,
            actual_date=None,
            scenario=request.scenario,
            expected_results=request.expected_results,
            observed_results="",
            status=ContinuityExerciseStatus.PLANNED,
            identified_weaknesses=[],
            corrective_action_references=[],
            evidence_references=[],
            disclaimer=CLINICAL_SAFETY_CONTINUITY_DISCLAIMER,
            created_at=now_str,
            updated_at=now_str,
        )
        return self.repository.save_exercise(record)

    def record_exercise_execution(
        self,
        tenant_id: str,
        coordinator_id: str,
        exercise_id: str,
        request: RecordExerciseExecutionRequest,
    ) -> ContinuityExerciseRecord:
        ex = self.repository.get_exercise(exercise_id)
        if not ex or ex.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.CONTINUITY_EXERCISE_NOT_FOUND,
                message=f"Continuity exercise '{exercise_id}' was not found.",
                status_code=404,
            )

        now_str = _get_utc_now_str()
        ev_list = list(ex.evidence_references)
        if request.evidence_references:
            ev_list.extend(request.evidence_references)

        updated = ex.model_copy(
            update={
                "status": ContinuityExerciseStatus.COMPLETED,
                "actual_date": request.actual_date,
                "observed_results": request.observed_results,
                "evidence_references": ev_list,
                "updated_at": now_str,
            }
        )
        return self.repository.save_exercise(updated)

    def submit_exercise_evaluation(
        self,
        tenant_id: str,
        evaluator_id: str,
        exercise_id: str,
        request: SubmitExerciseEvaluationRequest,
    ) -> ContinuityExerciseRecord:
        ex = self.repository.get_exercise(exercise_id)
        if not ex or ex.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.CONTINUITY_EXERCISE_NOT_FOUND,
                message=f"Continuity exercise '{exercise_id}' was not found.",
                status_code=404,
            )

        now_str = _get_utc_now_str()
        weaknesses = list(ex.identified_weaknesses)
        weaknesses.extend(request.identified_weaknesses)

        ca_refs = list(ex.corrective_action_references)
        if request.corrective_action_references:
            ca_refs.extend(request.corrective_action_references)

        updated = ex.model_copy(
            update={
                "status": request.status,
                "identified_weaknesses": weaknesses,
                "corrective_action_references": ca_refs,
                "updated_at": now_str,
            }
        )
        return self.repository.save_exercise(updated)

    def get_exercise(
        self,
        tenant_id: str,
        exercise_id: str,
    ) -> ContinuityExerciseRecord:
        ex = self.repository.get_exercise(exercise_id)
        if not ex or ex.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.CONTINUITY_EXERCISE_NOT_FOUND,
                message=f"Continuity exercise '{exercise_id}' was not found.",
                status_code=404,
            )
        return ex

    def list_exercises(
        self,
        tenant_id: str,
        exercise_type: Optional[ContinuityExerciseType] = None,
        status: Optional[ContinuityExerciseStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[ContinuityExerciseRecord]:
        return self.repository.list_exercises(
            tenant_id=tenant_id,
            exercise_type=exercise_type,
            status=status,
            skip=skip,
            limit=limit,
        )
