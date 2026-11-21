"""Phase 77: Governance Capability Improvement Plan Service.

Manages strategic capability improvement plans, milestones, and authoritative
handoffs to downstream governance processes (Phases 54, 63, 72, 73, 75).
"""

from datetime import datetime, timezone
import uuid
from typing import List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_strategic_assurance_repository import (
    GovernanceStrategicAssuranceRepository,
    get_strategic_assurance_repository,
)
from app.schemas.governance_improvement_plan import (
    CreateImprovementPlanRequest,
    GovernanceImprovementPlanRecord,
    ImprovementPlanStatus,
    RouteImprovementActionRequest,
    UpdateMilestoneRequest,
)
from app.schemas.governance_maturity_framework import CLINICAL_SAFETY_DISCLAIMER


def _get_utc_now_str() -> str:
    return datetime.now(timezone.utc).isoformat()


_VALID_TARGET_WORKFLOWS = {
    "PHASE_49_INCIDENT",
    "PHASE_54_CAPA",
    "PHASE_63_RISK",
    "PHASE_67_ESCALATION",
    "PHASE_69_COMPLIANCE",
    "PHASE_70_AUDIT",
    "PHASE_72_MANAGEMENT_REVIEW",
    "PHASE_73_IMPLEMENTATION",
    "PHASE_75_PORTFOLIO",
    "PHASE_76_BENEFIT",
}


class GovernanceImprovementPlanService:
    """Manages strategic governance continuous improvement plans and authoritative handoffs."""

    def __init__(
        self,
        repository: Optional[GovernanceStrategicAssuranceRepository] = None,
    ) -> None:
        self.repository = repository or get_strategic_assurance_repository()

    def create_plan(
        self,
        tenant_id: str,
        creator_id: str,
        request: CreateImprovementPlanRequest,
    ) -> GovernanceImprovementPlanRecord:
        now = _get_utc_now_str()
        plan_id = f"gip-{uuid.uuid4().hex[:12]}"

        # Validate linked gaps if provided
        if request.linked_gap_ids:
            for g_id in request.linked_gap_ids:
                gap = self.repository.get_gap(g_id)
                if not gap or gap.tenant_id != tenant_id:
                    raise AppException(
                        code=ErrorCode.SYSTEMIC_GAP_NOT_FOUND,
                        message=f"Linked systemic gap '{g_id}' was not found.",
                        status_code=404,
                    )

        plan = GovernanceImprovementPlanRecord(
            plan_id=plan_id,
            tenant_id=tenant_id,
            title=request.title,
            description=request.description,
            target_dimensions=request.target_dimensions,
            baseline_level=request.baseline_level,
            target_level=request.target_level,
            scope=request.scope or {},
            status=ImprovementPlanStatus.ACTIVE,
            accountable_owner_id=request.accountable_owner_id,
            milestones=request.milestones or [],
            linked_gap_ids=request.linked_gap_ids or [],
            external_handoffs=[],
            created_by=creator_id,
            target_completion_date=request.target_completion_date,
            disclaimer=CLINICAL_SAFETY_DISCLAIMER,
            created_at=now,
            updated_at=now,
        )
        return self.repository.save_plan(plan)

    def update_milestone(
        self,
        tenant_id: str,
        plan_id: str,
        milestone_id: str,
        request: UpdateMilestoneRequest,
    ) -> GovernanceImprovementPlanRecord:
        plan = self.repository.get_plan(plan_id)
        if not plan or plan.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.IMPROVEMENT_PLAN_NOT_FOUND,
                message=f"Improvement plan '{plan_id}' was not found.",
                status_code=404,
            )

        milestone_found = False
        updated_milestones = []
        for ms in plan.milestones:
            if ms.milestone_id == milestone_id:
                milestone_found = True
                updated_ms = ms.model_copy(
                    update={
                        "status": request.status,
                        "completion_evidence": request.completion_evidence or ms.completion_evidence,
                        "notes": request.notes or ms.notes,
                    }
                )
                updated_milestones.append(updated_ms)
            else:
                updated_milestones.append(ms)

        if not milestone_found:
            raise AppException(
                code=ErrorCode.IMPROVEMENT_PLAN_NOT_FOUND,
                message=f"Milestone '{milestone_id}' not found in improvement plan '{plan_id}'.",
                status_code=404,
            )

        now = _get_utc_now_str()
        plan = plan.model_copy(
            update={"milestones": updated_milestones, "updated_at": now}
        )
        return self.repository.save_plan(plan)

    def route_action(
        self,
        tenant_id: str,
        plan_id: str,
        routed_by: str,
        request: RouteImprovementActionRequest,
    ) -> GovernanceImprovementPlanRecord:
        plan = self.repository.get_plan(plan_id)
        if not plan or plan.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.IMPROVEMENT_PLAN_NOT_FOUND,
                message=f"Improvement plan '{plan_id}' was not found.",
                status_code=404,
            )

        if request.target_workflow not in _VALID_TARGET_WORKFLOWS:
            raise AppException(
                code=ErrorCode.INVALID_IMPROVEMENT_PLAN_STATE,
                message=f"Target workflow '{request.target_workflow}' is not a recognized authoritative workflow.",
                status_code=400,
            )

        now = _get_utc_now_str()
        handoff_entry = {
            "handoff_id": f"hnd-{uuid.uuid4().hex[:8]}",
            "target_workflow": request.target_workflow,
            "action_title": request.action_title,
            "action_description": request.action_description,
            "assigned_lead_id": request.assigned_lead_id,
            "target_date": request.target_date,
            "routed_by": routed_by,
            "routed_at": now,
        }

        handoffs = list(plan.external_handoffs)
        handoffs.append(handoff_entry)

        plan = plan.model_copy(
            update={"external_handoffs": handoffs, "updated_at": now}
        )
        return self.repository.save_plan(plan)

    def get_plan(
        self,
        tenant_id: str,
        plan_id: str,
    ) -> GovernanceImprovementPlanRecord:
        plan = self.repository.get_plan(plan_id)
        if not plan or plan.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.IMPROVEMENT_PLAN_NOT_FOUND,
                message=f"Improvement plan '{plan_id}' was not found.",
                status_code=404,
            )
        return plan

    def list_plans(
        self,
        tenant_id: str,
        status: Optional[ImprovementPlanStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[GovernanceImprovementPlanRecord]:
        return self.repository.list_plans(
            tenant_id=tenant_id,
            status=status,
            skip=skip,
            limit=limit,
        )
