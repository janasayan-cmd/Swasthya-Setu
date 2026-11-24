"""
Phase 88: Governance Recovery Resource Planning Service
Formulates resource requirement plans for candidate options without autonomous allocation.
"""
from datetime import datetime, timezone
from typing import List, Optional
import uuid

from app.core.exceptions import (
    AppException,
    ErrorCode,
)
from app.repositories.governance_response_strategy_repository import (
    GovernanceResponseStrategyRepository,
    get_governance_response_strategy_repository,
)
from app.schemas.governance_response_common import (
    MANDATORY_RESPONSE_STRATEGY_DISCLAIMER,
)
from app.schemas.governance_recovery_resource_planning import (
    CreateRecoveryResourcePlanRequest,
    RecoveryResourcePlanRecord,
    RecoveryResourceRequirementItem,
)


class GovernanceRecoveryResourcePlanningService:
    def __init__(self, repo: Optional[GovernanceResponseStrategyRepository] = None):
        self.repo = repo or get_governance_response_strategy_repository()

    def create_recovery_resource_plan(
        self,
        tenant_id: str,
        user_id: str,
        req: CreateRecoveryResourcePlanRequest,
    ) -> RecoveryResourcePlanRecord:
        now = datetime.now(timezone.utc)
        items = list(req.requirements)
        competing_count = sum(len(it.competing_demands) for it in items)

        record = RecoveryResourcePlanRecord(
            plan_id=f"rplan-{uuid.uuid4().hex[:10]}",
            tenant_id=tenant_id,
            option_id=req.option_id,
            resource_requirements=items,
            competing_demands_count=competing_count,
            unmet_resource_requirements=[],
            planning_status="PROPOSAL",
            created_by=user_id,
            created_at=now,
            disclaimer=MANDATORY_RESPONSE_STRATEGY_DISCLAIMER,
        )
        return self.repo.create_resource_plan(record)

    def get_recovery_resource_plan(
        self,
        plan_id: str,
        tenant_id: str,
    ) -> RecoveryResourcePlanRecord:
        record = self.repo.get_resource_plan(plan_id, tenant_id)
        if not record:
            raise AppException(
                ErrorCode.RECOVERY_RESOURCE_PLAN_NOT_FOUND,
                f"Recovery resource plan '{plan_id}' not found.",
            )
        return record

    def list_recovery_resource_plans(
        self,
        tenant_id: str,
        option_ref: Optional[str] = None,
        scenario_ref: Optional[str] = None,
    ) -> List[RecoveryResourcePlanRecord]:
        return self.repo.list_resource_plans(
            tenant_id=tenant_id,
            option_id=option_ref,
        )


_governance_recovery_resource_planning_service: Optional[GovernanceRecoveryResourcePlanningService] = None


def get_governance_recovery_resource_planning_service() -> GovernanceRecoveryResourcePlanningService:
    global _governance_recovery_resource_planning_service
    if _governance_recovery_resource_planning_service is None:
        _governance_recovery_resource_planning_service = GovernanceRecoveryResourcePlanningService()
    return _governance_recovery_resource_planning_service
