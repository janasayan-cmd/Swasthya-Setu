"""Phase 73: Decision Implementation Register Service.

Handles:
- Centralized decision implementation initiative registration
- Implementation lifecycle state progression (DRAFT -> PLANNING -> APPROVED -> IN_PROGRESS -> CLOSED)
- Updating and querying implementation initiatives
"""

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import status

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_decision_implementation_repository import (
    GovernanceDecisionImplementationRepository,
    get_governance_decision_implementation_repository,
)
from app.schemas.decision_implementation_intake import DecisionIntakeStatus
from app.schemas.decision_implementation_register import (
    ApproveImplementationRequest,
    CreateImplementationRequest,
    DecisionImplementationRecord,
    ImplementationCategory,
    ImplementationPriority,
    ImplementationStatus,
    SubmitImplementationRequest,
    UpdateImplementationRequest,
)
from app.schemas.decision_implementation_ownership_dependencies import (
    AcceptanceStatus,
    AssignmentRole,
    ImplementationAssignmentRecord,
)


class DecisionImplementationRegisterService:
    """Service governing decision implementation register."""

    def __init__(
        self,
        repository: Optional[GovernanceDecisionImplementationRepository] = None,
    ) -> None:
        self.repository = (
            repository or get_governance_decision_implementation_repository()
        )

    def create_implementation(
        self,
        request: CreateImplementationRequest,
        creator_id: str,
        organization_id: str,
    ) -> DecisionImplementationRecord:
        """Creates an implementation initiative for an ingested decision."""
        # 1. Verify that an accepted intake exists for this decision
        intake = self.repository.get_intake_by_decision(request.decision_id)
        if not intake or intake.intake_status != DecisionIntakeStatus.INTAKE_ACCEPTED:
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code=ErrorCode.DECISION_NOT_ELIGIBLE_FOR_IMPLEMENTATION,
                message=(
                    f"Decision '{request.decision_id}' must be ingested and accepted before "
                    f"an implementation initiative can be registered."
                ),
            )

        # 2. Prevent duplicate active implementation initiatives for the same decision
        existing = self.repository.get_implementation_by_decision(request.decision_id)
        if existing and existing.status not in [
            ImplementationStatus.CLOSED,
            ImplementationStatus.CLOSED_WITH_FOLLOW_UP,
            ImplementationStatus.CLOSED_WITH_LIMITATIONS,
            ImplementationStatus.CANCELLED_WITH_AUTHORIZATION,
        ]:
            return existing

        # 3. Create implementation record
        implementation = DecisionImplementationRecord(
            decision_id=request.decision_id,
            intake_id=intake.intake_id,
            title=request.title,
            description=request.description,
            intended_outcome=request.intended_outcome,
            responsible_owner_id=request.responsible_owner_id,
            accountable_lead_id=request.accountable_lead_id,
            supporting_teams=request.supporting_teams or [],
            category=request.category or ImplementationCategory.OPERATIONAL_WORKFLOW_CHANGE,
            priority=request.priority or ImplementationPriority.MEDIUM,
            status=ImplementationStatus.PLANNING,
            target_completion_date=request.target_completion_date,
            required_approvals=request.required_approvals or [],
            closure_conditions=request.closure_conditions or [],
            organization_id=organization_id,
            facility_id=request.facility_id or intake.facility_id,
            created_by=creator_id,
            metadata=request.metadata or {},
        )
        saved = self.repository.save_implementation(implementation)

        # 4. Create initial ownership assignments
        lead_assignment = ImplementationAssignmentRecord(
            implementation_id=saved.implementation_id,
            user_id=request.responsible_owner_id,
            role=AssignmentRole.IMPLEMENTATION_LEAD,
            acceptance_status=AcceptanceStatus.ACCEPTED,
            scope_of_responsibility="Overall implementation coordination and technical delivery.",
            assigned_by=creator_id,
        )
        self.repository.save_assignment(lead_assignment)

        sponsor_assignment = ImplementationAssignmentRecord(
            implementation_id=saved.implementation_id,
            user_id=request.accountable_lead_id,
            role=AssignmentRole.EXECUTIVE_SPONSOR,
            acceptance_status=AcceptanceStatus.ACCEPTED,
            scope_of_responsibility="Executive governance sponsorship and decision follow-through.",
            assigned_by=creator_id,
        )
        self.repository.save_assignment(sponsor_assignment)

        return saved

    def get_implementation(
        self, implementation_id: str
    ) -> DecisionImplementationRecord:
        """Retrieves an implementation initiative by ID."""
        imp = self.repository.get_implementation(implementation_id)
        if not imp:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code=ErrorCode.DECISION_IMPLEMENTATION_NOT_FOUND,
                message=f"Decision implementation '{implementation_id}' not found.",
            )
        return imp

    def list_implementations(
        self,
        organization_id: str,
        facility_id: Optional[str] = None,
        status_filter: Optional[str] = None,
        category: Optional[str] = None,
        priority: Optional[str] = None,
        owner_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[DecisionImplementationRecord]:
        """Lists implementations filtered by tenant and query criteria."""
        return self.repository.list_implementations(
            organization_id=organization_id,
            facility_id=facility_id,
            status=status_filter,
            category=category,
            priority=priority,
            owner_id=owner_id,
            limit=limit,
            offset=offset,
        )

    def update_implementation(
        self,
        implementation_id: str,
        request: UpdateImplementationRequest,
    ) -> DecisionImplementationRecord:
        """Updates properties of an implementation record."""
        imp = self.get_implementation(implementation_id)
        if imp.status in [
            ImplementationStatus.CLOSED,
            ImplementationStatus.CANCELLED_WITH_AUTHORIZATION,
        ]:
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code=ErrorCode.INVALID_IMPLEMENTATION_STATE,
                message=f"Cannot update implementation in terminal status '{imp.status.value}'.",
            )

        if request.title is not None:
            imp.title = request.title
        if request.description is not None:
            imp.description = request.description
        if request.intended_outcome is not None:
            imp.intended_outcome = request.intended_outcome
        if request.responsible_owner_id is not None:
            imp.responsible_owner_id = request.responsible_owner_id
        if request.accountable_lead_id is not None:
            imp.accountable_lead_id = request.accountable_lead_id
        if request.supporting_teams is not None:
            imp.supporting_teams = request.supporting_teams
        if request.category is not None:
            imp.category = request.category
        if request.priority is not None:
            imp.priority = request.priority
        if request.target_completion_date is not None:
            imp.target_completion_date = request.target_completion_date
        if request.closure_conditions is not None:
            imp.closure_conditions = request.closure_conditions
        if request.metadata is not None:
            imp.metadata.update(request.metadata)

        return self.repository.save_implementation(imp)

    def submit_implementation(
        self,
        implementation_id: str,
        request: SubmitImplementationRequest,
    ) -> DecisionImplementationRecord:
        """Advances implementation from PLANNING to PENDING_APPROVAL."""
        imp = self.get_implementation(implementation_id)
        if imp.status not in [ImplementationStatus.DRAFT, ImplementationStatus.PLANNING]:
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code=ErrorCode.INVALID_IMPLEMENTATION_STATE,
                message=f"Cannot submit implementation from current status '{imp.status.value}'.",
            )

        # Verify an active plan exists
        plan = self.repository.get_active_plan(implementation_id)
        if not plan:
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code=ErrorCode.PLAN_APPROVAL_REQUIRED,
                message="Cannot submit implementation without an implementation plan.",
            )

        imp.status = ImplementationStatus.PENDING_APPROVAL
        if request.submission_notes:
            imp.metadata["submission_notes"] = request.submission_notes

        return self.repository.save_implementation(imp)

    def approve_implementation(
        self,
        implementation_id: str,
        request: ApproveImplementationRequest,
        approver_id: str,
    ) -> DecisionImplementationRecord:
        """Approves implementation initiative, enabling work execution."""
        imp = self.get_implementation(implementation_id)
        if imp.status != ImplementationStatus.PENDING_APPROVAL:
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code=ErrorCode.INVALID_IMPLEMENTATION_STATE,
                message=f"Cannot approve implementation in status '{imp.status.value}'. Must be PENDING_APPROVAL.",
            )

        imp.status = ImplementationStatus.IN_PROGRESS
        imp.metadata["approved_by"] = approver_id
        imp.metadata["approved_at"] = datetime.now(timezone.utc).isoformat()
        imp.metadata["approval_rationale"] = request.approval_rationale

        return self.repository.save_implementation(imp)
