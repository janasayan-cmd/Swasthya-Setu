"""Phase 85: Coverage Scenarios and Stress-Testing Service.

Evaluates coverage resilience and identifies single points of failure under
simulated operational disruptions and personnel absences.
"""

import uuid
from datetime import datetime
from typing import List, Optional
from app.repositories.governance_role_coverage_repository import (
    GovernanceRoleCoverageRepository,
    get_governance_role_coverage_repository,
)
from app.schemas.governance_role_coverage_common import (
    ScenarioType,
)
from app.schemas.governance_role_coverage_scenario import (
    CoverageScenarioEvaluationRecord,
    EvaluateCoverageScenarioRequest,
)


class GovernanceRoleCoverageScenarioService:
    """Service for stress-testing role coverage resilience."""

    def __init__(self, repository: GovernanceRoleCoverageRepository) -> None:
        self.repository = repository

    def evaluate_scenario(
        self,
        tenant_id: str,
        user_id: str,
        request: EvaluateCoverageScenarioRequest,
    ) -> CoverageScenarioEvaluationRecord:
        responsibilities = self.repository.list_responsibilities(tenant_id)
        unavailable_set = set(request.simulated_unavailable_user_ids)

        total_count = len(responsibilities)
        fully_covered = 0
        partially_covered = 0
        uncovered = 0
        uncovered_ids = []
        spof_revealed = []
        recommendations = []

        for resp in responsibilities:
            coverage = self.repository.get_coverage_by_responsibility(
                resp.responsibility_id, tenant_id
            )
            primary_is_absent = resp.primary_owner_id in unavailable_set

            if not primary_is_absent:
                fully_covered += 1
            else:
                # Primary is absent, evaluate backup availability
                active_backups = []
                if coverage:
                    for b in coverage.designated_backups:
                        if (
                            b.backup_user_id not in unavailable_set
                            and b.capability_verified
                            and b.authorization_verified
                            and b.is_available
                        ):
                            active_backups.append(b)

                if active_backups:
                    partially_covered += 1
                else:
                    uncovered += 1
                    uncovered_ids.append(resp.responsibility_id)
                    spof_revealed.append(
                        f"Responsibility '{resp.role_title} ({resp.responsibility_name})' unstaffed when primary owner {resp.primary_owner_name} is absent."
                    )

        resilience_pct = 0.0
        if total_count > 0:
            resilience_pct = round(((fully_covered + partially_covered) / total_count) * 100, 2)

        if uncovered > 0:
            recommendations.append(
                f"Urgent: {uncovered} critical governance responsibilities have zero available verified backups during this scenario."
            )
        if partially_covered > 0:
            recommendations.append(
                f"{partially_covered} responsibilities relying on secondary backups; ensure emergency handovers are pre-briefed."
            )
        if resilience_pct >= 90.0:
            recommendations.append("Robust coverage resilience demonstrated under simulated scenario conditions.")

        record = CoverageScenarioEvaluationRecord(
            evaluation_id=f"scen-{uuid.uuid4().hex[:12]}",
            tenant_id=tenant_id,
            scenario_type=request.scenario_type,
            scenario_name=request.scenario_name,
            simulated_unavailable_user_ids=request.simulated_unavailable_user_ids,
            total_critical_responsibilities_evaluated=total_count,
            fully_covered_count=fully_covered,
            partially_covered_count=partially_covered,
            uncovered_count=uncovered,
            overall_coverage_resilience_percentage=resilience_pct,
            uncovered_responsibility_ids=uncovered_ids,
            single_points_of_failure_revealed=spof_revealed,
            evaluated_by=user_id,
            evaluated_at=datetime.utcnow(),
            advisory_recommendations=recommendations,
        )
        return self.repository.save_scenario(record)

    def get_scenario(
        self, tenant_id: str, evaluation_id: str
    ) -> CoverageScenarioEvaluationRecord:
        record = self.repository.get_scenario(evaluation_id, tenant_id)
        if not record:
            from app.core.exceptions import AppException, ErrorCode
            from fastapi import status
            raise AppException(
                code=ErrorCode.COVERAGE_SCENARIO_NOT_FOUND,
                message=f"Coverage scenario evaluation '{evaluation_id}' not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return record

    def list_scenarios(
        self, tenant_id: str, scenario_type: Optional[ScenarioType] = None
    ) -> List[CoverageScenarioEvaluationRecord]:
        return self.repository.list_scenarios(tenant_id, scenario_type)


_coverage_scenario_service: Optional[GovernanceRoleCoverageScenarioService] = None


def get_governance_role_coverage_scenario_service() -> GovernanceRoleCoverageScenarioService:
    global _coverage_scenario_service
    if _coverage_scenario_service is None:
        _coverage_scenario_service = GovernanceRoleCoverageScenarioService(
            get_governance_role_coverage_repository()
        )
    return _coverage_scenario_service
