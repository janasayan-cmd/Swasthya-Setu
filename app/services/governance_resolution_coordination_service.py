"""Phase 67: Governance Resolution Coordination, Closure and Reopening Service.

Coordinates resolution requirements across safety phases, enforces satisfaction
of all mandatory conditions before resolution, controls administrative closure,
and governs historical reopening upon material changes.

Mandatory Invariants:
1. An escalation may only become RESOLVED when all mandatory resolution conditions are satisfied.
2. Resolving one finding does not automatically resolve related findings.
3. An escalation closed administratively does not establish clinical safety.
4. Historical closure records are preserved across stales, conflicts, and reopenings.
"""

from datetime import datetime, timezone
from typing import List, Optional

from app.core.exceptions import AppException, ErrorCode
from app.repositories.governance_escalation_repository import (
    GovernanceEscalationRepository,
    get_governance_escalation_repository,
)
from app.schemas.auth import UserRole
from app.schemas.governance_escalation import (
    EscalationHistoryRecord,
    EscalationLifecycleState,
    GovernanceEscalationRecord,
)
from app.schemas.governance_resolution_requirement import (
    CloseEscalationRequest,
    ReconcileResolutionRequirementRequest,
    ReopenEscalationRequest,
    RequirementStatus,
    ResolutionRequirementRecord,
    ResolveEscalationRequest,
)
from app.schemas.user import AuthenticatedUserContext


class GovernanceResolutionCoordinationService:
    """Service coordinating cross-workflow resolution, closure, and governed reopening."""

    def __init__(
        self,
        repository: Optional[GovernanceEscalationRepository] = None,
    ) -> None:
        self.repository = repository or get_governance_escalation_repository()

    def reconcile_requirement(
        self,
        user: AuthenticatedUserContext,
        escalation_id: str,
        requirement_id: str,
        payload: ReconcileResolutionRequirementRequest,
    ) -> ResolutionRequirementRecord:
        """Reconcile an individual resolution requirement against its authoritative source."""
        escalation = self._get_and_check_tenant(escalation_id, user)

        req = self.repository.get_requirement(requirement_id)
        if not req or req.escalation_id != escalation_id:
            raise AppException(
                code=ErrorCode.RESOLUTION_REQUIREMENT_NOT_FOUND,
                message=f"Resolution requirement {requirement_id} not found on escalation {escalation_id}.",
                status_code=404,
            )

        now = datetime.now(timezone.utc)
        req.status = payload.status
        req.completion_evidence_refs.extend(payload.reconciliation_evidence or [])
        req.reconciled_at = now
        req.reconciled_by = user.user_id

        if payload.status == RequirementStatus.WAIVED_WITH_AUTHORIZATION:
            if user.role != UserRole.ADMIN:
                raise AppException(
                    code=ErrorCode.INSUFFICIENT_PERMISSIONS,
                    message="Only an administrator can authorize a requirement waiver.",
                    status_code=403,
                )
            req.waiver_rationale = payload.waiver_rationale or payload.notes
            req.waived_by = user.user_id

        self.repository.save_requirement(req)

        self.repository.record_history(
            EscalationHistoryRecord(
                escalation_id=escalation_id,
                from_state=escalation.lifecycle_state,
                to_state=escalation.lifecycle_state,
                action="RECONCILE_RESOLUTION_REQUIREMENT",
                performed_by=user.user_id,
                performed_at=now,
                rationale=payload.notes,
                details={
                    "requirement_id": requirement_id,
                    "new_status": payload.status.value,
                    "is_mandatory": req.is_mandatory,
                },
            )
        )
        return req

    def resolve_escalation(
        self,
        user: AuthenticatedUserContext,
        escalation_id: str,
        payload: ResolveEscalationRequest,
    ) -> GovernanceEscalationRecord:
        """Mark an escalation RESOLVED only if all mandatory resolution requirements are satisfied."""
        escalation = self._get_and_check_tenant(escalation_id, user)

        # 1. Role verification: Patient cannot resolve escalations
        if user.role == UserRole.PATIENT:
            raise AppException(
                code=ErrorCode.INSUFFICIENT_PERMISSIONS,
                message="Patient role is not authorized to resolve governance escalations.",
                status_code=403,
            )

        # 2. Check all mandatory resolution requirements
        requirements = self.repository.list_requirements(escalation_id)
        unsatisfied_mandatory = [
            r for r in requirements
            if r.is_mandatory and r.status not in {
                RequirementStatus.SATISFIED,
                RequirementStatus.WAIVED_WITH_AUTHORIZATION,
            }
        ]

        if unsatisfied_mandatory:
            unmet_titles = [f"{r.title} ({r.status.value})" for r in unsatisfied_mandatory]
            raise AppException(
                code=ErrorCode.RESOLUTION_CONDITIONS_UNMET,
                message=f"Cannot resolve escalation: {len(unsatisfied_mandatory)} mandatory requirement(s) unsatisfied: {', '.join(unmet_titles)}.",
                status_code=400,
            )

        # 3. Check for active unresolved conflicts
        conflicts = self.repository.list_conflicts(escalation_id)
        active_conflicts = [c for c in conflicts if not c.is_resolved]
        if active_conflicts:
            raise AppException(
                code=ErrorCode.DECISION_CONFLICT_UNRESOLVED,
                message=f"Cannot resolve escalation with {len(active_conflicts)} active cross-workflow decision conflict(s).",
                status_code=409,
            )

        now = datetime.now(timezone.utc)
        prev_state = escalation.lifecycle_state
        escalation.resolution_rationale = payload.resolution_rationale
        escalation.resolved_at = now
        escalation.resolved_by = user.user_id
        escalation.lifecycle_state = EscalationLifecycleState.RESOLVED

        self.repository.save_escalation(escalation)

        self.repository.record_history(
            EscalationHistoryRecord(
                escalation_id=escalation_id,
                from_state=prev_state,
                to_state=EscalationLifecycleState.RESOLVED,
                action="RESOLVE_ESCALATION",
                performed_by=user.user_id,
                performed_at=now,
                rationale=payload.resolution_rationale,
                details={"resolved_requirements_count": len(requirements)},
            )
        )
        return escalation

    def close_escalation(
        self,
        user: AuthenticatedUserContext,
        escalation_id: str,
        payload: CloseEscalationRequest,
    ) -> GovernanceEscalationRecord:
        """Perform controlled administrative closure of an escalation."""
        escalation = self._get_and_check_tenant(escalation_id, user)

        # 1. Enforce separation of duties: A preparer who created the escalation cannot self-close without review
        if user.user_id == escalation.created_by and user.role != UserRole.ADMIN:
            reviews = self.repository.list_reviews(escalation_id)
            if not reviews:
                raise AppException(
                    code=ErrorCode.SEPARATION_OF_DUTIES_VIOLATION,
                    message="Separation of duties violation: Creator cannot self-close escalation without an independent review.",
                    status_code=403,
                )

        # 2. Must be in RESOLVED state
        if escalation.lifecycle_state != EscalationLifecycleState.RESOLVED:
            raise AppException(
                code=ErrorCode.INVALID_ESCALATION_STATE,
                message=f"Cannot close escalation in state {escalation.lifecycle_state.value}. Must be RESOLVED first.",
                status_code=400,
            )

        now = datetime.now(timezone.utc)
        prev_state = escalation.lifecycle_state
        escalation.closure_rationale = payload.closure_rationale
        escalation.closed_at = now
        escalation.closed_by = user.user_id
        escalation.lifecycle_state = EscalationLifecycleState.CLOSED

        self.repository.save_escalation(escalation)

        self.repository.record_history(
            EscalationHistoryRecord(
                escalation_id=escalation_id,
                from_state=prev_state,
                to_state=EscalationLifecycleState.CLOSED,
                action="CLOSE_ESCALATION",
                performed_by=user.user_id,
                performed_at=now,
                rationale=payload.closure_rationale,
                details={"administrative_notes": payload.administrative_notes},
            )
        )
        return escalation

    def reopen_escalation(
        self,
        user: AuthenticatedUserContext,
        escalation_id: str,
        payload: ReopenEscalationRequest,
    ) -> GovernanceEscalationRecord:
        """Reopen a previously resolved or closed escalation upon material new findings."""
        escalation = self._get_and_check_tenant(escalation_id, user)

        # Patients cannot reopen governance escalations
        if user.role == UserRole.PATIENT:
            raise AppException(
                code=ErrorCode.INSUFFICIENT_PERMISSIONS,
                message="Patient role is not authorized to reopen governance escalations.",
                status_code=403,
            )

        if escalation.lifecycle_state not in {
            EscalationLifecycleState.RESOLVED,
            EscalationLifecycleState.CLOSED,
        }:
            raise AppException(
                code=ErrorCode.ESCALATION_REOPEN_INVALID,
                message=f"Escalation in state {escalation.lifecycle_state.value} is not resolved or closed; cannot reopen.",
                status_code=400,
            )

        now = datetime.now(timezone.utc)
        prev_state = escalation.lifecycle_state
        escalation.is_reopened = True
        escalation.reopen_count += 1
        escalation.reopened_at = now
        escalation.reopened_by = user.user_id
        escalation.reopen_trigger_source = (
            f"{payload.triggering_source_phase}:{payload.triggering_source_record_id}"
        )
        escalation.reopen_rationale = payload.reopen_reason
        escalation.lifecycle_state = EscalationLifecycleState.REOPENED

        # Mark mandatory requirements as REOPENED for necessary re-evaluation
        for req in self.repository.list_requirements(escalation_id):
            if req.is_mandatory:
                req.status = RequirementStatus.REOPENED
                self.repository.save_requirement(req)

        self.repository.save_escalation(escalation)

        self.repository.record_history(
            EscalationHistoryRecord(
                escalation_id=escalation_id,
                from_state=prev_state,
                to_state=EscalationLifecycleState.REOPENED,
                action="REOPEN_ESCALATION",
                performed_by=user.user_id,
                performed_at=now,
                rationale=payload.reopen_reason,
                details={
                    "reopen_count": escalation.reopen_count,
                    "trigger_source": escalation.reopen_trigger_source,
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
_global_resolution_service = GovernanceResolutionCoordinationService()


def get_governance_resolution_coordination_service() -> GovernanceResolutionCoordinationService:
    """Dependency provider for resolution service."""
    return _global_resolution_service
