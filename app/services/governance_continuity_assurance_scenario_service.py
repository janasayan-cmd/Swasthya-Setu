"""Phase 81: Scenario Coverage and Stress Validation Service.

Supports advisory stress testing and scenario coverage analysis across 12
predefined disruption scenarios without triggering actual production disruptions.
"""

from datetime import datetime
import uuid
from typing import List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_continuity_assurance_repository import (
    governance_continuity_assurance_repository,
)
from app.schemas.governance_continuity_assurance_scenario import (
    ContinuityScenarioAssessmentRecord,
    CreateScenarioAssessmentRequest,
    EvaluateScenarioRequest,
    ScenarioEvaluationOutcome,
)


class GovernanceContinuityAssuranceScenarioService:
    """Domain service for evaluating continuity scenarios and stress resilience."""

    def __init__(self, repo=None) -> None:
        self.repo = repo or governance_continuity_assurance_repository

    def create_scenario_assessment(
        self,
        req: CreateScenarioAssessmentRequest,
        actor_id: str,
        tenant_id: str = "default",
    ) -> ContinuityScenarioAssessmentRecord:
        scenario_id = f"CSA-{uuid.uuid4().hex[:8].upper()}"

        record = ContinuityScenarioAssessmentRecord(
            scenario_id=scenario_id,
            scenario_type=req.scenario_type,
            scenario_title=req.scenario_title,
            scenario_description=req.scenario_description,
            severity_level=req.severity_level,
            affected_capability_ids=req.affected_capability_ids,
            required_dependencies=req.required_dependencies,
            assumptions=req.assumptions,
            expected_continuity_response=req.expected_continuity_response,
            expected_recovery_sequence=req.expected_recovery_sequence,
            evaluation_outcome=ScenarioEvaluationOutcome.UNTESTED,
            is_advisory_only=True,
            created_by=actor_id,
            created_at=datetime.utcnow(),
            tenant_id=tenant_id,
        )
        return self.repo.save_scenario_assessment(record)

    def evaluate_scenario(
        self,
        scenario_id: str,
        req: EvaluateScenarioRequest,
        actor_id: str,
        tenant_id: str = "default",
    ) -> ContinuityScenarioAssessmentRecord:
        rec = self.repo.get_scenario_assessment(scenario_id, tenant_id)
        if not rec:
            raise AppException(
                code=ErrorCode.SCENARIO_ASSESSMENT_NOT_FOUND,
                message=f"Scenario assessment {scenario_id} not found",
                status_code=404,
            )

        # Separation of duties: creator cannot be evaluator
        if rec.created_by == actor_id:
            raise AppException(
                code=ErrorCode.CONTINUITY_ASSURANCE_SEPARATION_OF_DUTIES_VIOLATION,
                message="Author of scenario assessment cannot independently evaluate scenario stress results",
                status_code=400,
            )

        rec.evaluation_outcome = req.evaluation_outcome
        rec.actual_exercise_ref = req.actual_exercise_ref
        rec.identified_weaknesses = req.identified_weaknesses
        rec.recommended_mitigations = req.recommended_mitigations
        rec.limitations = req.limitations or "Advisory scenario analysis based on current system architecture."
        rec.evaluated_by = actor_id
        rec.evaluated_at = datetime.utcnow()
        return self.repo.save_scenario_assessment(rec)

    def get_scenario_assessment(self, scenario_id: str, tenant_id: str = "default") -> ContinuityScenarioAssessmentRecord:
        rec = self.repo.get_scenario_assessment(scenario_id, tenant_id)
        if not rec:
            raise AppException(
                code=ErrorCode.SCENARIO_ASSESSMENT_NOT_FOUND,
                message=f"Scenario assessment {scenario_id} not found",
                status_code=404,
            )
        return rec

    def list_scenario_assessments(self, tenant_id: str = "default") -> List[ContinuityScenarioAssessmentRecord]:
        return self.repo.list_scenario_assessments(tenant_id)


# Module-level instance
governance_continuity_assurance_scenario_service = GovernanceContinuityAssuranceScenarioService()
