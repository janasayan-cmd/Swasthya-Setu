"""Phase 78: Governance Strategic Objective Service.

Manages the lifecycle, versioning, review, approval, and retirement of strategic
clinical safety governance objectives.
"""

from datetime import datetime, timezone
import uuid
from typing import List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_strategy_repository import (
    GovernanceStrategyRepository,
    get_governance_strategy_repository,
)
from app.schemas.governance_strategy_objective import (
    ApproveObjectiveRequest,
    CLINICAL_SAFETY_STRATEGY_DISCLAIMER,
    CreateObjectiveRequest,
    GovernanceStrategyObjectiveRecord,
    ObjectiveCategory,
    ObjectiveStatus,
    RetireObjectiveRequest,
    SubmitObjectiveRequest,
    UpdateObjectiveRequest,
)


def _get_utc_now_str() -> str:
    return datetime.now(timezone.utc).isoformat()


class GovernanceStrategyObjectiveService:
    """Manages strategic governance objectives."""

    def __init__(
        self,
        repository: Optional[GovernanceStrategyRepository] = None,
    ) -> None:
        self.repository = repository or get_governance_strategy_repository()

    def create_objective(
        self,
        tenant_id: str,
        author_id: str,
        request: CreateObjectiveRequest,
    ) -> GovernanceStrategyObjectiveRecord:
        now = _get_utc_now_str()
        objective = GovernanceStrategyObjectiveRecord(
            objective_id=f"gso-{uuid.uuid4().hex[:12]}",
            tenant_id=tenant_id,
            title=request.title,
            description=request.description,
            rationale=request.rationale,
            category=request.category,
            organizational_scope=request.organizational_scope or {},
            source_reference=request.source_reference,
            related_phase77_gap_ids=request.related_phase77_gap_ids or [],
            related_governance_risk_ids=request.related_governance_risk_ids or [],
            related_audit_finding_ids=request.related_audit_finding_ids or [],
            related_management_decision_ids=request.related_management_decision_ids or [],
            intended_target_state=request.intended_target_state,
            priority=request.priority,
            planning_horizon=request.planning_horizon,
            responsible_governance_owner_id=request.responsible_governance_owner_id,
            supporting_stakeholders=request.supporting_stakeholders or [],
            dependencies=request.dependencies or [],
            success_indicators=request.success_indicators or [],
            measurement_methodology=request.measurement_methodology,
            baseline_reference=request.baseline_reference,
            target_condition=request.target_condition,
            status=ObjectiveStatus.DRAFT,
            created_by=author_id,
            approved_by=None,
            approval_date=None,
            approval_reference=None,
            version=1,
            disclaimer=CLINICAL_SAFETY_STRATEGY_DISCLAIMER,
            created_at=now,
            updated_at=now,
        )
        return self.repository.save_objective(objective)

    def update_objective(
        self,
        tenant_id: str,
        objective_id: str,
        request: UpdateObjectiveRequest,
    ) -> GovernanceStrategyObjectiveRecord:
        objective = self.repository.get_objective(objective_id)
        if not objective or objective.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.STRATEGY_OBJECTIVE_NOT_FOUND,
                message=f"Strategic objective '{objective_id}' was not found.",
                status_code=404,
            )

        if objective.status not in (ObjectiveStatus.DRAFT, ObjectiveStatus.UNDER_REVIEW):
            raise AppException(
                code=ErrorCode.INVALID_STRATEGY_OBJECTIVE_STATE,
                message=f"Objective in status '{objective.status.value}' cannot be edited. Only DRAFT or UNDER_REVIEW objectives can be modified.",
                status_code=400,
            )

        now = _get_utc_now_str()
        update_data = {}
        if request.title is not None:
            update_data["title"] = request.title
        if request.description is not None:
            update_data["description"] = request.description
        if request.rationale is not None:
            update_data["rationale"] = request.rationale
        if request.priority is not None:
            update_data["priority"] = request.priority
        if request.intended_target_state is not None:
            update_data["intended_target_state"] = request.intended_target_state
        if request.target_condition is not None:
            update_data["target_condition"] = request.target_condition
        if request.measurement_methodology is not None:
            update_data["measurement_methodology"] = request.measurement_methodology

        update_data["updated_at"] = now
        objective = objective.model_copy(update=update_data)
        return self.repository.save_objective(objective)

    def submit_objective(
        self,
        tenant_id: str,
        objective_id: str,
        request: SubmitObjectiveRequest,
    ) -> GovernanceStrategyObjectiveRecord:
        objective = self.repository.get_objective(objective_id)
        if not objective or objective.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.STRATEGY_OBJECTIVE_NOT_FOUND,
                message=f"Strategic objective '{objective_id}' was not found.",
                status_code=404,
            )

        if objective.status != ObjectiveStatus.DRAFT:
            raise AppException(
                code=ErrorCode.INVALID_STRATEGY_OBJECTIVE_STATE,
                message=f"Objective in status '{objective.status.value}' cannot be submitted. Only DRAFT objectives can be submitted.",
                status_code=400,
            )

        now = _get_utc_now_str()
        objective = objective.model_copy(
            update={"status": ObjectiveStatus.SUBMITTED, "updated_at": now}
        )
        return self.repository.save_objective(objective)

    def approve_objective(
        self,
        tenant_id: str,
        objective_id: str,
        approver_id: str,
        request: ApproveObjectiveRequest,
    ) -> GovernanceStrategyObjectiveRecord:
        objective = self.repository.get_objective(objective_id)
        if not objective or objective.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.STRATEGY_OBJECTIVE_NOT_FOUND,
                message=f"Strategic objective '{objective_id}' was not found.",
                status_code=404,
            )

        if objective.status != ObjectiveStatus.SUBMITTED:
            raise AppException(
                code=ErrorCode.INVALID_STRATEGY_OBJECTIVE_STATE,
                message=f"Objective in status '{objective.status.value}' cannot be approved. Only SUBMITTED objectives can be approved.",
                status_code=400,
            )

        # Separation of duties: author cannot approve their own objective
        if objective.created_by == approver_id:
            raise AppException(
                code=ErrorCode.STRATEGY_SEPARATION_OF_DUTIES_VIOLATION,
                message="Separation of duties violation: Author cannot approve their own strategic objective.",
                status_code=403,
            )

        now = _get_utc_now_str()
        objective = objective.model_copy(
            update={
                "status": ObjectiveStatus.APPROVED,
                "approved_by": approver_id,
                "approval_date": now,
                "approval_reference": request.approval_reference,
                "updated_at": now,
            }
        )
        return self.repository.save_objective(objective)

    def activate_objective(
        self,
        tenant_id: str,
        objective_id: str,
    ) -> GovernanceStrategyObjectiveRecord:
        objective = self.repository.get_objective(objective_id)
        if not objective or objective.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.STRATEGY_OBJECTIVE_NOT_FOUND,
                message=f"Strategic objective '{objective_id}' was not found.",
                status_code=404,
            )

        if objective.status != ObjectiveStatus.APPROVED:
            raise AppException(
                code=ErrorCode.INVALID_STRATEGY_OBJECTIVE_STATE,
                message=f"Objective in status '{objective.status.value}' cannot be activated. Only APPROVED objectives can be activated.",
                status_code=400,
            )

        now = _get_utc_now_str()
        objective = objective.model_copy(
            update={"status": ObjectiveStatus.ACTIVE, "updated_at": now}
        )
        return self.repository.save_objective(objective)

    def retire_objective(
        self,
        tenant_id: str,
        objective_id: str,
        request: RetireObjectiveRequest,
    ) -> GovernanceStrategyObjectiveRecord:
        objective = self.repository.get_objective(objective_id)
        if not objective or objective.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.STRATEGY_OBJECTIVE_NOT_FOUND,
                message=f"Strategic objective '{objective_id}' was not found.",
                status_code=404,
            )

        now = _get_utc_now_str()
        new_status = (
            ObjectiveStatus.SUPERSEDED
            if request.superseded_by_objective_id
            else ObjectiveStatus.COMPLETED
        )
        objective = objective.model_copy(
            update={"status": new_status, "updated_at": now}
        )
        return self.repository.save_objective(objective)

    def get_objective(
        self,
        tenant_id: str,
        objective_id: str,
    ) -> GovernanceStrategyObjectiveRecord:
        objective = self.repository.get_objective(objective_id)
        if not objective or objective.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.STRATEGY_OBJECTIVE_NOT_FOUND,
                message=f"Strategic objective '{objective_id}' was not found.",
                status_code=404,
            )
        return objective

    def list_objectives(
        self,
        tenant_id: str,
        category: Optional[ObjectiveCategory] = None,
        status: Optional[ObjectiveStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[GovernanceStrategyObjectiveRecord]:
        return self.repository.list_objectives(
            tenant_id=tenant_id,
            category=category,
            status=status,
            skip=skip,
            limit=limit,
        )
