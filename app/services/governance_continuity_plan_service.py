"""Phase 80: Governance Continuity Plan Management Service.

Manages creation, approval, and version-controlled revisions of clinical
safety governance continuity plans.
"""

from datetime import datetime, timezone
import uuid
from typing import List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_continuity_repository import (
    GovernanceContinuityRepository,
    get_governance_continuity_repository,
)
from app.schemas.governance_continuity_plan import (
    ApproveContinuityPlanRequest,
    ContinuityPlanStatus,
    CreateContinuityPlanRequest,
    GovernanceContinuityPlanRecord,
    ReviseContinuityPlanRequest,
    SubmitContinuityPlanRequest,
    UpdateContinuityPlanRequest,
)
from app.schemas.governance_continuity_capability import (
    CLINICAL_SAFETY_CONTINUITY_DISCLAIMER,
)


def _get_utc_now_str() -> str:
    return datetime.now(timezone.utc).isoformat()


class GovernanceContinuityPlanService:
    """Manages governance continuity plans, separation of duties, and material revisions."""

    def __init__(
        self,
        repository: Optional[GovernanceContinuityRepository] = None,
    ) -> None:
        self.repository = repository or get_governance_continuity_repository()

    def create_plan(
        self,
        tenant_id: str,
        author_id: str,
        request: CreateContinuityPlanRequest,
    ) -> GovernanceContinuityPlanRecord:
        plan_id = f"GCP-{uuid.uuid4().hex[:8].upper()}"
        now_str = _get_utc_now_str()

        record = GovernanceContinuityPlanRecord(
            plan_id=plan_id,
            tenant_id=tenant_id,
            title=request.title,
            organizational_scope=request.organizational_scope or {},
            covered_capability_ids=request.covered_capability_ids,
            plan_owner_id=request.plan_owner_id,
            authorized_approver_id=None,
            activation_conditions=request.activation_conditions,
            disruption_categories=request.disruption_categories,
            escalation_procedures=request.escalation_procedures,
            communication_arrangements=request.communication_arrangements,
            alternative_operating_procedures=request.alternative_operating_procedures,
            delegation_arrangements=request.delegation_arrangements,
            required_resources=request.required_resources,
            recovery_priorities=request.recovery_priorities,
            restoration_criteria=request.restoration_criteria,
            verification_requirements=request.verification_requirements,
            testing_schedule=request.testing_schedule,
            review_schedule=request.review_schedule,
            status=ContinuityPlanStatus.DRAFT,
            version=1,
            approval_reference=None,
            approval_history=[],
            version_history=[],
            disclaimer=CLINICAL_SAFETY_CONTINUITY_DISCLAIMER,
            created_at=now_str,
            updated_at=now_str,
        )
        return self.repository.save_plan(record)

    def update_plan(
        self,
        tenant_id: str,
        plan_id: str,
        request: UpdateContinuityPlanRequest,
    ) -> GovernanceContinuityPlanRecord:
        plan = self.repository.get_plan(plan_id)
        if not plan or plan.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.CONTINUITY_PLAN_NOT_FOUND,
                message=f"Continuity plan '{plan_id}' was not found.",
                status_code=404,
            )

        if plan.status not in (ContinuityPlanStatus.DRAFT, ContinuityPlanStatus.UNDER_REVIEW):
            raise AppException(
                code=ErrorCode.INVALID_CONTINUITY_PLAN_STATE,
                message=f"Continuity plan '{plan_id}' cannot be modified in status '{plan.status}'.",
                status_code=400,
            )

        now_str = _get_utc_now_str()
        updated = plan.model_copy(
            update={
                "title": request.title if request.title is not None else plan.title,
                "covered_capability_ids": request.covered_capability_ids if request.covered_capability_ids is not None else plan.covered_capability_ids,
                "activation_conditions": request.activation_conditions if request.activation_conditions is not None else plan.activation_conditions,
                "disruption_categories": request.disruption_categories if request.disruption_categories is not None else plan.disruption_categories,
                "escalation_procedures": request.escalation_procedures if request.escalation_procedures is not None else plan.escalation_procedures,
                "communication_arrangements": request.communication_arrangements if request.communication_arrangements is not None else plan.communication_arrangements,
                "alternative_operating_procedures": request.alternative_operating_procedures if request.alternative_operating_procedures is not None else plan.alternative_operating_procedures,
                "delegation_arrangements": request.delegation_arrangements if request.delegation_arrangements is not None else plan.delegation_arrangements,
                "required_resources": request.required_resources if request.required_resources is not None else plan.required_resources,
                "restoration_criteria": request.restoration_criteria if request.restoration_criteria is not None else plan.restoration_criteria,
                "updated_at": now_str,
            }
        )
        return self.repository.save_plan(updated)

    def submit_plan(
        self,
        tenant_id: str,
        author_id: str,
        plan_id: str,
        request: SubmitContinuityPlanRequest,
    ) -> GovernanceContinuityPlanRecord:
        plan = self.repository.get_plan(plan_id)
        if not plan or plan.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.CONTINUITY_PLAN_NOT_FOUND,
                message=f"Continuity plan '{plan_id}' was not found.",
                status_code=404,
            )

        if plan.status != ContinuityPlanStatus.DRAFT:
            raise AppException(
                code=ErrorCode.INVALID_CONTINUITY_PLAN_STATE,
                message=f"Continuity plan '{plan_id}' cannot be submitted from status '{plan.status}'.",
                status_code=400,
            )

        now_str = _get_utc_now_str()
        updated = plan.model_copy(
            update={
                "status": ContinuityPlanStatus.SUBMITTED,
                "updated_at": now_str,
            }
        )
        return self.repository.save_plan(updated)

    def approve_plan(
        self,
        tenant_id: str,
        approver_id: str,
        plan_id: str,
        request: ApproveContinuityPlanRequest,
    ) -> GovernanceContinuityPlanRecord:
        plan = self.repository.get_plan(plan_id)
        if not plan or plan.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.CONTINUITY_PLAN_NOT_FOUND,
                message=f"Continuity plan '{plan_id}' was not found.",
                status_code=404,
            )

        # Separation of duties: plan owner cannot approve own continuity plan
        if approver_id == plan.plan_owner_id:
            raise AppException(
                code=ErrorCode.CONTINUITY_SEPARATION_OF_DUTIES_VIOLATION,
                message="Plan owners cannot approve their own continuity plan.",
                status_code=403,
            )

        if plan.status != ContinuityPlanStatus.SUBMITTED:
            raise AppException(
                code=ErrorCode.INVALID_CONTINUITY_PLAN_STATE,
                message=f"Continuity plan '{plan_id}' must be in SUBMITTED status to approve (currently '{plan.status}').",
                status_code=400,
            )

        now_str = _get_utc_now_str()
        approval_entry = {
            "approved_by": approver_id,
            "approval_reference": request.approval_reference,
            "approval_notes": request.approval_notes,
            "approved_at": now_str,
            "approved_version": plan.version,
        }
        history = list(plan.approval_history)
        history.append(approval_entry)

        updated = plan.model_copy(
            update={
                "status": ContinuityPlanStatus.APPROVED,
                "authorized_approver_id": approver_id,
                "approval_reference": request.approval_reference,
                "approval_history": history,
                "updated_at": now_str,
            }
        )
        return self.repository.save_plan(updated)

    def revise_plan(
        self,
        tenant_id: str,
        reviser_id: str,
        plan_id: str,
        request: ReviseContinuityPlanRequest,
    ) -> GovernanceContinuityPlanRecord:
        plan = self.repository.get_plan(plan_id)
        if not plan or plan.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.CONTINUITY_PLAN_NOT_FOUND,
                message=f"Continuity plan '{plan_id}' was not found.",
                status_code=404,
            )

        now_str = _get_utc_now_str()

        # Archive baseline in version history
        archived_snapshot = {
            "version": plan.version,
            "status": plan.status.value,
            "alternative_operating_procedures": plan.alternative_operating_procedures,
            "activation_conditions": plan.activation_conditions,
            "restoration_criteria": plan.restoration_criteria,
            "revised_by": reviser_id,
            "revision_reason": request.revision_reason,
            "archived_at": now_str,
        }
        v_history = list(plan.version_history)
        v_history.append(archived_snapshot)

        new_version = plan.version + 1
        updated = plan.model_copy(
            update={
                "alternative_operating_procedures": request.updated_alternative_procedures or plan.alternative_operating_procedures,
                "activation_conditions": request.updated_activation_conditions or plan.activation_conditions,
                "restoration_criteria": request.updated_restoration_criteria or plan.restoration_criteria,
                "version": new_version,
                "version_history": v_history,
                "status": ContinuityPlanStatus.UNDER_REVISION,
                "updated_at": now_str,
            }
        )
        return self.repository.save_plan(updated)

    def get_plan(
        self,
        tenant_id: str,
        plan_id: str,
    ) -> GovernanceContinuityPlanRecord:
        plan = self.repository.get_plan(plan_id)
        if not plan or plan.tenant_id != tenant_id:
            raise AppException(
                code=ErrorCode.CONTINUITY_PLAN_NOT_FOUND,
                message=f"Continuity plan '{plan_id}' was not found.",
                status_code=404,
            )
        return plan

    def list_plans(
        self,
        tenant_id: str,
        status: Optional[ContinuityPlanStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[GovernanceContinuityPlanRecord]:
        return self.repository.list_plans(tenant_id, status=status, skip=skip, limit=limit)
