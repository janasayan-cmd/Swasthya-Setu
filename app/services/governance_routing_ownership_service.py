"""Phase 67: Governance Routing, Ownership and Deadline Service.

Manages policy-driven routing, owner assignment, acknowledgement, reassignment,
deadline tracking, and overdue state detection.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_escalation_repository import (
    GovernanceEscalationRepository,
    get_governance_escalation_repository,
)
from app.schemas.auth import UserRole
from app.schemas.governance_escalation import (
    AcknowledgeEscalationRequest,
    AssignEscalationRequest,
    EscalationHistoryRecord,
    EscalationLifecycleState,
    GovernanceEscalationRecord,
    ReassignEscalationRequest,
    RouteEscalationRequest,
)
from app.schemas.governance_exception import GovernancePriority
from app.schemas.governance_resolution_requirement import ExtendDeadlineRequest
from app.schemas.user import AuthenticatedUserContext


class GovernanceRoutingOwnershipService:
    """Service managing escalation routing, ownership assignment, acknowledgement, and deadlines."""

    def __init__(
        self,
        repository: Optional[GovernanceEscalationRepository] = None,
    ) -> None:
        self.repository = repository or get_governance_escalation_repository()

    def route_escalation(
        self,
        user: AuthenticatedUserContext,
        escalation_id: str,
        payload: RouteEscalationRequest,
    ) -> GovernanceEscalationRecord:
        """Route escalation to a governance domain and escalation level."""
        escalation = self._get_and_check_tenant(escalation_id, user)
        now = datetime.now(timezone.utc)

        prev_state = escalation.lifecycle_state
        escalation.routing_domain = payload.routing_domain
        escalation.escalation_level = payload.escalation_level or 1
        escalation.specialist_role_required = payload.specialist_role_required
        escalation.governance_committee_ref = payload.governance_committee_ref
        escalation.lifecycle_state = EscalationLifecycleState.ROUTED

        self.repository.save_escalation(escalation)

        self.repository.record_history(
            EscalationHistoryRecord(
                escalation_id=escalation_id,
                from_state=prev_state,
                to_state=EscalationLifecycleState.ROUTED,
                action="ROUTE_ESCALATION",
                performed_by=user.user_id,
                performed_at=now,
                rationale=payload.rationale,
                details={
                    "routing_domain": payload.routing_domain.value,
                    "escalation_level": escalation.escalation_level,
                    "specialist_role": payload.specialist_role_required,
                },
            )
        )
        return escalation

    def assign_owner(
        self,
        user: AuthenticatedUserContext,
        escalation_id: str,
        payload: AssignEscalationRequest,
    ) -> GovernanceEscalationRecord:
        """Assign primary owner and optional secondary reviewer to the escalation."""
        escalation = self._get_and_check_tenant(escalation_id, user)
        now = datetime.now(timezone.utc)

        prev_state = escalation.lifecycle_state
        escalation.assigned_owner_id = payload.assigned_owner_id
        escalation.assigned_owner_role = payload.assigned_owner_role
        escalation.secondary_reviewer_id = payload.secondary_reviewer_id
        escalation.assigned_at = now
        escalation.assigned_by = user.user_id
        escalation.is_acknowledged = False
        escalation.lifecycle_state = EscalationLifecycleState.ASSIGNED

        # Calculate policy deadlines based on priority
        ack_hours = 4 if escalation.governance_priority in {
            GovernancePriority.CRITICAL,
            GovernancePriority.URGENT,
        } else 24
        review_hours = 24 if escalation.governance_priority in {
            GovernancePriority.CRITICAL,
            GovernancePriority.URGENT,
        } else 48

        escalation.acknowledgement_deadline = now + timedelta(hours=ack_hours)
        escalation.initial_review_deadline = now + timedelta(hours=review_hours)

        self.repository.save_escalation(escalation)

        self.repository.record_history(
            EscalationHistoryRecord(
                escalation_id=escalation_id,
                from_state=prev_state,
                to_state=EscalationLifecycleState.ASSIGNED,
                action="ASSIGN_OWNER",
                performed_by=user.user_id,
                performed_at=now,
                rationale=payload.rationale,
                details={
                    "assigned_owner_id": payload.assigned_owner_id,
                    "assigned_owner_role": payload.assigned_owner_role,
                    "secondary_reviewer_id": payload.secondary_reviewer_id,
                    "acknowledgement_deadline": escalation.acknowledgement_deadline.isoformat(),
                },
            )
        )
        return escalation

    def reassign_owner(
        self,
        user: AuthenticatedUserContext,
        escalation_id: str,
        payload: ReassignEscalationRequest,
    ) -> GovernanceEscalationRecord:
        """Reassign escalation ownership to a new responsible actor."""
        escalation = self._get_and_check_tenant(escalation_id, user)
        now = datetime.now(timezone.utc)

        prev_owner = escalation.assigned_owner_id
        escalation.assigned_owner_id = payload.new_owner_id
        escalation.assigned_owner_role = payload.new_owner_role
        escalation.assigned_at = now
        escalation.assigned_by = user.user_id
        escalation.is_acknowledged = False
        escalation.lifecycle_state = EscalationLifecycleState.ASSIGNED

        # Refresh acknowledgement deadline
        ack_hours = 4 if escalation.governance_priority in {
            GovernancePriority.CRITICAL,
            GovernancePriority.URGENT,
        } else 24
        escalation.acknowledgement_deadline = now + timedelta(hours=ack_hours)

        self.repository.save_escalation(escalation)

        self.repository.record_history(
            EscalationHistoryRecord(
                escalation_id=escalation_id,
                from_state=escalation.lifecycle_state,
                to_state=EscalationLifecycleState.ASSIGNED,
                action="REASSIGN_OWNER",
                performed_by=user.user_id,
                performed_at=now,
                rationale=payload.reassignment_reason,
                details={
                    "previous_owner": prev_owner,
                    "new_owner": payload.new_owner_id,
                    "new_role": payload.new_owner_role,
                },
            )
        )
        return escalation

    def acknowledge_escalation(
        self,
        user: AuthenticatedUserContext,
        escalation_id: str,
        payload: AcknowledgeEscalationRequest,
    ) -> GovernanceEscalationRecord:
        """Acknowledge assigned ownership of an escalation."""
        escalation = self._get_and_check_tenant(escalation_id, user)

        # Enforce that assigned owner or an administrator can acknowledge
        if (
            escalation.assigned_owner_id
            and escalation.assigned_owner_id != user.user_id
            and user.role != UserRole.ADMIN
        ):
            raise AppException(
                code=ErrorCode.ESCALATION_ASSIGNMENT_UNAUTHORIZED,
                message="Only the designated assigned owner or an administrator can acknowledge this escalation.",
                status_code=403,
            )

        now = datetime.now(timezone.utc)
        prev_state = escalation.lifecycle_state
        escalation.is_acknowledged = True
        escalation.acknowledged_by = user.user_id
        escalation.acknowledged_at = now
        escalation.lifecycle_state = EscalationLifecycleState.ACKNOWLEDGED

        self.repository.save_escalation(escalation)

        self.repository.record_history(
            EscalationHistoryRecord(
                escalation_id=escalation_id,
                from_state=prev_state,
                to_state=EscalationLifecycleState.ACKNOWLEDGED,
                action="ACKNOWLEDGE_ESCALATION",
                performed_by=user.user_id,
                performed_at=now,
                rationale=payload.acknowledgement_notes,
                details={"acknowledged_at": now.isoformat()},
            )
        )
        return escalation

    def extend_deadline(
        self,
        user: AuthenticatedUserContext,
        escalation_id: str,
        payload: ExtendDeadlineRequest,
    ) -> GovernanceEscalationRecord:
        """Authorize an extension for an escalation deadline."""
        escalation = self._get_and_check_tenant(escalation_id, user)

        # Patients cannot extend governance deadlines
        if user.role == UserRole.PATIENT:
            raise AppException(
                code=ErrorCode.DEADLINE_EXTENSION_UNAUTHORIZED,
                message="Patient role is not authorized to grant governance deadline extensions.",
                status_code=403,
            )

        now = datetime.now(timezone.utc)
        if payload.extended_until <= now:
            raise AppException(
                code=ErrorCode.DEADLINE_EXTENSION_UNAUTHORIZED,
                message="Extended deadline must be in the future.",
                status_code=400,
            )

        dtype = payload.deadline_type.lower()
        if dtype == "acknowledgement":
            escalation.acknowledgement_deadline = payload.extended_until
        elif dtype == "review":
            escalation.initial_review_deadline = payload.extended_until
        elif dtype == "decision":
            escalation.decision_deadline = payload.extended_until
        elif dtype == "resolution":
            escalation.resolution_deadline = payload.extended_until
        else:
            escalation.resolution_deadline = payload.extended_until

        escalation.extensions_count += 1
        escalation.is_overdue = False
        self.repository.save_escalation(escalation)

        self.repository.record_history(
            EscalationHistoryRecord(
                escalation_id=escalation_id,
                from_state=escalation.lifecycle_state,
                to_state=escalation.lifecycle_state,
                action="EXTEND_DEADLINE",
                performed_by=user.user_id,
                performed_at=now,
                rationale=payload.extension_rationale,
                details={
                    "deadline_type": payload.deadline_type,
                    "extended_until": payload.extended_until.isoformat(),
                    "extensions_count": escalation.extensions_count,
                },
            )
        )
        return escalation

    def _get_and_check_tenant(
        self, escalation_id: str, user: AuthenticatedUserContext
    ) -> GovernanceEscalationRecord:
        escalation = self.repository.get_escalation(escalation_id)
        if not escalation:
            raise AppException(
                code=ErrorCode.GOVERNANCE_ESCALATION_NOT_FOUND,
                message=f"Governance escalation {escalation_id} not found.",
                status_code=404,
            )
        if escalation.organization_id != user.organization_id:
            raise AppException(
                code=ErrorCode.CROSS_TENANT_ACCESS_FORBIDDEN,
                message="Cannot access escalation across tenant boundaries.",
                status_code=403,
            )
        return escalation


# Global singleton
_global_routing_service = GovernanceRoutingOwnershipService()


def get_governance_routing_ownership_service() -> GovernanceRoutingOwnershipService:
    """Dependency provider for routing and ownership service."""
    return _global_routing_service
