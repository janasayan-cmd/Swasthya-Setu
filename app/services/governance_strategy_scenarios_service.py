"""Phase 79: Strategic Scenario Analysis Service.

Provides advisory what-if modeling across strategic execution constraints,
milestone delays, and capacity fluctuations with explicit projection caveats.
"""

from datetime import datetime, timezone
import uuid
from typing import Any, Dict, List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_strategy_execution_repository import (
    GovernanceStrategyExecutionRepository,
    get_governance_strategy_execution_repository,
)
from app.schemas.governance_strategy_scenarios import (
    CreateScenarioRequest,
    ExecuteScenarioRequest,
    ScenarioComparisonResponse,
    ScenarioType,
    StrategicScenarioRecord,
)
from app.schemas.governance_strategy_execution_monitoring import (
    CLINICAL_SAFETY_MONITORING_DISCLAIMER,
)


def _get_utc_now_str() -> str:
    return datetime.now(timezone.utc).isoformat()


class GovernanceStrategyScenariosService:
    """Manages strategic scenario definitions, what-if executions, and comparative analysis."""

    def __init__(
        self,
        repository: Optional[GovernanceStrategyExecutionRepository] = None,
    ) -> None:
        self.repository = repository or get_governance_strategy_execution_repository()

    def create_scenario(
        self,
        tenant_id: str,
        creator_id: str,
        request: CreateScenarioRequest,
    ) -> StrategicScenarioRecord:
        scenario_id = f"SCN-{uuid.uuid4().hex[:8].upper()}"
        now_str = _get_utc_now_str()

        record = StrategicScenarioRecord(
            scenario_id=scenario_id,
            tenant_id=tenant_id,
            title=request.title,
            scenario_type=request.scenario_type,
            description=request.description,
            input_roadmap_id=request.input_roadmap_id,
            assumptions=request.assumptions or [],
            variables=request.variables or {},
            calculation_method=request.calculation_method,
            projected_milestone_impacts=[],
            projected_dependency_impacts=[],
            projected_resource_implications=request.projected_resource_implications or "",
            expected_strategic_consequences=request.expected_strategic_consequences or "",
            uncertainty_range=request.uncertainty_range or "±15% variance based on preliminary modeling assumptions",
            limitations=request.limitations or "Advisory what-if simulation only. Not verified clinical or operational results.",
            created_by=creator_id,
            disclaimer=CLINICAL_SAFETY_MONITORING_DISCLAIMER,
            created_at=now_str,
        )
        return self.repository.save_scenario(record)

    def execute_scenario(
        self,
        tenant_id: str,
        scenario_id: str,
        request: ExecuteScenarioRequest,
    ) -> StrategicScenarioRecord:
        scenario = self.repository.get_scenario(scenario_id)
        if not scenario or scenario.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.STRATEGY_SCENARIO_NOT_FOUND,
                message=f"Strategic scenario '{scenario_id}' was not found.",
                status_code=404,
            )

        delay_days = request.milestone_delays_days or 0
        budget_pct = request.budget_variance_pct or 0.0

        projected_milestones = [
            {
                "projected_delay_days": delay_days,
                "projected_status": "OFF_TRACK" if delay_days > 30 else ("AT_RISK" if delay_days > 0 else "ON_TRACK"),
                "advisory_caveat": "Projected simulation outcome. Subject to authoritative governance review.",
            }
        ]

        projected_deps = [
            {
                "downstream_cascade_risk": "HIGH" if delay_days > 45 else "MODERATE",
                "simulated_variance_pct": budget_pct,
            }
        ]

        updated = scenario.model_copy(
            update={
                "projected_milestone_impacts": projected_milestones,
                "projected_dependency_impacts": projected_deps,
                "projected_resource_implications": f"Simulated budget variance: {budget_pct}%. Milestone delay factor: {delay_days} days.",
            }
        )
        return self.repository.save_scenario(updated)

    def compare_scenarios(
        self,
        tenant_id: str,
        scenario_ids: List[str],
        baseline_roadmap_id: str,
    ) -> ScenarioComparisonResponse:
        scenarios: List[StrategicScenarioRecord] = []
        for sid in scenario_ids:
            sc = self.repository.get_scenario(sid)
            if sc and sc.tenant_id == tenant_id:
                scenarios.append(sc)

        summary = (
            f"Compared {len(scenarios)} strategic scenario(s) against baseline roadmap '{baseline_roadmap_id}'. "
            "All scenario projections represent advisory modeling and do NOT constitute operational commitments or verified outcomes."
        )

        return ScenarioComparisonResponse(
            tenant_id=tenant_id,
            compared_scenarios=scenarios,
            baseline_roadmap_id=baseline_roadmap_id,
            comparative_summary=summary,
            disclaimer=CLINICAL_SAFETY_MONITORING_DISCLAIMER,
        )

    def get_scenario(
        self,
        tenant_id: str,
        scenario_id: str,
    ) -> StrategicScenarioRecord:
        scenario = self.repository.get_scenario(scenario_id)
        if not scenario or scenario.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.STRATEGY_SCENARIO_NOT_FOUND,
                message=f"Strategic scenario '{scenario_id}' was not found.",
                status_code=404,
            )
        return scenario

    def list_scenarios(
        self,
        tenant_id: str,
        roadmap_id: Optional[str] = None,
        scenario_type: Optional[ScenarioType] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[StrategicScenarioRecord]:
        return self.repository.list_scenarios(
            tenant_id=tenant_id,
            roadmap_id=roadmap_id,
            scenario_type=scenario_type,
            skip=skip,
            limit=limit,
        )
