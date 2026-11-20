"""Phase 73: Implementation Ownership & Responsibility Assignment Service.

Handles:
- Role assignments (lead, sponsor, owner, verifier, reviewer)
- Enforcing separation of duties (implementation leads cannot verify their own work)
- Assignment acceptance, delegation, and reassignment history
"""

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import status

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_decision_implementation_repository import (
    GovernanceDecisionImplementationRepository,
    get_governance_decision_implementation_repository,
)
from app.schemas.decision_implementation_ownership_dependencies import (
    AcceptanceStatus,
    AcceptAssignmentRequest,
    AssignmentRole,
    CreateAssignmentRequest,
    ImplementationAssignmentRecord,
    UpdateAssignmentRequest,
)


class ImplementationOwnershipService:
    """Service governing implementation ownership, delegation, and separation of duties."""

    def __init__(
        self,
        repository: Optional[GovernanceDecisionImplementationRepository] = None,
    ) -> None:
        self.repository = (
            repository or get_governance_decision_implementation_repository()
        )

    def create_assignment(
        self,
        implementation_id: str,
        request: CreateAssignmentRequest,
        assigned_by: str,
    ) -> ImplementationAssignmentRecord:
        """Assigns a functional role to a user, strictly enforcing separation of duties."""
        imp = self.repository.get_implementation(implementation_id)
        if not imp:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code=ErrorCode.DECISION_IMPLEMENTATION_NOT_FOUND,
                message=f"Implementation '{implementation_id}' not found.",
            )

        # Enforce separation of duties:
        # An independent verifier MUST NOT be the responsible owner, accountable lead, or have lead role
        if request.role == AssignmentRole.INDEPENDENT_VERIFIER:
            if request.user_id in [imp.responsible_owner_id, imp.accountable_lead_id]:
                raise AppException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code=ErrorCode.SEPARATION_OF_DUTIES_VIOLATION,
                    message=(
                        f"Separation of duties violation: User '{request.user_id}' is the implementation lead/owner "
                        f"and cannot be designated as an independent verifier for implementation '{implementation_id}'."
                    ),
                )
            existing_lead = [
                a
                for a in self.repository.list_assignments(implementation_id, user_id=request.user_id)
                if a.role in [AssignmentRole.IMPLEMENTATION_LEAD, AssignmentRole.WORK_ITEM_OWNER]
            ]
            if existing_lead:
                raise AppException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code=ErrorCode.SEPARATION_OF_DUTIES_VIOLATION,
                    message=(
                        f"Separation of duties violation: User '{request.user_id}' already has execution ownership "
                        f"and cannot be designated as an independent verifier."
                    ),
                )

        assignment = ImplementationAssignmentRecord(
            implementation_id=implementation_id,
            user_id=request.user_id,
            user_name=request.user_name,
            role=request.role,
            acceptance_status=AcceptanceStatus.PENDING,
            scope_of_responsibility=request.scope_of_responsibility or "Standard implementation responsibility",
            assigned_by=assigned_by,
            metadata=request.metadata or {},
        )

        return self.repository.save_assignment(assignment)

    def get_assignment(self, assignment_id: str) -> ImplementationAssignmentRecord:
        """Retrieves a single assignment by ID."""
        assignment = self.repository.get_assignment(assignment_id)
        if not assignment:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code=ErrorCode.IMPLEMENTATION_ASSIGNMENT_NOT_FOUND,
                message=f"Assignment record '{assignment_id}' not found.",
            )
        return assignment

    def list_assignments(
        self,
        implementation_id: str,
        user_id: Optional[str] = None,
        role: Optional[str] = None,
    ) -> List[ImplementationAssignmentRecord]:
        """Lists assignments for an implementation."""
        return self.repository.list_assignments(
            implementation_id=implementation_id, user_id=user_id, role=role
        )

    def update_assignment(
        self, assignment_id: str, request: UpdateAssignmentRequest
    ) -> ImplementationAssignmentRecord:
        """Updates assignment details or delegations."""
        assignment = self.get_assignment(assignment_id)
        if request.role is not None:
            assignment.role = request.role
        if request.delegated_to_id is not None:
            assignment.delegated_to_id = request.delegated_to_id
            assignment.acceptance_status = AcceptanceStatus.DELEGATED
        if request.scope_of_responsibility is not None:
            assignment.scope_of_responsibility = request.scope_of_responsibility

        return self.repository.save_assignment(assignment)

    def accept_assignment(
        self,
        assignment_id: str,
        user_id: str,
        request: AcceptAssignmentRequest,
    ) -> ImplementationAssignmentRecord:
        """Records acceptance, declination, or delegation by the assigned user."""
        assignment = self.get_assignment(assignment_id)
        if assignment.user_id != user_id:
            raise AppException(
                status_code=status.HTTP_403_FORBIDDEN,
                code=ErrorCode.FORBIDDEN,
                message="Only the assigned user can accept or decline this assignment.",
            )

        assignment.acceptance_status = request.acceptance_status
        assignment.accepted_at = datetime.now(timezone.utc)
        if request.delegated_to_id:
            assignment.delegated_to_id = request.delegated_to_id
        if request.comments:
            assignment.metadata["acceptance_comments"] = request.comments

        return self.repository.save_assignment(assignment)
