"""Phase 73: Implementation Planning & Versioning Service.

Handles:
- Implementation plan creation, updates, and submission
- Plan versioning when plans are modified after approval
- Preserving prior versions and enforcing change reasons
- Plan approval workflows
"""

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import status

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_decision_implementation_repository import (
    GovernanceDecisionImplementationRepository,
    get_governance_decision_implementation_repository,
)
from app.schemas.decision_implementation_register import ImplementationStatus
from app.schemas.decision_implementation_planning import (
    ApprovePlanRequest,
    CreatePlanRequest,
    ImplementationPlanRecord,
    PlanApprovalStatus,
    SubmitPlanRequest,
    UpdatePlanRequest,
)


class ImplementationPlanningService:
    """Service governing structured implementation planning and version control."""

    def __init__(
        self,
        repository: Optional[GovernanceDecisionImplementationRepository] = None,
    ) -> None:
        self.repository = (
            repository or get_governance_decision_implementation_repository()
        )

    def create_plan(
        self,
        implementation_id: str,
        request: CreatePlanRequest,
        creator_id: str,
    ) -> ImplementationPlanRecord:
        """Creates or versions an implementation plan."""
        imp = self.repository.get_implementation(implementation_id)
        if not imp:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code=ErrorCode.DECISION_IMPLEMENTATION_NOT_FOUND,
                message=f"Implementation '{implementation_id}' not found.",
            )

        if imp.status in [
            ImplementationStatus.CLOSED,
            ImplementationStatus.CANCELLED_WITH_AUTHORIZATION,
        ]:
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code=ErrorCode.INVALID_IMPLEMENTATION_STATE,
                message=f"Cannot add plans to implementation in status '{imp.status.value}'.",
            )

        # Check existing active plans
        existing_plans = self.repository.list_plans(implementation_id)
        version = len(existing_plans) + 1

        # If a prior approved plan exists, ensure change_reason is provided
        if any(p.approval_status == PlanApprovalStatus.APPROVED for p in existing_plans):
            if not request.change_reason:
                raise AppException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code=ErrorCode.INVALID_IMPLEMENTATION_STATE,
                    message="Modification of an approved plan requires an explicit change reason.",
                )

        # Deactivate existing active plans when introducing a new version
        for p in existing_plans:
            if p.is_active:
                p.is_active = False
                p.approval_status = PlanApprovalStatus.SUPERSEDED
                self.repository.save_plan(p)

        plan = ImplementationPlanRecord(
            implementation_id=implementation_id,
            version=version,
            objectives=request.objectives,
            work_items=request.work_items or [],
            target_dates=request.target_dates or {},
            expected_evidence=request.expected_evidence or [],
            verification_criteria=request.verification_criteria or [],
            completion_conditions=request.completion_conditions or [],
            approval_status=PlanApprovalStatus.DRAFT,
            change_reason=request.change_reason,
            is_active=True,
            created_by=creator_id,
            metadata=request.metadata or {},
        )

        return self.repository.save_plan(plan)

    def get_plan(self, plan_id: str) -> ImplementationPlanRecord:
        """Retrieves a plan by ID."""
        plan = self.repository.get_plan(plan_id)
        if not plan:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code=ErrorCode.IMPLEMENTATION_PLAN_NOT_FOUND,
                message=f"Implementation plan '{plan_id}' not found.",
            )
        return plan

    def get_active_plan(
        self, implementation_id: str
    ) -> ImplementationPlanRecord:
        """Retrieves the active plan for an implementation."""
        plan = self.repository.get_active_plan(implementation_id)
        if not plan:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code=ErrorCode.IMPLEMENTATION_PLAN_NOT_FOUND,
                message=f"No active implementation plan found for implementation '{implementation_id}'.",
            )
        return plan

    def list_plans(self, implementation_id: str) -> List[ImplementationPlanRecord]:
        """Lists all versioned plans for an implementation."""
        return self.repository.list_plans(implementation_id)

    def update_plan(
        self, plan_id: str, request: UpdatePlanRequest
    ) -> ImplementationPlanRecord:
        """Updates a plan while in DRAFT status."""
        plan = self.get_plan(plan_id)
        if plan.approval_status != PlanApprovalStatus.DRAFT:
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code=ErrorCode.INVALID_IMPLEMENTATION_STATE,
                message=f"Cannot edit plan in status '{plan.approval_status.value}'. Must create a new version.",
            )

        if request.objectives is not None:
            plan.objectives = request.objectives
        if request.work_items is not None:
            plan.work_items = request.work_items
        if request.target_dates is not None:
            plan.target_dates = request.target_dates
        if request.expected_evidence is not None:
            plan.expected_evidence = request.expected_evidence
        if request.verification_criteria is not None:
            plan.verification_criteria = request.verification_criteria
        if request.completion_conditions is not None:
            plan.completion_conditions = request.completion_conditions
        if request.metadata is not None:
            plan.metadata.update(request.metadata)

        return self.repository.save_plan(plan)

    def submit_plan(
        self, plan_id: str, request: SubmitPlanRequest
    ) -> ImplementationPlanRecord:
        """Submits a draft plan for formal approval."""
        plan = self.get_plan(plan_id)
        if plan.approval_status != PlanApprovalStatus.DRAFT:
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code=ErrorCode.INVALID_IMPLEMENTATION_STATE,
                message=f"Cannot submit plan in status '{plan.approval_status.value}'.",
            )

        plan.approval_status = PlanApprovalStatus.SUBMITTED
        if request.submission_notes:
            plan.metadata["submission_notes"] = request.submission_notes

        return self.repository.save_plan(plan)

    def approve_plan(
        self, plan_id: str, request: ApprovePlanRequest, approver_id: str
    ) -> ImplementationPlanRecord:
        """Approves an implementation plan."""
        plan = self.get_plan(plan_id)
        if plan.approval_status not in [PlanApprovalStatus.DRAFT, PlanApprovalStatus.SUBMITTED]:
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code=ErrorCode.INVALID_IMPLEMENTATION_STATE,
                message=f"Cannot approve plan in status '{plan.approval_status.value}'.",
            )

        plan.approval_status = PlanApprovalStatus.APPROVED
        plan.approved_by = approver_id
        plan.approved_at = datetime.now(timezone.utc)
        plan.metadata["approval_rationale"] = request.approval_rationale

        return self.repository.save_plan(plan)
